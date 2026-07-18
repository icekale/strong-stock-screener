from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "sync-a-stock-data.yml"


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
