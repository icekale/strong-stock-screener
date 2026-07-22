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

## Fix 2

### RED Evidence

- `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py -q` after adding the second semantic-hardening cases: `14 failed, 39 passed`.
- The failures included the reviewer's exact bypasses: `贵州茅台上涨 2%`, `控制资金比例为 30%`, `当前综合得分为 61.0`, `市场位于冷区`, `量能系数为 30%`, and `当前操作权限为强势进攻`.
- Separate failures proved that invented `69` facts passed in every free-text result field, a conditional-looking key driver could invent `69`, and `涨停 68 家` passed while the canonical market section was unavailable.
- A focused self-review RED run then found `3 failed, 53 passed`: a threshold cue could mask an unrelated number in the same watch clause, factor `占比` could reuse a different grounded value, and historical zone prose was treated as a current-level override.

### GREEN Evidence

- Focused analysis suite: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py -q` -> `56 passed in 0.40s`.
- Required regression: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py tests/test_model_maintenance.py -q` -> `68 passed in 0.76s`.
- Ruff: `cd apps/api && uv run ruff check app tests` -> `All checks passed!`.

### Fix Scope And Self-Review

- Semantic validation now operates per result item and clause. It normalizes canonical numeric evidence, percentage-form weights, and `万`/`亿`/`万亿` claims; factual numbers must match canonical input values.
- Only an explicitly conditional or threshold clause in `next_session_watch` may introduce a new number. Key drivers and all other fields remain grounded-only.
- Unavailable market, decision, sector, and validation metric claims are rejected, while conditional next-session thresholds remain allowed.
- Overall score, current level/zone, named factor coefficients, and trade/operation permission claims use context-aware checks. Permission claims are rejected even when they repeat canonical decision text.
- A-share codes, individual-security recommendations, position/fund sizing, and order actions are rejected. Movement subjects must be a market aggregate, index, generic aggregate metric, or a sector name present in canonical input.
- False-positive review covered grounded market prose, `中证全指上涨 2.5%`, `存储芯片上涨 2%`, correct `62.0`/`热区`/`20%` protected claims, and unavailable-market watch thresholds; all remain accepted.
- Retry, failed persistence, cache identity, and sanitized errors are unchanged. The pre-existing dirty Task 4 report was not modified.

## Fix 3

### RED Evidence

- Added the reviewer's exact forbidden, cross-field, conditional-consequence, and valid-prose probes to `tests/test_market_sentiment_analysis.py` before changing production code.
- Initial focused RED: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py -q` -> `12 failed, 57 passed`. The failures reproduced all newly accepted forbidden claims, `跌停 68 家`, the missing prior-level claim, the `若 ... 则 ...` consequence bypass, and the three valid-prose false positives.
- The first one-day-change wording was rejected by unrelated movement-subject validation, so the probe was isolated as `单日得分变化为 4.0 分`; its targeted RED run, together with the prior-level probe, produced `2 failed`.

### GREEN Evidence

- Focused analysis suite: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py -q` -> `69 passed in 0.36s`.
- Required combined regression: `cd apps/api && uv run pytest tests/test_market_sentiment_analysis.py tests/test_model_maintenance.py -q` -> `81 passed in 0.82s`.
- Ruff: `cd apps/api && uv run ruff check app tests` -> `All checks passed!`.
- `git diff --check` completed without errors.

### Fix Scope And Self-Review

- Recognizable market metrics, score changes, factor scores/raw values, and factor weights now validate against their own canonical fields. A grounded number from another field can no longer satisfy the claim, and unavailable prior/source values reject factual claims.
- Explicit watch thresholds remain allowed, but clauses are split at `则`, `那么`, `届时`, and `then`; only the condition-side threshold number is exempt, while consequence numbers are validated normally.
- Allowed movement subjects cover the requested broad market/index names, aggregate metric labels, and supplied sector names. Digits inside recognized index names are not treated as factual statistics.
- Semantic category detection now covers the reviewed allocation, subscribe/redeem/order, strategy permission, level-zone, contribution/coefficient/weight, and unknown-security valuation/attention wording without adding a stock-name dictionary.
- The strict input allowlist, hash/cache identity, three-attempt retry flow, sanitized failure persistence, and shared model-maintenance parsers were not changed. The pre-existing dirty Task 4 report was not modified.
