# Strong Stock Screener

Standalone strong-stock screening workbench.

This project is separate from the daily stock review app. It screens A-share candidates with recent limit-up evidence, trend and volume quality, and keeps empty-position discipline scoped to watchlist or holding risk.

## Apps

- `apps/api`: FastAPI backend on port `8010`
- `apps/web`: Next.js workbench on port `3110`

## Data Sources

- THSDK WenCai is the default live candidate source for the "limit-up within 20 days" hard filter. If it is unavailable, the API reports a candidate-source failure instead of fabricating candidates.
- Baidu K-line is the default daily K-line source for trend, moving-average, 200-day high, and volume rules.
- TickFlow is an independent quote/status source for this screener. It is optional in local development; without a key the API reports `missing_key` and does not fabricate quote data.

For TickFlow, set either environment variable:

```bash
STRONG_STOCK_TICKFLOW_API_KEY=...
TICKFLOW_API_KEY=...
```

Other useful API settings use the `STRONG_STOCK_` prefix, for example `STRONG_STOCK_DATA_DIR`, `STRONG_STOCK_TICKFLOW_BASE_URL`, and `STRONG_STOCK_CORS_ALLOW_ORIGINS`.

New-stock screening results never use `empty` as `status`. Empty-position discipline is only reported as `risk_action = "empty"` for watchlist or holding risk.

## Local Development

```bash
cd apps/api
uv sync
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

```bash
cd apps/web
corepack pnpm install
corepack pnpm exec next dev -p 3110
```

## Checks

```bash
cd apps/api
uv sync
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
```

```bash
cd apps/web
corepack pnpm install
corepack pnpm test
```

## Operator Flow

1. Start the API on `127.0.0.1:8010`.
2. Start the web app on `127.0.0.1:3110`.
3. Open `http://localhost:3110`.
4. Check data-source status first. Candidate and K-line sources are required for screening; TickFlow can remain `missing_key` until quote features need live data.
5. Run the screener for a trade date. New-stock screening statuses never include `empty`; empty-position discipline appears only in watchlist or holding risk.
