# Homepage Capital and ETF Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the duplicated homepage sector trend with fast capital summaries and add a source-transparent ETF capital radar at `/etf-radar`.

**Architecture:** Keep remote exchange access behind a small provider, calculations in a pure service module, and JSON persistence in an atomic store rooted at `STRONG_STOCK_DATA_DIR/capital-signals`. FastAPI serves a cached homepage projection and richer radar endpoints; the Next.js homepage loads only the projection, while the ETF page lazy-loads history and disclosure views.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, Next.js 14, React 18, TypeScript, Ant Design, ECharts, Node test runner.

---

## File Map

- `apps/api/app/models.py`: Pydantic request/response contracts shared by services and API routes.
- `apps/api/app/providers/capital_signals.py`: SSE/SZSE margin and ETF share HTTP clients plus payload parsers.
- `apps/api/app/services/capital_signal_store.py`: atomic JSON persistence under `capital-signals/`.
- `apps/api/app/services/capital_signals.py`: pure evidence calculations, snapshot assembly, cache fallback, and public service methods.
- `apps/api/app/main.py`: dependency construction, cache registration, and five read-only routes.
- `apps/api/tests/test_capital_signal_store.py`: JSON round-trip and corrupt-cache behavior.
- `apps/api/tests/test_capital_signal_providers.py`: official payload parsing, date handling, and partial-source behavior.
- `apps/api/tests/test_capital_signals.py`: robust z-score, estimated subscription, stage, synchronization, and fallback behavior.
- `apps/api/tests/test_api.py`: route schemas and injected-service cache behavior.
- `apps/web/lib/types.ts`: API response types.
- `apps/web/lib/api.ts`: capital summary and ETF radar clients.
- `apps/web/lib/capitalSignals.ts`: semantic tone, formatting, and chart projection helpers.
- `apps/web/lib/capitalSignals.test.ts`: positive/negative/zero/missing semantics and projections.
- `apps/web/app/MarketOverviewWorkbench.tsx`: remove sector/emotion trend requests and load capital summary independently.
- `apps/web/app/page.tsx`: homepage skeleton matching the new composition.
- `apps/web/components/overview/CapitalSignalPanels.tsx`: financing balance and ETF radar summary cards.
- `apps/web/components/overview/SectorHeatmapPreview.tsx`: retain the sole homepage sector visualization with bidirectional flow bars.
- `apps/web/app/etf-radar/page.tsx`: route shell and lazy client workspace.
- `apps/web/app/etf-radar/EtfRadarWorkspace.tsx`: four ETF radar views with local loading and stale states.
- `apps/web/app/market/MarketWorkspace.tsx`: add an ETF funds entry that navigates to `/etf-radar`.
- `apps/web/lib/appNavigation.ts`: classify the hidden detail route under the market group without adding a sidebar item.
- `apps/web/app/globals.css`: responsive capital panels, semantic colors, tables, and charts.
- `apps/web/lib/marketOverview.test.ts`: homepage structural and request assertions.
- `apps/web/lib/appNavigation.test.ts`: hidden route selection assertion.
- `apps/web/lib/marketWorkspace.test.ts`: ETF entry navigation assertion.

### Task 1: Domain Models, Calculations, and Store

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/capital_signals.py`
- Create: `apps/api/app/services/capital_signal_store.py`
- Create: `apps/api/tests/test_capital_signals.py`
- Create: `apps/api/tests/test_capital_signal_store.py`

- [ ] **Step 1: Write failing calculation tests**

Add tests that construct daily share rows and assert:

```python
def test_estimated_subscription_uses_share_delta_times_close() -> None:
    result = build_share_change(current_shares=12_000_000, previous_shares=10_000_000, close=4.25)
    assert result.share_change == 2_000_000
    assert result.estimated_subscription_cny == 8_500_000


def test_missing_previous_shares_stays_missing_instead_of_zero() -> None:
    result = build_share_change(current_shares=12_000_000, previous_shares=None, close=4.25)
    assert result.share_change is None
    assert result.estimated_subscription_cny is None


def test_robust_score_uses_median_absolute_deviation() -> None:
    assert robust_z_score(16, [9, 10, 10, 11, 12]) > 2


def test_synchronization_excludes_missing_etfs_from_denominator() -> None:
    result = synchronization_ratio([True, False, None, True])
    assert result.positive_count == 2
    assert result.valid_count == 3
```

- [ ] **Step 2: Run calculation tests and verify RED**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signals.py -q`

Expected: collection fails because `app.services.capital_signals` does not exist.

- [ ] **Step 3: Add minimal Pydantic contracts and pure calculations**

Add literals `CapitalSignalStage`, `CapitalSourceState`, and models for margin points, ETF share points, factor evidence, ETF rows, holder rows, source statuses, homepage summary, overview, history, holders, and methodology. Every top-level response contains `generated_at`, `trade_date`, `as_of`, `signal_stage`, `model_version`, and `source_status`.

Implement:

```python
MODEL_VERSION = "heuristic-v1"

def build_share_change(*, current_shares: float, previous_shares: float | None, close: float | None) -> EtfShareChange:
    if previous_shares is None:
        return EtfShareChange(share_change=None, estimated_subscription_cny=None)
    delta = current_shares - previous_shares
    return EtfShareChange(
        share_change=delta,
        estimated_subscription_cny=delta * close if close is not None else None,
    )

def robust_z_score(value: float | None, history: list[float]) -> float | None:
    if value is None or len(history) < 3:
        return None
    median = statistics.median(history)
    mad = statistics.median(abs(item - median) for item in history)
    return None if mad == 0 else (value - median) / (1.4826 * mad)
```

Keep evidence scoring deterministic and bounded to 0..100. Missing factors contribute neither score nor denominator; return `valid_factor_count` so the UI can expose coverage.

- [ ] **Step 4: Run calculation tests and verify GREEN**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signals.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing store tests**

Cover atomic round-trip, absent files returning defaults, corrupt JSON returning defaults, and history retention capped at 400 points.

- [ ] **Step 6: Run store tests and verify RED**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signal_store.py -q`

Expected: collection fails because `CapitalSignalStore` is missing.

- [ ] **Step 7: Implement the atomic JSON store**

Use `RLock`, `model_validate_json`, and `path.with_suffix(path.suffix + ".tmp").replace(path)`. Expose typed methods for `margin-history.json`, `etf-share-history.json`, `etf-holder-reports.json`, and `etf-radar-snapshot.json`; never convert missing values to zero.

- [ ] **Step 8: Run focused backend tests and commit**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signals.py apps/api/tests/test_capital_signal_store.py -q`

Expected: all pass.

Commit: `feat: add capital signal domain and store`

### Task 2: Official Exchange Providers

**Files:**
- Create: `apps/api/app/providers/capital_signals.py`
- Create: `apps/api/tests/test_capital_signal_providers.py`

- [ ] **Step 1: Write failing provider parser tests**

Use inline SSE/SZSE fixture dictionaries, not live network requests. Assert:

```python
def test_sse_margin_parser_normalizes_yuan_values_and_trade_date() -> None:
    rows = parse_sse_margin_payload(SSE_MARGIN_FIXTURE)
    assert rows[0].trade_date == "2026-07-17"
    assert rows[0].financing_balance_cny == 9_001_000_000


def test_sse_share_parser_keeps_exchange_trade_date_without_utc_shift() -> None:
    rows = parse_sse_etf_share_payload(SSE_SHARE_FIXTURE, symbol="510300.SH")
    assert rows[0].trade_date == "2026-07-17"


def test_szse_current_share_parser_does_not_invent_history() -> None:
    rows = parse_szse_etf_share_payload(SZSE_SHARE_FIXTURE, trade_date="2026-07-17")
    assert [row.symbol for row in rows] == ["159915.SZ"]
    assert rows[0].trade_date == "2026-07-17"
```

- [ ] **Step 2: Run provider tests and verify RED**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signal_providers.py -q`

Expected: collection fails because the provider module does not exist.

- [ ] **Step 3: Implement payload parsers and HTTP provider**

Create `OfficialCapitalDataProvider` with an injected `httpx.Client`. Use exchange referer/user-agent headers, `raise_for_status()`, exact field-name maps documented beside each parser, decimal/comma normalization, and date parsing that never passes date-only values through UTC conversion.

Expose:

```python
def get_margin_rows(self, trade_date: str | None = None) -> list[MarginMarketPoint]: ...
def get_etf_share_rows(self, trade_date: str, symbols: Sequence[str]) -> list[EtfSharePoint]: ...
```

Each market is fetched independently. Return successful rows plus source states; do not discard SSE data when SZSE fails.

- [ ] **Step 4: Run provider tests and verify GREEN**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signal_providers.py -q`

Expected: all pass.

- [ ] **Step 5: Run Ruff and commit**

Run: `cd apps/api && .venv/bin/ruff check app/providers/capital_signals.py tests/test_capital_signal_providers.py`

Expected: no errors.

Commit: `feat: ingest official margin and ETF share data`

### Task 3: Cached Capital Service and FastAPI Routes

**Files:**
- Modify: `apps/api/app/services/capital_signals.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_capital_signals.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing service fallback tests**

Inject a fake provider and clock. Assert that a fresh snapshot is persisted, a provider failure returns the persisted snapshot with `stale` source status, an empty store plus provider failure returns an unavailable projection instead of raising on the homepage, and history/holders endpoints do not run during `homepage_summary()`.

- [ ] **Step 2: Run service tests and verify RED**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signals.py -q`

Expected: fails because `CapitalSignalService` is missing.

- [ ] **Step 3: Implement minimal service orchestration**

Use the seven-symbol versioned core pool from the design. Build margin totals by trade date, daily share deltas, estimated subscription amount, robust score, direction consistency, effective ETF counts, evidence labels, and `intraday`/`post_close` stages. The homepage method reads the last snapshot first and refreshes only when expired; detail history and holder reports are separate calls.

The first implementation may leave unavailable TickFlow-only factors as `None`, but must list them in methodology and must not award score for them.

- [ ] **Step 4: Run service tests and verify GREEN**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signals.py -q`

Expected: all pass.

- [ ] **Step 5: Write failing API tests**

Inject `app.state.capital_signal_service` in `_client`. Assert 200 responses and top-level metadata for:

```text
GET /api/market/capital-summary
GET /api/etf-radar/overview
GET /api/etf-radar/history?days=120
GET /api/etf-radar/holders
GET /api/etf-radar/methodology
```

Assert `days=0` and `days=366` return 422, and that two homepage calls reuse the service snapshot/cache.

- [ ] **Step 6: Run API tests and verify RED**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_api.py -k 'capital_summary or etf_radar' -q`

Expected: 404 for the new routes.

- [ ] **Step 7: Wire dependencies, cache, and routes**

Construct provider/store/service lazily from `get_settings().data_dir`, allow `app.state.capital_signal_service` injection, register a 60-second `TtlCache` in the `home` group, and return Pydantic response models. Keep route handlers synchronous to match current providers and tests.

- [ ] **Step 8: Run focused API tests and commit**

Run: `apps/api/.venv/bin/pytest apps/api/tests/test_capital_signals.py apps/api/tests/test_capital_signal_providers.py apps/api/tests/test_capital_signal_store.py apps/api/tests/test_api.py -k 'capital or etf_radar' -q`

Expected: all selected tests pass.

Commit: `feat: expose cached capital and ETF radar APIs`

### Task 4: Frontend Contracts, Homepage Composition, and Semantic Colors

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/lib/capitalSignals.ts`
- Create: `apps/web/lib/capitalSignals.test.ts`
- Create: `apps/web/components/overview/CapitalSignalPanels.tsx`
- Modify: `apps/web/app/MarketOverviewWorkbench.tsx`
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: Write failing semantic helper tests**

Assert positive values map to `rise` and include `+`/`▲`, negative values map to `fall` and include `-`/`▼`, zero is neutral, `null` formats as `--`, and bidirectional flow widths are normalized from absolute values without changing sign.

- [ ] **Step 2: Run helper tests and verify RED**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/capitalSignals.test.ts`

Expected: module import fails.

- [ ] **Step 3: Implement types, API methods, and pure helpers**

Add frontend types matching Pydantic field names. Add `getCapitalSummary`, `getEtfRadarOverview`, `getEtfRadarHistory`, `getEtfRadarHolders`, and `getEtfRadarMethodology`. Keep helper output independent of React so Node tests run without DOM.

- [ ] **Step 4: Run helper tests and verify GREEN**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/capitalSignals.test.ts`

Expected: all pass.

- [ ] **Step 5: Update structural tests for the approved homepage**

Replace old trend assertions with checks that the workbench imports `CapitalSignalPanels`, calls `getCapitalSummary`, does not call `getSectorReplicaRadar` or `getMarketEmotionSnapshot`, and does not render `MarketTrendPanels`. Assert the skeleton order is sector flow, financing balance, and ETF radar with no sector rotation, emotion trend, market watch ranking, or data status.

- [ ] **Step 6: Run homepage tests and verify RED**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/marketOverview.test.ts`

Expected: old trend composition violates new assertions.

- [ ] **Step 7: Build the new homepage panels**

Load overview, sector flow, sentiment, and capital summary as independent requests. Render a desktop `minmax(0, 1.6fr) minmax(280px, .8fr)` main grid with sector flow left and two compact right panels. On narrow screens stack all three. The ETF summary links to `/etf-radar`; source stages and stale states remain visible but compact.

Remove trend activation, polling, and ECharts imports from the homepage. Keep the sector trend code and API untouched because the market detail page still owns it.

- [ ] **Step 8: Apply A-share semantic colors**

Use existing `--market-rise` red and `--market-fall` green variables. Color all direction-bearing homepage values while retaining signs/arrows. Do not color neutral or missing values. Preserve current Ant Design and product typography.

- [ ] **Step 9: Run focused frontend tests and commit**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/capitalSignals.test.ts lib/marketOverview.test.ts`

Expected: all pass.

Commit: `feat: refocus homepage on capital signals`

### Task 5: ETF Radar Detail Page and Market Entry

**Files:**
- Create: `apps/web/app/etf-radar/page.tsx`
- Create: `apps/web/app/etf-radar/EtfRadarWorkspace.tsx`
- Modify: `apps/web/app/market/MarketWorkspace.tsx`
- Modify: `apps/web/lib/marketWorkspace.ts`
- Modify: `apps/web/lib/appNavigation.ts`
- Modify: `apps/web/lib/appNavigation.test.ts`
- Modify: `apps/web/lib/marketWorkspace.test.ts`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Write failing route and entry tests**

Assert `/etf-radar` maps to `{ groupKey: "market", itemKey: null }`, the sidebar still has no ETF item, and `MarketWorkspace` has an “ETF资金” segmented option whose handler pushes `/etf-radar` rather than coercing it through `normalizeMarketView`.

- [ ] **Step 2: Run navigation tests and verify RED**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/appNavigation.test.ts lib/marketWorkspace.test.ts`

Expected: ETF route/entry assertions fail.

- [ ] **Step 3: Implement hidden route selection and market entry**

Special-case `/etf-radar` as market context with no selected sidebar item. Add the third segmented option and route directly on selection; keep `sectors | heatmap` URL normalization unchanged.

- [ ] **Step 4: Run navigation tests and verify GREEN**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/appNavigation.test.ts lib/marketWorkspace.test.ts`

Expected: all pass.

- [ ] **Step 5: Write failing workspace structure test**

Create a source-level test asserting four tabs (`盘中雷达`, `份额变化`, `持有人披露`, `方法与验证`), local API calls per tab, `证据强度` wording, no `概率`, and a `dynamic()` import boundary for the workspace.

- [ ] **Step 6: Run workspace test and verify RED**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/capitalSignals.test.ts`

Expected: route files are absent.

- [ ] **Step 7: Implement the four-view ETF workspace**

The overview tab shows stage, evidence strength, valid ETF coverage, three evidence lines, and an ETF factor table. The share tab shows daily estimated subscription values and a compact chart loaded only when selected. The holder tab labels rows “国家队持仓披露” and always shows report period/entity. The methodology tab shows model version, pool version, thresholds, source limitations, and factor definitions.

Use tabs rather than stacked cards, table horizontal scrolling on mobile, stable chart height, and `DataState` for loading/error/empty/stale states. Never call a value a probability.

- [ ] **Step 8: Run focused frontend tests and commit**

Run: `cd apps/web && corepack pnpm@9.15.0 test:unit -- lib/capitalSignals.test.ts lib/appNavigation.test.ts lib/marketWorkspace.test.ts`

Expected: all pass.

Commit: `feat: add ETF capital radar workspace`

### Task 6: Full Verification and Visual QA

**Files:**
- Modify only files changed by earlier tasks if verification identifies a regression.

- [ ] **Step 1: Run backend quality gates**

Run:

```bash
cd apps/api
.venv/bin/ruff check app tests
.venv/bin/pytest -q
```

Expected: Ruff passes and the suite passes. If the known one-second concurrency test flakes, rerun it alone and report both results; do not silently ignore it.

- [ ] **Step 2: Run frontend quality gates**

Run:

```bash
cd apps/web
corepack pnpm@9.15.0 test:unit
corepack pnpm@9.15.0 typecheck
corepack pnpm@9.15.0 build
```

Expected: tests, typecheck, and production build pass.

- [ ] **Step 3: Start preview services**

Start the API with the worktree virtual environment on an unused port and Next.js on an unused port with `NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL` pointing to that API. Record both URLs.

- [ ] **Step 4: Perform browser QA**

At desktop and mobile widths verify:

- homepage has only one sector visualization;
- the main grid has no blank lower half or text collision;
- positive/negative values are red/green and retain signs;
- ETF summary opens `/etf-radar`;
- four radar tabs load independently;
- missing values show `--`, stale values are not presented as real time;
- no console errors or hydration warnings appear.

- [ ] **Step 5: Review the final diff and commit fixes**

Run: `git diff --check && git status --short && git diff --stat 46b8573...HEAD`

Expected: no whitespace errors, no unrelated `apps/web/pnpm-workspace.yaml`, and every changed file traces to this feature.

Commit any QA fixes as: `fix: polish capital radar states`

