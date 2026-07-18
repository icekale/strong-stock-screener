from __future__ import annotations

import hashlib
import unittest
from typing import get_type_hints, is_typeddict

from scripts.sync_a_stock_data import (
    ArtifactValidationError,
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


if __name__ == "__main__":
    unittest.main()
