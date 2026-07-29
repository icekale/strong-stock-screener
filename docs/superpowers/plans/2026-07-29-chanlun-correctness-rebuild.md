# Chanlun Correctness Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop incorrect Chanlun structures from reaching decision features, replace approximate zones with CZSC's maintained zone sequence, fail closed on stale bars, and make the workbench chart preserve the selected period and zoom state.

**Architecture:** Keep CZSC as the owner of inclusion handling, fractals, and strokes. A focused project adapter maps CZSC's `get_zs_seq` output into display-only confirmed zones; custom segments and custom buy/sell signals remain disabled until separate golden-fixture validation exists. Data freshness is propagated through the public analysis response so alerts, replay, backtests, screening, and paper orders all fail closed.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, `czsc==0.10.12`, pytest, Vue 3, TypeScript, Ant Design Vue, ECharts 6, Vitest.

## Global Constraints

- Preserve the existing strong-stock, auction, ETF, sentiment, and GSGF behavior.
- Do not consume `stale`, `insufficient_bars`, or `unavailable` Chanlun analysis in alerts or paper-order decisions.
- Do not expose custom segments, divergence, or buy/sell points as confirmed until golden fixtures validate them.
- Do not merge `codex/chanlun-chart-correctness`; use it only as historical reference.
- Keep all changes within the tracked Vue frontend and the `apps/api/app/services/chanlun/` domain plus their tests.

---

### Task 1: Replace Approximate Zones and Gate Unvalidated Structures

**Files:**
- Create: `apps/api/app/services/chanlun/structures.py`
- Modify: `apps/api/app/services/chanlun/adapter.py`
- Modify: `apps/api/app/services/chanlun/service.py`
- Test: `apps/api/tests/test_chanlun_adapter.py`
- Test: `apps/api/tests/test_chanlun_service.py`

**Interfaces:**
- Consumes: `native.finished_bis`, mapped `(native_bi, ChanlunStroke)` pairs, and `czsc.utils.sig.get_zs_seq`.
- Produces: `map_confirmed_zones(completed_pairs) -> list[ChanlunZone]` and rule version `cl-v2-visual`.

- [ ] **Step 1: Write failing adapter tests**

Add tests proving that official CZSC zone groups map once, groups shorter than three strokes are ignored, confirmed and virtual zones never duplicate, and output segments/divergences/signals are empty while the correctness gate is active.

- [ ] **Step 2: Verify RED**

Run: `/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests/test_chanlun_adapter.py -q`

Expected: failures showing duplicate virtual zones and custom segments/signals are still emitted.

- [ ] **Step 3: Implement the minimal mapping layer**

Use `get_zs_seq` rather than `native.zs_list` or sliding three-stroke overlap. Require at least three native strokes and `zone.is_valid`; map `zd`/`zg` as low/high and native BI endpoints as the time range. Remove the call sites for `_segments`, `_virtual_zone`, and `derive_confirmed_events` from the active response path. Append source status explaining that segments and trading signals are disabled pending validation.

- [ ] **Step 4: Verify GREEN**

Run: `/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests/test_chanlun_adapter.py apps/api/tests/test_chanlun_service.py -q`

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/chanlun/structures.py apps/api/app/services/chanlun/adapter.py apps/api/app/services/chanlun/service.py apps/api/tests/test_chanlun_adapter.py apps/api/tests/test_chanlun_service.py
git commit -m "fix(chanlun): gate unvalidated structures"
```

### Task 2: Propagate Freshness and Fail Closed

**Files:**
- Modify: `apps/api/app/services/chanlun/service.py`
- Modify: `apps/api/app/services/chanlun/alert_service.py`
- Test: `apps/api/tests/test_chanlun_service.py`
- Test: `apps/api/tests/test_chanlun_alerts.py`
- Test: `apps/api/tests/test_chanlun_paper.py`

**Interfaces:**
- Consumes: `_ClosedPeriodData.freshness`.
- Produces: public `ChanlunAnalysisResponse.availability="stale"` whenever complete bars are older than `_expected_latest_close`.

- [ ] **Step 1: Write failing stale-data tests**

Add an analysis-level test where the provider succeeds but the latest completed bar is behind the expected close, then assert `analysis.availability == "stale"`. Add an alert test proving stale input does not call `store.observe`.

- [ ] **Step 2: Verify RED**

Run: `/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests/test_chanlun_service.py apps/api/tests/test_chanlun_alerts.py -q`

Expected: the successful-but-old payload is still reported as `ready`, and stale alerts are accepted.

- [ ] **Step 3: Implement fail-closed propagation**

In `_analyze_closed_period_data`, convert a ready adapter result to stale whenever `period_data.freshness == "stale"`, independent of whether the live call raised. Restrict alert refresh to `availability == "ready"`; keep paper-order rejection on any non-ready period.

- [ ] **Step 4: Verify GREEN**

Run: `/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests/test_chanlun_service.py apps/api/tests/test_chanlun_alerts.py apps/api/tests/test_chanlun_paper.py -q`

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/chanlun/service.py apps/api/app/services/chanlun/alert_service.py apps/api/tests/test_chanlun_service.py apps/api/tests/test_chanlun_alerts.py apps/api/tests/test_chanlun_paper.py
git commit -m "fix(chanlun): reject stale analysis inputs"
```

### Task 3: Preserve Workbench Period and Chart Zoom

**Files:**
- Modify: `apps/web-vue/src/views/ChanlunView.vue`
- Modify: `apps/web-vue/src/components/charts/EChart.vue`
- Modify: `apps/web-vue/src/components/charts/StockKlineChart.vue`
- Modify: `apps/web-vue/src/utils/charts/klineOverlayOption.ts`
- Modify: `apps/web-vue/src/utils/charts/chanlunOverlay.ts`
- Test: `apps/web-vue/src/components/charts/EChart.test.ts`
- Test: `apps/web-vue/src/utils/charts/chanlunOverlay.test.ts`
- Create: `apps/web-vue/src/views/ChanlunView.test.ts`

**Interfaces:**
- Produces: `EChart` event `datazoom`, retained ECharts zoom during option updates, and request-generation guards for period/symbol loads.

- [ ] **Step 1: Write failing UI-state tests**

Test that changing symbols while a non-daily period is selected loads that same period, that an older request cannot overwrite the latest selection, and that `datazoom` is emitted and does not require `setOption(..., true)`.

- [ ] **Step 2: Verify RED**

Run: `pnpm exec vitest run src/components/charts/EChart.test.ts src/utils/charts/chanlunOverlay.test.ts src/views/ChanlunView.test.ts`

- [ ] **Step 3: Implement minimal request and chart state handling**

Use a monotonically increasing request token in `ChanlunView`; load workspace summaries and then fetch the currently selected period when it is not daily. Emit normalized zoom ranges from `EChart`, use merge-by-series-id updates, and pass visible bar count into overlay generation so labels respond to the visible range.

- [ ] **Step 4: Replace deprecated alert props**

Change Ant Design Vue alert bindings from `message` to `title` in the workbench.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
pnpm exec vitest run src/components/charts/EChart.test.ts src/utils/charts/chanlunOverlay.test.ts src/views/ChanlunView.test.ts
pnpm typecheck
```

- [ ] **Step 6: Commit**

```bash
git add apps/web-vue/src/views/ChanlunView.vue apps/web-vue/src/views/ChanlunView.test.ts apps/web-vue/src/components/charts/EChart.vue apps/web-vue/src/components/charts/EChart.test.ts apps/web-vue/src/components/charts/StockKlineChart.vue apps/web-vue/src/utils/charts/klineOverlayOption.ts apps/web-vue/src/utils/charts/chanlunOverlay.ts apps/web-vue/src/utils/charts/chanlunOverlay.test.ts
git commit -m "fix(chanlun): preserve chart selection and zoom"
```

### Task 4: Verification and Follow-up Boundary

**Files:**
- Modify: `docs/superpowers/plans/2026-07-29-chanlun-correctness-rebuild.md`

- [ ] **Step 1: Run backend verification**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests/test_chanlun_*.py -q
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/ruff check apps/api/app/services/chanlun apps/api/tests/test_chanlun_*.py
```

- [ ] **Step 2: Run frontend verification**

```bash
cd apps/web-vue
pnpm exec vitest run
pnpm typecheck
pnpm build
```

- [ ] **Step 3: Validate live invariants against recorded API bars**

For `300308.SZ` and `600000.SH`, verify: no overlapping duplicate zone records, no virtual/confirmed duplicate bounds, no custom segments or trading signals, and stale intraday bars are not marked ready.

- [ ] **Step 4: Record the next independent phase**

Do not re-enable segments or trading signals in this plan. The next plan must establish manually reviewed golden fixtures and truncation-stability tests before implementing line segments, divergence, or buy/sell points. Treat 15-minute and 90-minute period semantics as a separate data-contract task rather than copying the old branch.

