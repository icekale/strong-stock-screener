from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "sync-a-stock-data.yml"
RUBY_EXTRACT_RUN_BLOCKS = r"""
workflow = YAML.load_file(ARGV.fetch(0))
run_blocks = workflow.fetch("jobs").values.flat_map do |job|
  job.fetch("steps", []).map { |step| step["run"] }.compact
end
STDOUT.write(JSON.generate(run_blocks))
"""
FAKE_GH = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "${GH_LOG}"

if [[ "$1" == "api" ]]; then
  if [[ "${GH_API_FAILURE:-false}" == true ]]; then
    exit 42
  fi
  if [[ "$*" == *"head=${EXPECTED_HEAD}"* ]]; then
    printf '%s\\n' "${GH_API_JSON}"
  else
    printf '%s\\n' "${GH_UNQUALIFIED_JSON}"
  fi
  exit 0
fi

if [[ "$1" == "pr" && "$2" == "list" ]]; then
  printf '%s\\n' "${GH_UNQUALIFIED_JSON}"
  exit 0
fi

if [[ "$1" == "pr" && ( "$2" == "create" || "$2" == "edit" ) ]]; then
  if [[ "$2" == "edit" && "${GH_EDIT_FAILURE:-false}" == true ]]; then
    exit 43
  fi
  exit 0
fi
exit 64
"""
BRANCH = "automation/a-stock-data-sync"
REPOSITORY_OWNER = "acme"


def top_level_block(source: str, key: str) -> str:
    lines = source.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.rstrip() == f"{key}:" and not line.startswith((" ", "\t"))
        ),
        None,
    )
    if start is None:
        raise AssertionError(f"missing top-level {key!r} block")

    block = []
    for line in lines[start + 1 :]:
        if line and not line.startswith((" ", "\t", "#")):
            break
        block.append(line)
    return "\n".join(block)


def step_containing(source: str, marker: str) -> str:
    steps = re.split(r"(?m)^      - ", source)
    try:
        return next(step for step in steps if marker in step)
    except StopIteration as error:
        raise AssertionError(f"missing workflow step containing {marker!r}") from error


def workflow_run_blocks() -> list[str]:
    try:
        result = subprocess.run(
            [
                "ruby",
                "-ryaml",
                "-rjson",
                "-e",
                RUBY_EXTRACT_RUN_BLOCKS,
                str(WORKFLOW_PATH),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise AssertionError("ruby is required to parse the workflow YAML") from error
    if result.returncode != 0:
        raise AssertionError(f"workflow YAML parsing failed:\n{result.stderr}")

    run_blocks = json.loads(result.stdout)
    if not isinstance(run_blocks, list) or not all(
        isinstance(block, str) for block in run_blocks
    ):
        raise AssertionError("workflow run blocks did not decode as strings")
    return run_blocks


def publish_pr_shell_block() -> str:
    sync_block = next(
        block
        for block in workflow_run_blocks()
        if 'branch="automation/a-stock-data-sync"' in block
    )
    start = sync_block.find('branch="automation/a-stock-data-sync"')
    if start < 0:
        raise AssertionError("missing publish/PR shell block")
    return sync_block[start:]


def proposal_snapshot(
    *,
    synced_at: str,
    commit: str = "2" * 40,
    version: str = "3.5.0",
) -> dict[str, bytes]:
    artifacts = {
        "SKILL.md": (
            "---\n"
            "name: a-stock-data\n"
            f"version: {version}\n"
            "---\n"
            f"# A\u80a1\u5168\u6808\u6570\u636e\u5de5\u5177\u5305 V{version}\n"
            "## Market\n"
            "Provider details.\n"
        ).encode(),
        "CHANGELOG.md": (
            f"# Changelog\n\n## {version}\n\n- Workflow test snapshot.\n"
        ).encode(),
        "LICENSE": (ROOT / "third_party" / "a-stock-data" / "LICENSE").read_bytes(),
    }
    metadata = {
        "schema_version": 1,
        "upstream": {
            "owner": "simonlin1212",
            "repository": "a-stock-data",
            "branch": "main",
            "commit": commit,
            "committed_at": "2026-07-11T08:00:00Z",
            "synced_at": synced_at,
            "version": version,
            "commit_url": (
                "https://github.com/simonlin1212/a-stock-data/commit/" + commit
            ),
        },
        "artifacts": {
            name: {
                "raw_url": (
                    "https://raw.githubusercontent.com/"
                    f"simonlin1212/a-stock-data/{commit}/{name}"
                ),
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(artifacts.items())
        },
    }
    return {
        **artifacts,
        "metadata.json": (
            json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        ).encode(),
    }


def pull_request(
    number: int,
    *,
    version: str = "3.5.0",
    title: str | None = None,
    body: str | None = "sync summary\n",
    base: str = "main",
    branch: str = BRANCH,
    owner: str = REPOSITORY_OWNER,
) -> dict[str, object]:
    return {
        "number": number,
        "title": title or f"chore: review a-stock-data {version}",
        "body": body,
        "base": {"ref": base},
        "head": {
            "ref": branch,
            "repo": {"owner": {"login": owner}},
        },
    }


class WorkflowShellHarness:
    def __init__(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)
        self.repository = self.root / "repository"
        self.origin = self.root / "origin.git"
        self.bin_path = self.root / "bin"
        self.gh_log = self.root / "gh.log"

        self._run(["git", "init", "--bare", str(self.origin)], cwd=self.root)
        self.repository.mkdir()
        self._run(["git", "init", "-b", "main"], cwd=self.repository)
        self.git("config", "user.name", "Workflow Test")
        self.git("config", "user.email", "workflow-test@example.invalid")
        self.git("remote", "add", "origin", str(self.origin))

        self.snapshot_directory = (
            self.repository / "third_party" / "a-stock-data"
        )
        self.write_snapshot(
            proposal_snapshot(
                commit="1" * 40,
                version="3.4.0",
                synced_at="2026-07-17T00:00:00Z",
            )
        )
        scripts_directory = self.repository / "scripts"
        scripts_directory.mkdir()
        shutil.copy2(
            ROOT / "scripts" / "sync_a_stock_data.py",
            scripts_directory / "sync_a_stock_data.py",
        )
        self.git("add", "third_party/a-stock-data", "scripts/sync_a_stock_data.py")
        self.git("commit", "-m", "baseline")
        self.git("push", "-u", "origin", "main")

        self.bin_path.mkdir()
        (self.bin_path / "python").symlink_to(sys.executable)
        fake_gh = self.bin_path / "gh"
        fake_gh.write_text(FAKE_GH, encoding="utf-8")
        fake_gh.chmod(0o755)
        (self.root / "a-stock-data-sync-summary.md").write_text(
            "sync summary\n",
            encoding="utf-8",
        )

    def __enter__(self) -> WorkflowShellHarness:
        return self

    def __exit__(self, *args: object) -> None:
        self._temporary_directory.cleanup()

    def _run(
        self,
        command: list[str],
        *,
        cwd: Path,
        check: bool = True,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            env=environment,
            text=True,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"command failed: {' '.join(command)}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def git(
        self,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            ["git", *arguments],
            cwd=self.repository,
            check=check,
        )

    def write_snapshot(self, snapshot: dict[str, bytes]) -> None:
        if self.snapshot_directory.exists():
            shutil.rmtree(self.snapshot_directory)
        self.snapshot_directory.mkdir(parents=True)
        for name, content in snapshot.items():
            (self.snapshot_directory / name).write_bytes(content)

    def push_remote_proposal(
        self,
        snapshot: dict[str, bytes],
        *,
        extra_files: dict[str, bytes] | None = None,
        executable_snapshot_file: str | None = None,
    ) -> str:
        self.git("switch", "-C", BRANCH, "main")
        self.write_snapshot(snapshot)
        if executable_snapshot_file is not None:
            (self.snapshot_directory / executable_snapshot_file).chmod(0o755)
        for relative_path, content in (extra_files or {}).items():
            path = self.repository / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.git("add", "--all")
        self.git("commit", "-m", "remote proposal")
        self.git("push", "origin", f"HEAD:refs/heads/{BRANCH}")
        remote_sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("switch", "main")
        self.git("branch", "-D", BRANCH)
        return remote_sha

    def remote_branch_sha(self) -> str:
        result = self.git("ls-remote", "origin", f"refs/heads/{BRANCH}")
        return result.stdout.split()[0]

    def remote_path_exists(self, relative_path: str) -> bool:
        result = self._run(
            [
                "git",
                f"--git-dir={self.origin}",
                "cat-file",
                "-e",
                f"refs/heads/{BRANCH}:{relative_path}",
            ],
            cwd=self.root,
            check=False,
        )
        return result.returncode == 0

    def remote_file(self, relative_path: str) -> str:
        return self._run(
            [
                "git",
                f"--git-dir={self.origin}",
                "show",
                f"refs/heads/{BRANCH}:{relative_path}",
            ],
            cwd=self.root,
        ).stdout

    def remote_file_mode(self, relative_path: str) -> str:
        result = self._run(
            [
                "git",
                f"--git-dir={self.origin}",
                "ls-tree",
                f"refs/heads/{BRANCH}",
                "--",
                relative_path,
            ],
            cwd=self.root,
        )
        return result.stdout.split()[0]

    def run_publish_pr_shell(
        self,
        pull_requests: list[dict[str, object]],
        *,
        list_failure: bool = False,
        edit_failure: bool = False,
        unqualified_pull_requests: list[dict[str, object]] | None = None,
        extra_environment: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        self.gh_log.unlink(missing_ok=True)
        environment = os.environ.copy()
        environment.update(
            {
                "GITHUB_REPOSITORY": f"{REPOSITORY_OWNER}/strong-stock-screener",
                "GITHUB_REPOSITORY_OWNER": REPOSITORY_OWNER,
                "GH_API_FAILURE": "true" if list_failure else "false",
                "GH_EDIT_FAILURE": "true" if edit_failure else "false",
                "GH_API_JSON": json.dumps(pull_requests),
                "GH_UNQUALIFIED_JSON": json.dumps(
                    unqualified_pull_requests
                    if unqualified_pull_requests is not None
                    else pull_requests
                ),
                "GH_LOG": str(self.gh_log),
                "EXPECTED_HEAD": f"{REPOSITORY_OWNER}:{BRANCH}",
                "PATH": f"{self.bin_path}:{environment.get('PATH', '')}",
                "RUNNER_TEMP": str(self.root),
            }
        )
        if extra_environment:
            environment.update(extra_environment)
        script = "set -euo pipefail\n" + publish_pr_shell_block()
        result = self._run(
            ["bash", "-c", script],
            cwd=self.repository,
            check=False,
            environment=environment,
        )
        commands = (
            self.gh_log.read_text(encoding="utf-8").splitlines()
            if self.gh_log.exists()
            else []
        )
        return result, commands


class AStockDataWorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            f"workflow does not exist: {WORKFLOW_PATH}",
        )
        self.source = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_triggers_are_only_the_daily_schedule_and_manual_dispatch(self) -> None:
        trigger_block = top_level_block(self.source, "on")
        trigger_keys = re.findall(r"(?m)^  ([a-z_]+):", trigger_block)

        self.assertEqual(set(trigger_keys), {"schedule", "workflow_dispatch"})
        self.assertEqual(
            re.findall(r"(?m)^\s*- cron:\s*['\"]([^'\"]+)['\"]", trigger_block),
            ["30 22 * * *"],
        )
        self.assertNotRegex(trigger_block, r"(?m)^\s+(?:push|pull_request):")

    def test_permissions_and_concurrency_are_minimal(self) -> None:
        permissions = top_level_block(self.source, "permissions")
        permission_pairs = dict(
            re.findall(r"(?m)^  ([a-z-]+):\s*([a-z]+)\s*$", permissions)
        )
        self.assertEqual(
            permission_pairs,
            {"contents": "write", "pull-requests": "write"},
        )

        concurrency = top_level_block(self.source, "concurrency")
        self.assertRegex(concurrency, r"(?m)^  group:\s*sync-a-stock-data\s*$")
        self.assertRegex(concurrency, r"(?m)^  cancel-in-progress:\s*false\s*$")

    def test_has_one_ubuntu_job_with_pinned_official_setup_actions(self) -> None:
        jobs = top_level_block(self.source, "jobs")
        self.assertEqual(re.findall(r"(?m)^  ([a-zA-Z0-9_-]+):\s*$", jobs), ["sync"])
        self.assertRegex(jobs, r"(?m)^    runs-on:\s*ubuntu-latest\s*$")

        checkout_pin = (
            "uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4"
        )
        checkout = step_containing(self.source, checkout_pin)
        self.assertRegex(checkout, r"(?m)^\s+ref:\s*main\s*$")
        self.assertRegex(checkout, r"(?m)^\s+fetch-depth:\s*0\s*$")

        setup_python_pin = (
            "uses: actions/setup-python@"
            "a26af69be951a213d495a4c3e4e4022e16d87065 # v5"
        )
        setup_python = step_containing(self.source, setup_python_pin)
        self.assertRegex(
            setup_python,
            r"(?m)^\s+python-version:\s*['\"]3\.12['\"]\s*$",
        )
        self.assertEqual(
            re.findall(r"(?m)^\s*(uses:\s*\S+\s+#\s+v\d+)\s*$", self.source),
            [checkout_pin, setup_python_pin],
        )

    def test_runs_dependency_free_tests_and_sync_with_expected_tokens(self) -> None:
        lines = {line.strip() for line in self.source.splitlines()}
        unittest_command = (
            "python -m unittest discover -s tests "
            "-p 'test_*a_stock_data*.py' -v"
        )
        sync_command = (
            'python scripts/sync_a_stock_data.py '
            '--destination "third_party/a-stock-data" '
            '--summary-path "${RUNNER_TEMP}/a-stock-data-sync-summary.md"'
        )
        self.assertIn(unittest_command, lines)
        self.assertIn(sync_command, lines)

        sync_step = step_containing(self.source, sync_command)
        token_expression = "${{ secrets.GITHUB_TOKEN }}"
        self.assertIn(f"GITHUB_TOKEN: {token_expression}", sync_step)
        self.assertIn(f"GH_TOKEN: {token_expression}", sync_step)
        self.assertIn(
            'cat "${RUNNER_TEMP}/a-stock-data-sync-summary.md" '
            '>> "${GITHUB_STEP_SUMMARY}"',
            lines,
        )

    def test_every_shell_step_enables_strict_mode(self) -> None:
        lines = self.source.splitlines()
        run_lines = [
            index
            for index, line in enumerate(lines)
            if re.fullmatch(r"\s+run:\s*\|\s*", line)
        ]
        self.assertGreaterEqual(len(run_lines), 2)
        self.assertNotRegex(self.source, r"(?m)^\s+run:\s*(?!\|\s*$)\S")
        for index in run_lines:
            first_command = next(
                line.strip() for line in lines[index + 1 :] if line.strip()
            )
            self.assertEqual(first_command, "set -euo pipefail")

    def test_workflow_yaml_and_every_run_block_have_valid_syntax(self) -> None:
        run_blocks = workflow_run_blocks()
        self.assertGreaterEqual(len(run_blocks), 2)
        for index, block in enumerate(run_blocks):
            with self.subTest(run_block=index):
                try:
                    result = subprocess.run(
                        ["bash", "-n"],
                        input=block,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                except OSError as error:
                    self.fail(f"bash is required to parse workflow run blocks: {error}")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_unchanged_snapshot_exits_before_branch_git_or_gh_commands(self) -> None:
        sync_step = step_containing(
            self.source,
            "python scripts/sync_a_stock_data.py",
        )
        gate = 'if git diff --quiet -- "third_party/a-stock-data"; then'
        gate_index = sync_step.index(gate)
        gate_end = sync_step.index("fi", gate_index)
        before_gate = sync_step[:gate_index]
        unchanged_block = sync_step[gate_index:gate_end]

        self.assertNotRegex(before_gate, r"(?m)^\s+(?:git|gh)\s")
        self.assertRegex(unchanged_block, r"(?m)^\s+exit 0\s*$")
        self.assertNotRegex(unchanged_block, r"(?m)^\s+(?:git|gh)\s")

        guarded_commands = sync_step[gate_end + len("fi") :]
        self.assertRegex(guarded_commands, r"(?m)^\s+git config\s")
        self.assertRegex(guarded_commands, r"(?m)^\s+gh (?:api|pr (?:create|edit))\s")

    def test_stable_branch_is_reset_from_main_and_pushed_safely(self) -> None:
        sync_step = step_containing(
            self.source,
            "python scripts/sync_a_stock_data.py",
        )
        self.assertIn('branch="automation/a-stock-data-sync"', sync_step)
        self.assertIn(
            'git config user.name "github-actions[bot]"',
            sync_step,
        )
        self.assertIn(
            'git config user.email "41898282+github-actions[bot]@users.noreply.github.com"',
            sync_step,
        )
        self.assertIn(
            'git ls-remote --exit-code --heads origin "refs/heads/${branch}"',
            sync_step,
        )
        self.assertIn(
            'git fetch --no-tags origin "refs/heads/${branch}:'
            'refs/remotes/origin/${branch}"',
            sync_step,
        )
        self.assertIn('git merge-base main "${remote_ref}"', sync_step)
        self.assertIn(
            'git diff --quiet "${merge_base}" "${remote_ref}" -- . '
            '":(exclude)third_party/a-stock-data"',
            sync_step,
        )
        self.assertIn('git archive "${remote_ref}" -- "third_party/a-stock-data"', sync_step)
        self.assertIn(
            'expected_remote_modes=$\'100644\\n100644\\n100644\\n100644\'',
            sync_step,
        )
        self.assertIn(
            'git ls-tree -r "${remote_ref}" -- "third_party/a-stock-data"',
            sync_step,
        )
        self.assertIn("awk '{print $1}'", sync_step)
        self.assertIn(
            'python scripts/sync_a_stock_data.py --check --destination '
            '"${remote_snapshot_root}/third_party/a-stock-data"',
            sync_step,
        )
        self.assertIn('metadata["upstream"].pop("synced_at")', sync_step)
        self.assertIn("path.read_bytes()", sync_step)
        self.assertLess(
            sync_step.index("git fetch --no-tags origin"),
            sync_step.index('git merge-base main "${remote_ref}"'),
        )
        self.assertLess(
            sync_step.index('python scripts/sync_a_stock_data.py --check'),
            sync_step.index('git switch -C "${branch}" main'),
        )
        self.assertIn('git switch -C "${branch}" main', sync_step)
        self.assertIn(
            '--force-with-lease="refs/heads/${branch}:${remote_sha}"',
            sync_step,
        )
        reuse_push = (
            'git push --force-with-lease="refs/heads/${branch}:${remote_sha}" '
            'origin "${remote_sha}:refs/heads/${branch}"'
        )
        self.assertIn(reuse_push, sync_step)
        self.assertLess(sync_step.index(reuse_push), sync_step.index("desired_title="))
        self.assertIn('git push origin "HEAD:refs/heads/${branch}"', sync_step)
        for line in sync_step.splitlines():
            if "git push" in line:
                self.assertNotRegex(line, r"(?:^|\s)--force(?:\s|$)")

    def test_commit_stages_only_vendor_snapshot_and_uses_metadata(self) -> None:
        sync_step = step_containing(
            self.source,
            "python scripts/sync_a_stock_data.py",
        )
        git_add_lines = re.findall(r"(?m)^\s*(git add\b.*)$", sync_step)
        self.assertEqual(
            git_add_lines,
            ['git add -- "third_party/a-stock-data"'],
        )
        self.assertIn('Path("third_party/a-stock-data/metadata.json")', sync_step)
        self.assertIn('upstream["version"]', sync_step)
        self.assertIn('upstream["commit"][:7]', sync_step)
        commit_command = re.search(
            r"git commit(?P<arguments>.*?)(?=\n\s*(?:if|git push))",
            sync_step,
            re.DOTALL,
        )
        self.assertIsNotNone(commit_command)
        commit_arguments = commit_command.group("arguments")
        self.assertIn("--only", commit_arguments)
        self.assertIn('"third_party/a-stock-data"', commit_arguments)
        self.assertRegex(
            commit_arguments,
            r'-m "[^"]*\$\{upstream_version\}'
            r"[^\"]*\$\{upstream_short_sha\}[^\"]*\"",
        )

    def test_pr_is_created_or_updated_without_merging(self) -> None:
        sync_step = step_containing(
            self.source,
            "python scripts/sync_a_stock_data.py",
        )
        self.assertIn('gh api --method GET "repos/${GITHUB_REPOSITORY}/pulls"', sync_step)
        self.assertIn(
            '-f "head=${GITHUB_REPOSITORY_OWNER}:${branch}"',
            sync_step,
        )
        self.assertNotIn('-f "base=main"', sync_step)
        self.assertIn('-f "state=open"', sync_step)
        self.assertNotIn("--limit", sync_step)
        self.assertNotIn("gh pr list", sync_step)
        self.assertIn('pr["title"] == desired_title', sync_step)
        self.assertIn('pr["body"] == desired_body', sync_step)
        self.assertIn('pr["base"]["ref"] == "main"', sync_step)
        self.assertIn('len(pull_requests) > 1', sync_step)
        self.assertRegex(sync_step, r"(?m)^\s+gh pr create\s")
        self.assertRegex(sync_step, r"(?m)^\s+gh pr edit \"\$\{pr_number\}\"\s")
        self.assertNotRegex(sync_step, r"proposal_changed[^\n]*gh pr edit")
        self.assertIn("--base main", sync_step)
        self.assertIn('--head "${branch}"', sync_step)
        self.assertIn(
            'desired_title="chore: review a-stock-data ${upstream_version}"',
            sync_step,
        )
        self.assertIn('--title "${desired_title}"', sync_step)
        self.assertIn(
            '--body-file "${RUNNER_TEMP}/a-stock-data-sync-summary.md"',
            sync_step,
        )
        self.assertNotRegex(
            self.source.lower(),
            r"gh pr merge|auto-merge|--auto(?:\s|$)",
        )

    def test_matching_remote_proposal_and_internal_pr_are_not_republished(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(remote_snapshot)
            original_local_sha = harness.git("rev-parse", "HEAD").stdout.strip()
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([pull_request(17)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("verified a-stock-data 3.5.0", result.stdout)
            self.assertEqual(
                harness.git("rev-parse", "HEAD").stdout.strip(),
                original_local_sha,
            )
            self.assertEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(len(commands), 1, commands)
            self.assertTrue(commands[0].startswith("api "), commands)

    def test_matching_remote_proposal_without_pr_only_creates_pr(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(remote_snapshot)
            original_local_sha = harness.git("rev-parse", "HEAD").stdout.strip()
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                harness.git("rev-parse", "HEAD").stdout.strip(),
                original_local_sha,
            )
            self.assertEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(len(commands), 2, commands)
            self.assertTrue(commands[0].startswith("api "), commands)
            self.assertTrue(commands[1].startswith("pr create "), commands)

    def test_existing_internal_pr_with_wrong_base_is_repaired_not_duplicated(
        self,
    ) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )
        wrong_base_pr = pull_request(17, base="release")

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(remote_snapshot)
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([wrong_base_pr])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(len(commands), 2, commands)
            self.assertNotIn("base=main", commands[0])
            self.assertTrue(commands[1].startswith("pr edit 17 "), commands)

    def test_commit_only_excludes_an_unrelated_staged_file(self) -> None:
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            harness.write_snapshot(generated_snapshot)
            unrelated_path = harness.repository / "unrelated-staged.txt"
            unrelated_path.write_text("must not be committed\n", encoding="utf-8")
            harness.git("add", "unrelated-staged.txt")

            result, commands = harness.run_publish_pr_shell([])

            self.assertEqual(result.returncode, 0, result.stderr)
            committed_unrelated = harness.git(
                "cat-file",
                "-e",
                f"refs/remotes/origin/{BRANCH}:unrelated-staged.txt",
                check=False,
            )
            self.assertNotEqual(committed_unrelated.returncode, 0)
            self.assertEqual(len(commands), 2, commands)
            self.assertTrue(commands[1].startswith("pr create "), commands)

    def test_force_with_lease_rejection_does_not_overwrite_remote_branch(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            commit="3" * 40,
            version="3.6.0",
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            expected_remote_sha = harness.push_remote_proposal(remote_snapshot)
            harness.git("switch", "-c", "concurrent-update", "main")
            concurrent_path = harness.repository / "concurrent-update.txt"
            concurrent_path.write_text("new remote state\n", encoding="utf-8")
            harness.git("add", "concurrent-update.txt")
            harness.git("commit", "-m", "concurrent update")
            concurrent_sha = harness.git("rev-parse", "HEAD").stdout.strip()
            harness.git(
                "push",
                "origin",
                "HEAD:refs/heads/concurrent-update",
            )
            harness.git("switch", "main")
            harness.git("branch", "-D", "concurrent-update")
            harness.write_snapshot(generated_snapshot)

            hook = harness.repository / ".git" / "hooks" / "pre-push"
            hook.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'git --git-dir="${ORIGIN_PATH}" update-ref '
                f'"refs/heads/{BRANCH}" "${{CONCURRENT_SHA}}" '
                '"${EXPECTED_REMOTE_SHA}"\n',
                encoding="utf-8",
            )
            hook.chmod(0o755)

            result, commands = harness.run_publish_pr_shell(
                [],
                extra_environment={
                    "CONCURRENT_SHA": concurrent_sha,
                    "EXPECTED_REMOTE_SHA": expected_remote_sha,
                    "ORIGIN_PATH": str(harness.origin),
                },
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(harness.remote_branch_sha(), concurrent_sha)
            self.assertEqual(commands, [])

    def test_reusable_proposal_lease_failure_stops_before_pr_reconciliation(
        self,
    ) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            expected_remote_sha = harness.push_remote_proposal(remote_snapshot)
            harness.git("switch", "-c", "concurrent-update", "main")
            concurrent_path = harness.repository / "concurrent-update.txt"
            concurrent_path.write_text("new remote state\n", encoding="utf-8")
            harness.git("add", "concurrent-update.txt")
            harness.git("commit", "-m", "concurrent update")
            concurrent_sha = harness.git("rev-parse", "HEAD").stdout.strip()
            harness.git("push", "origin", "HEAD:refs/heads/concurrent-update")
            harness.git("switch", "main")
            harness.git("branch", "-D", "concurrent-update")
            harness.write_snapshot(generated_snapshot)

            real_git = shutil.which("git")
            self.assertIsNotNone(real_git)
            fake_git = harness.bin_path / "git"
            fake_git.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'if [[ "${GIT_INJECT_NOOP_LEASE_RACE:-false}" == true '
                '&& "${1:-}" == push '
                '&& "$*" == *"${EXPECTED_REMOTE_SHA}:refs/heads/'
                f'{BRANCH}"* ]]; then\n'
                '  "${REAL_GIT}" --git-dir="${ORIGIN_PATH}" update-ref '
                f'"refs/heads/{BRANCH}" "${{CONCURRENT_SHA}}" '
                '"${EXPECTED_REMOTE_SHA}"\n'
                "fi\n"
                'exec "${REAL_GIT}" "$@"\n',
                encoding="utf-8",
            )
            fake_git.chmod(0o755)

            result, commands = harness.run_publish_pr_shell(
                [],
                extra_environment={
                    "CONCURRENT_SHA": concurrent_sha,
                    "EXPECTED_REMOTE_SHA": expected_remote_sha,
                    "GIT_INJECT_NOOP_LEASE_RACE": "true",
                    "ORIGIN_PATH": str(harness.origin),
                    "REAL_GIT": real_git,
                },
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(harness.remote_branch_sha(), concurrent_sha)
            self.assertEqual(commands, [])

    def test_remote_proposal_with_executable_snapshot_file_is_replaced(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(
                remote_snapshot,
                executable_snapshot_file="SKILL.md",
            )
            self.assertEqual(
                harness.remote_file_mode("third_party/a-stock-data/SKILL.md"),
                "100755",
            )
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([pull_request(17)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(
                harness.remote_file_mode("third_party/a-stock-data/SKILL.md"),
                "100644",
            )
            self.assertEqual(len(commands), 1, commands)

    def test_remote_branch_with_unrelated_change_is_replaced(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(
                remote_snapshot,
                extra_files={"apps/runtime.py": b"unsafe = True\n"},
            )
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([pull_request(17)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertFalse(harness.remote_path_exists("apps/runtime.py"))
            self.assertEqual(len(commands), 1, commands)

    def test_remote_branch_with_tampered_vendor_bytes_is_replaced(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        tampered_snapshot = dict(remote_snapshot)
        tampered_snapshot["SKILL.md"] += b"tampered without metadata update\n"
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(tampered_snapshot)
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([pull_request(17)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(
                harness.remote_file("third_party/a-stock-data/SKILL.md"),
                generated_snapshot["SKILL.md"].decode(),
            )
            self.assertEqual(len(commands), 1, commands)

    def test_remote_branch_with_extra_vendor_file_is_replaced(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(
                remote_snapshot,
                extra_files={"third_party/a-stock-data/EXTRA.md": b"extra\n"},
            )
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([pull_request(17)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertFalse(
                harness.remote_path_exists("third_party/a-stock-data/EXTRA.md")
            )
            self.assertEqual(len(commands), 1, commands)

    def test_owner_qualified_api_does_not_return_same_branch_from_fork(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )
        fork_pr = pull_request(91, owner="fork-owner")

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(remote_snapshot)
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell(
                [],
                unqualified_pull_requests=[fork_pr],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(len(commands), 2, commands)
            self.assertIn(f"head={REPOSITORY_OWNER}:{BRANCH}", commands[0])
            self.assertTrue(commands[1].startswith("pr create "), commands)

    def test_one_internal_pr_is_edited_when_proposal_changes(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            commit="3" * 40,
            version="3.6.0",
            synced_at="2026-07-19T00:00:00Z",
        )
        candidates = [pull_request(17)]

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(remote_snapshot)
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell(candidates)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(len(commands), 2, commands)
            self.assertTrue(commands[1].startswith("pr edit 17 "), commands)

    def test_stale_pr_is_repaired_after_prior_edit_failure(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            commit="3" * 40,
            version="3.6.0",
            synced_at="2026-07-19T00:00:00Z",
        )
        stale_pr = pull_request(17, version="3.6.0", body="stale summary\n")

        with WorkflowShellHarness() as harness:
            harness.push_remote_proposal(remote_snapshot)
            harness.write_snapshot(generated_snapshot)

            first_result, first_commands = harness.run_publish_pr_shell(
                [stale_pr],
                edit_failure=True,
            )

            self.assertNotEqual(first_result.returncode, 0)
            self.assertGreaterEqual(len(first_commands), 2, first_commands)
            self.assertTrue(first_commands[1].startswith("pr edit 17 "))
            harness.git("switch", "main")
            harness.write_snapshot(generated_snapshot)
            proposal_sha = harness.remote_branch_sha()

            second_result, second_commands = harness.run_publish_pr_shell([stale_pr])

            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertEqual(harness.remote_branch_sha(), proposal_sha)
            self.assertEqual(len(second_commands), 2, second_commands)
            self.assertTrue(second_commands[1].startswith("pr edit 17 "))

    def test_multiple_internal_prs_fail_without_pr_mutation(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )
        candidates = [
            pull_request(17),
            pull_request(18),
        ]

        with WorkflowShellHarness() as harness:
            original_remote_sha = harness.push_remote_proposal(remote_snapshot)
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell(candidates)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "More than one open synchronization PR exists.",
                result.stderr,
            )
            self.assertEqual(harness.remote_branch_sha(), original_remote_sha)
            self.assertEqual(len(commands), 1, commands)
            self.assertTrue(commands[0].startswith("api "), commands)

    def test_pr_lookup_failure_stops_without_pr_mutation(self) -> None:
        remote_snapshot = proposal_snapshot(
            synced_at="2026-07-18T00:00:00Z",
        )
        generated_snapshot = proposal_snapshot(
            synced_at="2026-07-19T00:00:00Z",
        )

        with WorkflowShellHarness() as harness:
            harness.push_remote_proposal(remote_snapshot)
            harness.write_snapshot(generated_snapshot)

            result, commands = harness.run_publish_pr_shell([], list_failure=True)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Failed to list open synchronization PRs.", result.stderr)
            self.assertEqual(len(commands), 1, commands)
            self.assertTrue(commands[0].startswith("api "), commands)

    def test_workflow_contains_no_execution_or_deployment_paths(self) -> None:
        lowered = self.source.lower()
        forbidden = (
            "docker",
            "unraid",
            "deploy",
            "curl ",
            "wget ",
            "ssh ",
            "scp ",
            "rsync ",
            "skill.md",
            "eval ",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, lowered)


if __name__ == "__main__":
    unittest.main()
