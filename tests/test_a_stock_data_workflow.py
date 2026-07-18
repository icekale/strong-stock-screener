from __future__ import annotations

import json
import os
import re
import subprocess
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

if [[ "$1" == "pr" && "$2" == "list" ]]; then
  case "${GH_LIST_RESULT}" in
    failure) exit 42 ;;
    empty) exit 0 ;;
    one) printf '17\\n'; exit 0 ;;
    many) printf '17\\n18\\n'; exit 0 ;;
  esac
fi

if [[ "$1" == "pr" && ( "$2" == "create" || "$2" == "edit" ) ]]; then
  exit 0
fi
exit 64
"""


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


def pr_shell_block() -> str:
    sync_block = next(
        block
        for block in workflow_run_blocks()
        if "gh pr list --state open" in block
    )
    markers = ('if ! PR_NUMBERS="$(gh pr list', "mapfile -t pr_numbers < <(")
    start = next(
        (sync_block.find(marker) for marker in markers if marker in sync_block),
        -1,
    )
    if start < 0:
        raise AssertionError("missing PR lookup shell block")
    return sync_block[start:]


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

        checkout = step_containing(self.source, "uses: actions/checkout@v4")
        self.assertRegex(checkout, r"(?m)^\s+ref:\s*main\s*$")
        self.assertRegex(checkout, r"(?m)^\s+fetch-depth:\s*0\s*$")

        setup_python = step_containing(self.source, "uses: actions/setup-python@v5")
        self.assertRegex(
            setup_python,
            r"(?m)^\s+python-version:\s*['\"]3\.12['\"]\s*$",
        )
        self.assertEqual(
            re.findall(r"(?m)^\s*uses:\s*(\S+)\s*$", self.source),
            ["actions/checkout@v4", "actions/setup-python@v5"],
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
        self.assertRegex(guarded_commands, r"(?m)^\s+gh pr (?:list|create|edit)\s")

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
        self.assertIn('git switch -C "${branch}" main', sync_step)
        self.assertIn(
            '--force-with-lease="refs/heads/${branch}:${remote_sha}"',
            sync_step,
        )
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
        self.assertRegex(
            sync_step,
            r'git commit -m "[^"]*\$\{upstream_version\}'
            r"[^\"]*\$\{upstream_short_sha\}[^\"]*\"",
        )

    def test_pr_is_created_or_updated_without_merging(self) -> None:
        sync_step = step_containing(
            self.source,
            "python scripts/sync_a_stock_data.py",
        )
        self.assertIn(
            'gh pr list --state open --head "${branch}" --base main',
            sync_step,
        )
        self.assertIn(
            'if ! PR_NUMBERS="$(gh pr list --state open --head "${branch}" '
            "--base main --limit 2 --json number --jq '.[].number')\"; then",
            sync_step,
        )
        self.assertNotRegex(sync_step, r"mapfile[^\n]*<\s*<\(")
        self.assertIn("pr_numbers=()", sync_step)
        self.assertIn('if [[ -n "${PR_NUMBERS}" ]]; then', sync_step)
        self.assertIn("--limit 2", sync_step)
        self.assertRegex(sync_step, r"\$\{#pr_numbers\[@\]\}\s*>\s*1")
        self.assertRegex(sync_step, r"(?m)^\s+gh pr create\s")
        self.assertRegex(sync_step, r"(?m)^\s+gh pr edit \"\$\{pr_numbers\[0\]\}\"\s")
        self.assertIn("--base main", sync_step)
        self.assertIn('--head "${branch}"', sync_step)
        self.assertIn('--title "chore: review a-stock-data ${upstream_version}"', sync_step)
        self.assertIn(
            '--body-file "${RUNNER_TEMP}/a-stock-data-sync-summary.md"',
            sync_step,
        )
        self.assertNotRegex(
            self.source.lower(),
            r"gh pr merge|auto-merge|--auto(?:\s|$)",
        )

    def test_pr_lookup_failure_and_result_cardinality_are_enforced(self) -> None:
        shell_block = pr_shell_block()
        cases = {
            "failure": (1, None, "Failed to list open synchronization PRs."),
            "empty": (0, "pr create", None),
            "one": (0, "pr edit 17", None),
            "many": (1, None, "More than one open synchronization PR exists."),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            bin_path = temp_path / "bin"
            bin_path.mkdir()
            fake_gh = bin_path / "gh"
            fake_gh.write_text(FAKE_GH, encoding="utf-8")
            fake_gh.chmod(0o755)

            for mode, (returncode, action, error_message) in cases.items():
                with self.subTest(mode=mode):
                    log_path = temp_path / f"{mode}.log"
                    environment = os.environ.copy()
                    environment.update(
                        {
                            "GH_LIST_RESULT": mode,
                            "GH_LOG": str(log_path),
                            "PATH": f"{bin_path}:{environment.get('PATH', '')}",
                            "RUNNER_TEMP": str(temp_path),
                        }
                    )
                    script = (
                        "set -euo pipefail\n"
                        'branch="automation/a-stock-data-sync"\n'
                        'upstream_version="3.5.0"\n'
                        f"{shell_block}"
                    )
                    result = subprocess.run(
                        ["bash", "-c", script],
                        check=False,
                        capture_output=True,
                        env=environment,
                        text=True,
                    )
                    commands = log_path.read_text(encoding="utf-8").splitlines()

                    self.assertEqual(result.returncode, returncode, result.stderr)
                    self.assertTrue(commands[0].startswith("pr list "), commands)
                    if action is None:
                        self.assertEqual(len(commands), 1, commands)
                    else:
                        self.assertEqual(len(commands), 2, commands)
                        self.assertTrue(commands[1].startswith(action), commands)
                    if error_message is not None:
                        self.assertIn(error_message, result.stderr)

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
