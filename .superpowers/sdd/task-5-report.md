# Task 5 Report: Market Sentiment LLM Analysis Core

## Status

Completed and committed. This task adds only the strict analysis contracts, canonical input/hash, OpenAI-compatible generator, per-date atomic store, and focused tests. Routes, samplers, and frontend remain unchanged for Task 6 and later.

## Changed Files

- `apps/api/app/models.py`
- `apps/api/app/services/ai_model_analysis.py`
- `apps/api/app/services/market_sentiment_analysis.py`
- `apps/api/app/services/market_sentiment_analysis_store.py`
- `apps/api/tests/test_market_sentiment_analysis.py`

## Commit

- `3e02a6f feat: generate daily LLM sentiment analysis`

## RED

Before production implementation, ran:

```text
cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py -q
```

Observed the expected collection failure:

```text
ImportError: cannot import name 'SentimentAnalysisResult' from 'app.models'
```

## GREEN And Regression

Focused analysis suite:

```text
17 passed in 0.23s
```

Required combined analysis and model-maintenance regression:

```text
29 passed in 0.52s
```

Ruff:

```text
cd apps/api && uv run ruff check app tests
All checks passed!
```

The focused tests cover canonical allowlisted input and stable SHA-256 hashing, explicit missing auxiliary context, strict result validation including ASCII-digit evidence, no deterministic-field overrides, ready-cache identity, changed model/input regeneration, pending persistence, five-sector/symbol-free truncation, malformed/unknown/missing-field retries, matching failed cooldown, unconfigured no-I/O behavior, atomic writes, and secret-safe failure persistence.

## Self-Review

- The result contract uses `extra="forbid"`; score, level, weights, and trade permission cannot enter LLM output.
- Input includes only declared percentile, market aggregate, sector aggregate, decision, and validation fields. Leaders, symbols, raw validation samples, notes, and source secrets are excluded.
- Every LLM request uses the existing OpenAI-compatible configuration, JSON response format, temperature `0.1`, and exported existing parsers.
- The system instruction prohibits changing statistics, individual stock names, position sizing, orders, and invented missing values.
- Pending is atomically stored before network I/O. Success and failure replace the same per-date record atomically.
- Failures retry exactly three times, then persist a 30-minute retry deadline and a generic class/category message. API keys and provider exception text are never stored or returned.
- Existing model-maintenance parsing is preserved by exporting, rather than altering, the generic response parsers.

## Concerns

- Analysis APIs, lifecycle sampling, and frontend presentation are deliberately deferred to Task 6 and later.
- The pre-existing modification to `.superpowers/sdd/task-4-report.md` was not staged, altered, or included in the Task 5 commit.

## Fix

### RED Evidence

- `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py -q` after adding the boundary, missing-snapshot, semantic-retry, and filesystem-error tests: `17 failed, 18 passed`. The failures showed arbitrary input was requested, missing snapshots retained metrics, semantic output became ready, and read `PermissionError` was swallowed.
- The recursive `sample_counts` allowlist test then failed independently: `1 failed, 35 passed`.
- The English current-level claim test failed independently: `1 failed, 36 passed`.

### GREEN Evidence

- Focused analysis suite: `37 passed in 0.33s`.
- Required regression: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py tests/test_model_maintenance.py -q` -> `49 passed in 0.63s`.
- Ruff: `cd apps/api && uv run ruff check app/services/market_sentiment_analysis.py app/services/market_sentiment_analysis_store.py tests/test_market_sentiment_analysis.py` -> `All checks passed!`.

### Fix Scope

- `generate` validates the complete recursive allowlist before hashing, caching, persistence, or provider I/O; the validated JSON payload is the only payload hashed and sent.
- Missing summary snapshots are explicit unavailable market context. Semantic violations in any result text retry through the existing three-attempt path and persist `failed` rather than `ready`.
- Malformed analysis records remain cache misses, while filesystem read failures propagate.
- Reviewed cache identity and failure persistence: identity remains trade date, model version, provider, model, and validated-input hash; provider errors and API keys are not persisted. The pre-existing dirty Task 4 report was not modified.
