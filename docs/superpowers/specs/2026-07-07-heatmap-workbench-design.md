# Heatmap Workbench Design

## Goal

Add an independent A-share market heatmap board to StockMaster, referencing the feature set and interaction model of [wenyuanw/a-share-heatmap](https://github.com/wenyuanw/a-share-heatmap) and its live preview at `https://map.wenyuanw.me/`.

The new board should feel native to this project: compact, restrained, data-forward, and consistent with the existing Ant Design workbench pages.

## Success Criteria

- A new left-nav entry opens `/heatmap`.
- The page renders a large interactive Canvas treemap for the A-share market.
- Users can switch market universe, board filter, trend filter, size mode, and return period.
- Users can hover or select a stock to see name, code, industry, price, change, turnover, and size metrics.
- Clicking a stock opens the existing K-line page with source context.
- Data source status is explicit; fallback/sample data is never hidden as live data.
- Visual style matches the current workbench instead of copying the standalone dark theme.

## Scope

### In Scope

- Independent route: `/heatmap`.
- Left navigation item: `热图`.
- FastAPI endpoints:
  - `GET /api/heatmap/treemap`
  - `GET /api/heatmap/quotes`
  - `GET /api/heatmap/overview`
- Canvas treemap with industry groups and stock rectangles.
- Controls:
  - Market universe: 全 A, 上证 A 股, 深证 A 股, 沪深 300, 中证 A500, 创业板, 科创板.
  - Board filter: 全部 + 一级行业.
  - Trend filter: 全部, 上涨, 下跌.
  - Size mode: 流通市值, 成交额.
  - Period: 日, 周, 月, 年.
- Canvas interactions:
  - Hover detail on desktop.
  - Click/tap selection for stable detail on mobile.
  - Zoom/pan.
  - Reset view.
  - Fullscreen.
  - Screenshot download or share where browser support allows.
- MIT attribution for `wenyuanw/a-share-heatmap`.

### Out of Scope

- Trade execution or recommendation logic.
- Replacing the existing sector workbench.
- Full theme customization from the upstream project.
- English localization in the first implementation.
- Storing user heatmap settings on the backend.

## User Experience

The page should behave like a dense trading workbench, not a marketing page.

Layout:

- Use the existing app shell and left sidebar.
- Page header shows `市场热力图`, latest update time, source status, and refresh action.
- Main content uses three zones:
  - Left control rail: universe, board, trend, size mode, period.
  - Center canvas: dominant visual area.
  - Right detail rail: selected/hovered stock, market summary, legend, source status.
- On narrow screens, the control rail collapses above the canvas and the detail rail becomes a bottom panel.

Visual style:

- Keep current workbench background `#f5f3f0`, panel surface `#f8f7f4`, ink `#11100e`, and muted text `#7b756d`.
- Use 8px radius for panels and controls.
- Use red for rising and green for falling, matching A-share convention already used in the project.
- The Canvas itself may use a dark inner background for contrast, but surrounding UI remains native to StockMaster.
- Avoid the upstream project's standalone dark-page frame, large branding footer, GitHub/social chrome, and theme settings drawer.

Core interactions:

- Hovering a stock updates the right detail rail without requiring a click.
- Clicking a stock pins the detail and exposes `查看K线`.
- Double-clicking or explicit `查看K线` opens `/stock/[symbol]` with `source=heatmap`, name, and industry query params.
- Selecting an industry board filters the canvas and recalculates summary metrics.
- Reset view clears zoom/pan and active selection, but keeps current filters.

## Data Model

Backend models should be added to `apps/api/app/models.py`:

- `HeatmapPeriodKey`: `day | week | month | year`
- `HeatmapMarketKey`: `all | sse | szse | hs300 | zza500 | cyb | kcb`
- `HeatmapSizeMode`: `market_cap | turnover`
- `HeatmapStockNode`
- `HeatmapBoardNode`
- `HeatmapSummary`
- `HeatmapTreemapResponse`
- `HeatmapQuotesResponse`
- `HeatmapOverviewResponse`

Response objects must include `source_status: list[StrongStockSourceStatus]` so the UI can show live/fallback state clearly.

## Data Sources

First implementation should adapt the upstream source strategy:

- Eastmoney quote endpoint for latest price, day/week/month/year changes, turnover, and quote timestamp.
- Bundled static baseline stock universe copied from the upstream MIT project, including industry/sub-industry mapping and market-cap fields.
- Tonghuashun summary endpoints for all-market advance/flat/decline and turnover summary when available.
- Fallback bundled sample data if live quote fetch fails.

This keeps `free-stockdb` out of live heatmap rendering. `free-stockdb` remains training-only, consistent with the current architecture decision.

## Backend Architecture

Add a provider module under `apps/api/app/providers/heatmap.py`.

Responsibilities:

- Validate market and period params.
- Maintain short in-process caches for quote, summary, and index snapshots.
- Build treemap nodes from baseline stocks plus live quotes.
- Provide fallback responses when live data is unavailable.
- Deduplicate source statuses and expose partial failures.

Cache expectations:

- Quote cache: about 8-15 seconds.
- Overview cache: about 8-15 seconds.
- Endpoints should return quickly during market hours and not block the UI for long network retries.

The provider should avoid depending on Next.js server APIs. All data is served through FastAPI to preserve the existing API/Web split and Docker structure.

## Frontend Architecture

Add route and workspace files:

- `apps/web/app/heatmap/page.tsx`
- `apps/web/app/heatmap/HeatmapWorkspace.tsx`
- `apps/web/app/heatmap/HeatmapCanvas.tsx`
- `apps/web/app/heatmap/heatmapTreemap.ts`
- `apps/web/lib/heatmap.ts`
- API and types additions in `apps/web/lib/api.ts` and `apps/web/lib/types.ts`

Component boundaries:

- `HeatmapWorkspace` owns data loading, filters, refresh, error/source state, and page layout.
- `HeatmapCanvas` owns drawing and pointer interactions.
- `heatmapTreemap.ts` owns pure layout/color math and should be tested without React.
- Small UI subcomponents handle filter rail, detail rail, legend, and toolbar.

Use Ant Design controls and existing icon library. Do not add lucide-react or sonner for the first implementation.

## Error Handling

- If live quote fetch fails and fallback data exists, render fallback data with an orange `stale`/`fallback` status.
- If no renderable data exists, show an Ant Design `Empty` state with a retry button.
- Source status must distinguish:
  - live success,
  - partial fallback,
  - live source failed,
  - bundled sample snapshot.
- Screenshot/share failures should show a non-blocking message and keep the heatmap usable.

## Testing

Backend tests:

- Param validation for market and period.
- Provider builds treemap nodes from quote snapshots.
- Fallback path returns sample data and source status.
- API endpoints return expected schema and bounded data.

Frontend tests:

- Filter state maps to API query params.
- Treemap layout preserves total area and handles tiny nodes.
- Color mapping follows red-rise/green-fall convention.
- Stock detail href carries `source=heatmap`, name, and industry.
- Error/fallback status labels are user-visible.

Manual/browser verification:

- Desktop `/heatmap` renders nonblank Canvas.
- Hover stock updates detail rail.
- Click stock opens existing K-line route.
- Zoom/pan/reset works.
- Fullscreen and screenshot controls do not break layout.
- Mobile viewport recomposes controls and details without overlapping text.

## Licensing And Attribution

`wenyuanw/a-share-heatmap` is MIT licensed. If implementation copies or adapts code/data, preserve license attribution in:

- source comments near copied/adapted modules,
- README or documentation,
- optional page footer/source note.

The implementation should avoid presenting the upstream bundled sample as proprietary live data.

## Implementation Defaults

- Store fallback data under `apps/api/app/data/heatmap/`.
- Implement screenshot download in v1. Clipboard/share can be added after the base page is stable.
- Use provider-local cache in v1. Registering heatmap cache in the system cache panel can be a follow-up if operational visibility becomes necessary.
