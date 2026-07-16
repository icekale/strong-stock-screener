# Soybean Vue Frontend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Next.js/React frontend with a full Soybean Vue 3 frontend while preserving the existing trading workbenches, backend contracts, and public URLs.

**Architecture:** Build a temporary `apps/web-vue` frontend by copying the Soybean admin template, then migrate framework-agnostic domain logic and each existing workbench into Vue views and composables. Keep the React frontend as a comparison target until all route and workflow checks pass; switch Docker to the Vue static build only at the end, then delete `apps/web` and its Next/React dependencies.

**Tech Stack:** Vue 3, Vite, TypeScript, `ant-design-vue`, Pinia, Vue Router, VueUse, UnoCSS, ECharts, existing FastAPI API, Node static server for production history fallback.

## Global Constraints

- Preserve the public routes `/`, `/screener`, `/auction`, `/market`, `/stock/:symbol`, `/watchlist`, `/sentiment`, `/chanlun`, and `/system`.
- Preserve compatibility redirects for `/settings`, `/sectors`, `/heatmap`, and `/model-maintenance`.
- Preserve the existing FastAPI endpoints and response field names; do not fabricate data in the Vue client.
- Preserve auction Top3 cache-only fallback, background-job polling, manual review, and manual paper-order approval boundaries.
- Preserve daily, 5-minute, 15-minute, 30-minute, 60-minute, and 90-minute Chanlun periods and current chart overlay semantics.
- Use Soybean's `AdminLayout`, Pinia, route metadata, theme settings, global tab store, and responsive navigation as the only frontend shell.
- Keep page-specific data in composables; reserve Pinia for shell-wide state and user preferences.
- Do not delete `apps/web` until the full route and workflow parity checklist passes.
- Run typecheck and the focused test suite after every task; do not mix unrelated existing worktree changes into migration commits.

---

### Task 1: Scaffold the Soybean Vue Application

**Files:**
- Create: `apps/web-vue/` by copying `/tmp/soybean-admin-antd/`
- Modify: `apps/web-vue/package.json`
- Modify: `apps/web-vue/vite.config.ts`
- Create: `apps/web-vue/.env.test`
- Create: `apps/web-vue/.env.prod`
- Modify: `apps/web-vue/src/App.vue`
- Modify: `apps/web-vue/src/main.ts`

**Interfaces:**
- Produces a standalone Vite application with `pnpm dev`, `pnpm typecheck`, `pnpm build`, and `pnpm preview`.
- Exposes `VITE_API_BASE_URL` to the service layer and `VITE_ROUTER_HISTORY_MODE=history` to Vue Router.

- [ ] **Step 1: Copy the template and verify its baseline.**

  ```bash
  cp -R /tmp/soybean-admin-antd apps/web-vue
  cd apps/web-vue
  pnpm install --frozen-lockfile
  pnpm typecheck
  pnpm build
  ```

  Expected: the unmodified Soybean template typechecks and builds successfully.

- [ ] **Step 2: Remove demo-only pages and dependencies from the application entry.**

  Keep the template's `src/layouts`, `src/store`, `src/theme`, `src/plugins`, `src/styles`, and `packages/*`. Replace `src/App.vue` with a router-only root component and remove demo menu entries from the route source. Do not remove shared layout modules used by the product shell.

  Add `vitest` and `@vue/test-utils` to `devDependencies` and add `"test:unit": "vitest run"` to the package scripts so the later service, route, composable, and pure chart tests have a stable runner.

- [ ] **Step 3: Add product environment defaults.**

  `apps/web-vue/.env.test` must contain:

  ```text
  VITE_API_BASE_URL=http://127.0.0.1:8010
  VITE_ROUTER_HISTORY_MODE=history
  VITE_BASE_URL=/
  ```

  `apps/web-vue/.env.prod` must leave `VITE_API_BASE_URL` empty so the browser uses the same-origin API proxy/static server configuration.

- [ ] **Step 4: Verify the scaffold.**

  ```bash
  cd apps/web-vue
  pnpm typecheck
  pnpm build
  ```

  Expected: PASS, with no demo route required for the product build.

- [ ] **Step 5: Commit the isolated scaffold.**

  ```bash
  git add apps/web-vue
  git commit -m "feat: scaffold soybean vue frontend"
  ```

---

### Task 2: Replace Demo Routing With Product Routes and Navigation

**Files:**
- Modify: `apps/web-vue/src/router/index.ts`
- Modify: `apps/web-vue/src/router/routes/index.ts`
- Modify: `apps/web-vue/src/router/routes/builtin.ts`
- Modify: `apps/web-vue/src/router/elegant/imports.ts`
- Create: `apps/web-vue/src/router/product-routes.ts`
- Create: `apps/web-vue/src/router/product-routes.test.ts`
- Modify: `apps/web-vue/src/locales/langs/zh-cn.ts`

**Interfaces:**
- `productRoutes` contains explicit route records for all public paths and route meta `{ title, icon, order, hideInMenu?, activeMenu? }`.
- Legacy paths redirect without reimplementing duplicate pages.
- `resolveProductRoute(path: string): { name: string; path: string } | null` is exported for unit tests.

- [ ] **Step 1: Write route parity tests before changing routing.**

  Add tests that assert the route table contains every required route, dynamic stock symbols are accepted, and compatibility paths resolve exactly to:

  ```text
  /settings -> /system?tab=data
  /sectors -> /market?view=sectors
  /heatmap -> /market?view=heatmap
  /model-maintenance -> /system?tab=model
  ```

- [ ] **Step 2: Define the product route table.**

  Use `layout.base` for all workspaces and `layout.blank` only for 404/500. Define the product route names `home`, `screener`, `auction`, `market`, `stock`, `watchlist`, `sentiment`, `chanlun`, and `system`. Mark compatibility routes `hideInMenu: true`.

- [ ] **Step 3: Wire Soybean's route store to the product route table.**

  Remove demo generated routes from the auth route source, keep the template's route guard/tab store, and ensure menu labels are Chinese product labels: 市场总览, 强势选股, 竞价雷达, 板块与热图, 自选与风险, 情绪与复盘, 缠论工作台, 模型与数据源.

- [ ] **Step 4: Verify route behavior.**

  ```bash
  cd apps/web-vue
  pnpm exec vitest run src/router/product-routes.test.ts
  pnpm typecheck
  ```

  Expected: route tests and typecheck pass.

- [ ] **Step 5: Commit routing and navigation.**

  ```bash
  git add apps/web-vue/src/router apps/web-vue/src/locales
  git commit -m "feat: add product routes to soybean shell"
  ```

---

### Task 3: Port API Contracts and Shared Domain Helpers

**Files:**
- Create: `apps/web-vue/src/service/types.ts`
- Create: `apps/web-vue/src/service/request.ts`
- Create: `apps/web-vue/src/service/api.ts`
- Create: `apps/web-vue/src/service/api.test.ts`
- Create: `apps/web-vue/src/composables/useAsyncResource.ts`
- Create: `apps/web-vue/src/composables/useJobPolling.ts`
- Create: `apps/web-vue/src/composables/useTradeDate.ts`
- Create: `apps/web-vue/src/utils/domain/marketOverview.ts`
- Create: `apps/web-vue/src/utils/domain/auctionModel.ts`
- Create: `apps/web-vue/src/utils/domain/stockNavigation.ts`

**Interfaces:**
- `apiRequest<T>(path: string, init?: RequestInit): Promise<T>` prefixes `VITE_API_BASE_URL`, checks `response.ok`, and includes response status/body in errors.
- `useAsyncResource<T>(loader: () => Promise<T>)` returns `{ data, loading, refreshing, error, isStale, refresh }`.
- `useJobPolling<T>(start: () => Promise<BackgroundJobState>, read: (id: string) => Promise<T>)` returns `{ job, progress, polling, error, run, cancel }`.
- Exported API functions retain the existing names and request parameters from `apps/web/lib/api.ts`, including Top3, Chanlun, watchlist, sentiment, market, stock, and system operations.

- [ ] **Step 1: Copy response types without changing backend contracts.**

  Port `apps/web/lib/types.ts` to `src/service/types.ts`. Keep literal unions for periods, cache statuses, Top3 buckets, sentiment states, Chanlun periods, and paper-order status.

- [ ] **Step 2: Write request and API contract tests.**

  Mock `globalThis.fetch` and assert that `getAuctionModelTop3('2026-07-16', { cacheOnly: true })` produces `/api/auction/model/top3?trade_date=2026-07-16&cache_only=true`, and failed responses throw errors containing status and body. Add a test for stock symbol encoding and job polling URL encoding.

- [ ] **Step 3: Implement the API service.**

  Port every exported function from `apps/web/lib/api.ts` into `src/service/api.ts` through `apiRequest`, including `getMarketOverview`, `getAuctionSnapshot`, `getAuctionModelTop3`, `createAuctionModelTop3Job`, `getStockKline`, `getChanlunWorkspace`, paper-order operations, watchlist, sentiment, system, and model-maintenance functions.

- [ ] **Step 4: Implement generic request composables.**

  Preserve stale data on refresh errors, distinguish initial errors from recovered refresh errors, and stop polling on terminal job states or explicit cancellation. Do not show numeric zero for missing backend values.

- [ ] **Step 5: Port framework-agnostic domain helpers and verify.**

  Port the market overview, auction model, stock navigation, market trend, sector, and list-filter helpers that do not import React or Next. Run:

  ```bash
  cd apps/web-vue
  pnpm exec vitest run src/service src/utils/domain
  pnpm typecheck
  ```

- [ ] **Step 6: Commit service and domain layer.**

  ```bash
  git add apps/web-vue/src/service apps/web-vue/src/composables apps/web-vue/src/utils/domain
  git commit -m "feat: port stock workbench api and domain services"
  ```

---

### Task 4: Port Chart and K-Line Infrastructure

**Files:**
- Create: `apps/web-vue/src/components/charts/MarketTrendChart.vue`
- Create: `apps/web-vue/src/components/charts/SectorRadarChart.vue`
- Create: `apps/web-vue/src/components/charts/HeatmapTreemap.vue`
- Create: `apps/web-vue/src/components/charts/StockKlineChart.vue`
- Create: `apps/web-vue/src/components/charts/ChanlunOverlay.ts`
- Create: `apps/web-vue/src/utils/charts/klineWindow.ts`
- Create: `apps/web-vue/src/utils/charts/klineIndicatorLayout.ts`
- Create: `apps/web-vue/src/utils/charts/klineOverlayOption.ts`
- Create: `apps/web-vue/src/utils/charts/chanlunOverlay.ts`
- Create: `apps/web-vue/src/utils/charts/sectorReplicaChartOption.ts`
- Create: `apps/web-vue/src/utils/charts/chartOptions.test.ts`

**Interfaces:**
- Chart components accept typed `data`, `height`, `loading`, and `error` props and emit `select`/`hover` events without exposing ECharts instances to workspaces.
- `buildChanlunOverlayOption`, `buildKlineOverlayOption`, and `buildSectorReplicaOption` remain pure functions and are testable without a browser.

- [ ] **Step 1: Port pure chart helpers and existing tests.**

  Move the existing K-line window, indicator layout, overlay, heatmap, and Chanlun overlay calculations. Remove only React-specific imports; keep the data and coordinate semantics unchanged.

- [ ] **Step 2: Write chart contract tests.**

  Assert daily/minute period mapping, stable central-zone IDs, divergence coefficient labels, buy/sell markers, virtual zones, heatmap fixed axis, and the no-data behavior for missing values.

- [ ] **Step 3: Build Vue chart adapters.**

  Use direct ECharts lifecycle (`echarts.init`, `setOption`, `resize`, `dispose`) in `onMounted`, `watch`, and `onBeforeUnmount`. Register resize observers and never create a chart when the container has zero dimensions.

- [ ] **Step 4: Verify chart rendering contracts.**

  ```bash
  cd apps/web-vue
  pnpm exec vitest run src/utils/charts/chartOptions.test.ts
  pnpm typecheck
  ```

- [ ] **Step 5: Commit chart infrastructure.**

  ```bash
  git add apps/web-vue/src/components/charts apps/web-vue/src/utils/charts
  git commit -m "feat: add vue chart and chanlun infrastructure"
  ```

---

### Task 5: Migrate Market Overview, Market Radar, and Heatmap

**Files:**
- Create: `apps/web-vue/src/views/home/index.vue`
- Create: `apps/web-vue/src/views/home/modules/MarketStatusPanel.vue`
- Create: `apps/web-vue/src/views/home/modules/SectorFlowPanel.vue`
- Create: `apps/web-vue/src/views/home/modules/EmotionTrendPanel.vue`
- Create: `apps/web-vue/src/views/market/index.vue`
- Create: `apps/web-vue/src/views/market/modules/SectorWorkspace.vue`
- Create: `apps/web-vue/src/views/market/modules/HeatmapWorkspace.vue`
- Create: `apps/web-vue/src/views/market/modules/BoardStockDrawer.vue`
- Create: `apps/web-vue/src/composables/useMarketOverview.ts`
- Create: `apps/web-vue/src/composables/useMarketWorkspace.ts`
- Create: `apps/web-vue/src/composables/useHeatmap.ts`

**Interfaces:**
- `useMarketOverview()` exposes independent resources for overview, rankings, emotion, and Top3 preview.
- `useMarketWorkspace()` keeps `view=sectors|heatmap`, mode, scope, board selection, and date in the route query.
- Heatmap selection emits `{ symbol, name, industry }` and navigates to `/stock/:symbol` with encoded context.

- [ ] **Step 1: Write route-query and data-state tests.**

  Cover default market view, invalid view fallback, sector/heatmap query persistence, stale turnover display, full-market breadth, and Top3 unavailable/error states.

- [ ] **Step 2: Implement the home composable and panels.**

  Run independent overview requests in parallel, render important market numbers with strong hierarchy, and keep cached turnover labeled with its source/date. Use the Soybean card and spacing tokens rather than old page-frame CSS.

- [ ] **Step 3: Implement sector and heatmap workspace.**

  Port sector radar, sector replica, board comparison, live curves, treemap sizing, period filters, stock drill-down, and loading/error/empty states. Keep the heatmap interaction and zoom semantics from the existing pure helpers.

- [ ] **Step 4: Verify with unit tests and build.**

  ```bash
  cd apps/web-vue
  pnpm exec vitest run src/views/home src/views/market src/composables/useMarketOverview.ts src/composables/useMarketWorkspace.ts src/composables/useHeatmap.ts
  pnpm typecheck
  ```

- [ ] **Step 5: Commit market workspaces.**

  ```bash
  git add apps/web-vue/src/views/home apps/web-vue/src/views/market apps/web-vue/src/composables/useMarketOverview.ts apps/web-vue/src/composables/useMarketWorkspace.ts apps/web-vue/src/composables/useHeatmap.ts
  git commit -m "feat: migrate market overview and heatmap workspaces"
  ```

---

### Task 6: Migrate Strong Screener and Auction Radar

**Files:**
- Create: `apps/web-vue/src/views/screener/index.vue`
- Create: `apps/web-vue/src/views/screener/modules/FilterRail.vue`
- Create: `apps/web-vue/src/views/screener/modules/CandidateResults.vue`
- Create: `apps/web-vue/src/views/screener/modules/GsgfPanels.vue`
- Create: `apps/web-vue/src/views/auction/index.vue`
- Create: `apps/web-vue/src/views/auction/modules/AuctionSnapshotPanel.vue`
- Create: `apps/web-vue/src/views/auction/modules/AuctionTop3Panel.vue`
- Create: `apps/web-vue/src/views/auction/modules/AuctionReviewPanel.vue`
- Create: `apps/web-vue/src/views/auction/modules/AuctionIndustryPanel.vue`
- Create: `apps/web-vue/src/composables/useScreener.ts`
- Create: `apps/web-vue/src/composables/useAuction.ts`
- Create: `apps/web-vue/src/composables/useAuctionTop3.ts`

**Interfaces:**
- `useScreener()` exposes screen filters, result state, job state, selected candidate, and GSGF diagnostics.
- `useAuctionTop3()` exposes `{ data, loading, refreshing, error, cacheMiss, job, progress, run, loadCacheOnly, confirm }`.
- All stock links use the normalized `/stock/:symbol` route and preserve source/name/industry query context.

- [ ] **Step 1: Port and test screener selection logic.**

  Move candidate filters, status grouping, GSGF funnel, risk checks, industry metadata, and stock navigation tests before creating templates.

- [ ] **Step 2: Implement screener filters and results.**

  Keep filter state shareable in query parameters, show data-incomplete rows explicitly, and separate observation/research output from ranking.

- [ ] **Step 3: Port auction snapshot and industry panels.**

  Preserve snapshot refresh jobs, industry grouping, close-percent review data, missing industry labels, and compact side panels. Initial render must not wait for model generation.

- [ ] **Step 4: Port Top3 model lifecycle.**

  Implement cache-only read first, show the cache miss separately from API failure, start background generation on demand, poll until terminal state, and render live confirmation and manual review controls.

- [ ] **Step 5: Verify and commit.**

  ```bash
  cd apps/web-vue
  pnpm exec vitest run src/views/screener src/views/auction src/composables/useScreener.ts src/composables/useAuction.ts src/composables/useAuctionTop3.ts
  pnpm typecheck
  pnpm build
  git add apps/web-vue/src/views/screener apps/web-vue/src/views/auction apps/web-vue/src/composables/useScreener.ts apps/web-vue/src/composables/useAuction.ts apps/web-vue/src/composables/useAuctionTop3.ts
  git commit -m "feat: migrate screener and auction workspaces"
  ```

---

### Task 7: Migrate Stock Detail and Chanlun Workbench

**Files:**
- Create: `apps/web-vue/src/views/stock/index.vue`
- Create: `apps/web-vue/src/views/stock/modules/StockHeader.vue`
- Create: `apps/web-vue/src/views/stock/modules/StockQuotePanel.vue`
- Create: `apps/web-vue/src/views/stock/modules/StockResearchPanel.vue`
- Create: `apps/web-vue/src/views/chanlun/index.vue`
- Create: `apps/web-vue/src/views/chanlun/modules/ChanlunToolbar.vue`
- Create: `apps/web-vue/src/views/chanlun/modules/ChanlunSignalRail.vue`
- Create: `apps/web-vue/src/views/chanlun/modules/ChanlunReplayPanel.vue`
- Create: `apps/web-vue/src/views/chanlun/modules/ChanlunPaperOrderPanel.vue`
- Create: `apps/web-vue/src/composables/useStockWorkspace.ts`
- Create: `apps/web-vue/src/composables/useChanlunWorkspace.ts`

**Interfaces:**
- `useStockWorkspace(symbol: Ref<string>)` exposes quote, K-line, research, loading, source status, and stock context.
- `useChanlunWorkspace(symbol: Ref<string>, period: Ref<ChanlunPeriod>)` exposes workspace data, chart options, selected overlays, replay/backtest jobs, alerts, paper account, and order actions.
- Paper order actions require an explicit user action for draft, approve, fill, or cancel; no automatic live order API is introduced.

- [ ] **Step 1: Port stock identity, K-line, period, and overlay tests.**

  Assert symbol/query normalization, 90-minute mapping, missing valuation display, chart resize behavior, and overlay gating on matching native data.

- [ ] **Step 2: Implement stock detail.**

  Preserve quote/research source labels, industry and valuation fields, K-line period controls, and links from auction/screener/heatmap back to the originating workspace.

- [ ] **Step 3: Implement Chanlun workspace.**

  Render daily and all minute periods with the same expanded chart height, toggleable moving averages defaulting off, stable overlays for fractals/segments/zones/signals, divergence coefficient, warnings, replay, backtest, backfill, and paper-order lifecycle.

- [ ] **Step 4: Verify real chart interactions.**

  ```bash
  cd apps/web-vue
  pnpm exec vitest run src/views/stock src/views/chanlun src/utils/charts
  pnpm typecheck
  pnpm build
  ```

  Then use the browser smoke script to open `/stock/603823.SH` and `/chanlun?symbol=300308.SZ`, switch all periods, zoom, and confirm no blank canvas or overlapping labels.

- [ ] **Step 5: Commit stock and Chanlun workspaces.**

  ```bash
  git add apps/web-vue/src/views/stock apps/web-vue/src/views/chanlun apps/web-vue/src/composables/useStockWorkspace.ts apps/web-vue/src/composables/useChanlunWorkspace.ts apps/web-vue/src/utils/charts
  git commit -m "feat: migrate stock and chanlun workspaces"
  ```

---

### Task 8: Migrate Watchlist, Sentiment, and System Workspaces

**Files:**
- Create: `apps/web-vue/src/views/watchlist/index.vue`
- Create: `apps/web-vue/src/views/sentiment/index.vue`
- Create: `apps/web-vue/src/views/system/index.vue`
- Create: `apps/web-vue/src/views/system/modules/ModelMaintenancePanel.vue`
- Create: `apps/web-vue/src/views/system/modules/DataSourcePanel.vue`
- Create: `apps/web-vue/src/views/system/modules/RuntimeSettingsPanel.vue`
- Create: `apps/web-vue/src/composables/useWatchlist.ts`
- Create: `apps/web-vue/src/composables/useSentiment.ts`
- Create: `apps/web-vue/src/composables/useSystemSettings.ts`

**Interfaces:**
- Each composable exposes explicit data, error, refresh, save, and job state matching its existing API operations.
- `/system?tab=model|data` remains the canonical system state; `/settings` only redirects.

- [ ] **Step 1: Port watchlist and sentiment tests.**

  Cover watchlist pool parsing/saving, GSGF statuses, sentiment snapshot freshness, intraday monitor controls, alert archive, and decision display.

- [ ] **Step 2: Implement watchlist and sentiment views.**

  Use compact tables and action rails from Soybean/Ant Design Vue, keep stale snapshots labeled, and keep monitor start/stop/run-once actions explicit.

- [ ] **Step 3: Implement system view.**

  Port model maintenance packet/report/suggestion actions, data-source health, runtime settings, notification channels, cache controls, and health checks. Keep `tab` in the URL and preserve unsaved-form protection.

- [ ] **Step 4: Verify and commit.**

  ```bash
  cd apps/web-vue
  pnpm exec vitest run src/views/watchlist src/views/sentiment src/views/system src/composables
  pnpm typecheck
  pnpm build
  git add apps/web-vue/src/views/watchlist apps/web-vue/src/views/sentiment apps/web-vue/src/views/system apps/web-vue/src/composables
  git commit -m "feat: migrate watchlist sentiment and system workspaces"
  ```

---

### Task 9: Add Vue Browser Smoke Tests and Route Parity Checks

**Files:**
- Create: `scripts/smoke-vue-ui.mjs`
- Create: `apps/web-vue/src/router/route-parity.test.ts`
- Modify: `apps/web-vue/package.json`
- Create: `apps/web-vue/playwright.config.ts`

- [ ] **Step 1: Add a Vue smoke command.**

  Add `"smoke:ui": "node ../../scripts/smoke-vue-ui.mjs"` and point the script at `VUE_SMOKE_UI_BASE_URL` defaulting to `http://127.0.0.1:9527`.

- [ ] **Step 2: Implement desktop/mobile checks.**

  Visit every public and compatibility route at 1440x900 and 390x844, wait for the shell and page root, fail on uncaught console errors, HTTP responses >= 400, client error overlays, horizontal overflow, and missing `main` content.

- [ ] **Step 3: Add core interaction checks.**

  Verify menu navigation, tab creation/close, market view query changes, auction Top3 cache/run controls, stock symbol navigation, Chanlun period switching, heatmap stock drill-down, watchlist save, and system tab switching.

- [ ] **Step 4: Run the parity suite against the Vue dev server.**

  ```bash
  cd apps/web-vue
  pnpm dev --host 127.0.0.1 --port 9527
  VUE_SMOKE_UI_BASE_URL=http://127.0.0.1:9527 pnpm smoke:ui
  ```

  Expected: all routes pass at both viewports with no overflow or browser error overlay.

- [ ] **Step 5: Commit verification tooling.**

  ```bash
  git add scripts/smoke-vue-ui.mjs apps/web-vue/package.json apps/web-vue/playwright.config.ts apps/web-vue/src/router/route-parity.test.ts
  git commit -m "test: add vue route and browser parity checks"
  ```

---

### Task 10: Switch Docker and Local Production Serving to Vue

**Files:**
- Create: `scripts/static-web-server.mjs`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `scripts/start-single-container.sh`
- Modify: `apps/web-vue/vite.config.ts`
- Modify: `.dockerignore`
- Create: `apps/web-vue/.dockerignore`

**Interfaces:**
- `static-web-server.mjs` accepts `STATIC_WEB_ROOT`, `API_BASE_URL`, `PORT`, and `HOSTNAME`; it serves existing files, falls back to `index.html` for history routes, and proxies `/api/*` and `/health` to the internal FastAPI service.

- [ ] **Step 1: Write static server tests.**

  Use a temporary directory containing `index.html` and `assets/app.js`; assert `/`, `/auction`, and `/stock/603823.SH` return `index.html`, while `/assets/app.js` returns the asset and missing assets return 404.

- [ ] **Step 2: Implement static server and local proxy configuration.**

  Use Node's built-in `http`, `fs/promises`, and `url` modules; do not add a runtime web-server dependency. Proxy `/api/*` and `/health` to `API_BASE_URL` (default `http://127.0.0.1:8010`) and configure the Vite dev proxy for the same paths.

- [ ] **Step 3: Replace the Docker web build stage.**

  Copy `apps/web-vue` into a Node build stage, run `pnpm install --frozen-lockfile` and `pnpm build`, copy `dist` into `/app/web`, and start `node /app/static-web-server.mjs` beside the existing API process. Remove Next standalone copies and `next start` assumptions.

- [ ] **Step 4: Build and run the single container.**

  ```bash
  docker build -t strong-stock-screener:soybean-vue .
  docker run --rm -p 3110:3110 -v "$PWD/data:/app/data" strong-stock-screener:soybean-vue
  curl --fail http://127.0.0.1:3110/
  curl --fail http://127.0.0.1:3110/health
  curl --fail http://127.0.0.1:3110/auction
  ```

- [ ] **Step 5: Commit deployment switch.**

  ```bash
  git add Dockerfile docker-compose.yml scripts/start-single-container.sh scripts/static-web-server.mjs apps/web-vue/vite.config.ts apps/web-vue/.dockerignore .dockerignore
  git commit -m "build: serve soybean vue frontend in single container"
  ```

---

### Task 11: Remove Next/React and Promote Vue to `apps/web`

**Files:**
- Delete: `apps/web/`
- Rename: `apps/web-vue/` to `apps/web/`
- Modify: `README.md`
- Modify: `README.en_US.md`
- Modify: `.github/workflows/linter.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `scripts/smoke-ui.mjs` or delete it after `smoke-vue-ui.mjs` becomes canonical

- [ ] **Step 1: Run the final parity checklist before deletion.**

  ```bash
  cd apps/web-vue
  pnpm typecheck
  pnpm build
  VUE_SMOKE_UI_BASE_URL=http://127.0.0.1:9725 pnpm smoke:ui
  cd ../..
  pytest -q apps/api/tests
  git diff --check
  ```

  Expected: all frontend and backend tests pass, all routes are accessible from the production static preview, and no test imports `apps/web`.

- [ ] **Step 2: Promote the Vue directory.**

  Remove the old `apps/web` only after the previous step passes, rename `apps/web-vue` to `apps/web`, update Docker paths from `apps/web-vue` to `apps/web`, and remove all Next/React-specific config and dependencies.

- [ ] **Step 3: Update project documentation.**

  Document Vue/Soybean commands, local API prerequisite, preview command, 3110 production entry, route list, and the fact that paper orders require manual confirmation. Remove Next/React startup instructions.

- [ ] **Step 4: Verify the final tree.**

  ```bash
  rg -n "next|Next|react|React|AppShell|next/navigation" apps/web Dockerfile scripts README.md .github || true
  cd apps/web
  pnpm typecheck
  pnpm build
  cd ../..
  git diff --check
  git status --short --branch
  ```

  Expected: no active frontend dependency or source reference to Next.js/React, Vue build passes, and only intentional migration changes remain.

- [ ] **Step 5: Commit the final removal.**

  ```bash
  git add -A apps/web apps/web-vue Dockerfile docker-compose.yml scripts README.md .github
  git commit -m "feat: replace react frontend with soybean vue"
  ```

---

## Final Verification

After Task 11, run the following from the repository root:

```bash
cd apps/web
pnpm typecheck
pnpm build
cd ../..
pytest -q apps/api/tests
git diff --check
git status --short --branch
```

Then start the production container on port `3110` and complete the manual browser workflows for market overview, screener, auction Top3, stock K-line, Chanlun, heatmap drill-down, watchlist, sentiment, and system settings. Only after these checks pass is the migration complete.
