from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import socket
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import get_type_hints, is_typeddict
from unittest.mock import patch

import scripts.sync_a_stock_data as sync_module

from scripts.sync_a_stock_data import (
    ArtifactValidationError,
    MAX_FILE_BYTES,
    REQUIRED_FILES,
    SyncError,
    build_metadata,
    compare_sections,
    parse_markdown_sections,
    validate_artifacts,
)


VALID_SKILL = """---
name: a-stock-data
version: 3.4.0
---
# A股全栈数据工具包 V3.4.0
## 行情层
Tencent quote details.
## 信号层
Eastmoney signal details.
""".encode()
VALID_CHANGELOG = b"# Changelog\n\n## 3.4.0\n\n- Updated providers.\n"
VALID_LICENSE = b"Apache License\nVersion 2.0, January 2004\n"


def valid_artifacts() -> dict[str, bytes]:
    return {
        "SKILL.md": VALID_SKILL,
        "CHANGELOG.md": VALID_CHANGELOG,
        "LICENSE": VALID_LICENSE,
    }


class FakeGitHubClient:
    def __init__(
        self,
        *,
        identity: str = "simonlin1212/a-stock-data",
        commit: str = "a" * 40,
        committed_at: str = "2026-07-11T08:00:00Z",
        artifacts: dict[str, bytes] | None = None,
        fail_file: str | None = None,
    ) -> None:
        self.identity = identity
        self.commit = commit
        self.committed_at = committed_at
        self.artifacts = artifacts or valid_artifacts()
        self.fail_file = fail_file
        self.identity_calls = 0
        self.resolve_calls = 0
        self.downloads: list[tuple[str, str, int]] = []

    def repository_identity(self) -> str:
        self.identity_calls += 1
        return self.identity

    def resolve_commit(self) -> tuple[str, str]:
        self.resolve_calls += 1
        return self.commit, self.committed_at

    def download_file(self, commit: str, name: str, max_bytes: int) -> bytes:
        self.downloads.append((commit, name, max_bytes))
        if name == self.fail_file:
            raise SyncError(f"failed to download {name}")
        return self.artifacts[name]


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.read_limits: list[int] = []

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int) -> bytes:
        self.read_limits.append(amount)
        return self.content[:amount]


class HeaderResponse(FakeResponse):
    def __init__(self, content: bytes, content_length: int) -> None:
        super().__init__(content)
        self.headers = {"Content-Length": str(content_length)}


class IncompleteResponse(FakeResponse):
    def read(self, amount: int) -> bytes:
        self.read_limits.append(amount)
        raise http.client.IncompleteRead(self.content, amount)


def snapshot_bytes(destination: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted(destination.iterdir())
        if path.is_file()
    }


def load_snapshot_metadata(destination: Path) -> dict[str, object]:
    return json.loads((destination / "metadata.json").read_bytes())


def write_snapshot_metadata(destination: Path, metadata: object) -> None:
    (destination / "metadata.json").write_text(
        json.dumps(metadata, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


class ArtifactValidationTests(unittest.TestCase):
    def test_validates_required_files_and_extracts_version(self) -> None:
        self.assertEqual(validate_artifacts(valid_artifacts()), "3.4.0")

    def test_rejects_prefixed_name_key(self) -> None:
        artifacts = valid_artifacts()
        artifacts["SKILL.md"] = VALID_SKILL.replace(
            b"name: a-stock-data", b"not-name: a-stock-data"
        )

        with self.assertRaisesRegex(ArtifactValidationError, "name: a-stock-data"):
            validate_artifacts(artifacts)

    def test_body_name_does_not_rescue_wrong_frontmatter_name(self) -> None:
        artifacts = valid_artifacts()
        artifacts["SKILL.md"] = VALID_SKILL.replace(
            b"name: a-stock-data", b"name: wrong"
        ).replace(
            "# A股全栈数据工具包".encode(),
            "name: a-stock-data\n# A股全栈数据工具包".encode(),
        )

        with self.assertRaisesRegex(ArtifactValidationError, "name: a-stock-data"):
            validate_artifacts(artifacts)

    def test_rejects_version_value_on_the_next_line(self) -> None:
        artifacts = valid_artifacts()
        artifacts["SKILL.md"] = VALID_SKILL.replace(
            b"version: 3.4.0", b"version:\n3.4.0"
        )

        with self.assertRaisesRegex(ArtifactValidationError, "frontmatter version"):
            validate_artifacts(artifacts)

    def test_rejects_level_two_project_heading(self) -> None:
        artifacts = valid_artifacts()
        artifacts["SKILL.md"] = VALID_SKILL.replace(
            "# A股全栈数据工具包".encode(), "## A股全栈数据工具包".encode()
        )

        with self.assertRaisesRegex(ArtifactValidationError, "project heading"):
            validate_artifacts(artifacts)

    def test_rejects_leading_html(self) -> None:
        for html in (b"<!doctype html><title>404</title>", b"  <HTML>not found</HTML>"):
            with self.subTest(html=html), self.assertRaisesRegex(
                ArtifactValidationError, "HTML"
            ):
                artifacts = valid_artifacts()
                artifacts["SKILL.md"] = html
                validate_artifacts(artifacts)

    def test_rejects_invalid_license(self) -> None:
        artifacts = valid_artifacts()
        artifacts["LICENSE"] = b"Unknown license"

        with self.assertRaisesRegex(ArtifactValidationError, "Apache License 2.0"):
            validate_artifacts(artifacts)

    def test_rejects_negated_apache_license_header(self) -> None:
        artifacts = valid_artifacts()
        artifacts["LICENSE"] = b"Not the Apache License\nNot Version 2.0\n"

        with self.assertRaisesRegex(ArtifactValidationError, "Apache License 2.0"):
            validate_artifacts(artifacts)

    def test_rejects_missing_empty_oversized_and_non_utf8_files(self) -> None:
        invalid_cases = {
            "missing": {"SKILL.md": VALID_SKILL, "CHANGELOG.md": VALID_CHANGELOG},
            "empty": {**valid_artifacts(), "CHANGELOG.md": b""},
            "oversized": {**valid_artifacts(), "LICENSE": b"x" * 64_001},
            "non-UTF-8": {**valid_artifacts(), "CHANGELOG.md": b"\xff"},
        }

        for name, artifacts in invalid_cases.items():
            with self.subTest(name=name), self.assertRaises(ArtifactValidationError):
                validate_artifacts(artifacts)

    def test_requires_version_in_frontmatter(self) -> None:
        artifacts = valid_artifacts()
        artifacts["SKILL.md"] = """# A股全栈数据工具包
name: a-stock-data
version: 3.4.0
""".encode()

        with self.assertRaisesRegex(ArtifactValidationError, "frontmatter version"):
            validate_artifacts(artifacts)


class MarkdownSectionTests(unittest.TestCase):
    def test_parses_and_compares_level_two_sections_stably(self) -> None:
        previous = parse_markdown_sections(
            "# Root\n## Quotes\nold\n## Signals\nsame\n## Legacy\nremoved\n"
        )
        current = parse_markdown_sections(
            "# Root\n## Quotes\nnew\n## Signals\nsame\n## Fallbacks\nadded\n"
        )

        self.assertEqual(
            previous,
            {
                "Quotes": "## Quotes\nold\n",
                "Signals": "## Signals\nsame\n",
                "Legacy": "## Legacy\nremoved\n",
            },
        )
        self.assertEqual(
            compare_sections(previous, current),
            {"added": ["Fallbacks"], "changed": ["Quotes"], "removed": ["Legacy"]},
        )

    def test_ignores_headings_inside_backtick_fences(self) -> None:
        markdown = (
            "# Root\n"
            "## Parent\n"
            "before\n"
            "   ````python\n"
            "## Fake Backtick\n"
            "inside\n"
            "```\n"
            "## Still Fake Backtick\n"
            " `````\n"
            "after\n"
            "## Real\n"
            "body\n"
        )

        self.assertEqual(
            parse_markdown_sections(markdown),
            {
                "Parent": (
                    "## Parent\n"
                    "before\n"
                    "   ````python\n"
                    "## Fake Backtick\n"
                    "inside\n"
                    "```\n"
                    "## Still Fake Backtick\n"
                    " `````\n"
                    "after\n"
                ),
                "Real": "## Real\nbody\n",
            },
        )

    def test_ignores_headings_inside_tilde_fences(self) -> None:
        markdown = (
            "# Root\n"
            "## Parent\n"
            "before\n"
            "  ~~~text\n"
            "## Fake Tilde\n"
            "inside\n"
            "````\n"
            "## Still Fake Tilde\n"
            "   ~~~~\n"
            "after\n"
            "## Real\n"
            "body\n"
        )

        self.assertEqual(
            parse_markdown_sections(markdown),
            {
                "Parent": (
                    "## Parent\n"
                    "before\n"
                    "  ~~~text\n"
                    "## Fake Tilde\n"
                    "inside\n"
                    "````\n"
                    "## Still Fake Tilde\n"
                    "   ~~~~\n"
                    "after\n"
                ),
                "Real": "## Real\nbody\n",
            },
        )


class MetadataTests(unittest.TestCase):
    def test_build_metadata_returns_typed_schema(self) -> None:
        return_type = get_type_hints(build_metadata)["return"]

        self.assertTrue(is_typeddict(return_type))
        self.assertEqual(return_type.__name__, "SyncMetadata")

    def test_hashes_exact_bytes_and_uses_commit_pinned_urls(self) -> None:
        artifacts = valid_artifacts()
        commit = "a" * 40

        metadata = build_metadata(
            commit=commit,
            committed_at="2026-07-11T08:00:00Z",
            synced_at="2026-07-18T06:30:00Z",
            version="3.4.0",
            artifacts=artifacts,
        )

        expected_artifacts = {
            name: {
                "raw_url": (
                    "https://raw.githubusercontent.com/"
                    f"simonlin1212/a-stock-data/{commit}/{name}"
                ),
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(artifacts.items())
        }
        self.assertEqual(
            metadata,
            {
                "schema_version": 1,
                "upstream": {
                    "owner": "simonlin1212",
                    "repository": "a-stock-data",
                    "branch": "main",
                    "commit": commit,
                    "version": "3.4.0",
                    "committed_at": "2026-07-11T08:00:00Z",
                    "synced_at": "2026-07-18T06:30:00Z",
                    "commit_url": (
                        "https://github.com/simonlin1212/a-stock-data/commit/" + commit
                    ),
                },
                "artifacts": expected_artifacts,
            },
        )
        self.assertEqual(list(metadata["artifacts"]), sorted(artifacts))

    def test_rejects_malformed_commit_sha(self) -> None:
        for commit in ("a" * 39, "A" * 40, "not-a-sha"):
            with self.subTest(commit=commit), self.assertRaisesRegex(
                ArtifactValidationError, "commit SHA"
            ):
                build_metadata(
                    commit=commit,
                    committed_at="2026-07-11T08:00:00Z",
                    synced_at="2026-07-18T06:30:00Z",
                    version="3.4.0",
                    artifacts=valid_artifacts(),
                )


class SnapshotVerificationTests(unittest.TestCase):
    def test_verifies_valid_local_snapshot_and_returns_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="b" * 40), destination)

            metadata = sync_module.verify_snapshot(destination)

            self.assertEqual(metadata, load_snapshot_metadata(destination))
            self.assertEqual(metadata["upstream"]["version"], "3.4.0")
            self.assertEqual(metadata["upstream"]["commit"], "b" * 40)

    def test_rejects_changed_artifact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            changelog = destination / "CHANGELOG.md"
            changelog.write_bytes(changelog.read_bytes().replace(b"Updated", b"Changed"))

            with self.assertRaisesRegex(
                ArtifactValidationError,
                "CHANGELOG.md.*SHA256",
            ):
                sync_module.verify_snapshot(destination)

    def test_rejects_wrong_artifact_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            metadata = load_snapshot_metadata(destination)
            metadata["artifacts"]["LICENSE"]["size"] += 1
            write_snapshot_metadata(destination, metadata)

            with self.assertRaisesRegex(ArtifactValidationError, "LICENSE.*size"):
                sync_module.verify_snapshot(destination)

    def test_rejects_wrong_artifact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            metadata = load_snapshot_metadata(destination)
            metadata["artifacts"]["SKILL.md"]["sha256"] = "0" * 64
            write_snapshot_metadata(destination, metadata)

            with self.assertRaisesRegex(ArtifactValidationError, "SKILL.md.*SHA256"):
                sync_module.verify_snapshot(destination)

    def test_rejects_wrong_artifact_raw_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            metadata = load_snapshot_metadata(destination)
            metadata["artifacts"]["LICENSE"]["raw_url"] = (
                "https://example.invalid/LICENSE"
            )
            write_snapshot_metadata(destination, metadata)

            with self.assertRaisesRegex(ArtifactValidationError, "LICENSE.*raw_url"):
                sync_module.verify_snapshot(destination)

    def test_rejects_metadata_version_different_from_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            metadata = load_snapshot_metadata(destination)
            metadata["upstream"]["version"] = "3.5.0"
            write_snapshot_metadata(destination, metadata)

            with self.assertRaisesRegex(ArtifactValidationError, "version.*SKILL.md"):
                sync_module.verify_snapshot(destination)

    def test_rejects_wrong_upstream_identity_commit_and_version_fields(self) -> None:
        invalid_fields = {
            "owner": "someone-else",
            "repository": "another-repository",
            "branch": "develop",
            "commit": "A" * 40,
            "version": "3.4",
        }

        for field, value in invalid_fields.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "a-stock-data"
                sync_module.sync_snapshot(FakeGitHubClient(), destination)
                metadata = load_snapshot_metadata(destination)
                metadata["upstream"][field] = value
                write_snapshot_metadata(destination, metadata)

                with self.assertRaisesRegex(SyncError, field):
                    sync_module.verify_snapshot(destination)

    def test_rejects_wrong_schema_and_artifact_metadata_fields(self) -> None:
        invalid_mutations = {
            "schema_version": lambda metadata: metadata.update(schema_version=2),
            "SKILL.md fields": lambda metadata: metadata["artifacts"][
                "SKILL.md"
            ].update(unexpected=True),
        }

        for field, mutate in invalid_mutations.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "a-stock-data"
                sync_module.sync_snapshot(FakeGitHubClient(), destination)
                metadata = load_snapshot_metadata(destination)
                mutate(metadata)
                write_snapshot_metadata(destination, metadata)

                with self.assertRaisesRegex(SyncError, field):
                    sync_module.verify_snapshot(destination)

    def test_rejects_malformed_or_naive_metadata_timestamps(self) -> None:
        invalid_timestamps = {
            "committed_at": "not-a-timestamp",
            "synced_at": "2026-07-18T06:30:00",
        }

        for field, value in invalid_timestamps.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "a-stock-data"
                sync_module.sync_snapshot(FakeGitHubClient(), destination)
                metadata = load_snapshot_metadata(destination)
                metadata["upstream"][field] = value
                write_snapshot_metadata(destination, metadata)

                with self.assertRaisesRegex(SyncError, field):
                    sync_module.verify_snapshot(destination)

    def test_rejects_wrong_artifact_set_and_missing_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            metadata = load_snapshot_metadata(destination)
            del metadata["artifacts"]["LICENSE"]
            write_snapshot_metadata(destination, metadata)

            with self.assertRaisesRegex(SyncError, "artifacts"):
                sync_module.verify_snapshot(destination)

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            (destination / "CHANGELOG.md").unlink()

            with self.assertRaisesRegex(ArtifactValidationError, "CHANGELOG.md"):
                sync_module.verify_snapshot(destination)

    def test_requires_destination_directory_and_metadata_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(SyncError, "destination"):
                sync_module.verify_snapshot(root / "missing")

            snapshot_file = root / "snapshot-file"
            snapshot_file.write_text("not a directory", encoding="utf-8")
            with self.assertRaisesRegex(SyncError, "directory"):
                sync_module.verify_snapshot(snapshot_file)

            destination = root / "a-stock-data"
            destination.mkdir()
            with self.assertRaisesRegex(SyncError, "metadata.json"):
                sync_module.verify_snapshot(destination)


class SnapshotSyncTests(unittest.TestCase):
    def test_requires_the_exact_repository_identity_before_resolving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            client = FakeGitHubClient(identity="SimonLin1212/a-stock-data")

            with self.assertRaisesRegex(SyncError, "unexpected upstream repository"):
                sync_module.sync_snapshot(client, destination)

            self.assertEqual(client.identity_calls, 1)
            self.assertEqual(client.resolve_calls, 0)
            self.assertEqual(client.downloads, [])
            self.assertFalse(destination.exists())

    def test_downloads_required_files_once_in_order_from_one_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            commit = "b" * 40
            client = FakeGitHubClient(commit=commit)

            sync_module.sync_snapshot(client, destination)

            self.assertEqual(
                client.downloads,
                [
                    (commit, name, MAX_FILE_BYTES[name])
                    for name in REQUIRED_FILES
                ],
            )

    def test_rejects_invalid_resolved_commit_metadata_without_downloads(self) -> None:
        invalid_cases = (("A" * 40, "timestamp"), ("a" * 40, ""))

        for commit, committed_at in invalid_cases:
            with self.subTest(commit=commit, committed_at=committed_at):
                with tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory) / "a-stock-data"
                    client = FakeGitHubClient(
                        commit=commit,
                        committed_at=committed_at,
                    )

                    with self.assertRaises(ArtifactValidationError):
                        sync_module.sync_snapshot(client, destination)

                    self.assertEqual(client.downloads, [])
                    self.assertFalse(destination.exists())

    def test_rejects_malformed_and_naive_commit_timestamps_without_downloads(self) -> None:
        for committed_at in ("not-a-timestamp", "2026-07-11T08:00:00"):
            with self.subTest(committed_at=committed_at):
                with tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory) / "a-stock-data"
                    client = FakeGitHubClient(committed_at=committed_at)

                    with self.assertRaisesRegex(
                        ArtifactValidationError,
                        "commit timestamp",
                    ):
                        sync_module.sync_snapshot(client, destination)

                    self.assertEqual(client.downloads, [])
                    self.assertFalse(destination.exists())

    def test_rejects_non_rfc3339_commit_timestamp_syntax_without_downloads(self) -> None:
        invalid_timestamps = (
            "20260711T08:00:00Z",
            "2026-07-11 08:00:00Z",
            "2026-07-11t08:00:00Z",
            "2026-07-11T08:00:00+0800",
        )

        for committed_at in invalid_timestamps:
            with self.subTest(committed_at=committed_at):
                with tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory) / "a-stock-data"
                    client = FakeGitHubClient(committed_at=committed_at)

                    with self.assertRaisesRegex(
                        ArtifactValidationError,
                        "commit timestamp",
                    ):
                        sync_module.sync_snapshot(client, destination)

                    self.assertEqual(client.downloads, [])
                    self.assertFalse(destination.exists())

    def test_converts_commit_timestamp_utc_overflow_to_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            client = FakeGitHubClient(committed_at="0001-01-01T00:00:00+23:59")

            with self.assertRaisesRegex(
                ArtifactValidationError,
                "commit timestamp",
            ):
                sync_module.sync_snapshot(client, destination)

            self.assertEqual(client.downloads, [])
            self.assertFalse(destination.exists())

    def test_normalizes_commit_timestamp_to_utc_in_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            client = FakeGitHubClient(
                committed_at="2026-07-11T16:00:00.123456+08:00"
            )

            sync_module.sync_snapshot(client, destination)

            metadata = json.loads((destination / "metadata.json").read_bytes())
            self.assertEqual(
                metadata["upstream"]["committed_at"],
                "2026-07-11T08:00:00.123456Z",
            )

    def test_same_commit_is_a_no_op_without_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)
            client = FakeGitHubClient()

            result = sync_module.sync_snapshot(client, destination)

            self.assertFalse(result.changed)
            self.assertEqual(result.previous_commit, "a" * 40)
            self.assertEqual(result.current_commit, "a" * 40)
            self.assertEqual(result.previous_version, "3.4.0")
            self.assertEqual(result.current_version, "3.4.0")
            self.assertEqual(
                result.section_diff,
                {"added": [], "changed": [], "removed": []},
            )
            self.assertEqual(client.downloads, [])

    def test_first_sync_writes_exact_bytes_metadata_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            commit = "b" * 40
            artifacts = valid_artifacts()
            client = FakeGitHubClient(commit=commit, artifacts=artifacts)
            china_standard_time = timezone(timedelta(hours=8))

            result = sync_module.sync_snapshot(
                client,
                destination,
                now=lambda: datetime(
                    2026,
                    7,
                    18,
                    14,
                    30,
                    tzinfo=china_standard_time,
                ),
            )

            self.assertTrue(result.changed)
            self.assertIsNone(result.previous_commit)
            self.assertEqual(result.current_commit, commit)
            self.assertIsNone(result.previous_version)
            self.assertEqual(result.current_version, "3.4.0")
            self.assertEqual(
                result.section_diff,
                {"added": ["信号层", "行情层"], "changed": [], "removed": []},
            )
            self.assertIn("`simonlin1212/a-stock-data`", result.summary)
            self.assertIn("none (first sync)", result.summary)
            self.assertIn(
                f"https://github.com/simonlin1212/a-stock-data/commit/{commit}",
                result.summary,
            )
            self.assertNotIn("/compare/", result.summary)
            self.assertIn("Added: `信号层`, `行情层`", result.summary)
            with self.assertRaises(FrozenInstanceError):
                result.changed = False

            for name, content in artifacts.items():
                self.assertEqual((destination / name).read_bytes(), content)

            expected_metadata = build_metadata(
                commit=commit,
                committed_at="2026-07-11T08:00:00Z",
                synced_at="2026-07-18T06:30:00Z",
                version="3.4.0",
                artifacts=artifacts,
            )
            expected_json = (
                json.dumps(expected_metadata, sort_keys=True, indent=2) + "\n"
            ).encode()
            self.assertEqual(
                (destination / "metadata.json").read_bytes(),
                expected_json,
            )

    def test_update_reports_previous_and_current_version_and_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            updated_artifacts = valid_artifacts()
            updated_artifacts["SKILL.md"] = """---
name: a-stock-data
version: 3.5.0
---
# A股全栈数据工具包 V3.5.0
## 行情层
Updated quote details.
## 数据层
New 备用源 data details.
""".encode()

            result = sync_module.sync_snapshot(
                FakeGitHubClient(commit="b" * 40, artifacts=updated_artifacts),
                destination,
            )

            self.assertTrue(result.changed)
            self.assertEqual(result.previous_commit, "a" * 40)
            self.assertEqual(result.current_commit, "b" * 40)
            self.assertEqual(result.previous_version, "3.4.0")
            self.assertEqual(result.current_version, "3.5.0")
            self.assertEqual(
                result.section_diff,
                {"added": ["数据层"], "changed": ["行情层"], "removed": ["信号层"]},
            )
            self.assertIn("# Upstream a-stock-data", result.summary)
            self.assertIn("Previous version: `3.4.0`", result.summary)
            self.assertIn("Current version: `3.5.0`", result.summary)
            self.assertIn(f"Previous commit: `{'a' * 40}`", result.summary)
            self.assertIn(
                f"https://github.com/simonlin1212/a-stock-data/commit/{'b' * 40}",
                result.summary,
            )
            self.assertIn(
                "https://github.com/simonlin1212/a-stock-data/compare/"
                f"{'a' * 40}...{'b' * 40}",
                result.summary,
            )
            self.assertIn("Added: `数据层`", result.summary)
            self.assertIn("Changed: `行情层`", result.summary)
            self.assertIn("Removed: `信号层`", result.summary)
            for name, content in sorted(updated_artifacts.items()):
                self.assertIn(
                    f"| `{name}` | {len(content)} | "
                    f"`{hashlib.sha256(content).hexdigest()}` |",
                    result.summary,
                )
            self.assertLess(
                result.summary.index("`CHANGELOG.md`"),
                result.summary.index("`LICENSE`"),
            )
            self.assertLess(
                result.summary.index("`LICENSE`"),
                result.summary.index("`SKILL.md`"),
            )
            self.assertIn("WARNING", result.summary)
            self.assertIn("Tencent", result.summary)
            self.assertIn("Eastmoney", result.summary)
            self.assertIn("备用源", result.summary)
            self.assertIn("Upstream Markdown is not executed", result.summary)
            self.assertIn("runtime providers are unchanged", result.summary)

    def test_download_failure_preserves_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            before = snapshot_bytes(destination)

            with self.assertRaisesRegex(SyncError, "CHANGELOG.md"):
                sync_module.sync_snapshot(
                    FakeGitHubClient(commit="b" * 40, fail_file="CHANGELOG.md"),
                    destination,
                )

            self.assertEqual(snapshot_bytes(destination), before)

    def test_validation_failure_preserves_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            before = snapshot_bytes(destination)
            invalid_artifacts = valid_artifacts()
            invalid_artifacts["LICENSE"] = b"not the expected license"

            with self.assertRaises(ArtifactValidationError):
                sync_module.sync_snapshot(
                    FakeGitHubClient(commit="b" * 40, artifacts=invalid_artifacts),
                    destination,
                )

            self.assertEqual(snapshot_bytes(destination), before)

    def test_malformed_existing_metadata_fails_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            (destination / "metadata.json").write_text(
                '{"schema_version": 1, "upstream": []}\n',
                encoding="utf-8",
            )
            before = snapshot_bytes(destination)
            client = FakeGitHubClient(commit="b" * 40)

            with self.assertRaisesRegex(SyncError, "metadata.json"):
                sync_module.sync_snapshot(client, destination)

            self.assertEqual(client.resolve_calls, 0)
            self.assertEqual(client.downloads, [])
            self.assertEqual(snapshot_bytes(destination), before)

    def test_deeply_nested_existing_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            deeply_nested_json = b"[" * 10_000 + b"0" + b"]" * 10_000
            (destination / "metadata.json").write_bytes(deeply_nested_json)
            before = snapshot_bytes(destination)
            client = FakeGitHubClient(commit="b" * 40)

            with self.assertRaisesRegex(SyncError, "malformed JSON"):
                sync_module.sync_snapshot(client, destination)

            self.assertEqual(client.resolve_calls, 0)
            self.assertEqual(snapshot_bytes(destination), before)

    def test_malformed_existing_metadata_schema_fails_without_overwrite(self) -> None:
        for mutation in (
            lambda metadata: metadata.update(schema_version=True),
            lambda metadata: metadata.update(artifacts={}),
        ):
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory) / "a-stock-data"
                    sync_module.sync_snapshot(
                        FakeGitHubClient(commit="a" * 40),
                        destination,
                    )
                    metadata_path = destination / "metadata.json"
                    metadata = json.loads(metadata_path.read_bytes())
                    mutation(metadata)
                    metadata_path.write_text(
                        json.dumps(metadata),
                        encoding="utf-8",
                    )
                    before = snapshot_bytes(destination)
                    client = FakeGitHubClient(commit="b" * 40)

                    with self.assertRaisesRegex(SyncError, "metadata.json"):
                        sync_module.sync_snapshot(client, destination)

                    self.assertEqual(client.resolve_calls, 0)
                    self.assertEqual(snapshot_bytes(destination), before)

    def test_final_directory_replace_failure_restores_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            before = snapshot_bytes(destination)
            real_replace = sync_module._replace_path

            def fail_candidate_replace(source: Path, target: Path) -> None:
                if (
                    target == destination
                    and source.name.startswith(f".{destination.name}.tmp-")
                ):
                    raise OSError("simulated final rename failure")
                real_replace(source, target)

            with patch.object(
                sync_module,
                "_replace_path",
                side_effect=fail_candidate_replace,
            ):
                with self.assertRaisesRegex(SyncError, "replace snapshot"):
                    sync_module.sync_snapshot(
                        FakeGitHubClient(commit="b" * 40),
                        destination,
                    )

            self.assertEqual(snapshot_bytes(destination), before)
            self.assertEqual([path.name for path in root.iterdir()], ["a-stock-data"])

    def test_transient_restore_failure_retries_and_restores_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            before = snapshot_bytes(destination)
            real_replace = sync_module._replace_path
            restore_attempts = 0

            def fail_install_and_first_restore(source: Path, target: Path) -> None:
                nonlocal restore_attempts
                if target == destination and source.name.startswith(
                    f".{destination.name}.tmp-"
                ):
                    raise OSError("simulated candidate installation failure")
                if target == destination and source.name.startswith(
                    f".{destination.name}.backup-"
                ):
                    restore_attempts += 1
                    if restore_attempts == 1:
                        raise OSError("simulated transient restoration failure")
                real_replace(source, target)

            with patch.object(
                sync_module,
                "_replace_path",
                side_effect=fail_install_and_first_restore,
            ):
                with self.assertRaisesRegex(SyncError, "replace snapshot"):
                    sync_module.sync_snapshot(
                        FakeGitHubClient(commit="b" * 40),
                        destination,
                    )

            self.assertEqual(restore_attempts, 2)
            self.assertEqual(snapshot_bytes(destination), before)
            self.assertEqual([path.name for path in root.iterdir()], ["a-stock-data"])

    def test_persistent_restore_failure_preserves_recovery_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            before = snapshot_bytes(destination)
            real_replace = sync_module._replace_path
            restore_attempts = 0

            def fail_install_and_restore(source: Path, target: Path) -> None:
                nonlocal restore_attempts
                if target == destination and source.name.startswith(
                    f".{destination.name}.tmp-"
                ):
                    raise OSError("simulated candidate installation failure")
                if target == destination and source.name.startswith(
                    f".{destination.name}.backup-"
                ):
                    restore_attempts += 1
                    raise OSError("simulated persistent restoration failure")
                real_replace(source, target)

            with patch.object(
                sync_module,
                "_replace_path",
                side_effect=fail_install_and_restore,
            ):
                with self.assertRaisesRegex(SyncError, "restore previous snapshot"):
                    sync_module.sync_snapshot(
                        FakeGitHubClient(commit="b" * 40),
                        destination,
                    )

            backups = [
                path
                for path in root.iterdir()
                if path.name.startswith(f".{destination.name}.backup-")
            ]
            candidates = [
                path
                for path in root.iterdir()
                if path.name.startswith(f".{destination.name}.tmp-")
            ]
            self.assertEqual(restore_attempts, 2)
            self.assertFalse(destination.exists())
            self.assertEqual(len(backups), 1)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(snapshot_bytes(backups[0]), before)
            for name, content in valid_artifacts().items():
                self.assertEqual((candidates[0] / name).read_bytes(), content)
            candidate_metadata = json.loads(
                (candidates[0] / "metadata.json").read_bytes()
            )
            self.assertEqual(candidate_metadata["upstream"]["commit"], "b" * 40)

    def test_partial_backup_cleanup_failure_keeps_complete_new_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
            real_remove = sync_module._remove_directory

            def partially_remove_backup(path: Path) -> None:
                if path.name.startswith(f".{destination.name}.backup-"):
                    (path / "CHANGELOG.md").unlink()
                    raise OSError("simulated partial backup cleanup failure")
                real_remove(path)

            with patch.object(
                sync_module,
                "_remove_directory",
                side_effect=partially_remove_backup,
            ):
                result = sync_module.sync_snapshot(
                    FakeGitHubClient(commit="b" * 40),
                    destination,
                )

            backups = [
                path
                for path in root.iterdir()
                if path.name.startswith(f".{destination.name}.backup-")
            ]
            candidates = [
                path
                for path in root.iterdir()
                if path.name.startswith(f".{destination.name}.tmp-")
            ]
            self.assertTrue(result.changed)
            for name, content in valid_artifacts().items():
                self.assertEqual((destination / name).read_bytes(), content)
            metadata = json.loads((destination / "metadata.json").read_bytes())
            self.assertEqual(metadata["upstream"]["commit"], "b" * 40)
            self.assertEqual(len(backups), 1)
            self.assertFalse((backups[0] / "CHANGELOG.md").exists())
            self.assertEqual(candidates, [])


class CliTests(unittest.TestCase):
    def test_check_verifies_locally_without_factory_or_network_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            sync_module.sync_snapshot(FakeGitHubClient(), destination)

            def fail_factory(token: str | None) -> FakeGitHubClient:
                self.fail(f"client factory called with {token!r}")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.dict(
                os.environ,
                {"GITHUB_TOKEN": "must-not-be-read"},
            ), patch.object(
                sync_module.urllib.request,
                "urlopen",
                side_effect=AssertionError("network call attempted"),
            ) as urlopen, redirect_stdout(stdout), redirect_stderr(stderr):
                status = sync_module.main(
                    ["--check", "--destination", str(destination)],
                    client_factory=fail_factory,
                )

            self.assertEqual(status, 0)
            self.assertEqual(urlopen.call_count, 0)
            self.assertIn(f"verified a-stock-data 3.4.0 at {'a' * 40}", stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")

    def test_normal_mode_passes_token_and_reports_updated_then_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "a-stock-data"
            commit = "c" * 40
            factory_tokens: list[str | None] = []
            clients: list[FakeGitHubClient] = []

            def factory(token: str | None) -> FakeGitHubClient:
                factory_tokens.append(token)
                client = FakeGitHubClient(commit=commit)
                clients.append(client)
                return client

            first_stdout = io.StringIO()
            second_stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.dict(
                os.environ,
                {"GITHUB_TOKEN": "secret-cli-token"},
                clear=True,
            ), redirect_stderr(stderr):
                with redirect_stdout(first_stdout):
                    first_status = sync_module.main(
                        ["--destination", str(destination)],
                        client_factory=factory,
                    )
                with redirect_stdout(second_stdout):
                    second_status = sync_module.main(
                        ["--destination", str(destination)],
                        client_factory=factory,
                    )

            self.assertEqual(first_status, 0)
            self.assertEqual(second_status, 0)
            self.assertEqual(factory_tokens, ["secret-cli-token", "secret-cli-token"])
            self.assertIn(f"updated none -> {commit}", first_stdout.getvalue())
            self.assertIn(f"unchanged {commit}", second_stdout.getvalue())
            self.assertEqual(clients[1].downloads, [])
            combined_output = first_stdout.getvalue() + second_stdout.getvalue()
            self.assertNotIn("secret-cli-token", combined_output)
            self.assertEqual(stderr.getvalue(), "")

    def test_summary_path_creates_parents_and_writes_exact_utf8_content(self) -> None:
        result = sync_module.SyncResult(
            changed=True,
            previous_commit=None,
            current_commit="d" * 40,
            previous_version=None,
            current_version="3.4.0",
            section_diff={"added": [], "changed": [], "removed": []},
            summary="# Upstream a-stock-data\n\n中文 summary\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "snapshot"
            summary_path = root / "nested" / "reports" / "summary.md"
            stdout = io.StringIO()
            with patch.object(
                sync_module,
                "sync_snapshot",
                return_value=result,
            ), patch.dict(os.environ, {}, clear=True), redirect_stdout(stdout):
                status = sync_module.main(
                    [
                        "--destination",
                        str(destination),
                        "--summary-path",
                        str(summary_path),
                    ],
                    client_factory=lambda token: FakeGitHubClient(),
                )

            self.assertEqual(status, 0)
            self.assertEqual(summary_path.read_bytes(), result.summary.encode("utf-8"))

    def test_errors_are_concise_redacted_and_have_no_traceback(self) -> None:
        error_types = (SyncError, ArtifactValidationError)

        for error_type in error_types:
            with self.subTest(error_type=error_type), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "snapshot"

                def failing_factory(token: str | None) -> FakeGitHubClient:
                    raise error_type(f"failure for {token}: metadata.json")

                stdout = io.StringIO()
                stderr = io.StringIO()
                with patch.dict(
                    os.environ,
                    {"GITHUB_TOKEN": "secret-error-token"},
                    clear=True,
                ), redirect_stdout(stdout), redirect_stderr(stderr):
                    status = sync_module.main(
                        ["--destination", str(destination)],
                        client_factory=failing_factory,
                    )

                self.assertEqual(status, 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue().count("\n"), 1)
                self.assertIn("error:", stderr.getvalue())
                self.assertIn("metadata.json", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())
                self.assertNotIn("secret-error-token", stderr.getvalue())

    def test_default_destination_is_resolved_from_repository_not_cwd(self) -> None:
        result = sync_module.SyncResult(
            changed=False,
            previous_commit="e" * 40,
            current_commit="e" * 40,
            previous_version="3.4.0",
            current_version="3.4.0",
            section_diff={"added": [], "changed": [], "removed": []},
            summary="summary\n",
        )
        expected = (
            Path(sync_module.__file__).resolve().parents[1]
            / "third_party"
            / "a-stock-data"
        )
        with tempfile.TemporaryDirectory() as directory:
            previous_cwd = Path.cwd()
            stdout = io.StringIO()
            try:
                os.chdir(directory)
                with patch.object(
                    sync_module,
                    "sync_snapshot",
                    return_value=result,
                ) as sync_snapshot, patch.dict(
                    os.environ,
                    {},
                    clear=True,
                ), redirect_stdout(stdout):
                    status = sync_module.main(
                        [],
                        client_factory=lambda token: FakeGitHubClient(),
                    )
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(status, 0)
        self.assertEqual(sync_snapshot.call_args.args[1], expected)


class GitHubClientTests(unittest.TestCase):
    def test_reads_api_endpoints_and_raw_file_with_expected_requests(self) -> None:
        commit = "b" * 40
        responses = [
            FakeResponse(b'{"full_name": "simonlin1212/a-stock-data"}'),
            FakeResponse(
                (
                    '{"sha": "'
                    + commit
                    + '", "commit": {"committer": '
                    '{"date": "2026-07-11T08:00:00Z"}}}'
                ).encode()
            ),
            FakeResponse(b"raw"),
        ]

        with patch.object(
            sync_module.urllib.request,
            "urlopen",
            side_effect=responses,
        ) as urlopen:
            client = sync_module.GitHubClient(token="secret-token", timeout=7)
            self.assertEqual(client.repository_identity(), "simonlin1212/a-stock-data")
            self.assertEqual(
                client.resolve_commit(),
                (commit, "2026-07-11T08:00:00Z"),
            )
            self.assertEqual(client.download_file(commit, "SKILL.md", 3), b"raw")

        requests = [call.args[0] for call in urlopen.call_args_list]
        self.assertEqual(
            [request.full_url for request in requests],
            [
                "https://api.github.com/repos/simonlin1212/a-stock-data",
                "https://api.github.com/repos/simonlin1212/a-stock-data/commits/main",
                (
                    "https://raw.githubusercontent.com/simonlin1212/a-stock-data/"
                    f"{commit}/SKILL.md"
                ),
            ],
        )
        self.assertEqual(
            [call.kwargs["timeout"] for call in urlopen.call_args_list],
            [7, 7, 7],
        )
        for request in requests:
            headers = {name.lower(): value for name, value in request.header_items()}
            self.assertEqual(headers["accept"], "application/vnd.github+json")
            self.assertEqual(headers["authorization"], "Bearer secret-token")
            self.assertIn("StockMaster", headers["user-agent"])
        self.assertEqual(responses[0].read_limits, [1_000_001])
        self.assertEqual(responses[1].read_limits, [1_000_001])
        self.assertEqual(responses[2].read_limits, [4])

    def test_rejects_oversized_json_and_raw_responses(self) -> None:
        oversized_json = FakeResponse(b" " * 1_000_001)
        with patch.object(
            sync_module.urllib.request,
            "urlopen",
            return_value=oversized_json,
        ):
            with self.assertRaisesRegex(ArtifactValidationError, "JSON response"):
                sync_module.GitHubClient().repository_identity()
        self.assertEqual(oversized_json.read_limits, [1_000_001])

        oversized_raw = FakeResponse(b"1234")
        with patch.object(
            sync_module.urllib.request,
            "urlopen",
            return_value=oversized_raw,
        ):
            with self.assertRaisesRegex(ArtifactValidationError, "SKILL.md"):
                sync_module.GitHubClient().download_file("a" * 40, "SKILL.md", 3)
        self.assertEqual(oversized_raw.read_limits, [4])

    def test_rejects_truncated_content_length_response(self) -> None:
        response = HeaderResponse(b"raw", content_length=4)
        url = (
            "https://raw.githubusercontent.com/simonlin1212/a-stock-data/"
            f"{'a' * 40}/SKILL.md"
        )

        with patch.object(
            sync_module.urllib.request,
            "urlopen",
            return_value=response,
        ):
            with self.assertRaisesRegex(SyncError, "truncated") as raised:
                sync_module.GitHubClient().download_file("a" * 40, "SKILL.md", 4)

        self.assertIn(url, str(raised.exception))
        self.assertEqual(response.read_limits, [5])

    def test_rejects_content_length_over_limit_before_read(self) -> None:
        response = HeaderResponse(b"raw", content_length=4)

        with patch.object(
            sync_module.urllib.request,
            "urlopen",
            return_value=response,
        ):
            with self.assertRaisesRegex(SyncError, "size limit"):
                sync_module.GitHubClient().download_file("a" * 40, "SKILL.md", 3)

        self.assertEqual(response.read_limits, [])

    def test_converts_incomplete_read_to_sync_error_with_safe_url(self) -> None:
        response = IncompleteResponse(b"partial")
        url = (
            "https://raw.githubusercontent.com/simonlin1212/a-stock-data/"
            f"{'a' * 40}/SKILL.md"
        )

        with patch.object(
            sync_module.urllib.request,
            "urlopen",
            return_value=response,
        ):
            with self.assertRaises(SyncError) as raised:
                sync_module.GitHubClient(token="secret-token").download_file(
                    "a" * 40,
                    "SKILL.md",
                    10,
                )

        self.assertIn(url, str(raised.exception))
        self.assertNotIn("secret-token", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertEqual(response.read_limits, [11])

    def test_rejects_malformed_json_and_non_object_responses(self) -> None:
        for content in (b"{", b"[]"):
            with self.subTest(content=content), patch.object(
                sync_module.urllib.request,
                "urlopen",
                return_value=FakeResponse(content),
            ):
                with self.assertRaises(ArtifactValidationError):
                    sync_module.GitHubClient().repository_identity()

    def test_rejects_deeply_nested_json_response(self) -> None:
        deeply_nested_json = b"[" * 10_000 + b"0" + b"]" * 10_000
        self.assertLess(len(deeply_nested_json), 1_000_000)

        with patch.object(
            sync_module.urllib.request,
            "urlopen",
            return_value=FakeResponse(deeply_nested_json),
        ):
            with self.assertRaisesRegex(ArtifactValidationError, "malformed JSON"):
                sync_module.GitHubClient().repository_identity()

    def test_converts_network_errors_without_leaking_token(self) -> None:
        failures = (
            urllib.error.HTTPError("https://api.github.com", 500, "error", {}, None),
            urllib.error.URLError("Authorization: Bearer secret-token"),
            socket.timeout("timed out"),
            http.client.HTTPException("Authorization: Bearer secret-token"),
        )

        for failure in failures:
            with self.subTest(failure=failure), patch.object(
                sync_module.urllib.request,
                "urlopen",
                side_effect=failure,
            ):
                with self.assertRaises(SyncError) as raised:
                    sync_module.GitHubClient(token="secret-token").repository_identity()
                self.assertIn(
                    "https://api.github.com/repos/simonlin1212/a-stock-data",
                    str(raised.exception),
                )
                self.assertNotIn("secret-token", str(raised.exception))
                self.assertIsNone(raised.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
