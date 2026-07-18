# a-stock-data Upstream Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily, review-gated synchronization pipeline that vendors a commit-pinned `a-stock-data` snapshot and creates one auditable PR without executing or deploying upstream code.

**Architecture:** A standard-library Python module owns GitHub reads, artifact validation, section comparison, deterministic metadata, and transactional snapshot replacement. A GitHub Actions workflow owns scheduling, Git commits, and PR creation on the stable `automation/a-stock-data-sync` branch. Runtime providers remain unchanged.

**Tech Stack:** Python 3.12 standard library, `unittest`, GitHub REST/raw content APIs, GitHub Actions, GitHub CLI.

---

## File Map

- Create `scripts/sync_a_stock_data.py`: validation, GitHub client, report generation, snapshot transaction, and CLI.
- Create `tests/test_sync_a_stock_data.py`: deterministic tests with a fake GitHub client and temporary directories.
- Create `tests/test_a_stock_data_workflow.py`: source-contract tests for the scheduled workflow.
- Create `.github/workflows/sync-a-stock-data.yml`: daily/manual synchronization and stable-branch PR management.
- Create `third_party/a-stock-data/{SKILL.md,CHANGELOG.md,LICENSE,metadata.json}`: the pinned snapshot.

No file under `apps/api`, `apps/web`, `apps/web-vue`, Docker, or Unraid configuration is modified.

### Task 1: Validate Artifacts And Compare Markdown Sections

**Files:**
- Create: `scripts/sync_a_stock_data.py`
- Create: `tests/test_sync_a_stock_data.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/test_sync_a_stock_data.py`:

```python
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

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


class ArtifactValidationTests(unittest.TestCase):
    def test_validates_required_files_and_extracts_version(self) -> None:
        version = validate_artifacts(
            {"SKILL.md": VALID_SKILL, "CHANGELOG.md": VALID_CHANGELOG, "LICENSE": VALID_LICENSE}
        )
        self.assertEqual(version, "3.4.0")

    def test_rejects_html_and_invalid_license(self) -> None:
        with self.assertRaisesRegex(ArtifactValidationError, "HTML"):
            validate_artifacts(
                {"SKILL.md": b"<!doctype html><title>404</title>", "CHANGELOG.md": VALID_CHANGELOG, "LICENSE": VALID_LICENSE}
            )
        with self.assertRaisesRegex(ArtifactValidationError, "Apache License 2.0"):
            validate_artifacts(
                {"SKILL.md": VALID_SKILL, "CHANGELOG.md": VALID_CHANGELOG, "LICENSE": b"Unknown license"}
            )

    def test_compares_level_two_sections_stably(self) -> None:
        previous = parse_markdown_sections("# Root\n## Quotes\nold\n## Signals\nsame\n")
        current = parse_markdown_sections("# Root\n## Quotes\nnew\n## Signals\nsame\n## Fallbacks\nadded\n")
        self.assertEqual(
            compare_sections(previous, current),
            {"added": ["Fallbacks"], "changed": ["Quotes"], "removed": []},
        )

    def test_metadata_hashes_exact_bytes_and_pins_raw_urls(self) -> None:
        artifacts = {"SKILL.md": VALID_SKILL, "CHANGELOG.md": VALID_CHANGELOG, "LICENSE": VALID_LICENSE}
        metadata = build_metadata(
            commit="a" * 40,
            committed_at="2026-07-11T08:00:00Z",
            synced_at="2026-07-18T06:30:00Z",
            version="3.4.0",
            artifacts=artifacts,
        )
        item = metadata["artifacts"]["SKILL.md"]
        self.assertEqual(item["size"], len(VALID_SKILL))
        self.assertEqual(item["sha256"], hashlib.sha256(VALID_SKILL).hexdigest())
        self.assertIn("/" + "a" * 40 + "/SKILL.md", item["raw_url"])
```

- [ ] **Step 2: Run the tests to verify red**

Run from the repository root:

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m unittest tests.test_sync_a_stock_data -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.sync_a_stock_data'`.

- [ ] **Step 3: Implement pure validation and metadata functions**

Create `scripts/sync_a_stock_data.py` with only standard-library imports and these exact constants/contracts:

```python
OWNER = "simonlin1212"
REPOSITORY = "a-stock-data"
BRANCH = "main"
REQUIRED_FILES = ("SKILL.md", "CHANGELOG.md", "LICENSE")
MAX_FILE_BYTES = {"SKILL.md": 512_000, "CHANGELOG.md": 256_000, "LICENSE": 64_000}
VERSION_RE = re.compile(r"(?m)^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class SyncError(RuntimeError):
    pass


class ArtifactValidationError(SyncError):
    pass
```

Implement `validate_artifacts(artifacts) -> str` to require all three non-empty UTF-8 files, enforce the per-file byte limits, reject leading HTML, require `name: a-stock-data`, the Chinese project H1, a semantic `version:` field, a `# Changelog` prefix, and Apache License 2.0. Implement `parse_markdown_sections` by grouping `## ` headings and bodies. Implement `compare_sections` with sorted `added`, `changed`, and `removed` lists.

Implement `build_metadata` with this stable schema:

```python
{
    "schema_version": 1,
    "upstream": {
        "owner": OWNER,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "commit": commit,
        "version": version,
        "committed_at": committed_at,
        "synced_at": synced_at,
        "commit_url": f"https://github.com/{OWNER}/{REPOSITORY}/commit/{commit}",
    },
    "artifacts": {
        name: {
            "raw_url": f"https://raw.githubusercontent.com/{OWNER}/{REPOSITORY}/{commit}/{name}",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for name, content in sorted(artifacts.items())
    },
}
```

- [ ] **Step 4: Run focused tests and verify green**

Run the Step 2 command. Expected: four tests pass.

- [ ] **Step 5: Commit validation primitives**

```bash
git add scripts/sync_a_stock_data.py tests/test_sync_a_stock_data.py
git commit -m "feat: validate a-stock-data snapshots"
```

### Task 2: Fetch And Replace One Commit-Pinned Snapshot

**Files:**
- Modify: `scripts/sync_a_stock_data.py`
- Modify: `tests/test_sync_a_stock_data.py`

- [ ] **Step 1: Add failing transaction tests**

Add a fake client with `repository_identity()`, `resolve_commit()`, and `download_file(commit, name, max_bytes)`. Add tests proving:

```python
def test_sync_downloads_every_file_from_one_resolved_commit(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "a-stock-data"
        client = FakeGitHubClient(commit="b" * 40)
        result = sync_snapshot(client, destination, now=lambda: datetime(2026, 7, 18, tzinfo=timezone.utc))
        self.assertTrue(result.changed)
        self.assertEqual(client.downloads, [("b" * 40, name) for name in REQUIRED_FILES])

def test_same_commit_is_a_no_op_without_downloads(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "a-stock-data"
        client = FakeGitHubClient()
        sync_snapshot(client, destination)
        client.downloads.clear()
        self.assertFalse(sync_snapshot(client, destination).changed)
        self.assertEqual(client.downloads, [])

def test_download_failure_preserves_previous_snapshot(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "a-stock-data"
        sync_snapshot(FakeGitHubClient(commit="a" * 40), destination)
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        with self.assertRaisesRegex(SyncError, "CHANGELOG.md"):
            sync_snapshot(FakeGitHubClient(commit="b" * 40, fail_file="CHANGELOG.md"), destination)
        self.assertEqual(before, {path.name: path.read_bytes() for path in destination.iterdir()})
```

- [ ] **Step 2: Run transaction tests and confirm red**

Expected: missing `sync_snapshot`, `SyncResult`, and `REQUIRED_FILES` imports.

- [ ] **Step 3: Implement the client and transaction**

Add:

```python
class UpstreamClient(Protocol):
    def repository_identity(self) -> str: ...
    def resolve_commit(self) -> tuple[str, str]: ...
    def download_file(self, commit: str, name: str, max_bytes: int) -> bytes: ...


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    previous_commit: str | None
    current_commit: str
    previous_version: str | None
    current_version: str
    section_diff: dict[str, list[str]]
    summary: str
```

`GitHubClient` uses `urllib.request`, an optional bearer token, a 20-second timeout, a 1 MB JSON limit, and `max_bytes + 1` bounded raw reads. It validates `full_name == "simonlin1212/a-stock-data"`, resolves `main` through `/commits/main`, and downloads each raw file from the resolved SHA URL. Convert HTTP, timeout, and JSON errors to `SyncError` without printing request headers.

`sync_snapshot` must check existing `metadata.json` before downloads, no-op on the same commit, validate all downloaded bytes in memory, compare old/new `SKILL.md` sections, build metadata, and only then call `_write_snapshot`. `_write_snapshot` writes a sibling temporary directory, renames the old snapshot to a backup, renames the complete candidate into place, restores the backup if replacement fails, and removes the backup after success.

- [ ] **Step 4: Run all synchronization tests**

Run the Task 1 test command. Expected: validation, pinning, no-op, and atomicity tests pass.

- [ ] **Step 5: Commit synchronization behavior**

```bash
git add scripts/sync_a_stock_data.py tests/test_sync_a_stock_data.py
git commit -m "feat: synchronize pinned a-stock-data snapshots"
```

### Task 3: Add Local Verification, CLI, And The Initial Snapshot

**Files:**
- Modify: `scripts/sync_a_stock_data.py`
- Modify: `tests/test_sync_a_stock_data.py`
- Create: `third_party/a-stock-data/SKILL.md`
- Create: `third_party/a-stock-data/CHANGELOG.md`
- Create: `third_party/a-stock-data/LICENSE`
- Create: `third_party/a-stock-data/metadata.json`

- [ ] **Step 1: Add failing local-verification tests**

Add tests for `verify_snapshot(destination)` and `main(argv, client_factory=...)`:

```python
def test_verify_snapshot_rejects_tampered_content(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "a-stock-data"
        sync_snapshot(FakeGitHubClient(), destination)
        (destination / "SKILL.md").write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(ArtifactValidationError, "SHA256"):
            verify_snapshot(destination)

def test_cli_writes_the_generated_summary(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "a-stock-data"
        summary = Path(directory) / "summary.md"
        exit_code = main(
            ["--destination", str(destination), "--summary-path", str(summary)],
            client_factory=lambda _token: FakeGitHubClient(),
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("a-stock-data", summary.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run the new tests and confirm red**

Run the full sync test module. Expected: missing `verify_snapshot` and `main` imports.

- [ ] **Step 3: Implement CLI and local verification**

Support this exact command:

```text
python scripts/sync_a_stock_data.py [--destination PATH] [--summary-path PATH] [--check]
```

`--check` performs no network calls. It validates metadata identity, 40-character commit, semantic version, required file set, file sizes, commit-pinned raw URLs, and exact SHA256 values. Normal mode reads `GITHUB_TOKEN`, calls `sync_snapshot`, writes the report when requested, prints `updated <old> -> <new>` or `unchanged <sha>`, and returns zero. A `SyncError` prints one message to stderr and returns one without a traceback. Keep `client_factory` injectable for tests and call `raise SystemExit(main())` only in the module guard.

The summary must include old/new version and commit, commit/compare links, sorted section changes, file sizes and hashes, and a warning when changed section content contains any tracked term from this fixed set:

```python
TRACKED_TERMS = ("腾讯", "Tencent", "mootdx", "通达信", "Eastmoney", "东财", "行业", "备用源", "降级")
```

- [ ] **Step 4: Run tests, then seed and verify the real upstream**

Run:

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m unittest tests.test_sync_a_stock_data -v
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python scripts/sync_a_stock_data.py --destination third_party/a-stock-data --summary-path /tmp/a-stock-data-sync-summary.md
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python scripts/sync_a_stock_data.py --destination third_party/a-stock-data --check
```

Expected: tests pass; the baseline records upstream version `3.4.0` and commit `9ed665cc9773457bc23fed6b770b2b5a8cede40f` or a newer valid commit; local verification passes.

- [ ] **Step 5: Prove the real baseline is idempotent**

Run normal synchronization a second time. Expected: `unchanged <sha>` and `git diff --exit-code -- third_party/a-stock-data` after staging/committing the initial baseline.

- [ ] **Step 6: Commit the CLI and baseline**

```bash
git add scripts/sync_a_stock_data.py tests/test_sync_a_stock_data.py third_party/a-stock-data
git commit -m "feat: vendor a-stock-data upstream baseline"
```

### Task 4: Schedule A Single Review-Gated Pull Request

**Files:**
- Create: `.github/workflows/sync-a-stock-data.yml`
- Create: `tests/test_a_stock_data_workflow.py`

- [ ] **Step 1: Write a failing workflow contract test**

Create `tests/test_a_stock_data_workflow.py`:

```python
from pathlib import Path
import unittest


class WorkflowContractTests(unittest.TestCase):
    def test_workflow_is_scheduled_review_gated_and_non_deploying(self) -> None:
        root = Path(__file__).parents[1]
        source = (root / ".github/workflows/sync-a-stock-data.yml").read_text(encoding="utf-8")
        for required in (
            "cron: '30 22 * * *'",
            "workflow_dispatch:",
            "contents: write",
            "pull-requests: write",
            "group: sync-a-stock-data",
            "automation/a-stock-data-sync",
            "python -m unittest discover",
            "scripts/sync_a_stock_data.py",
            "gh pr create",
            "gh pr edit",
        ):
            self.assertIn(required, source)
        for forbidden in ("docker build", "docker push", "unraid", "ssh "):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test and verify red**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m unittest tests.test_a_stock_data_workflow -v
```

Expected: `FileNotFoundError` for `.github/workflows/sync-a-stock-data.yml`.

- [ ] **Step 3: Create the workflow**

Create `.github/workflows/sync-a-stock-data.yml` with:

```yaml
name: Sync a-stock-data

on:
  schedule:
    - cron: '30 22 * * *'
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

concurrency:
  group: sync-a-stock-data
  cancel-in-progress: false
```

Add one Ubuntu job that checks out `main` with full history, sets up Python 3.12, runs `python -m unittest discover -s tests -p 'test_*a_stock_data*.py' -v`, and executes the sync script with `GITHUB_TOKEN`, `third_party/a-stock-data`, and `$RUNNER_TEMP/a-stock-data-summary.md`.

If `git diff --quiet -- third_party/a-stock-data` is true, exit without Git operations. Otherwise configure `github-actions[bot]`, fetch the existing `automation/a-stock-data-sync` branch when present, create/reset that branch from the checked-out `main`, commit only `third_party/a-stock-data`, and push with `--force-with-lease`. With `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`, find an open PR using `gh pr list --head automation/a-stock-data-sync --base main --state open --json number --jq '.[0].number'`; call `gh pr create` when absent or `gh pr edit` when present. Use the generated summary as the PR body. Do not invoke Docker, SSH, Unraid, or deployment workflows.

- [ ] **Step 4: Run both root test modules**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m unittest discover -s tests -p 'test_*a_stock_data*.py' -v
```

Expected: all synchronization and workflow contract tests pass.

- [ ] **Step 5: Commit the workflow**

```bash
git add .github/workflows/sync-a-stock-data.yml tests/test_a_stock_data_workflow.py
git commit -m "ci: schedule a-stock-data update reviews"
```

### Task 5: Verify Security, Idempotence, And Isolation

**Files:**
- Verify only; modify earlier files only when a check identifies a defect.

- [ ] **Step 1: Run synchronization tests with the system Python**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m unittest discover -s tests -p 'test_*a_stock_data*.py' -v
```

Expected: pass with no project dependencies.

- [ ] **Step 2: Verify the real snapshot and no-op behavior**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python scripts/sync_a_stock_data.py --destination third_party/a-stock-data --check
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python scripts/sync_a_stock_data.py --destination third_party/a-stock-data --summary-path /tmp/a-stock-data-sync-summary.md
git diff --exit-code -- third_party/a-stock-data
```

Expected: verification passes, synchronization reports unchanged, and the vendored directory has no uncommitted changes.

- [ ] **Step 3: Scan for forbidden runtime/deployment coupling**

```bash
git diff 5a5a57a --name-only
rg -n "exec\(|eval\(|importlib|subprocess|docker (build|push)|unraid|ssh " scripts/sync_a_stock_data.py .github/workflows/sync-a-stock-data.yml
```

Expected: changed implementation files are limited to root scripts/tests, workflow, and `third_party/a-stock-data`; forbidden scan returns no matches.

- [ ] **Step 4: Run the existing API regression suite**

From `apps/api` run:

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pytest -q
```

Expected: `831 passed` or more, zero failures.

- [ ] **Step 5: Run lint and whitespace checks**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m ruff check scripts/sync_a_stock_data.py tests/test_sync_a_stock_data.py tests/test_a_stock_data_workflow.py
git diff --check 5a5a57a
git status --short
```

Run Ruff from the repository root. Expected: lint and whitespace checks pass, and status contains no uncommitted implementation files.

- [ ] **Step 6: Review the commit series**

```bash
git log --oneline 5a5a57a..HEAD
git diff --stat 5a5a57a..HEAD
```

Expected commits after the plan commit:

1. `feat: validate a-stock-data snapshots`
2. `feat: synchronize pinned a-stock-data snapshots`
3. `feat: vendor a-stock-data upstream baseline`
4. `ci: schedule a-stock-data update reviews`
