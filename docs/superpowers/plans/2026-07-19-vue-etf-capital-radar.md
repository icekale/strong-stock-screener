# Vue ETF Capital Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the approved homepage capital summaries and ETF capital radar into the production Vue/Soybean workbench served on port 3110.

**Architecture:** Reuse the existing FastAPI capital endpoints and keep all remote data access in the backend. Add typed Vue API clients, a discoverable product route, a lazy four-view ETF workspace, and one cached capital-summary resource on the homepage. Remove the homepage ranking, source-status, and duplicate sector-trend requests so the first screen remains dense and fast.

**Tech Stack:** Vue 3, TypeScript, Vite, Vitest, Ant Design Vue, ECharts, FastAPI.

---

## File Map

- `apps/web-vue/src/service/types.ts`: capital and ETF radar response contracts.
- `apps/web-vue/src/service/product-api.ts`: five read-only capital endpoint clients.
- `apps/web-vue/src/utils/domain/capitalSignals.ts`: direction and financial-value formatting helpers.
- `apps/web-vue/src/router/product-routes.ts`: visible ETF radar menu route.
- `apps/web-vue/src/router/elegant/imports.ts`: lazy route component registration.
- `apps/web-vue/src/views/HomeView.vue`: single sector-flow visualization plus capital summaries.
- `apps/web-vue/src/composables/useHomeDashboard.ts`: overview, sector flow, and capital summary resources only.
- `apps/web-vue/src/views/EtfRadarView.vue`: four lazy data views and responsive tables.
- `apps/web-vue/src/views/MarketView.vue`: direct ETF radar entry from the market workspace.
- `apps/web-vue/src/**/*.test.ts`: route, API, formatting, homepage, and radar regression coverage.

### Task 1: Typed API and Product Route

**Files:**
- Modify: `apps/web-vue/src/service/types.ts`
- Modify: `apps/web-vue/src/service/product-api.ts`
- Create: `apps/web-vue/src/utils/domain/capitalSignals.ts`
- Create: `apps/web-vue/src/utils/domain/capitalSignals.test.ts`
- Modify: `apps/web-vue/src/service/api.test.ts`
- Modify: `apps/web-vue/src/router/product-routes.ts`
- Modify: `apps/web-vue/src/router/product-routes.test.ts`
- Modify: `apps/web-vue/src/router/elegant/imports.ts`

- [ ] **Step 1: Write failing route, API, and formatting tests**

Assert that `/etf-radar` is a visible menu route titled `ETF资金雷达`, each endpoint uses port 8010 through `API_BASE_URL`, positive values format with `▲ +` and negative values with `▼ -`, and missing values remain `--`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/router/product-routes.test.ts src/service/api.test.ts src/utils/domain/capitalSignals.test.ts`

Expected: failures for the absent route, clients, and helper module.

- [ ] **Step 3: Add minimal contracts, clients, helpers, and lazy route registration**

Copy the backend response shape exactly. Use the existing `apiFetch` wrapper and current A-share semantic tokens; do not add a second request abstraction.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2 and expect all selected tests to pass.

### Task 2: Refocus the Vue Homepage

**Files:**
- Modify: `apps/web-vue/src/composables/useHomeDashboard.ts`
- Modify: `apps/web-vue/src/composables/useHomeDashboard.test.ts`
- Modify: `apps/web-vue/src/views/HomeView.vue`
- Modify: `apps/web-vue/src/views/HomeView.test.ts`

- [ ] **Step 1: Write failing homepage resource and composition tests**

Assert that initial loading requests market overview, sector flow, and capital summary concurrently; it must not request market rankings or the duplicate sector replica trend. Assert that the rendered page contains `板块资金流`, `两融余额`, and `宽基护盘雷达`, and omits `板块实时曲线`, `市场关注榜`, and `数据状态`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/composables/useHomeDashboard.test.ts src/views/HomeView.test.ts`

Expected: the old four-resource dashboard and old panel assertions fail.

- [ ] **Step 3: Replace duplicate resources and panels**

Keep the existing main index and market-state strips. Keep sector capital flow as the only sector visualization, showing six inflow/outflow rows. Add compact stacked margin and ETF summary panels with explicit partial coverage, stage, model version, evidence strength, signs, and a router link to `/etf-radar`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2 and expect all selected tests to pass.

### Task 3: Build the ETF Radar Workspace

**Files:**
- Create: `apps/web-vue/src/views/EtfRadarView.vue`
- Create: `apps/web-vue/src/views/EtfRadarView.test.ts`

- [ ] **Step 1: Write the failing workspace test**

Assert four tabs (`盘中雷达`, `份额变化`, `持有人披露`, `方法与验证`), overview-only initial loading, one request on first activation of each other tab, force refresh of the active tab, `证据强度` wording, and no probability wording.

- [ ] **Step 2: Run the workspace test and verify RED**

Run: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts`

Expected: module import fails because the view does not exist.

- [ ] **Step 3: Implement the lazy four-view workspace**

Use Ant Design Vue tabs and tables. The overview view shows the four summary metrics and seven-ETF evidence table; history shows a stable-height bar chart plus records; holders show exact legal entities and report period; methodology shows factors, thresholds, and limitations. Each view owns loading, error, empty, and stale source states. Wide tables scroll inside the panel without page overflow.

- [ ] **Step 4: Run the workspace test and verify GREEN**

Run the command from Step 2 and expect all tests to pass.

### Task 4: Add the Market Workspace Entry

**Files:**
- Modify: `apps/web-vue/src/views/MarketView.vue`
- Create: `apps/web-vue/src/views/MarketView.test.ts`

- [ ] **Step 1: Write a failing navigation test**

Assert that the market segmented control exposes `ETF资金` and routes directly to `/etf-radar` without coercing it into the existing `sectors | heatmap` query state.

- [ ] **Step 2: Run the test and verify RED**

Run: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/views/MarketView.test.ts`

Expected: `ETF资金` is absent.

- [ ] **Step 3: Add the direct navigation option**

Keep `sectors | heatmap` normalization unchanged and route only the ETF option to the dedicated workspace.

- [ ] **Step 4: Run the test and verify GREEN**

Run the command from Step 2 and expect all tests to pass.

### Task 5: Full Verification and Product QA

- [ ] **Step 1: Run Vue quality gates**

Run:

```bash
cd apps/web-vue
corepack pnpm@9.15.0 test:unit --run
corepack pnpm@9.15.0 typecheck
corepack pnpm@9.15.0 build
```

Expected: all tests, type checks, and production build pass.

- [ ] **Step 2: Start isolated preview against port 8010**

Run the worktree Vue app on an unused port with `VITE_API_BASE_URL=http://127.0.0.1:8010`.

- [ ] **Step 3: Perform desktop and mobile browser QA**

Verify the sidebar entry, homepage single sector visualization, summary navigation, all four views, internal table scrolling, positive-red/negative-green semantics with signs, no document overflow, and no console errors.

- [ ] **Step 4: Review diff and commit**

Run `git diff --check`, confirm only Vue files and this plan changed, then commit the implementation.
