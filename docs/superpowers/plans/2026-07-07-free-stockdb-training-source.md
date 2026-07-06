# free-stockdb Training Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make free-stockdb a training-only source while daily auction Top3 inference uses the configured candidate and K-line providers.

**Architecture:** Keep `FreeStockDbAuctionModelSource` for offline training and add `ProviderAuctionModelSource` for daily inference. Wire the default `/api/auction/model/top3` service to the provider source, preserve cache behavior, and add a background job endpoint so the auction page does not block while regenerating Top3.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js, TypeScript, Ant Design.

---

### Task 1: Provider-Based Top3 Source

**Files:**
- Modify: `apps/api/app/services/auction_model.py`
- Test: `apps/api/tests/test_auction_model.py`

- [ ] **Step 1: Write failing tests**

Add tests that prove a provider source builds rows from `get_candidates()` and `get_klines()` without calling free-stockdb:

```python
def test_provider_auction_model_source_builds_rows_from_candidate_and_kline_providers() -> None:
    source = ProviderAuctionModelSource(
        candidate_provider=FakeCandidateProvider(),
        kline_provider=FakeKlineProvider(),
    )

    rows, feature_end_date = build_live_prediction_rows(source, trade_date="2026-07-06", lookback=5)

    assert feature_end_date == "2026-07-03"
    assert rows[0]["symbol"] == "300001.SZ"
    assert rows[0]["market_cap_float"] == 5_000_000_000
    assert "uses_provider_daily_bar" in rows[0]["data_quality"]
    assert "free-stockdb" not in source.source_name
```

```python
def test_provider_auction_model_source_skips_candidate_when_kline_fails() -> None:
    source = ProviderAuctionModelSource(
        candidate_provider=FakeCandidateProvider(),
        kline_provider=FailingKlineProvider(),
    )

    rows, _ = build_live_prediction_rows(source, trade_date="2026-07-06", lookback=5)

    assert rows == []
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd apps/api
uv run pytest tests/test_auction_model.py::test_provider_auction_model_source_builds_rows_from_candidate_and_kline_providers tests/test_auction_model.py::test_provider_auction_model_source_skips_candidate_when_kline_fails -q
```

Expected: fail because `ProviderAuctionModelSource` does not exist.

- [ ] **Step 3: Implement provider source**

Add provider protocols and `ProviderAuctionModelSource` to `auction_model.py`. It should:

- Convert `StrongStockCandidate` to the existing candidate row dict.
- Convert `KlineBar` to `DailyBar`.
- Use real `bar.amount` when available, otherwise estimate amount from `volume * close` and tag `daily_amount_estimated`.
- Return empty bars when one symbol K-line fetch fails so the failed symbol is skipped.
- Implement no-op `prefetch_daily_window()`.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same two pytest targets. Expected: pass.

### Task 2: Default API Wiring

**Files:**
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_auction_model.py`

- [ ] **Step 1: Write failing API wiring test**

Add a test that builds the default auction model service from injected candidate and K-line providers:

```python
def test_default_auction_model_service_uses_provider_source_not_free_stockdb(tmp_path: Path, monkeypatch) -> None:
    metadata_path = tmp_path / "metadata.json"
    model_path = tmp_path / "model.pkl"
    performance_path = tmp_path / "performance.json"
    metadata_path.write_text(json.dumps({"feature_names": ["prev_return"]}), encoding="utf-8")
    model_path.write_bytes(b"unused")
    performance_path.write_text("{}", encoding="utf-8")

    app.state.candidate_provider = FakeCandidateProvider()
    app.state.kline_provider = FakeKlineProvider()
    monkeypatch.setattr("app.main.get_settings", lambda: FakeAuctionModelSettings(model_path, metadata_path, performance_path))
    monkeypatch.setattr(
        "app.services.auction_model.score_rows_with_model",
        lambda rows, model_path, metadata_path: [{**row, "prob_3pct": 0.9} for row in rows],
    )

    try:
        result = app.state.auction_model_service.predict_top3("2026-07-06") if hasattr(app.state, "auction_model_service") else _auction_model_service().predict_top3("2026-07-06")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "kline_provider")

    assert result.items[0].symbol == "300001.SZ"
    assert result.source_status[0].source == "K线推理源"
```

- [ ] **Step 2: Run test to verify RED**

Run the new test. Expected: fail because `_auction_model_service()` still wires `FreeStockDbAuctionModelSource`.

- [ ] **Step 3: Wire default service to provider source**

Modify imports and `_auction_model_service()` so default daily inference uses:

```python
ProviderAuctionModelSource(
    candidate_provider=_candidate_provider(),
    kline_provider=_kline_provider(),
)
```

Leave `FreeStockDbAuctionModelSource` import available for training code and direct tests.

- [ ] **Step 4: Run related API tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_auction_model.py -q
```

Expected: pass.

### Task 3: Background Top3 Generation Endpoint

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/app/auction/AuctionWorkspace.tsx`
- Test: `apps/api/tests/test_auction_model.py`

- [ ] **Step 1: Write failing backend job tests**

Add tests for:

- `POST /api/auction/model/top3/jobs?trade_date=YYYY-MM-DD` returns a background job.
- `GET /api/auction/model/top3/jobs/{job_id}` returns the job.
- Job success result includes `trade_date` and does not remove existing cache on failure.

- [ ] **Step 2: Run tests to verify RED**

Run the new job tests. Expected: 404 because endpoints do not exist.

- [ ] **Step 3: Implement backend job endpoints**

Use existing `BackgroundJobStore.create_transient_job()` with job type `auction_model_top3_generate`.

Runner behavior:

```python
def _run_auction_top3_generation_job(trade_date, progress, should_cancel):
    if should_cancel():
        raise RuntimeError("竞价模型Top3生成已取消")
    progress(1, 3, "读取候选池和K线")
    result = _generate_auction_top3_for_date(trade_date)
    progress(3, 3, "竞价模型Top3生成完成")
    return {"trade_date": result.trade_date, "run_id": result.run_id, "cache_status": result.cache_status}
```

- [ ] **Step 4: Update frontend API and UI**

Add:

```typescript
export async function createAuctionModelTop3Job(tradeDate: string): Promise<BackgroundJobState>
export async function getAuctionModelTop3Job(jobId: string): Promise<BackgroundJobState>
```

Change the “重新生成” handler to create a job, poll it, then read cache when status becomes `success`. Keep the current result visible during polling.

- [ ] **Step 5: Run backend and web tests**

Run:

```bash
cd apps/api && uv run pytest tests/test_auction_model.py -q
cd apps/web && pnpm test
```

Expected: pass.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `unraid/strong-stock-screener.xml`

- [ ] **Step 1: Update docs**

Change wording so free-stockdb is described as a training/retraining/offline backtest source, not the daily Top3 inference source.

- [ ] **Step 2: Run final verification**

Run:

```bash
cd apps/api && uv run pytest -q
cd apps/web && pnpm test
cd apps/web && pnpm build
```

Expected: all pass.
