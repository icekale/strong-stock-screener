# Duanxianxia-Style Sector Radar Replica Design

## Goal

Replace the existing `/sectors` board page with a pixel-level recreation of the Duanxianxia `板块强度 / 主力流入` panel shown by the user, while keeping StockMaster's own data pipeline and avoiding runtime dependency on Duanxianxia production APIs.

This is a replacement of the current board feature, not a new navigation module.

## Product Position

The new `/sectors` page should behave like a short-term trading sector radar:

- identify intraday main-line sectors quickly,
- compare several sector strength curves on the same minute axis,
- inspect selected sector sub-themes,
- rank component stocks with short-term trading fields,
- enter the existing K-line page from any stock row.

The visual target is the reference panel, not the current StockMaster workbench style. The surrounding app shell can remain, but the sector panel itself should intentionally look like the reference.

## Legal And Technical Boundary

In scope:

- recreate the visible layout, density, typography, colors, table structure, chart behavior, and interaction model;
- reproduce the observed data structure and curve semantics with StockMaster data sources;
- use public page behavior as a research reference.

Out of scope:

- copying Duanxianxia source code, private assets, brand marks, or encrypted data payloads into StockMaster;
- making StockMaster depend on Duanxianxia production APIs at runtime;
- claiming exact proprietary server-side formulas when they are not public.

The implementation target is: pixel-level UI match plus data-structure compatibility plus calibrated self-owned curve generation.

## Research Summary

Observed Duanxianxia frontend:

- Home page is old-style jQuery + Bootstrap + ECharts + iframe composition.
- The relevant iframe is `/web/qxlive`.
- The reference script polls board chart data about every 15 seconds.
- Selected stock quotes refresh about every 8 seconds through a quote URL returned by the board-stock endpoint.
- The frontend does not calculate the board strength curve. It receives server-generated `data.series` and passes it to ECharts.
- The `板块强度 / 主力流入` switch changes the board list and chart source.

Observed qxlive response shape:

- `result`: success flag.
- `qxlive`: market emotion chart payload.
- `plates`: board list, each item has at least `code`, `name`, `val`, `ztcount`.
- `checkplate`: default checked board codes.
- `legend`: chart legend names.
- `series`: ECharts line-series array for selected board curves.

Observed `qxlive.series` metric names:

- `QX`: 情绪指标.
- `ZT`: 涨停家数.
- `DT`: 跌停家数.
- `KQXY`: 亏钱效应.
- `HSLN`: 主力流入.
- `LBGD`: 连板高度.
- `SZ`: 上涨家数.
- `XD`: 下跌家数.
- `PB`: 今日封板率.
- `ZTBX`: 昨涨停表现.
- `LBBX`: 昨连板表现.
- `JRLN`: 今日 5 分钟量能.
- `KQB`: 亏钱效应柱.

Observed selected-board stock row fields:

- `item[0]`: code.
- `item[1]`: name.
- `item[2]`: latest pct change.
- `item[3]`: auction pct change or comparison pct.
- `item[7]`: circulating value.
- `item[8]`: turnover amount.
- `item[12]`: board count or board label.
- `item[13]`: leader / break label, for tags such as `龙`.
- `item[14]`: buy turnover ratio.
- `item[15]`: auction volume ratio or quantity field.
- `item[16]`: auction amount.
- `item[17]`: seal amount.

## Success Criteria

Visual:

- `/sectors` keeps the existing left navigation item `板块`.
- The main sector panel uses a white, compact, reference-like frame instead of the current Ant Design card-heavy layout.
- At desktop width, the first viewport closely matches the reference screenshot:
  - left list width near the reference proportion;
  - `板块强度 / 主力流入` two-tab header;
  - checkbox list with red sector names for active rows, red outlined `N涨停` badges, and tight row height;
  - ECharts legend centered above the chart;
  - ECharts x-axis fixed to `09:15-15:00`;
  - y-axis uses reference-like grid and numeric formatting;
  - sub-theme buttons are white, bordered, compact, and wrap in dense rows;
  - stock table uses compact text and row height, not Ant Design default table spacing.
- Color convention matches the reference: red rising/strong, green falling/weak, thin line chart strokes, no StockMaster beige panels inside the replicated frame.

Behavior:

- Switching `板块强度` and `主力流入` changes the left list values and curve metric.
- Checking or unchecking boards updates the chart series without navigating away.
- Clicking a board row updates sub-theme tags and component stocks.
- Clicking a sub-theme filters or prioritizes the component-stock table.
- Clicking a stock opens the existing stock K-line page with stock name and industry/theme context when available.
- The page keeps working when only partial data is available; stale or estimated data is visible in a small source/status area outside the reference-critical table/chart area.

Data:

- The backend exposes a Duanxianxia-compatible response shape for the replicated panel.
- The implementation never calls Duanxianxia production APIs at runtime.
- The curve generator produces stable minute-series points for the same fixed trading axis:
  `09:15-11:30` and `13:00-15:00`.
- Board strength values are calibrated to the reference-like range and ordering, not merely raw average pct change.
- Main-flow mode prefers real capital-flow data when available and falls back to documented estimation when unavailable.

Performance:

- Initial page render should use cached latest sector radar data and avoid long blocking network calls.
- Board chart refresh target: 15 seconds.
- Selected component-stock quote refresh target: 8 seconds.
- Backend heavy recomputation should be cached by trade date, mode, selected board list, and sample timestamp.

## Data Source Strategy

Primary live sources:

- TickFlow real-time quotes for stock price, pct change, turnover, turnover rate, open price, and quote time.
- TickFlow intraday bars for minute-level curve generation.
- Existing StockMaster auction snapshot and Top3 sources for auction pct, auction turnover, and live auction confirmation fields.
- Existing short-term sentiment and recent limit-up providers for limit-up pool, board count, break-board context, and seal amount when available.
- Existing heatmap baseline and Eastmoney fallback for industry and stock identity backfill.
- Existing plate reference provider for Kaipan/THS-style theme reference and leader persistence.

Secondary enrichment:

- Eastmoney sector rankings and capital-flow endpoints.
- Concept block provider for stock-to-theme mapping.
- Existing local sector theme row snapshots.

Excluded from live runtime:

- Duanxianxia `platechart1.json`, `platechart2.json`, `ztpool.json`, and related encrypted payloads.
- Duanxianxia `bm.duanxianxia.com`, `duanxianxia.cn`, or WebSocket endpoints.

## Curve Generation Design

The backend should add a focused sector-radar replica service that emits a response matching the qxlive-style frontend model.

### Time Axis

Use a fixed minute axis:

- auction period: `09:15` to `09:25` when auction data is available;
- continuous morning session: `09:30` to `11:30`;
- afternoon session: `13:00` to `15:00`.

When the source has no `09:15-09:25` minute bars, seed auction-period points from auction snapshots and carry forward until `09:30`.

### Board Membership

Build board membership in this order:

1. theme membership from recent limit-up and concept tags;
2. industry membership from heatmap baseline and F10 backfill;
3. plate reference membership where available;
4. fallback to industry-only membership when theme tags are missing.

Each stock may belong to multiple themes. For the reference-like board list, theme boards should rank ahead of plain industries when they have current limit-up activity.

### Strength Score

The board strength score should be a compressed value, calibrated to the observed reference range.

Inputs:

- weighted pct change of board members;
- count of stocks above `3%`, `5%`, `7%`, and limit-up thresholds;
- active limit-up count;
- consecutive board height contribution;
- turnover confirmation;
- seal amount confirmation;
- auction pct and auction turnover confirmation before and shortly after open;
- breadth penalty for weak members.

Output:

- positive strong boards should land in the same visual scale as the reference list, often hundreds to thousands and occasionally higher for main-line sectors;
- weak boards can go negative;
- value should be smooth enough for line-chart reading but still react to abrupt limit-up or capital-flow changes.

The exact initial formula can be self-owned. It must include coefficients that can be calibrated by sample captures without schema changes.

### Main Flow Score

Main-flow mode should emit a monetary-style value:

- Use real net inflow if a reliable sector or stock-level capital-flow source exists.
- Otherwise estimate by cumulative turnover multiplied by signed intraday return strength:
  `estimated_flow = cumulative_amount * signed_strength_factor`.
- Normalize display to the reference style:
  - board list values use `万` or `亿`;
  - chart values are numeric and formatted by the chart axis.

The response must include a source status explaining whether the value is real capital flow or estimated from TickFlow turnover.

### Market Emotion Payload

The qxlive-style response should include the market emotion series even if the first UI phase only renders the board chart. This preserves compatibility for future expansion:

- `QX` from existing market emotion score;
- `ZT`, `DT`, `LBGD`, `PB`, `ZTBX`, `LBBX` from short-term sentiment and review stores;
- `SZ`, `XD` from market overview advance/decline data;
- `HSLN` from capital-flow source or estimate;
- `JRLN` from market turnover intraday samples where available;
- `KQB` from losing-effect score or break-board/downside distribution.

## Backend API Design

Add endpoints under the existing sectors namespace:

- `GET /api/sectors/replica/radar`
  - params: `mode=strength|main_flow`, `selected=code1,code2`, `limit`, `stock_limit`;
  - returns a qxlive-compatible board chart response.

- `GET /api/sectors/replica/boards/{board_code}/stocks`
  - params: `sort`, `sub_theme`, `limit`;
  - returns component-stock table rows in named fields plus a compatibility array for strict frontend matching.

- `GET /api/sectors/replica/status`
  - returns latest sample time, cache age, live/estimated source status, and calibration profile version.

The frontend should not consume positional arrays directly internally. The backend may include compatibility arrays for testing and parity, but TypeScript should use named fields.

## Frontend Design

Replace the primary content of `apps/web/app/sectors` with a replica component.

Component boundaries:

- `SectorReplicaWorkspace`
  - owns mode, selected boards, active board, sub-theme, refresh timers, and API state.

- `SectorReplicaPanel`
  - renders the reference-like shell and fixed layout.

- `SectorReplicaBoardList`
  - renders the left checkbox board list with red limit-up badges.

- `SectorReplicaChart`
  - renders ECharts with reference-like legend, grid, axes, colors, and line widths.

- `SectorReplicaSubThemes`
  - renders compact bordered sub-theme buttons.

- `SectorReplicaStockTable`
  - renders a custom dense table, not Ant Design `Table`, so row height and spacing can match the reference.

- `sectorReplicaChartOption.ts`
  - pure ECharts option builder, tested separately.

Visual measurements should be encoded as local CSS classes for the replica panel, not by globally changing workbench styles.

## Interaction Details

Default state:

- mode: `板块强度`;
- checked boards: backend `checkplate`;
- active board: first checked board when available, otherwise first board;
- stock table: active board stocks sorted by short-term strength.

Mode switch:

- `板块强度` displays `plates.val` as raw strength score and `N涨停` badge.
- `主力流入` displays `plates.val` as money value and hides or de-emphasizes `N涨停` only if that matches the selected visual target.

Board checkbox:

- checked boards appear in the chart legend and line series;
- unchecking keeps the board in the left list;
- a minimum of one checked board is enforced.

Board row click:

- sets active board;
- refreshes sub-theme tags and stocks;
- does not automatically toggle checkbox unless the click target is the checkbox.

Stock table:

- column order must match the reference:
  `名称 / 代码 / 涨幅 / 成交 / 流通 / 板数 / 竞涨 / 竞额 / 竟量 / 买成比 / 封单`.
- leader tags such as `龙一`, `龙二`, and `龙三` display as small red rectangular badges next to the name.
- pct cells use red/green text, and limit-up pct can use a red filled rectangular badge like the reference.

## Error Handling

- If live quote data fails, show cached board list and chart if available.
- If only industry data is available, render the panel with an explicit source status that theme mapping is degraded.
- If curve generation fails, show board list and stock table with an empty chart state inside the chart area.
- If component stocks are unavailable for an active board, show an empty table row with a short message using the reference table density.
- Source-status details should be visible but not visually dominate the replica panel.

## Testing Strategy

Backend tests:

- qxlive-compatible response includes `plates`, `checkplate`, `legend`, `series`, `qxlive`.
- fixed time axis includes auction and trading-session labels in the expected order.
- strength scoring ranks a board with more limit-up and stronger turnover above a weaker board.
- main-flow fallback emits estimated-source status.
- selected board filtering limits chart series to selected board codes.
- stock endpoint returns named fields and compatibility row arrays with the expected column order.

Frontend tests:

- mode switch maps to `strength` and `main_flow`.
- checkbox changes selected board codes without dropping active board state.
- board click updates active board but does not toggle selection.
- chart option uses reference-like legend position, grid, x-axis labels, and series colors.
- stock href routes to the existing K-line page with context params.

Manual verification:

- Open `/sectors` at desktop size and compare with the reference screenshot.
- Verify dense layout: left board rows, sub-theme buttons, and stock table row heights are visibly close.
- Toggle `主力流入`.
- Check and uncheck multiple boards.
- Click a board, then click a stock row into K-line page and return.
- Leave the page open for two refresh cycles and confirm chart/stocks update without layout shift.

## Calibration Plan

The first implementation should ship with a versioned calibration profile:

- `profile_version`: starts at `dxx-replica-v1`.
- weight fields for pct buckets, limit-up count, board height, turnover, seal amount, auction strength, and breadth penalty.
- compression fields for score scaling and max/min clipping.

Calibration process:

1. Capture same-time reference screenshots or observed values from Duanxianxia public page for several market states.
2. Generate StockMaster curves for the same time using TickFlow and local sources.
3. Compare board order, curve direction, peak/trough location, and score range.
4. Adjust profile weights.
5. Preserve old profile values in tests or fixtures so future changes are intentional.

The goal is not to claim proprietary formula equality. The goal is to make our self-owned generator produce the same decision signals and similar visual curves from our data.

## Rollout

Phase 1:

- Implement qxlive-compatible backend response and replica `/sectors` UI.
- Keep existing sector APIs available for compatibility.
- Hide the old sector workbench from the primary `/sectors` viewport.

Phase 2:

- Add calibration fixtures and refine score weights.
- Add source-status drilldown and cache inspection.
- Improve theme membership with additional concept sources.

Phase 3:

- Fold in涨停池, 连板天梯, and竞价封单 as secondary panels if needed, still under `/sectors` or existing relevant modules.

## Acceptance Decision

This design intentionally prioritizes the user's stated requirement over the previous StockMaster visual direction:

- Pixel-level similarity for the reference panel is required.
- Data and curve semantics are first-class requirements.
- Runtime dependency on Duanxianxia is forbidden.
- `/sectors` remains the single board module; no new board navigation item is added.
