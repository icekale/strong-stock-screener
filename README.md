# Strong Stock Screener

Standalone strong-stock screening workbench.

This project is separate from the daily stock review app. It screens A-share candidates with recent limit-up evidence, trend and volume quality, and keeps empty-position discipline scoped to watchlist or holding risk.

## Apps

- `apps/api`: FastAPI backend on port `8010`
- `apps/web`: Next.js workbench on port `3110`

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

