# Task 2 Report: Remove Corrupted Future-Dated SZSE History

## Implementation Summary

- Added `_discard_future_szse_rows(history, disclosed_trade_date)` as a pure sanitizer.
- The sanitizer removes only rows where the symbol is in `ALL_ETFS`, ends with `.SZ`, and has a date later than the latest completed disclosure date.
- `CapitalSignalService.overview()` sanitizes immediately after loading history, persists only when history changes, and uses the sanitized list for all subsequent calculations.
- Added the focused regression test for corrupted `159915.SZ` history and preservation of the unrelated future `600000.SH` row.

## TDD Evidence

RED command (executed from `apps/api`):

```text
.venv/bin/pytest tests/test_capital_signals.py -k 'future_szse' -vv
```

RED output:

```text
collected 34 items / 33 deselected / 1 selected
tests/test_capital_signals.py::test_overview_discards_only_future_szse_rows_from_broken_date_parser FAILED
E       assert not True
1 failed, 33 deselected in 0.20s
```

GREEN command (executed from `apps/api`):

```text
.venv/bin/pytest tests/test_capital_signals.py -k 'future_szse' -vv
```

GREEN output:

```text
collected 34 items / 33 deselected / 1 selected
tests/test_capital_signals.py::test_overview_discards_only_future_szse_rows_from_broken_date_parser PASSED
1 passed, 33 deselected in 0.20s
```

## Verification

```text
.venv/bin/pytest tests/test_capital_signals.py tests/test_capital_signal_store.py -q
...........................................                              [100%]
43 passed in 0.48s

.venv/bin/ruff check app/services/capital_signals.py tests/test_capital_signals.py
All checks passed!
```

## Files Changed

- `apps/api/app/services/capital_signals.py`
- `apps/api/tests/test_capital_signals.py`
- `.superpowers/sdd/task-2-report.md`

## Self-Review Findings

- No issues found.
- The hook is before `stored_current_rows`, `_latest_share_before`, and final history merging, so corrupted rows cannot affect overview calculations.
- SSE rows, valid/non-future SZSE rows, and symbols outside `ALL_ETFS` are not removed by the predicate.
- `git diff --check` passed and no unrelated worktree files are modified.

## Concerns

None identified within the requested scope.
