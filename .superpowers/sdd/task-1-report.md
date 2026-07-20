# Task 1 Report: Parse the Actual SZSE ETF Share Date

## Implementation Summary

- Replaced SZSE ETF fixture metadata with the real response shape: page date `2026-07-20` and scale-column share date `2026-07-17`.
- Added strict `_szse_share_date` extraction from `metadata.cols.dqgm` using one valid ISO date only.
- The parser compares the extracted share date with the requested trade date and does not fall back to `metadata.subname`.
- Added the collected actual share date to successful and partial SZSE provider status details.

## RED Evidence

Command:

    .venv/bin/pytest tests/test_capital_signal_providers.py -k 'szse_share_parser' -vv

Initial output: `zsh:1: no such file or directory: .venv/bin/pytest` because this worktree had no API virtual environment.

Command used with the available locked environment:

    uv run --offline pytest tests/test_capital_signal_providers.py -k 'szse_share_parser' -vv

Output: `1 failed, 4 passed, 20 deselected`. The mismatch test failed with `assert 0 == 1`, proving the old parser incorrectly rejected the real response shape while reading `metadata.subname`.

## GREEN Evidence

    .venv/bin/pytest tests/test_capital_signal_providers.py -k 'szse_share_parser' -vv
    5 passed, 20 deselected in 0.27s

    .venv/bin/pytest tests/test_capital_signal_providers.py -q
    25 passed in 0.32s

    .venv/bin/ruff check app/providers/capital_signals.py tests/test_capital_signal_providers.py
    All checks passed!

## Files Changed

- `apps/api/app/providers/capital_signals.py`
- `apps/api/tests/test_capital_signal_providers.py`
- `.superpowers/sdd/task-1-report.md`

## Self-Review Findings

No findings. The diff is limited to the requested provider, test, and report files. The parser preserves the distinction between page generation date and actual share date, rejects missing, ambiguous, and invalid scale-column dates, and reports actual dates for both successful and partial SZSE coverage.

## Concerns

No known functional concerns. The required `.venv` was created locally by `uv run --offline` because it was absent initially; it is ignored and is not part of the commit.
