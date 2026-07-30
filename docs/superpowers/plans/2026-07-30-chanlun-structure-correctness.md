# Chanlun Structure Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Chanlun fractals, strokes, and confirmed zones trustworthy by enforcing continuous minute history, mapping CZSC timestamps to the canonical chart bars, validating fixed golden samples, and making both stock and Chanlun pages consume the same bar series.

**Architecture:** Add a pure intraday coverage auditor before aggregation, then let `ChanlunAnalysisService` carry coverage into the public response and fail closed when a window is incomplete or unverified. Keep CZSC responsible for inclusion handling and maintained zone sequences; the adapter will use native `dt` values and raise a structural mapping error instead of returning a successful empty layer. The frontend will use `ChanlunAnalysisResponse.bars` for supported periods and expose only validated layers.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, `czsc==0.10.12`, pytest, Ruff, Vue 3, TypeScript, Vitest, Ant Design Vue, ECharts 6.

## Global Constraints

- Preserve the existing strong-stock, auction, ETF, sentiment, GSGF, and stock quote behavior.
- Support only daily, 60-minute, 30-minute, and 5-minute Chanlun periods; do not add 15-minute or 90-minute semantics in this plan.
- Keep line segments, divergences, buy/sell points, confluence, alerts, screening scores, backtests, and paper-order decisions disabled until their own golden fixtures and no-future-function tests exist.
- A `ready` analysis requires complete coverage, fresh closed bars, successful CZSC mapping, and no structural mapping errors.
- Do not consume `stale`, `insufficient_bars`, `unverified`, or `unavailable` Chanlun data for alerts, screening, replay decisions, backtests, or paper orders.
- Use `ChanlunAnalysisResponse.bars` as the canonical chart coordinate sequence for supported periods.
- Keep all changes within the tracked backend/frontend files and Chanlun tests/fixtures described below; preserve unrelated dirty files.
- Keep `czsc==0.10.12`; do not introduce a second Chanlun engine or depend on a commercial product implementation.

---

## File Map

- `apps/api/app/models.py`: public coverage and backfill request contracts.
- `apps/api/app/config.py`: safe default raw-minute backfill capacity.
- `apps/api/app/services/chanlun/coverage.py`: pure trading-session and raw-minute coverage audit.
- `apps/api/app/services/chanlun/bars.py`: shared intraday period constants and timestamp/bucket helpers.
- `apps/api/app/services/chanlun/service.py`: coverage-aware loading, dynamic fetch sizing, backfill result, and fail-closed availability.
- `apps/api/app/services/chanlun/adapter.py`: native CZSC time mapping and structural error conversion.
- `apps/api/app/services/chanlun/structures.py`: strict maintained-zone mapping and mapping exceptions.
- `apps/api/app/main.py`: pass backfill request parameters to the background job and expose result details.
- `apps/api/scripts/run_chanlun_golden_validation.py`: reproducible fixture validation and Markdown report.
- `apps/api/tests/fixtures/chanlun/golden/*.json`: frozen bars and independently reviewed expected structures.
- `apps/api/tests/test_chanlun_coverage.py`: unit coverage cases for sessions, gaps, and target counts.
- `apps/api/tests/test_chanlun_service.py`: service integration cases for coverage, backfill, and availability.
- `apps/api/tests/test_chanlun_adapter.py`: exact endpoint and strict zone mapping cases.
- `apps/api/tests/test_chanlun_golden.py`: frozen sample and truncation-stability tests.
- `apps/api/tests/test_chanlun_models.py`: Pydantic and configuration contract tests.
- `apps/api/tests/test_api.py`: HTTP backfill contract tests.
- `apps/web-vue/src/service/types.ts`: TypeScript coverage and backfill contracts.
- `apps/web-vue/src/service/product-api.ts`: serialize the new backfill request fields.
- `apps/web-vue/src/utils/domain/stockViewState.ts`: select the canonical Chanlun bars for stock charts.
- `apps/web-vue/src/views/StockView.vue`: render canonical bars and suppress overlays on non-ready analysis.
- `apps/web-vue/src/views/ChanlunView.vue`: truthful layer states and backfill progress interaction.
- `apps/web-vue/src/views/ChanlunView.test.ts`: workbench request, layer, and backfill behavior.
- `apps/web-vue/src/utils/domain/stockViewState.test.ts`: canonical bar selection tests.

### Task 1: Add Coverage and Backfill Contracts

**Files:**
- Modify: `apps/api/app/models.py:88-92, 648-660, 812-814`
- Modify: `apps/api/app/config.py:73-76`
- Modify: `apps/web-vue/src/service/types.ts:1550-1568, 1715-1730, 1886-1888`
- Modify: `apps/api/tests/test_chanlun_models.py`

**Interfaces:**
- Produces `ChanlunCoverageStatus = Literal["complete", "incomplete", "unverified"]`.
- Produces `ChanlunCoverage` with fields `status`, `required_period_bars`, `available_period_bars`, `required_raw_minutes`, `available_raw_minutes`, `complete_sessions`, `incomplete_sessions`, `missing_minutes`, `earliest_at`, `latest_at`, `reason`, and `backfill_required`.
- Adds `coverage: ChanlunCoverage` to `ChanlunAnalysisResponse` with an explicit unknown default for test/fallback construction; production service responses must always replace it with an audited value.
- Changes `ChanlunBackfillRequest` to `periods: list[Literal["5m", "30m", "60m"]]`, `lookback: int`, and optional legacy `history_days`.
- Changes `chanlun_backfill_max_bars` default from `4800` to `16000`; retain validation bounds `240..24000`.

- [x] **Step 1: Write failing model and TypeScript contract tests**

Add these assertions to `apps/api/tests/test_chanlun_models.py`:

```python
def test_coverage_contract_has_unknown_safe_default() -> None:
    response = ChanlunAnalysisResponse(symbol="600000.SH", period="5m", availability="unavailable")

    assert response.coverage.status == "unverified"
    assert response.coverage.backfill_required is True


def test_backfill_contract_defaults_to_all_minute_periods_and_220_bars() -> None:
    request = ChanlunBackfillRequest()

    assert request.periods == ["5m", "30m", "60m"]
    assert request.lookback == 220
    assert request.history_days is None
```

Update the existing settings assertion to require `16000`, and assert the TypeScript source contains the same optional `history_days`, `periods`, and `lookback` fields.

- [x] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_models.py -q
```

Expected: collection or assertion failures because `ChanlunCoverage`, the new request fields, and the `16000` default do not exist yet.

- [x] **Step 3: Implement the public models and settings**

Add the Pydantic model before `ChanlunAnalysisResponse`:

```python
ChanlunCoverageStatus = Literal["complete", "incomplete", "unverified"]

class ChanlunCoverage(BaseModel):
    status: ChanlunCoverageStatus = "unverified"
    required_period_bars: int = Field(default=0, ge=0)
    available_period_bars: int = Field(default=0, ge=0)
    required_raw_minutes: int | None = Field(default=None, ge=0)
    available_raw_minutes: int | None = Field(default=None, ge=0)
    complete_sessions: int = Field(default=0, ge=0)
    incomplete_sessions: int = Field(default=0, ge=0)
    missing_minutes: int = Field(default=0, ge=0)
    earliest_at: str | None = None
    latest_at: str | None = None
    reason: str = "尚未执行覆盖审计"
    backfill_required: bool = True
```

Add `coverage` to `ChanlunAnalysisResponse`, add the new fields and duplicate-period validation to `ChanlunBackfillRequest`, and update `Settings.chanlun_backfill_max_bars` to `Field(default=16000, ge=240, le=24000)`. Mirror these exact fields in `apps/web-vue/src/service/types.ts` and update `ChanlunBackfillRequest` in the TypeScript client type.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_models.py -q
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm exec vitest run src/utils/domain/stockViewState.test.ts
pnpm typecheck
```

Expected: all focused backend tests pass; the frontend typecheck passes with the expanded response type.

- [x] **Step 5: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/models.py apps/api/app/config.py apps/api/tests/test_chanlun_models.py apps/web-vue/src/service/types.ts
git commit -m "feat(chanlun): add coverage contracts"
```

### Task 2: Implement the Pure Minute Coverage Auditor

**Files:**
- Create: `apps/api/app/services/chanlun/coverage.py`
- Modify: `apps/api/app/services/chanlun/bars.py:10-72`
- Create: `apps/api/tests/test_chanlun_coverage.py`

**Interfaces:**
- Produces `required_intraday_raw_minutes(period: Literal["5m", "30m", "60m"], lookback: int) -> int` using `lookback * period_minutes + 5 * 240`.
- Produces `round_intraday_fetch_count(raw_minutes: int, page_size: int = 800) -> int`.
- Produces `open_sessions_in_calendar_window(history_days: int, *, now: datetime) -> int`, counting open exchange sessions in the trailing natural-day window.
- Produces `audit_intraday_coverage(timestamps: Iterable[str], *, period: Literal["5m", "30m", "60m"], lookback: int, now: datetime, expected_trade_dates: set[date] | None) -> ChanlunCoverage`.
- The auditor treats `expected_trade_dates=None` as `unverified`, ignores lunch/weekends/holidays, and never treats two separated sessions as one continuous sample.

- [x] **Step 1: Write failing coverage tests**

Use deterministic Shanghai timestamps and test all of these cases in `test_chanlun_coverage.py`:

```python
def test_two_sessions_with_a_28_day_trading_gap_are_incomplete() -> None:
    timestamps = full_session("2026-06-01") + full_session("2026-06-29")

    result = audit_intraday_coverage(
        timestamps,
        period="5m",
        lookback=20,
        now=shanghai("2026-06-29 15:05"),
        expected_trade_dates={date(2026, 6, 1), date(2026, 6, 29)},
    )

    assert result.status == "incomplete"
    assert result.incomplete_sessions == 1
    assert result.backfill_required is True


def test_220_60m_bars_require_14400_raw_minutes() -> None:
    assert required_intraday_raw_minutes("60m", 220) == 14400
    assert round_intraday_fetch_count(14400) == 14400


def test_missing_one_minute_does_not_cross_a_5m_bucket() -> None:
    timestamps = full_session("2026-07-10")
    timestamps.remove(shanghai("2026-07-10 09:32").isoformat())

    result = audit_intraday_coverage(
        timestamps,
        period="5m",
        lookback=20,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates={date(2026, 7, 10)},
    )

    assert result.status == "incomplete"
    assert result.missing_minutes == 1
```

Also test that a complete 09:30-11:29 and 13:00-14:59 day has no lunch gap, duplicate timestamps do not inflate `available_raw_minutes`, and `expected_trade_dates=None` returns `unverified`.

- [x] **Step 2: Run the coverage tests and verify RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_coverage.py -q
```

Expected: import failures because the auditor module and functions do not exist.

- [x] **Step 3: Implement session and bucket auditing**

In `coverage.py`, normalize every timestamp to `Asia/Shanghai`, deduplicate it, and build expected minute starts only inside `09:30..11:29` and `13:00..14:59` for `expected_trade_dates`. Group timestamps into the existing session-aligned period buckets from `bars.py`; a bucket is complete only when it contains every expected minute. Select the trailing `lookback` complete buckets, count missing minutes and incomplete sessions in that selected history, and set:

```python
status = "complete" if selected_count >= lookback and missing_minutes == 0 and dates_are_verified else "incomplete"
```

Use `status="unverified"` when no symbol trading-date reference was provided. Set `backfill_required` whenever status is not `complete` or fewer than `lookback` buckets exist. Keep `required_raw_minutes` equal to the formula above and round fetch counts up to the TDX page size of 800.

- [x] **Step 4: Run coverage and existing bar tests**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_coverage.py tests/test_chanlun_bars.py -q
.venv/bin/ruff check app/services/chanlun/coverage.py app/services/chanlun/bars.py tests/test_chanlun_coverage.py tests/test_chanlun_bars.py
```

Expected: all coverage and existing aggregation tests pass.

- [x] **Step 5: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/services/chanlun/coverage.py apps/api/app/services/chanlun/bars.py apps/api/tests/test_chanlun_coverage.py
git commit -m "feat(chanlun): audit minute coverage"
```

### Task 3: Integrate Coverage and Dynamic Backfill into the Service

**Files:**
- Modify: `apps/api/app/services/chanlun/service.py:40-75, 363-440, 651-710, 750-810`
- Modify: `apps/api/tests/test_chanlun_service.py:752-920`
- Modify: `apps/api/tests/test_chanlun_research_service.py` where fake `ClosedWorkspaceInputs` or analysis responses are constructed.

**Interfaces:**
- Extends `_ClosedPeriodData` with `coverage: ChanlunCoverage`.
- Extends `ChanlunAnalysisService.backfill` to `backfill(symbol, *, periods: tuple[Literal["5m", "30m", "60m"], ...], lookback: int, history_days: int | None, progress, should_cancel)`.
- Uses `required_intraday_raw_minutes` and `round_intraday_fetch_count` before calling `history_provider.get_minute_bars`.
- Adds `coverage` to every service-created `ChanlunAnalysisResponse`, including stale, insufficient, unavailable, and adapter-failure responses.

- [x] **Step 1: Write failing service tests**

Update the fake history provider assertions and add tests like:

```python
def test_workspace_backfill_requests_enough_raw_minutes_for_60m(tmp_path: Path) -> None:
    history = FakeHistoryProvider()
    service = make_service(tmp_path, history_provider=history)

    service.backfill(
        "600000.SH",
        periods=("5m", "30m", "60m"),
        lookback=220,
        history_days=None,
        progress=lambda *_: None,
        should_cancel=lambda: False,
    )

    assert history.calls == [("600000.SH", 14400)]


def test_internal_minute_gap_is_insufficient_even_when_20_period_bars_exist(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    seed_two_sessions_with_gap(store)
    result = make_service(tmp_path, store=store).analysis(
        "600000.SH", period="5m", lookback=20, include_observing=False,
        now=shanghai("2026-06-29 15:05"),
    )

    assert result.availability == "insufficient_bars"
    assert result.coverage.status == "incomplete"
```

Add a cap test asserting a request whose computed raw count is greater than `settings.chanlun_backfill_max_bars` fails before the history provider is called, and a stale test asserting complete historical coverage with an old latest bucket remains `availability="stale"` while `coverage.status="complete"`.

- [x] **Step 2: Run the service tests and verify RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_service.py tests/test_chanlun_research_service.py -q
```

Expected: signature failures, the old 4,800-count assertion, or a false `ready` result for the gapped history.

- [x] **Step 3: Load the symbol trading-date reference and audit before analysis**

In `_load_closed_intraday_periods`, fetch the closed daily bars needed for the raw-history window through the configured `daily_provider`. Build `expected_trade_dates` from completed daily bars with positive volume; include a live date when normalized TickFlow minutes exist. If the daily reference fails, keep the raw archive but pass `None` to the auditor and append a source status explaining that continuity is unverified.

Run `audit_intraday_coverage` on stored closed-minute timestamps before treating aggregated bars as usable. Store its result in `_ClosedPeriodData`. Keep the existing live failure behavior, but let coverage decide whether a successful provider response still yields `insufficient_bars` or `stale`.

- [x] **Step 4: Implement dynamic fetch sizing and coverage propagation**

Compute the raw target as:

```python
target = max(required_intraday_raw_minutes(period, lookback) for period in periods)
if history_days is not None:
    target = max(target, open_sessions_in_calendar_window(history_days) * 240)
target = round_intraday_fetch_count(target)
if target > self.history_max_bars:
    raise RuntimeError(f"需要 {target} 根分钟线，当前上限为 {self.history_max_bars}")
```

Pass `target` to `get_minute_bars`, then upsert, prune, clear caches, and return `requested_bars`, `written_bars`, and coverage results for every requested period. In `_analyze_closed_period_data`, return `insufficient_bars` when coverage is not complete, convert only a complete but old input to `stale`, and pass coverage through `_unavailable_response` and adapter results. Never run the adapter for an incomplete or unverified window.

- [x] **Step 5: Run the service tests and verify GREEN**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_service.py tests/test_chanlun_research_service.py tests/test_chanlun_alerts.py tests/test_chanlun_paper.py -q
.venv/bin/ruff check app/services/chanlun/service.py tests/test_chanlun_service.py tests/test_chanlun_research_service.py
```

Expected: all service and fail-closed consumer tests pass; stale, insufficient, and unavailable responses contain truthful coverage.

- [x] **Step 6: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/services/chanlun/service.py apps/api/tests/test_chanlun_service.py apps/api/tests/test_chanlun_research_service.py
git commit -m "fix(chanlun): gate analysis on continuous history"
```

### Task 4: Correct CZSC Endpoint Mapping and Strict Zone Errors

**Files:**
- Modify: `apps/api/app/services/chanlun/adapter.py:134-300`
- Modify: `apps/api/app/services/chanlun/structures.py:1-80`
- Modify: `apps/api/tests/test_chanlun_adapter.py`

**Interfaces:**
- Produces `StructureMappingError(ValueError)` for a native endpoint, BI reference, or zone that cannot map exactly to canonical bars.
- Changes `_occurred_at(native_item, dates_by_id)` to `_occurred_at(native_item, chart_dates)`; the function reads native public `dt`, normalizes to Shanghai, and requires exact membership in `chart_dates`.
- `map_confirmed_zones(completed_pairs)` raises `StructureMappingError` for native mapping/runtime errors and returns `[]` only when CZSC returns a normal empty zone sequence.

- [x] **Step 1: Write failing mapping and error tests**

Add a native fixture where the endpoint has `id=3` but `dt` equals the canonical bar at index 5. Assert that the output uses the `dt` bar, not index 3:

```python
def test_adapter_maps_inclusion_endpoint_by_native_dt_not_old_id() -> None:
    bars = fixture_bars_with_distinct_dates()
    native = native_with_endpoint(id_value=3, dt=bars[5].date)

    analysis = ChanlunAdapter()._map_native(
        "600000.SH", "1d", bars, native, include_observing=False
    )

    assert analysis.strokes[0].end_at == bars[5].date
```

Add tests that a native `dt` absent from `bars[].date`, a zone referring to an unmapped BI, and a `get_zs_seq` exception produce `availability="unavailable"` with a failed Chanlun source status. Retain the existing duplicate-zone and disabled-derived-layer assertions.

- [x] **Step 2: Run adapter tests and verify RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_adapter.py -q
```

Expected: the deliberately different `id`/`dt` fixture resolves to the old wrong date or the zone exception is swallowed as an empty result.

- [x] **Step 3: Use native `dt` and fail closed on mapping ambiguity**

Normalize a native datetime as follows:

```python
def _native_datetime(value: object) -> str:
    timestamp = getattr(value, "dt")
    parsed = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(str(timestamp))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI).isoformat(timespec="seconds")
```

Use this function for `FX.dt`, `BI.fx_a.dt`, `BI.fx_b.dt`, and the observing extreme. Validate exact membership, preserve endpoint prices and direction, and remove timestamp decisions based on `elements[].id` or nearest-bar lookup. In `structures.py`, validate every native BI reference and let `StructureMappingError` escape. Catch that exception in `ChanlunAdapter.analyze` and build an unavailable response containing the original bars and no structure layers.

- [x] **Step 4: Run adapter and service tests and verify GREEN**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_adapter.py tests/test_chanlun_service.py -q
.venv/bin/ruff check app/services/chanlun/adapter.py app/services/chanlun/structures.py tests/test_chanlun_adapter.py
```

Expected: exact endpoint tests pass, invalid native mappings are unavailable, and normal empty zone sequences remain valid empty output.

- [x] **Step 5: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/services/chanlun/adapter.py apps/api/app/services/chanlun/structures.py apps/api/tests/test_chanlun_adapter.py
git commit -m "fix(chanlun): map native endpoints by timestamp"
```

### Task 5: Freeze Golden Samples and Add Reproducible Validation

**Files:**
- Create: `apps/api/tests/fixtures/chanlun/golden/inclusion_synthetic.json`
- Create: `apps/api/tests/fixtures/chanlun/golden/300308_SZ_1d.json`
- Create: `apps/api/tests/fixtures/chanlun/golden/600000_SH_1d.json`
- Create: `apps/api/tests/fixtures/chanlun/golden/300308_SZ_60m.json`
- Create: `apps/api/tests/fixtures/chanlun/golden/600000_SH_60m.json`
- Create: `apps/api/tests/test_chanlun_golden.py`
- Create: `apps/api/scripts/run_chanlun_golden_validation.py`

**Interfaces:**
- Fixture schema contains `schema_version`, `symbol`, `period`, `lookback`, `source`, `adjustment_mode`, `czsc_version`, `rule_version`, `bars`, `fractals`, `strokes`, `zones`, `confirmed_at`, `reviewed_by`, `reviewed_at`, `review_status`, and `review_notes`.
- Produces `load_golden_fixture(path: Path) -> GoldenFixture` and `validate_golden_fixture(path: Path) -> GoldenFixtureResult`; tests use `GOLDEN_FIXTURE_DIR / "300308_SZ_1d.json"` rather than an adapter-generated expected value. The CLI writes a deterministic Markdown report with exact match counts, coverage, truncation stability, and rule version.
- Does not regenerate expected labels from the adapter during test setup.

- [x] **Step 1: Write the fixture loader and failing exact-match tests**

Implement a loader that rejects missing `review_status="approved"`, malformed bars, unsupported periods, and missing expected structure arrays. Add tests that compare every timestamp, price, direction, status, and zone bound rather than only list lengths:

```python
def test_golden_fixture_rejects_an_unapproved_label_file(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, review_status="pending")

    with pytest.raises(ValueError, match="review_status"):
        load_golden_fixture(path)


def test_golden_result_requires_exact_stroke_coordinates() -> None:
    result = validate_golden_fixture(GOLDEN_300308_DAILY)

    assert result.stroke_coordinate_mismatches == 0
    assert result.zone_coordinate_mismatches == 0
    assert result.early_confirmations == 0
    assert result.confirmed_coordinate_drifts == 0
```

- [x] **Step 2: Run the fixture tests and verify RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_golden.py -q
```

Expected: import or fixture-schema failures because the loader, fixtures, and report command do not exist.

- [x] **Step 3: Capture and independently review the four real samples**

Freeze exactly 220 canonical closed bars for `300308.SZ` and `600000.SH` at daily and 60-minute periods. Store no live response or generated expected labels; store the bars and manually reviewed expected structures. The reviewer must verify each fractal extreme, each adjacent stroke endpoint, and each confirmed zone overlap against the frozen bars, then set:

```json
{
  "reviewed_by": "manual-reviewer",
  "reviewed_at": "2026-07-30T16:00:00+08:00",
  "review_status": "approved",
  "review_notes": "逐项核对分型、笔端点和中枢三笔重叠区"
}
```

The synthetic fixture must contain a deliberate inclusion chain where a native `id` differs from the endpoint bar represented by native `dt`. Each real fixture must contain at least one inclusion chain, both stroke directions, and one confirmed zone; choose a frozen window that meets those criteria rather than accepting an empty-zone sample.

- [x] **Step 4: Implement exact matching and truncation stability**

Compare frozen expected structures against adapter output with `1e-6` price tolerance and exact timestamp/enum equality. For every expected structure, replay prefixes from the minimum required bar count through the full fixture; assert no structure is emitted before its recorded `confirmed_at`, and after confirmation its ID, coordinates, and zone bounds match the frozen label. Keep segments, divergences, and signals excluded from this validator.

- [x] **Step 5: Implement the deterministic validation report CLI**

Create `run_chanlun_golden_validation.py` with `argparse` options `--fixture-dir` and `--output`. It must sort fixture paths, run the same `validate_golden_fixture` function used by tests, and write stable Markdown rows for fixture name, symbol, period, bar count, coverage status, fractal matches, stroke matches, zone matches, early confirmations, coordinate drifts, and rule version. Exit `0` only when every fixture passes and `1` otherwise.

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python scripts/run_chanlun_golden_validation.py \
  --fixture-dir tests/fixtures/chanlun/golden \
  --output /tmp/chanlun-golden-report.md
```

Expected: five passing fixtures and a reproducible report; the report must not include current-time values or network response ordering.

- [x] **Step 6: Promote the rule version only after all fixtures pass**

Keep `VISUAL_RULE_VERSION` as `cl-v2-visual` while any fixture fails. After the five fixtures and truncation tests pass, change it to `cl-v3-validated` and update the model/TypeScript fixture assertions to require that version.

- [x] **Step 7: Run golden tests and commit**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_chanlun_golden.py tests/test_chanlun_adapter.py -q
.venv/bin/ruff check app/services/chanlun/structures.py scripts/run_chanlun_golden_validation.py tests/test_chanlun_golden.py
```

Then commit:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/tests/fixtures/chanlun/golden apps/api/tests/test_chanlun_golden.py apps/api/scripts/run_chanlun_golden_validation.py apps/api/app/services/chanlun/structures.py apps/api/tests/test_chanlun_adapter.py
git commit -m "test(chanlun): freeze validated structure samples"
```

### Task 6: Wire the Backfill HTTP Contract

**Files:**
- Modify: `apps/api/app/main.py:2665-2708`
- Modify: `apps/api/tests/test_api.py:2511-2527`
- Modify: `apps/web-vue/src/service/product-api.ts:1520-1555`
- Modify: `apps/web-vue/src/service/types.ts:1886-1890`

**Interfaces:**
- `POST /api/chanlun/stocks/{symbol}/backfill` passes `request.periods`, `request.lookback`, and `request.history_days` into `ChanlunAnalysisService.backfill`.
- The background-job result contains `requested_bars`, `written_bars`, and per-period coverage payloads.
- Existing active-job deduplication remains keyed by normalized symbol.

- [x] **Step 1: Write the failing HTTP contract test**

Extend `BlockingChanlunService` to record the parameters it receives and assert:

```python
response = client.post(
    "/api/chanlun/stocks/600000.SH/backfill",
    json={"periods": ["60m"], "lookback": 220, "history_days": 90},
)

assert response.status_code == 200
assert service.backfill_requests == [(
    "600000.SH", ("60m",), 220, 90,
)]
```

- [x] **Step 2: Run the API test and verify RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_api.py::test_chanlun_backfill_reuses_active_symbol_job_and_reports_status -q
```

Expected: the fake service receives no new request fields because the current lambda only passes the symbol and callbacks.

- [x] **Step 3: Pass request fields through the job and client**

Change the job lambda to call:

```python
_chanlun_analysis_service().backfill(
    normalized_symbol,
    periods=tuple(request.periods),
    lookback=request.lookback,
    history_days=request.history_days,
    progress=progress,
    should_cancel=should_cancel,
)
```

Serialize only provided optional `history_days` from `createChanlunBackfillJob`; always send `periods` and `lookback` from the workbench. Keep the response polling function unchanged except for the richer `result` type.

- [x] **Step 4: Run API and frontend checks**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest tests/test_api.py::test_chanlun_backfill_reuses_active_symbol_job_and_reports_status -q
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm typecheck
```

Expected: the request recorder sees the exact tuple and TypeScript compiles.

- [x] **Step 5: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/api/app/main.py apps/api/tests/test_api.py apps/web-vue/src/service/product-api.ts apps/web-vue/src/service/types.ts
git commit -m "fix(chanlun): honor backfill request parameters"
```

### Task 7: Make Stock and Chanlun Pages Use Truthful Canonical Bars

**Files:**
- Modify: `apps/web-vue/src/utils/domain/stockViewState.ts`
- Modify: `apps/web-vue/src/utils/domain/stockViewState.test.ts`
- Modify: `apps/web-vue/src/views/StockView.vue`
- Modify: `apps/web-vue/src/views/ChanlunView.vue`
- Modify: `apps/web-vue/src/views/ChanlunView.test.ts`

**Interfaces:**
- Produces `selectCanonicalStockBars(fallbackBars: KlineBar[], analysis: ChanlunAnalysisResponse | null, period: StockKlinePeriod | "weekly"): KlineBar[]`.
- Produces `hasCanonicalBarDates(bars: KlineBar[], analysis: ChanlunAnalysisResponse | null): boolean` for overlay coordinate validation.
- Supported stock periods use analysis bars when present; weekly always uses the fallback K-line bars.
- Overlay availability is `true` only for `analysis.availability === "ready"`; stale/insufficient/unavailable data may still provide fallback price bars but never render Chanlun layers.
- Workbench exposes `createChanlunBackfillJob` and `getChanlunBackfillJob` through a local polling state without changing the order-confirmation flow.

- [x] **Step 1: Write failing canonical-bar and UI-state tests**

Add to `stockViewState.test.ts`:

```ts
it('uses analysis bars as the supported-period chart coordinate source', () => {
  const fallback = [{ date: '2026-07-30T15:00:00+08:00', close: 10 } as KlineBar];
  const analysis = { availability: 'ready', bars: [{ date: '2026-07-30T15:00:00+08:00', close: 11 }] } as ChanlunAnalysisResponse;

  expect(selectCanonicalStockBars(fallback, analysis, '60m')[0].close).toBe(11);
});

it('keeps weekly charts on the stock K-line source', () => {
  const fallback = [{ date: '2026-07-30T15:00:00+08:00', close: 10 } as KlineBar];
  const analysis = { availability: 'ready', bars: [{ date: '2026-07-30T15:00:00+08:00', close: 11 }] } as ChanlunAnalysisResponse;

  expect(selectCanonicalStockBars(fallback, analysis, 'weekly')[0].close).toBe(10);
});
```

Extend `ChanlunView.test.ts` to assert that a response with `coverage.backfill_required=true` shows the backfill command, sends `periods=["5m","30m","60m"]` and `lookback=220`, and disables segments/divergences/signals. Add a stale response case where the K-line chart remains mounted but the Chanlun overlay prop is `null`.

- [x] **Step 2: Run frontend tests and verify RED**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm exec vitest run src/utils/domain/stockViewState.test.ts src/views/ChanlunView.test.ts
```

Expected: the canonical selector and backfill/layer assertions fail against the current two-source chart and always-enabled checkboxes.

- [x] **Step 3: Select canonical bars in StockView**

Implement:

```ts
export function selectCanonicalStockBars(
  fallbackBars: KlineBar[],
  analysis: ChanlunAnalysisResponse | null,
  period: StockKlinePeriod | 'weekly',
): KlineBar[] {
  if (period !== 'weekly' && analysis?.bars?.length) return analysis.bars;
  return fallbackBars;
}
```

Use it before `buildStockViewChartBars`; retain the stock K-line response for GSGF annotations and the fallback path. Set `chartChanlun` to `null` unless the analysis is `ready` and its `bars` dates exactly equal the displayed canonical dates. Keep weekly out of the Chanlun request and overlay path.

- [x] **Step 4: Add truthful workbench layer and backfill state**

In `ChanlunView.vue`, initialize `layers.segments`, `layers.divergences`, and `layers.signals` to `false`, define `validatedLayerKeys = new Set(['fractals', 'strokes', 'zones'])`, and render the checkbox `disabled` when the key is not validated or `analysis?.availability !== 'ready'`. Display “尚未通过黄金样本验证” for segments, divergences, and signals. Display coverage counts/reason and a “补齐分钟历史” button when `coverage.backfill_required` is true. Poll the returned `BackgroundJobState` every 1 second, stop on `success`, `failed`, or `canceled`, reload the workspace on success, and show the job error on failure. Read `latest_signal` and `latest_divergence` in period summaries; show “未启用” for disabled derived layers.

- [x] **Step 5: Run frontend tests and typecheck**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm exec vitest run src/utils/domain/stockViewState.test.ts src/views/ChanlunView.test.ts src/utils/charts/chanlunOverlay.test.ts
pnpm typecheck
```

Expected: canonical bars, stale overlay suppression, backfill polling, and disabled-layer tests pass.

- [x] **Step 6: Commit**

```bash
cd /Users/kale/Documents/strong-stock-screener
git add apps/web-vue/src/utils/domain/stockViewState.ts apps/web-vue/src/utils/domain/stockViewState.test.ts apps/web-vue/src/views/StockView.vue apps/web-vue/src/views/ChanlunView.vue apps/web-vue/src/views/ChanlunView.test.ts
git commit -m "fix(chanlun): use canonical bars and honest layer states"
```

### Task 8: Run Full Verification and Record the Release Boundary

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-chanlun-structure-correctness.md` to mark completed steps and record the verification output.
- Do not modify: `.superpowers/sdd/task-1-report.md`, `.superpowers/sdd/task-5-report.md`, or untracked `apps/web/`.

**Interfaces:**
- Produces a passing backend/frontend verification record and the Markdown golden report from Task 5.
- Does not enable segments, divergences, signals, alerts, backtests, screening scores, or paper-order decisions.

- [x] **Step 1: Run the complete backend suite and lint**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/pytest -q
.venv/bin/ruff check app tests
```

Expected: all backend tests pass and Ruff reports no errors.

- [x] **Step 2: Run the complete frontend suite, typecheck, and build**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web-vue
pnpm exec vitest run
pnpm typecheck
pnpm build
```

Expected: all frontend tests pass, typecheck succeeds, and the production build completes.

- [x] **Step 3: Run the golden report and live invariant checks**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/api
.venv/bin/python scripts/run_chanlun_golden_validation.py \
  --fixture-dir tests/fixtures/chanlun/golden \
  --output /tmp/chanlun-golden-report.md
```

Verify the report has five passing fixtures, zero endpoint/zone mismatches, zero early confirmations, zero post-confirmation coordinate drifts, and the expected rule version. For `300308.SZ` and `600000.SH`, also verify the API response has no duplicate zones, no virtual zones, no derived trading layers, and no `ready` response when the minute archive contains an internal gap.

- [x] **Step 4: Record and commit the verification boundary**

Update only the checkbox state and verification record in this plan. The record must list the exact test commands, fixture count, rule version, and the explicit deferred layers. Then commit:

```bash
cd /Users/kale/Documents/strong-stock-screener
git add docs/superpowers/plans/2026-07-30-chanlun-structure-correctness.md
git commit -m "docs(chanlun): record correctness phase verification"
```

The phase is complete only when the frozen samples, coverage audit, canonical bar selection, and full test suites pass together. The next plan must separately establish golden samples for line segments, divergences, and buy/sell points before any of those layers can be enabled.

### Verification Record (2026-07-30)

- Backend: `.venv/bin/pytest -q` -> `1387 passed, 1 skipped in 38.13s`.
- Backend lint: `.venv/bin/ruff check app tests` -> `All checks passed!`.
- Frontend: `pnpm exec vitest run` -> `38 files passed, 250 tests passed`.
- Frontend typecheck: `pnpm typecheck` -> exit code `0`.
- Frontend build: `pnpm build` -> `Build successful`.
- Golden validation: five fixtures passed with exact fractal/stroke/zone coordinates, `Early=0`, `Drifts=0`, and rule version `cl-v3-validated`.
- Post-promotion focused checks: backend golden/adapter tests `21 passed`; frontend Chanlun/stock-state tests `14 passed`.
- The first concurrent full-suite attempt exposed a scheduling-sensitive failure in the pre-existing noisy-worker benchmark test. The test passed in isolation and in eight consecutive repetitions; a subsequent full backend run passed completely.
- Deferred by design: line segments, divergences, buy/sell points, alerts, screening scores, backtests, and paper-order decisions remain disabled until separate golden fixtures and no-future-function validation exist.
