# Task 1 Report: Deterministic Five-Factor Calculator

## Status

DONE_WITH_CONCERNS

## Files Changed

- `apps/api/app/models.py`
- `apps/api/app/services/market_sentiment_percentile.py`
- `apps/api/tests/market_sentiment_fixtures.py`
- `apps/api/tests/test_market_sentiment_percentile.py`
- `.superpowers/sdd/task-1-report.md`

## Commit SHA(s)

- Implementation commit: pending commit

## RED Evidence

Command:

```text
cd apps/api && uv run pytest tests/test_market_sentiment_percentile.py -q
```

Observed failure:

```text
ERROR collecting tests/test_market_sentiment_percentile.py
ImportError: cannot import name 'SentimentPercentileFactor' from 'app.models'
1 error during collection
```

This was the expected failure before the Task 1 models and calculator existed.

## GREEN And Regression Evidence

```text
cd apps/api && uv run pytest tests/test_market_sentiment_percentile.py -q
25 passed in 0.66s
```

```text
cd apps/api && uv run ruff check app/models.py app/services/market_sentiment_percentile.py tests/market_sentiment_fixtures.py tests/test_market_sentiment_percentile.py
All checks passed!
```

```text
cd apps/api && uv run pytest tests/test_api.py tests/test_short_term_sentiment.py tests/test_chanlun_models.py -q
186 passed in 15.72s
```

Full API suite:

```text
cd apps/api && uv run pytest -q
1105 passed, 1 failed in 46.79s
```

The single full-suite failure was `tests/test_chanlun_research_report.py::test_research_cli_preserves_rc8_virtualenv_interpreter_path`, asserting an existing unrelated `scripts/czsc-research.py` behavior. That script and test are outside the Task 1 scope and were not changed.

## Self-Review Notes

- The calculator normalizes unsorted bars by date and keeps the last duplicate record.
- It validates finite, positive OHLC and amount values plus OHLC ordering before calculation.
- It uses the required index-518 warmup, exact 500-observation midrank windows, equal 20% weights, fixed level boundaries, and signed directional amplitude.
- A zero 500-day high/low range skips only that date's composite point.
- `git diff --check` passed, and no unrelated files were modified.

## Concerns

- The full API suite has one pre-existing failure in `scripts/czsc-research.py`; it is unrelated to this task and remains unresolved by design.
