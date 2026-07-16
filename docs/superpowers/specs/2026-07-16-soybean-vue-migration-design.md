# Soybean Vue Frontend Migration Design

## Goal

Replace the existing Next.js/React frontend with a Vue 3 + Vite + ant-design-vue frontend based fully on `soybeanjs/soybean-admin-antd`, while preserving the existing backend APIs, core trading workbenches, and public URLs.

## Scope

The final frontend will use Soybean's `AdminLayout`, Pinia stores, Vue Router, theme settings, global header, sider, breadcrumb, multi-tab workspace, and responsive layout. The existing React/Next frontend is retained only as a temporary comparison target during migration and is removed after parity verification.

The following URLs remain supported:

| URL | Vue workspace |
| --- | --- |
| `/` | Market overview |
| `/screener` | Strong-stock screener |
| `/auction` | Auction radar and Top3 model |
| `/market` | Sector radar and heatmap |
| `/stock/:symbol` | Stock quote, K-line, research, and Chanlun entry |
| `/watchlist` | Watchlist and risk controls |
| `/sentiment` | Short-term sentiment and review |
| `/chanlun` | Multi-period Chanlun workbench |
| `/system` | Model and data-source settings |
| `/settings` | Compatibility redirect to `/system?tab=data` |
| `/sectors` | Compatibility redirect to `/market?view=sectors` |
| `/heatmap` | Compatibility redirect to `/market?view=heatmap` |
| `/model-maintenance` | Compatibility redirect to `/system?tab=model` |

## Architecture

The new frontend is built in `apps/web-vue` during migration, using the Soybean repository as the base rather than wrapping or embedding the React application. The backend in `apps/api` remains the source of truth and is not rewritten as part of this migration.

The frontend layers are:

1. **Soybean shell**
   - `AdminLayout` for layout modes, responsive sider, fixed header/tab behavior, and content scrolling.
   - Soybean global header, menu, breadcrumb, theme drawer, multi-tab store, and route metadata.
   - A product-specific navigation tree containing only market, observation, and system workspaces.

2. **API and domain layer**
   - Port `apps/web/lib/api.ts` to a Vue service module with a single configurable API base URL.
   - Port the shared response types from `apps/web/lib/types.ts` without changing backend field names.
   - Use composables for request lifecycle, polling, cache/stale state, trading-date handling, and chart windows.
   - Keep business calculations and chart option helpers framework-agnostic where possible.

3. **Workspace layer**
   - Each major route owns a focused view directory and uses smaller components for controls, tables, empty states, and charts.
   - `echarts` remains the chart engine for K-lines, Chanlun overlays, sector curves, sentiment trends, and heatmaps.
   - Loading, error, empty, stale-cache, and partial-data states are explicit UI states in every data-backed workspace.

## Workspace Responsibilities

### Market Overview

Render market status, full-market breadth, total turnover and comparison, index snapshot, sector capital flow, sector rotation, intraday emotion, and a compact Top3 entry. Requests that do not depend on each other run in parallel; stale cached values remain visible with a freshness label when live data fails.

### Strong Stock Screener

Preserve current filtering, candidate ranking, GSGF diagnostics, intraday confirmation, backtest/calibration actions, and stock-detail navigation. Filters and result rows remain URL-safe and do not depend on the shell tab store.

### Auction Radar

Preserve auction snapshot refresh, industry strength, model Top3 generation and cache-only fallback, live confirmation, review metrics, manual review, and stock-detail context. Background jobs use the existing create/status endpoints and never block the initial workspace render.

### Market and Stock Workspaces

The market workspace contains the sector radar, sector replica, heatmap, board comparison, and stock drill-down. The stock workspace preserves quote, K-line, research, industry metadata, valuation fields, and the entry to the standalone Chanlun workspace.

### Chanlun Workbench

Preserve daily, 5-minute, 15-minute, 30-minute, 60-minute, and 90-minute periods; K-line rendering; strokes, segments, central zones, virtual zones, divergence coefficient, top/bottom and consolidation divergence, buy/sell markers, alerts, replay, backtest, backfill, and paper-order lifecycle. Real order execution is out of scope; approval remains manual for paper orders.

### Watchlist, Sentiment, and System

Port watchlist pool editing and risk status, sentiment summary/detail/intraday monitoring, model maintenance packets, data-source status, runtime settings, cache controls, notification settings, and health checks. Existing backend contracts are reused directly.

## Data Flow and State Rules

- Views call service functions through composables rather than calling `fetch` directly.
- A composable exposes `data`, `loading`, `refreshing`, `error`, `isStale`, and `refresh` where the endpoint supports refresh.
- Background-job composables expose `job`, `progress`, `polling`, `error`, and `cancel` where the backend supports cancellation.
- Route query parameters are the source of truth for selected market view, stock symbol, period, system tab, and other shareable workspace state.
- Pinia is reserved for shell-wide state: theme, tabs, route cache, responsive layout, and user preferences. Page-specific data remains local to the view/composable.
- No endpoint is silently replaced by fabricated values. Fallbacks are labeled as cached or estimated and retain their source metadata.

## Deployment

The Vue app builds to `apps/web-vue/dist`. The single-container image continues to expose port `3110` and starts the API on internal port `8010`. A small static Node server serves `dist`, falls back to `index.html` for Vue Router history URLs, and proxies or leaves API calls pointed at the internal API base as configured by the build environment.

The Docker build is changed only after Vue production build and route smoke checks pass. The final image no longer copies Next standalone output and no longer installs React/Next dependencies.

## Verification

The migration is accepted only when:

1. Vue type-check and production build pass.
2. API service and domain helper tests pass.
3. All listed routes return successfully, including compatibility redirects and `/stock/:symbol`.
4. Desktop 1440x900 and mobile 390x844 smoke checks find no horizontal overflow or client error overlay.
5. Manual browser checks complete one real workflow each for screener, auction Top3, stock K-line, Chanlun overlay, heatmap drill-down, watchlist editing, sentiment refresh, and system settings.
6. Docker build and single-container startup expose the Vue app at port 3110 and keep API health checks green.
7. `apps/web` and all Next.js/React frontend dependencies are removed after the Vue parity checklist is complete.

## Risks and Mitigations

- **Large component migration:** move one workspace at a time and keep the old frontend available as a comparison target until each route is verified.
- **Chart behavior drift:** preserve existing framework-agnostic chart option and calculation helpers, then add screenshot and interaction checks around K-line and heatmap surfaces.
- **URL or query regression:** define route metadata and redirect tests before deleting the old router.
- **Build/deployment regression:** keep Docker changes as the final migration phase and run a production static-server smoke test before removing Next.
- **Data-source failures:** retain explicit stale/error states and existing API fallbacks rather than hiding failures behind loading placeholders.
