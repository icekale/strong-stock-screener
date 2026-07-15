# CZSC Scoreable Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict rc8 scoring and cached validation to candidates with sufficient frozen minute history.

**Architecture:** Add pure manifest-coverage helpers beside the score cache, then use their selected keys in both CLI paths. Keep the frozen dataset and historical cache immutable; only the effective candidate universe changes.

**Tech Stack:** Python 3.12, dataclasses, pytest, Parquet manifest JSON, existing rc8 worker CLI.

---

### Task 1: Derive scoreable candidate keys

**Files:**
- Modify: `apps/api/app/services/chanlun/research_score_cache.py`
- Test: `apps/api/tests/test_chanlun_research_score_cache.py`

- [ ] Add a failing test proving warm-up is calculated per symbol and symbols without minute partitions are excluded.
- [ ] Run `uv run pytest -q tests/test_chanlun_research_score_cache.py` and confirm the new test fails for the missing helper.
- [ ] Implement a pure helper that returns keys and the effective date range from manifest samples and minute partitions.
- [ ] Re-run the score-cache tests and confirm they pass.

### Task 2: Filter the scoring queue

**Files:**
- Modify: `scripts/czsc-research.py`
- Test: `apps/api/tests/test_chanlun_research_report.py`

- [ ] Add a failing CLI unit test showing unscoreable keys never enter a score batch.
- [ ] Update `_score` to select from scoreable keys and print dataset, scoreable, attempted, and scored counts.
- [ ] Run the focused CLI and score-cache tests.

### Task 3: Filter cached validation and report coverage

**Files:**
- Modify: `scripts/czsc-research.py`
- Test: `apps/api/tests/test_chanlun_research_report.py`

- [ ] Add a failing test for candidate filtering and scoreable-window metrics.
- [ ] Filter cached validation candidates before portfolio and fold calculations.
- [ ] Report the scoreable date range and calculate coverage against scoreable candidates.
- [ ] Run all CZSC research tests.

### Task 4: Execute and verify

**Files:**
- Generated: `artifacts/czsc-research/scores/rc8-v2.json`
- Generated: `artifacts/czsc-research/reports-rc8-partial/`

- [ ] Run one resumed 300-sample rc8 batch.
- [ ] Regenerate the partial cached-score report and verify its checksums.
- [ ] Run backend tests, Ruff, and `git diff --check`; record any unrelated flaky test separately.
