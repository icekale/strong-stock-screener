from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import unittest
import urllib.error
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


def snapshot_bytes(destination: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted(destination.iterdir())
        if path.is_file()
    }


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
            self.assertIn(f"`none` -> `{commit}`", result.summary)
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
New data details.
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
            self.assertIn("`3.4.0` -> `3.5.0`", result.summary)
            self.assertIn("Changed: `行情层`", result.summary)

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

    def test_rejects_malformed_json_and_non_object_responses(self) -> None:
        for content in (b"{", b"[]"):
            with self.subTest(content=content), patch.object(
                sync_module.urllib.request,
                "urlopen",
                return_value=FakeResponse(content),
            ):
                with self.assertRaises(ArtifactValidationError):
                    sync_module.GitHubClient().repository_identity()

    def test_converts_network_errors_without_leaking_token(self) -> None:
        failures = (
            urllib.error.HTTPError("https://api.github.com", 500, "error", {}, None),
            urllib.error.URLError("Authorization: Bearer secret-token"),
            socket.timeout("timed out"),
        )

        for failure in failures:
            with self.subTest(failure=failure), patch.object(
                sync_module.urllib.request,
                "urlopen",
                side_effect=failure,
            ):
                with self.assertRaises(SyncError) as raised:
                    sync_module.GitHubClient(token="secret-token").repository_identity()
                self.assertNotIn("secret-token", str(raised.exception))
                self.assertIsNone(raised.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
