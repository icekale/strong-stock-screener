# Task 2 Report: Versioned Store And Cache-Aware Service

## Status

Completed and committed on branch `codex/sentiment-percentile-model`.

## Files Changed

- `apps/api/app/services/market_sentiment_percentile_store.py` (created)
- `apps/api/app/services/market_sentiment_percentile_service.py` (created)
- `apps/api/tests/test_market_sentiment_percentile_service.py` (created)

## Commit

- `0f42ae9237d9b91a801669d796a5228d607a0f2b feat: persist sentiment percentile snapshots`

## TDD Evidence

### RED

Command:

```bash
cd apps/api && uv run pytest tests/test_market_sentiment_percentile_service.py -q
```

Observed failure:

```text
ModuleNotFoundError: No module named 'app.services.market_sentiment_percentile_store'
```

The test module failed during collection because the required store module did not exist.

### GREEN And Regression

Focused service tests:

```bash
cd apps/api && uv run pytest tests/test_market_sentiment_percentile_service.py -q
```

Exact result: `11 passed in 1.25s`.

Calculator and service regression suite:

```bash
cd apps/api && uv run pytest tests/test_market_sentiment_percentile.py tests/test_market_sentiment_percentile_service.py -q
```

Exact result: `36 passed in 1.65s`.

Ruff checks:

```bash
cd apps/api && uv run ruff check app/services/market_sentiment_percentile_store.py app/services/market_sentiment_percentile_service.py tests/test_market_sentiment_percentile_service.py
cd apps/api && uv run ruff format --check app/services/market_sentiment_percentile_store.py app/services/market_sentiment_percentile_service.py tests/test_market_sentiment_percentile_service.py
```

Exact results: `All checks passed!` and `3 files already formatted`.

## Self-Review Notes

- The store uses a per-instance `RLock`, ignores corrupt and model-version-mismatched snapshots, and atomically replaces `latest.json` from `latest.json.tmp`.
- The service requests 1,020 benchmark bars, filters the current Shanghai local date before 15:10, retains prior valid bars for weekends and holidays, keeps at most 500 calculated points, and saves only successful results.
- Cache reads project a deep-copied canonical snapshot and apply `as_of` only after cache loading or calculation.
- Refresh errors return the last valid snapshot as `stale`, preserve its actual trade date, and expose only the exception class in source status and notes.
- The staged diff contained only the three Task 2 implementation files; `git diff --cached --check` was clean before commit.

## Concerns

- The cache treats a snapshot as same-day using its `generated_at` Shanghai local date. This matches the specified same-day cache behavior, but a market-calendar-aware freshness policy is intentionally deferred to a later task.

## Fix

### Status

Completed. Cache freshness now requires both the same Shanghai local date and the same pre/post-15:10 completion phase, so a pre-cutoff snapshot cannot satisfy a post-cutoff request.

### Changed Files

- `apps/api/app/services/market_sentiment_percentile_service.py`
- `apps/api/tests/test_market_sentiment_percentile_service.py`

### RED Evidence

Command:

```bash
cd apps/api && uv run pytest tests/test_market_sentiment_percentile_service.py -q -k post_cutoff_call_refreshes_pre_cutoff_same_day_snapshot
```

Observed failure:

```text
1 failed, 11 deselected in 0.38s
E       assert 1 == 2
E        +  where 1 = <test_market_sentiment_percentile_service.FakeProvider object at ...>.calls
```

The later 16:00 call incorrectly reused the 15:09 snapshot without calling the provider.

### GREEN Evidence

Focused service suite:

```bash
cd apps/api && uv run pytest tests/test_market_sentiment_percentile_service.py -q
```

Result: `12 passed in 1.42s`.

Calculator and service suite:

```bash
cd apps/api && uv run pytest tests/test_market_sentiment_percentile.py tests/test_market_sentiment_percentile_service.py -q
```

Result: `37 passed in 1.95s`.

Ruff:

```bash
cd apps/api && uv run ruff check app/services/market_sentiment_percentile_service.py tests/test_market_sentiment_percentile_service.py
cd apps/api && uv run ruff format --check app/services/market_sentiment_percentile_service.py tests/test_market_sentiment_percentile_service.py
```

Results: `All checks passed!` and `2 files already formatted`.

### Concerns

- No new concerns within scope. The existing market-calendar-aware freshness limitation remains deferred; this fix addresses the required same-date 15:10 phase transition while preserving same-phase cache hits.
