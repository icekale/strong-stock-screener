# Market Sector Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the market heatmap from the product UI and ensure live sector constituents include industry and current-board theme metadata.

**Architecture:** Keep the existing heatmap backend because other market services reuse its baseline data, but remove all heatmap state and rendering from the Vue market page. Enrich live constituent rows at the API boundary with one batch call to the existing market overview industry provider, while passing the selected board name from the client to populate empty themes.

**Tech Stack:** Vue 3, TypeScript, Vitest, FastAPI, Pydantic, pytest.

## Global Constraints

- Do not delete backend heatmap providers or APIs.
- Do not change sector ranking, intraday chart, or strength calculations.
- Industry enrichment must be batched and must not make the constituent endpoint fail when metadata lookup fails.
- Existing row industry and themes take precedence over supplemental values.

---

### Task 1: Enrich live sector constituent metadata

**Files:**
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/api/app/main.py`

**Interfaces:**
- Consumes: `_market_overview_provider().get_stock_industries(symbols: list[str]) -> dict[str, str]`
- Produces: `/api/sectors/replica/boards/{board_code}/stocks` rows with `industry` and `themes` populated when supplemental data exists.

- [ ] **Step 1: Write failing endpoint tests**

Add one test that injects a live sector provider and a market overview provider returning `{"603137.SH": "装修建材"}`. Request the endpoint with `board_name=装配式建筑` and assert that the live row has `industry == "装修建材"`, `themes == ["装配式建筑"]`, and that the industry provider receives one list containing `603137.SH`.

Add a second test whose industry provider raises an exception. Assert HTTP 200, the original live row remains present, and `source_status` includes a failed industry-supplement entry.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests/test_api.py -k 'sector_replica_board_stocks_endpoint_enriches or sector_replica_board_stocks_endpoint_survives' -q
```

Expected: enrichment assertions fail because the endpoint currently returns `industry: null` and `themes: []`.

- [ ] **Step 3: Implement minimal batch enrichment**

In the successful live-row branch:

1. Collect symbols whose `industry` is empty.
2. Call `get_stock_industries` once when supported.
3. Build copied Pydantic rows preserving existing fields, filling only empty `industry` and `themes`.
4. Append a `StrongStockSourceStatus` describing success, stale coverage, unsupported provider, or failure.
5. Return the enriched rows without changing live quote fields.

- [ ] **Step 4: Run focused and neighboring API tests**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests/test_api.py -k 'sector_replica_board_stocks_endpoint' -q
```

Expected: all sector constituent endpoint tests pass.

### Task 2: Remove heatmap product UI and pass the selected board name

**Files:**
- Modify: `apps/web-vue/src/views/MarketView.test.ts`
- Modify: `apps/web-vue/src/views/MarketView.vue`
- Modify: `apps/web-vue/src/router/product-routes.test.ts`
- Modify: `apps/web-vue/src/router/product-routes.ts`
- Modify: `apps/web-vue/src/locales/langs/zh-cn.ts`
- Modify: `apps/web-vue/src/utils/domain/stockNavigation.test.ts`
- Modify: `apps/web-vue/src/utils/domain/stockNavigation.ts`

**Interfaces:**
- Consumes: `getSectorReplicaBoardStocks(boardCode, { boardName, mode, limit })`
- Produces: a sector-only `/market` page and compatibility redirects from `/heatmap` to `/market`.

- [ ] **Step 1: Write failing frontend tests**

Update `MarketView.test.ts` to resolve a radar response containing plate `{ code: "801220", name: "食品饮料" }`. Assert:

- the rendered view does not contain `市场热图`;
- `getHeatmapTreemap` is never called;
- `getSectorReplicaBoardStocks` receives `"801220"` and an options object containing `boardName: "食品饮料"`.

Update route tests to expect the market title `板块雷达` and `/heatmap` redirect `/market`. Update stock-navigation tests so legacy `from=heatmap` links return to `/market` with label `返回板块雷达`.

- [ ] **Step 2: Run the tests and verify RED**

```bash
pnpm --dir apps/web-vue test:unit -- src/views/MarketView.test.ts src/router/product-routes.test.ts src/utils/domain/stockNavigation.test.ts
```

Expected: tests fail on the existing heatmap tab, old title/redirect, and missing `boardName` option.

- [ ] **Step 3: Implement the sector-only view**

Remove heatmap imports, state, computed options, metrics, request function, conditional template, and query watchers from `MarketView.vue`. Always load sectors on mount. Resolve the selected plate name from `radar.plates` and pass it as `boardName` to the constituent request. Rename the page and route labels to `板块雷达`; keep `/heatmap` as a hidden compatibility redirect to `/market`.

- [ ] **Step 4: Run focused frontend tests and typecheck**

```bash
pnpm --dir apps/web-vue test:unit -- src/views/MarketView.test.ts src/router/product-routes.test.ts src/utils/domain/stockNavigation.test.ts
pnpm --dir apps/web-vue typecheck
```

Expected: all focused tests and TypeScript checks pass.

### Task 3: Full verification

**Files:**
- Verify only; no production files added.

**Interfaces:**
- Consumes: completed API and Vue changes.
- Produces: reproducible test and build evidence.

- [ ] **Step 1: Run API tests**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/pytest apps/api/tests -q
```

- [ ] **Step 2: Run frontend tests and production build**

```bash
pnpm --dir apps/web-vue test:unit
pnpm --dir apps/web-vue build
```

- [ ] **Step 3: Check the final diff**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors, and only files listed in this plan are changed.
