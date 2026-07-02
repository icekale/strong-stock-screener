# Auction Review Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-version auction review loop that archives daily auction snapshots, attributes intraday/day/next-day outcomes, summarizes rule buckets, and exposes the results in the auction page.

**Architecture:** Extend the existing auction service instead of replacing it. `AuctionSnapshotStore` remains the in-memory fast path for today's live radar, while a new `AuctionReviewStore` persists deduplicated daily records under `STRONG_STOCK_DATA_DIR/auction_reviews`; a review service computes rule tags, outcome attribution, composite scores, and bucket suggestions. FastAPI exposes lightweight manual endpoints, and the existing `/auction` client gets a compact review panel without disrupting the morning workflow.

**Tech Stack:** FastAPI + Pydantic models + JSONL storage for backend; Next.js/React/Ant Design for frontend; existing TickFlow/fallback providers for rankings, daily K-line, and optional minute-line data.

---

### Task 1: Auction Review Models and Store

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/auction_review_store.py`
- Modify: `apps/api/tests/test_auction_snapshot_store.py`
- Modify: `apps/api/tests/test_retention_policy.py`

- [ ] **Step 1: Write failing store tests**

Add tests proving the store persists records, dedupes by `trade_date + symbol + selected_at_label`, reloads from disk, and prunes old trade-date files:

```python
def test_auction_review_store_persists_and_dedupes_records(tmp_path: Path) -> None:
    store = AuctionReviewStore(tmp_path, retention_days=120)
    record = _auction_review_record("2026-07-01", "300001.SZ", "09:25")

    store.upsert_records([record])
    store.upsert_records([record])

    reloaded = AuctionReviewStore(tmp_path, retention_days=120)
    records = reloaded.load_records("2026-07-01")
    assert len(records) == 1
    assert records[0].symbol == "300001.SZ"
    assert records[0].selected_at_label == "09:25"
```

```python
def test_auction_review_store_prunes_old_trade_dates(tmp_path: Path) -> None:
    store = AuctionReviewStore(tmp_path, retention_days=2)

    for trade_date in ["2026-06-29", "2026-06-30", "2026-07-01"]:
        store.upsert_records([_auction_review_record(trade_date, f"{trade_date}.SZ", "09:25")])

    remaining = sorted(path.stem for path in (tmp_path / "auction_reviews" / "records").glob("*.jsonl"))
    assert remaining == ["2026-06-30", "2026-07-01"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && .venv/bin/pytest tests/test_auction_snapshot_store.py tests/test_retention_policy.py -q`

Expected: FAIL because `AuctionReviewStore` and auction review models do not exist.

- [ ] **Step 3: Add Pydantic models**

Add focused models to `apps/api/app/models.py`: `AuctionReviewSnapshot`, `AuctionReviewOutcome`, `AuctionReviewScore`, `AuctionReviewRecord`, `AuctionRuleBucket`, `AuctionReviewSummary`, and `AuctionBackfillResponse`. Use plain optional numeric fields and `review_status` values `pending`, `intraday_done`, `day_done`, `next_day_done`, `data_incomplete`.

- [ ] **Step 4: Implement JSONL store**

Create `AuctionReviewStore` with:

- `upsert_records(records: list[AuctionReviewRecord]) -> list[AuctionReviewRecord]`
- `load_records(trade_date: str | None = None, limit: int | None = None) -> list[AuctionReviewRecord]`
- `save_summary(summary: AuctionReviewSummary) -> None`
- `load_latest_summary() -> AuctionReviewSummary | None`
- retention pruning by newest trade-date filenames.

- [ ] **Step 5: Run tests to verify green**

Run: `cd apps/api && .venv/bin/pytest tests/test_auction_snapshot_store.py tests/test_retention_policy.py -q`

Expected: PASS.

### Task 2: Archive Auction Snapshots Into Review Records

**Files:**
- Modify: `apps/api/app/services/auction_snapshot_store.py`
- Create: `apps/api/app/services/auction_review.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_auction_snapshot_store.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing archive tests**

Add a test that saving an auction snapshot at `09:25` writes review records with selected label, ranking, rule tags, and industry concentration tags.

```python
def test_auction_snapshot_store_archives_review_records(tmp_path: Path) -> None:
    review_store = AuctionReviewStore(tmp_path)
    store = AuctionSnapshotStore(review_store=review_store)
    snapshot = _snapshot_with_items("2026-07-01")

    store.save(snapshot, captured_at=datetime(2026, 7, 1, 9, 25, 0))

    records = review_store.load_records("2026-07-01")
    assert [record.symbol for record in records] == ["300001.SZ", "300002.SZ"]
    assert records[0].selected_at_label == "09:25"
    assert records[0].auction_snapshot.rank == 1
    assert "温和高开" in records[0].rule_tags
    assert "行业集中" in records[0].rule_tags
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && .venv/bin/pytest tests/test_auction_snapshot_store.py::test_auction_snapshot_store_archives_review_records -q`

Expected: FAIL because snapshot archival is not wired.

- [ ] **Step 3: Implement review record builder**

Create `build_auction_review_records(snapshot, selected_at_label, selected_at, limit=100)` in `auction_review.py`. It should:

- Use snapshot item order as rank.
- Copy only compact snapshot fields.
- Build rule tags from `tier`, `signals`, `risk_flags`, open gap, turnover, and industry concentration.
- Preserve source status.

- [ ] **Step 4: Wire store into snapshot saving**

Update `AuctionSnapshotStore.__init__` to accept optional `review_store`. In `save`, when `timeline_label` is not `None`, upsert review records for that label. Add `_auction_review_store()` in `main.py` and pass it when constructing `_auction_snapshot_store()`.

- [ ] **Step 5: Run tests to verify green**

Run: `cd apps/api && .venv/bin/pytest tests/test_auction_snapshot_store.py tests/test_api.py::test_auction_timeline_returns_locked_observation_points -q`

Expected: PASS.

### Task 3: Outcome Attribution and Rule Buckets

**Files:**
- Modify: `apps/api/app/services/auction_review.py`
- Modify: `apps/api/tests/test_auction.py`
- Create: `apps/api/tests/test_auction_review.py`

- [ ] **Step 1: Write failing attribution tests**

Add tests for:

- intraday 10:00 strength from minute bars when available.
- daily and next-day outcomes from K-line bars.
- incomplete minute data still produces day/next-day attribution.
- rule buckets calculate sample count, win rate, average score, average drawdown, and suggestion.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && .venv/bin/pytest tests/test_auction_review.py -q`

Expected: FAIL because attribution helpers do not exist.

- [ ] **Step 3: Implement outcome scoring**

Implement pure functions:

- `finalize_auction_records(records, symbol_bars, symbol_intraday_bars=None) -> AuctionReviewSummary`
- `build_auction_rule_buckets(records) -> list[AuctionRuleBucket]`
- `score_auction_record(record) -> AuctionReviewScore`

Composite score should combine intraday, day, and next-day scores, while preserving each sub-score.

- [ ] **Step 4: Run tests to verify green**

Run: `cd apps/api && .venv/bin/pytest tests/test_auction_review.py -q`

Expected: PASS.

### Task 4: Review APIs and Backfill Skeleton

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/api/tests/test_config.py`

- [ ] **Step 1: Write failing API tests**

Add tests for:

- `GET /api/auction/review/latest` returns latest summary or 404 before summary exists.
- `GET /api/auction/review?trade_date=YYYY-MM-DD` returns records and buckets.
- `POST /api/auction/review/finalize?trade_date=YYYY-MM-DD` saves latest summary.
- `POST /api/auction/review/backfill` returns explicit `data_unavailable` until a verified historical auction source exists.
- default `auction_review_retention_days == 120`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && .venv/bin/pytest tests/test_api.py tests/test_config.py -q`

Expected: FAIL on missing API/config fields.

- [ ] **Step 3: Add config and API wiring**

Add `auction_review_retention_days` to settings. Add `_auction_review_store()`. Add endpoints:

- `GET /api/auction/review/latest`
- `GET /api/auction/review`
- `POST /api/auction/review/finalize`
- `POST /api/auction/review/backfill`
- `GET /api/auction/rules/summary`

For finalize, first version may use daily K-line provider only when available through existing provider helpers; minute result remains `data_incomplete` if no minute helper is present.

- [ ] **Step 4: Run tests to verify green**

Run: `cd apps/api && .venv/bin/pytest tests/test_api.py tests/test_config.py -q`

Expected: PASS.

### Task 5: Frontend Types, API Client, and Auction Review UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/auction/AuctionWorkspace.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Write failing frontend contract test**

Extend `strongStockWorkbench.test.ts` to assert:

- Types include `AuctionReviewSummary`, `AuctionReviewRecord`, and `AuctionRuleBucket`.
- API client includes `getAuctionReviewLatest`, `getAuctionReview`, `finalizeAuctionReview`, and `getAuctionRuleSummary`.
- Auction page includes text for `竞价复盘`, `规则统计`, `失败样本`, and `生成/刷新今日复盘`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && node --experimental-strip-types --test lib/strongStockWorkbench.test.ts`

Expected: FAIL because types/client/UI are not implemented.

- [ ] **Step 3: Add client types and API functions**

Mirror backend response shapes in `types.ts` and add API functions in `api.ts`.

- [ ] **Step 4: Add compact UI panel**

Add a collapsed or below-fold `竞价复盘` section to `AuctionWorkspace`. It should:

- Load latest review summary on page load.
- Show status cards for total records, pending count, completed count, and data incomplete count.
- Show rule bucket table.
- Show high-score failure samples.
- Provide a button to finalize today's review.

- [ ] **Step 5: Run frontend verification**

Run:

```bash
cd apps/web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/strongStockWorkbench.test.ts
```

Expected: PASS.

### Task 6: Full Verification and Release Prep

**Files:**
- All changed files.

- [ ] **Step 1: Run backend test suite**

Run: `cd apps/api && .venv/bin/pytest`

Expected: all tests pass.

- [ ] **Step 2: Run frontend test suite**

Run:

```bash
cd apps/web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/*.test.ts
```

Expected: all tests pass.

- [ ] **Step 3: Build Docker image**

Run: `docker buildx build --platform linux/amd64 -t icekale/strong-stock-screener:auction-review-test --load .`

Expected: image builds successfully.

- [ ] **Step 4: Smoke test container**

Run:

```bash
docker run --rm -d --name strong-stock-screener-auction-review-test -p 3112:3110 --env-file .env icekale/strong-stock-screener:auction-review-test
curl -sS http://127.0.0.1:3112/health
curl -sS -I http://127.0.0.1:3112/auction
docker rm -f strong-stock-screener-auction-review-test
```

Expected: health returns `{"status":"ok"}` and `/auction` returns HTTP 200.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git status --short
git add apps docs
git commit -m "Add auction review workflow"
```

Expected: commit succeeds on `codex/auction-review-workflow`.
