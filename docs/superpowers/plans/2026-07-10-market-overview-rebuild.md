# Market Overview Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the web workbench as a market-overview product while retaining the existing strong-stock screening and morning-auction execution capabilities.

**Architecture:** Keep all backend contracts and business controllers. Replace the legacy shell and presentation layer with a grouped product shell, a resilient dashboard that reads cached results only, and route-level workspaces for screener, auction, market analysis, watchlist, sentiment, and system maintenance. Use pure presentation helpers for navigation, decision ordering, market-session copy, and partial-response states so behavior is unit tested without browser mocking.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, Ant Design 6, Tailwind utilities, ECharts, Node built-in test runner.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `apps/web/lib/appNavigation.ts` | Typed grouped navigation, active-route lookup, and legacy route destinations. |
| `apps/web/lib/appNavigation.test.ts` | Navigation and compatibility-route unit tests. |
| `apps/web/lib/workbenchPresentation.ts` | Copy and class helpers for shared loading, stale, empty, and error states. |
| `apps/web/lib/marketOverview.ts` | Pure decision-queue selection, trading-session label, and panel-state helpers. |
| `apps/web/lib/marketOverview.test.ts` | Dashboard ordering and partial-data unit tests. |
| `apps/web/components/AppShell.tsx` | New product shell with desktop grouped navigation and mobile drawer. |
| `apps/web/components/workbench/PageFrame.tsx` | Shared compact page header and content frame. |
| `apps/web/components/workbench/DataState.tsx` | Shared loading, empty, stale, and recoverable-error surfaces. |
| `apps/web/app/MarketOverviewWorkbench.tsx` | Parallel, cache-only dashboard data loading and top-level refresh behavior. |
| `apps/web/components/overview/*.tsx` | Small, presentational dashboard panels. |
| `apps/web/app/screener/page.tsx` | Stable route for the existing strong-stock screener controller. |
| `apps/web/app/market/*` | Unified sector radar and heatmap workspace. |
| `apps/web/app/system/*` | Unified maintenance and data-source workspace. |

### Task 1: Establish typed navigation and compatibility destinations

**Files:**
- Create: `apps/web/lib/appNavigation.ts`
- Create: `apps/web/lib/appNavigation.test.ts`

- [ ] **Step 1: Write the failing navigation tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { getLegacyDestination, getNavigationSelection, navigationGroups } from "./appNavigation";

test("navigation groups preserve the market decision path", () => {
  assert.deepEqual(navigationGroups.map((group) => group.label), ["市场", "观察", "系统"]);
  assert.deepEqual(getNavigationSelection("/auction"), { groupKey: "market", itemKey: "auction" });
  assert.deepEqual(getNavigationSelection("/stock/603823.SH"), { groupKey: "market", itemKey: null });
});

test("legacy routes resolve to unified workspaces", () => {
  assert.equal(getLegacyDestination("/sectors"), "/market?view=sectors");
  assert.equal(getLegacyDestination("/heatmap"), "/market?view=heatmap");
  assert.equal(getLegacyDestination("/model-maintenance"), "/system?tab=model");
  assert.equal(getLegacyDestination("/settings"), "/system?tab=data");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test --test-name-pattern="navigation" lib/appNavigation.test.ts`

Expected: TypeScript reports that `./appNavigation` cannot be resolved.

- [ ] **Step 3: Implement the minimal route model**

```ts
export type NavigationGroupKey = "market" | "observe" | "system";

export const navigationGroups = [
  { key: "market", label: "市场", items: [
    { key: "overview", href: "/", label: "市场总览" },
    { key: "screener", href: "/screener", label: "强势选股" },
    { key: "auction", href: "/auction", label: "竞价雷达" },
    { key: "market", href: "/market", label: "板块与热图" },
  ] },
  { key: "observe", label: "观察", items: [
    { key: "watchlist", href: "/watchlist", label: "自选与风险" },
    { key: "sentiment", href: "/sentiment", label: "情绪与复盘" },
  ] },
  { key: "system", label: "系统", items: [
    { key: "system", href: "/system", label: "模型与数据源" },
  ] },
] as const;

export function getLegacyDestination(pathname: string): string | null {
  return new Map([["/sectors", "/market?view=sectors"], ["/heatmap", "/market?view=heatmap"], ["/model-maintenance", "/system?tab=model"], ["/settings", "/system?tab=data"]]).get(pathname) ?? null;
}
```

Implement `getNavigationSelection` by selecting the longest matching href. Keep navigation behavior covered in `appNavigation.test.ts`; do not modify unrelated workbench wiring tests in this task.

- [ ] **Step 4: Run focused and full tests**

Run: `corepack pnpm test`

Expected: all existing tests and the new navigation tests pass.

- [ ] **Step 5: Commit the isolated route model**

```bash
git add apps/web/lib/appNavigation.ts apps/web/lib/appNavigation.test.ts
git commit -m "feat: define product navigation model"
```

### Task 2: Replace the global visual foundation and application shell

**Files:**
- Modify: `apps/web/components/AppShell.tsx`
- Modify: `apps/web/components/AntdAppProvider.tsx`
- Modify: `apps/web/app/globals.css`
- Create: `apps/web/components/workbench/PageFrame.tsx`
- Create: `apps/web/components/workbench/DataState.tsx`
- Create: `apps/web/lib/workbenchPresentation.ts`
- Create: `apps/web/lib/workbenchPresentation.test.ts`

- [ ] **Step 1: Write failing presentation tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { dataStateCopy, joinClassNames } from "./workbenchPresentation";

test("data state uses action-oriented copy", () => {
  assert.deepEqual(dataStateCopy("empty", "候选"), {
    title: "暂无候选",
    description: "当前条件下没有符合规则的标的。",
  });
  assert.equal(dataStateCopy("stale", "竞价").action, "重新读取");
});

test("joinClassNames removes falsey presentation classes", () => {
  assert.equal(joinClassNames("page-frame", false, undefined, "dense"), "page-frame dense");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test lib/workbenchPresentation.test.ts`

Expected: module resolution fails for `./workbenchPresentation`.

- [ ] **Step 3: Implement shared primitives and the product shell**

```tsx
export function PageFrame({ title, context, status, actions, children }: PageFrameProps) {
  return <main className="page-frame"><header className="page-command-bar"><div><h1>{title}</h1>{context}</div><div>{status}{actions}</div></header>{children}</main>;
}
```

`PageFrame` accepts only `title`, `actions`, `status`, `context`, and `children`; do not add `eyebrow`, `description`, or `meta`. `DataState` uses a discriminated `kind: "loading" | "empty" | "stale" | "error"` and renders an Ant Design skeleton, empty state, or alert with one recovery action.

Rebuild `AppShell` from `navigationGroups`: a 216px labelled desktop sidebar above 980px, an icon-only 64px collapsed state saved under `stockmaster:app-shell-collapsed`, and a `Drawer` below 980px. Do not retain duplicate settings links.

Replace tokens with:

```css
:root {
  --app-canvas: #edf3f8;
  --app-surface: #ffffff;
  --app-raised: #f7f9fc;
  --app-ink: #182336;
  --app-muted: #697991;
  --app-border: #d9e2ed;
  --app-primary: #1769e0;
  --market-rise: #d9363e;
  --market-fall: #07845e;
  --market-warning: #a86000;
}
```

Set matching Ant Design `colorPrimary`, background, text, border, Layout, and table tokens. Retain old `--workbench-*` variables only until Task 8 removes their final market and system consumers.

- [ ] **Step 4: Run tests and typecheck**

Run: `corepack pnpm test`

Expected: primitives compile, route metadata is consumed by the shell, and all tests pass.

- [ ] **Step 5: Commit the shell foundation**

```bash
git add apps/web/components/AppShell.tsx apps/web/components/AntdAppProvider.tsx apps/web/app/globals.css apps/web/components/workbench/PageFrame.tsx apps/web/components/workbench/DataState.tsx apps/web/lib/workbenchPresentation.ts apps/web/lib/workbenchPresentation.test.ts
git commit -m "feat: rebuild product shell and workbench primitives"
```

### Task 3: Build a testable, cache-only dashboard data model

**Files:**
- Create: `apps/web/lib/marketOverview.ts`
- Create: `apps/web/lib/marketOverview.test.ts`
- Create: `apps/web/app/MarketOverviewWorkbench.tsx`
- Create: `apps/web/components/overview/DecisionQueue.tsx`
- Create: `apps/web/components/overview/MarketPulse.tsx`
- Create: `apps/web/components/overview/SectorHeatmapPreview.tsx`
- Create: `apps/web/components/overview/MarketFeed.tsx`
- Modify: `apps/web/app/page.tsx`

- [ ] **Step 1: Write failing dashboard selection tests**

```ts
test("top3 keeps selected bucket items in rank order", () => {
  assert.deepEqual(
    selectTop3([{ symbol: "B", bucket: "selected", rank: 2 }, { symbol: "A", bucket: "selected", rank: 1 }, { symbol: "C", bucket: "watch", rank: 3 }] as AuctionModelPredictionItem[]).map((item) => item.symbol),
    ["A", "B"],
  );
});

const screenResponse = {
  items: [{ symbol: "603001.SH", status: "focus" }, { symbol: "300001.SZ", status: "wait_pullback" }, { symbol: "600001.SH", status: "data_incomplete" }],
  watchlist_risk_items: [],
} as StrongStockScreeningResponse;

test("decision queue keeps usable screening candidates before data-incomplete rows", () => {
  assert.deepEqual(selectScreenCandidates(screenResponse).map((item) => item.symbol), ["603001.SH", "300001.SZ"]);
});

test("settled panel state isolates a rejected service", () => {
  assert.deepEqual(toPanelState({ status: "rejected", reason: new Error("timeout") }), { kind: "error", value: null });
});
```

Use fixture builders to construct the required `StrongStockScreeningResponse` fields. Include `watchlist_risk_items` in the fixture; do not introduce an `empty` screening status.

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test lib/marketOverview.test.ts`

Expected: module resolution fails for `./marketOverview`.

- [ ] **Step 3: Implement pure dashboard helpers**

```ts
export function selectTop3(items: AuctionModelPredictionItem[]) {
  return items
    .filter((item) => item.bucket === "selected")
    .sort((a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity))
    .slice(0, 3);
}

export function selectScreenCandidates(response: StrongStockScreeningResponse | null) {
  return (response?.items ?? []).filter((item) => item.status !== "data_incomplete").slice(0, 6);
}

export type PanelState<T> = { kind: "ready"; value: T } | { kind: "error"; value: null };

export function toPanelState<T>(result: PromiseSettledResult<T>): PanelState<T> {
  return result.status === "fulfilled" ? { kind: "ready", value: result.value } : { kind: "error", value: null };
}
```

Also export `getShanghaiTradeDate(now = new Date())` and `getMarketSession(now = new Date())`; each returns plain data used for labels and must be tested with fixed dates.

- [ ] **Step 4: Implement resilient dashboard loading and panels**

`MarketOverviewWorkbench` uses one `Promise.allSettled` request batch:

```ts
const results = await Promise.allSettled([
  getLatestScreenRun(),
  getMarketOverview(),
  getAuctionModelTop3(getShanghaiTradeDate(), { cacheOnly: true }),
  getSectorRadar(12),
  getSentimentSummary(getShanghaiTradeDate(), 80, false),
]);
```

Map results individually with `toPanelState`. Keep the last successful result while a later refresh is pending or fails. Do not import `createAuctionModelTop3Job`, `createScreenRunJob`, or any mutation API in this file. `DecisionQueue` links Top3 rows to `/stock/${symbol}?from=auction-model`, screening rows to `/stock/${symbol}`, and risk rows to `/watchlist`.

Replace the root dynamic import in `app/page.tsx` with `MarketOverviewWorkbench`; its loading fallback uses `PageFrame` plus independent skeleton panels.

- [ ] **Step 5: Run dashboard tests and full test suite**

Run: `corepack pnpm test`

Expected: dashboard helper tests pass and the selection business tests remain unchanged.

- [ ] **Step 6: Commit the dashboard**

```bash
git add apps/web/lib/marketOverview.ts apps/web/lib/marketOverview.test.ts apps/web/app/MarketOverviewWorkbench.tsx apps/web/components/overview apps/web/app/page.tsx
git commit -m "feat: add resilient market overview dashboard"
```

### Task 4: Move the complete strong-stock workflow to its dedicated route

**Files:**
- Create: `apps/web/app/screener/page.tsx`
- Modify: `apps/web/app/HomeWorkbench.tsx`
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Modify: `apps/web/app/watchlist/WatchlistWorkspace.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Extend the existing source-level route test**

```ts
assert.match(screenerPageSource, /HomeWorkbench/);
assert.match(navigationSource, /href: "\\/screener"/);
assert.match(watchlistWorkspaceSource, /href="\\/screener"/);
assert.doesNotMatch(rootPageSource, /HomeWorkbench/);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test --test-name-pattern="standalone strong stock workbench" lib/strongStockWorkbench.test.ts`

Expected: the new page source cannot be read or expected `/screener` references are absent.

- [ ] **Step 3: Add the route without changing screening behavior**

```tsx
// apps/web/app/screener/page.tsx
import { HomeWorkbench } from "../HomeWorkbench";

export default function ScreenerPage() {
  return <HomeWorkbench />;
}
```

`HomeWorkbench` keeps its filters, `localStorage` key, background job polling, source refresh, and watchlist-add handlers. Only replace the outer visual frame through `ScreenerWorkbench`; do not change `createScreenRunJob` payloads, candidate statuses, or existing result helpers. Replace the watchlist return link with `/screener`.

- [ ] **Step 4: Run regression tests**

Run: `corepack pnpm test`

Expected: scan-limit, strategy, filter persistence, candidate status, and stock-detail link checks remain green.

- [ ] **Step 5: Commit the screener route**

```bash
git add apps/web/app/screener/page.tsx apps/web/app/HomeWorkbench.tsx apps/web/components/ScreenerWorkbench.tsx apps/web/app/watchlist/WatchlistWorkspace.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "feat: move strong stock workflow to dedicated route"
```

### Task 5: Merge sector radar and heatmap into one market-analysis route

**Files:**
- Create: `apps/web/app/market/page.tsx`
- Create: `apps/web/app/market/MarketWorkspace.tsx`
- Create: `apps/web/lib/marketWorkspace.ts`
- Create: `apps/web/lib/marketWorkspace.test.ts`
- Modify: `apps/web/lib/stockNavigation.ts`
- Modify: `apps/web/lib/stockNavigation.test.ts`
- Modify: `apps/web/app/heatmap/HeatmapWorkspace.tsx`
- Modify: `apps/web/app/sectors/SectorPageWorkspace.tsx`
- Modify: `apps/web/app/heatmap/page.tsx`
- Modify: `apps/web/app/sectors/page.tsx`
- Modify: `apps/web/lib/heatmap.test.ts`

- [ ] **Step 1: Write failing tab and stock-context tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { normalizeMarketView } from "./marketWorkspace";
import { resolveStockDetailContext } from "./stockNavigation";

test("market tab normalizes unknown input to sectors", () => {
  assert.equal(normalizeMarketView("heatmap"), "heatmap");
  assert.equal(normalizeMarketView("bad-input"), "sectors");
});

test("legacy market detail sources return to the unified route", () => {
  assert.equal(resolveStockDetailContext(new URLSearchParams("from=sectors")).returnHref, "/market?view=sectors");
  assert.equal(resolveStockDetailContext(new URLSearchParams("from=heatmap")).returnHref, "/market?view=heatmap");
});

```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test lib/marketWorkspace.test.ts lib/stockNavigation.test.ts`

Expected: `./marketWorkspace` cannot be resolved.

- [ ] **Step 3: Extract embeddable market content**

Change `HeatmapWorkspace` and `SectorPageWorkspace` so each exports a content component without `WorkbenchPage`; retain their existing fetch logic, query construction, chart options, cache rules, and stock-detail context. `MarketWorkspace` reads `view` from `useSearchParams`, uses Ant Design `Segmented`, and updates the tab without scrolling:

```tsx
const view = normalizeMarketView(searchParams.get("view"));
return <PageFrame title="板块与热图" actions={<Segmented value={view} options={MARKET_VIEW_OPTIONS} onChange={changeView} />}>
  {view === "sectors" ? <SectorRadarContent /> : <HeatmapContent />}
</PageFrame>;
```

Implement `changeView` as `router.replace(`/market?view=${next}`, { scroll: false })`. Convert old `/sectors` and `/heatmap` pages to server redirects using `redirect("/market?view=sectors")` and `redirect("/market?view=heatmap")`.

Update `resolveStockDetailContext` so existing `from=sectors` returns `/market?view=sectors` and existing `from=heatmap` returns `/market?view=heatmap`. Update the corresponding assertions in `stockNavigation.test.ts`; retain `from` values rather than inventing a third market source value.

- [ ] **Step 4: Run focused and full tests**

Run: `corepack pnpm test`

Expected: existing heatmap query and sector radar tests remain green; new tab normalization tests pass.

- [ ] **Step 5: Commit the market workspace**

```bash
git add apps/web/app/market apps/web/app/heatmap apps/web/app/sectors apps/web/lib/marketWorkspace.ts apps/web/lib/marketWorkspace.test.ts apps/web/lib/stockNavigation.ts apps/web/lib/stockNavigation.test.ts apps/web/lib/heatmap.test.ts
git commit -m "feat: unify sector and heatmap analysis"
```

### Task 6: Consolidate model maintenance and data sources into system

**Files:**
- Create: `apps/web/app/system/page.tsx`
- Create: `apps/web/app/system/SystemWorkspace.tsx`
- Create: `apps/web/lib/systemWorkspace.ts`
- Create: `apps/web/lib/systemWorkspace.test.ts`
- Modify: `apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx`
- Modify: `apps/web/app/settings/SettingsWorkspace.tsx`
- Modify: `apps/web/app/model-maintenance/page.tsx`
- Modify: `apps/web/app/settings/page.tsx`

- [ ] **Step 1: Write failing system-tab tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { normalizeSystemTab } from "./systemWorkspace";

test("system tab accepts model and data only", () => {
  assert.equal(normalizeSystemTab("model"), "model");
  assert.equal(normalizeSystemTab("data"), "data");
  assert.equal(normalizeSystemTab(null), "model");
  assert.equal(normalizeSystemTab("unknown"), "model");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test lib/systemWorkspace.test.ts`

Expected: `./systemWorkspace` cannot be resolved.

- [ ] **Step 3: Extract content and compose the system route**

Export `ModelMaintenanceContent` and `SettingsContent` that retain their API calls, job states, packet pages, health checks, and notification forms. `SystemWorkspace` is the only new wrapper:

```tsx
const tab = normalizeSystemTab(searchParams.get("tab"));
return <PageFrame title="模型与数据源" actions={<Segmented value={tab} options={SYSTEM_TAB_OPTIONS} onChange={changeTab} />}>
  {tab === "model" ? <ModelMaintenanceContent /> : <SettingsContent />}
</PageFrame>;
```

Replace `/model-maintenance` and `/settings` with server redirects to `/system?tab=model` and `/system?tab=data`. Keep `/model-maintenance/packets/[packetId]` as a direct readable packet page.

- [ ] **Step 4: Run tests**

Run: `corepack pnpm test`

Expected: cache, system-health, model-maintenance, and settings checks pass.

- [ ] **Step 5: Commit system consolidation**

```bash
git add apps/web/app/system apps/web/app/model-maintenance apps/web/app/settings apps/web/lib/systemWorkspace.ts apps/web/lib/systemWorkspace.test.ts
git commit -m "feat: consolidate system maintenance workspace"
```

### Task 7: Migrate operational workspaces and remove legacy presentation

**Files:**
- Modify: `apps/web/app/auction/AuctionWorkspace.tsx`
- Modify: `apps/web/app/auction/page.tsx`
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Modify: `apps/web/components/screener/FilterLogicRail.tsx`
- Modify: `apps/web/components/screener/CandidateResults.tsx`
- Modify: `apps/web/components/screener/MarketOverviewPanels.tsx`
- Modify: `apps/web/components/screener/GsgfWorkflowPanels.tsx`
- Modify: `apps/web/components/screener/GsgfFunnelPanel.tsx`
- Modify: `apps/web/app/watchlist/WatchlistWorkspace.tsx`
- Modify: `apps/web/app/watchlist/page.tsx`
- Modify: `apps/web/app/sentiment/SentimentWorkspace.tsx`
- Modify: `apps/web/app/sentiment/page.tsx`
- Modify: `apps/web/app/stock/[symbol]/StockKlineWorkspace.tsx`
- Modify: `apps/web/app/stock/[symbol]/page.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Make legacy-frame removal fail first**

```ts
const screenerWorkspaceSource = readFileSync(new URL("../components/ScreenerWorkbench.tsx", import.meta.url), "utf8");
const stockWorkspaceSource = readFileSync(new URL("../app/stock/[symbol]/StockKlineWorkspace.tsx", import.meta.url), "utf8");

for (const source of [auctionWorkspaceSource, screenerWorkspaceSource, watchlistWorkspaceSource, sentimentWorkspaceSource, stockWorkspaceSource]) {
  assert.doesNotMatch(source, /WorkbenchPage/);
  assert.match(source, /PageFrame/);
}
assert.doesNotMatch(globalsSource, /--workbench-bg: #f5f3f0/);
assert.doesNotMatch(globalsSource, /#1d1b18/);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test --test-name-pattern="standalone strong stock workbench" lib/strongStockWorkbench.test.ts`

Expected: source assertions fail because workspaces still import `WorkbenchPage` and old tokens.

- [ ] **Step 3: Replace page chrome without changing operational logic**

For each workspace, replace the opening `WorkbenchPage` element with `PageFrame`, map its existing `title`, `actions`, `status`, and date value to `PageFrame` props, and replace the matching closing tag. The JSX between those tags is retained verbatim. This is a presentation-only substitution.

Preserve auction background-job polling, cached Top3 behavior, local-storage persistence, sector-radar chart behavior, sentiment monitor actions, and stock `from` navigation contexts. Replace brown/cream hard-coded colors in touched files with new token classes. Keep red/green only for market rise/fall, risk, or signal state.

Do not delete `WorkbenchPage` and `workbenchLayout` in this task because the market and system extraction still references them. Task 8 removes them after every route has migrated.

- [ ] **Step 4: Run regression suite and static cleanup checks**

Run:

```bash
corepack pnpm test
rg "WorkbenchPage|workbenchLayout" apps/web/app/auction apps/web/app/watchlist apps/web/app/sentiment 'apps/web/app/stock/[symbol]' apps/web/components/ScreenerWorkbench.tsx apps/web/components/screener
git diff --check
```

Expected: tests pass, ripgrep prints no operational-workspace references, and `git diff --check` prints nothing.

- [ ] **Step 5: Commit migrated operational surfaces**

```bash
git add apps/web/app/auction apps/web/app/screener apps/web/app/watchlist apps/web/app/sentiment 'apps/web/app/stock/[symbol]' apps/web/components/ScreenerWorkbench.tsx apps/web/components/screener apps/web/app/globals.css apps/web/lib/strongStockWorkbench.test.ts
git commit -m "refactor: migrate operational workspaces to product frame"
```

### Task 8: Migrate merged workspaces and remove legacy token consumers

**Files:**
- Modify: `apps/web/app/market/MarketWorkspace.tsx`
- Modify: `apps/web/app/heatmap/HeatmapWorkspace.tsx`
- Modify: `apps/web/app/sectors/SectorPageWorkspace.tsx`
- Modify: `apps/web/app/sectors/SectorReplicaPanel.tsx`
- Modify: `apps/web/app/system/SystemWorkspace.tsx`
- Modify: `apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx`
- Modify: `apps/web/app/settings/SettingsWorkspace.tsx`
- Modify: `apps/web/app/globals.css`
- Delete: `apps/web/components/workbench/WorkbenchPage.tsx`
- Delete: `apps/web/components/workbench/workbenchLayout.ts`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Add failing source-level token assertions**

```ts
const marketWorkspaceSource = readFileSync(new URL("../app/market/MarketWorkspace.tsx", import.meta.url), "utf8");
const heatmapWorkspaceSource = readFileSync(new URL("../app/heatmap/HeatmapWorkspace.tsx", import.meta.url), "utf8");
const sectorWorkspaceSource = readFileSync(new URL("../app/sectors/SectorPageWorkspace.tsx", import.meta.url), "utf8");
const systemWorkspaceSource = readFileSync(new URL("../app/system/SystemWorkspace.tsx", import.meta.url), "utf8");

for (const source of [marketWorkspaceSource, heatmapWorkspaceSource, sectorWorkspaceSource, systemWorkspaceSource]) {
  assert.doesNotMatch(source, /workbench-panel|workbench-page|bg-\[#f5f3f0\]|#1d1b18/);
}
assert.doesNotMatch(globalsSource, /--workbench-/);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --experimental-strip-types --test --test-name-pattern="standalone strong stock workbench" lib/strongStockWorkbench.test.ts`

Expected: legacy workbench classes and color literals are still present in the composed market and system workspaces.

- [ ] **Step 3: Finish token migration and delete retired frame helpers**

Use `PageFrame` in `MarketWorkspace` and `SystemWorkspace`; their children use only `app-*`, `market-*`, and standard Ant Design class names. Replace sector replica CSS selectors with `market-radar-*` names and map their colors to `--app-*` and `--market-*` tokens. Preserve the fixed chart axis, comparison board behavior, heatmap filters, model packet actions, and data-source health actions.

After imports have been replaced across `apps/web`, delete `WorkbenchPage.tsx` and `workbenchLayout.ts`. Remove every `--workbench-*` declaration from `globals.css`; do not delete `market-*` semantic color classes.

- [ ] **Step 4: Run full regression and cleanup checks**

Run:

```bash
corepack pnpm test
rg "WorkbenchPage|workbenchLayout|--workbench-" apps/web --glob '!**/*.test.ts'
git diff --check
```

Expected: tests pass, ripgrep prints no production references, and no whitespace errors are reported.

- [ ] **Step 5: Commit merged-workspace migration**

```bash
git add apps/web/app/market apps/web/app/heatmap apps/web/app/sectors apps/web/app/system apps/web/app/model-maintenance apps/web/app/settings apps/web/components/workbench apps/web/app/globals.css apps/web/lib/strongStockWorkbench.test.ts
git commit -m "refactor: complete market workspace visual migration"
```

### Task 9: Build and visually verify the product flow

**Files:**
- Modify only when verification finds a concrete defect: the smallest affected `apps/web` file and its focused test.
- Modify: `README.md` only when route links or screenshots are explicitly documented there.

- [ ] **Step 1: Run production verification**

Run:

```bash
corepack pnpm test
corepack pnpm build
git diff --check
```

Expected: tests pass, the Next production build succeeds, and diff check is empty.

- [ ] **Step 2: Start an isolated development server**

Run: `NEXT_DIST_DIR=.next-dev corepack pnpm dev -- --port 3112`

Expected: Next reports `http://127.0.0.1:3112` as ready. Use a different free port only if 3112 is occupied.

- [ ] **Step 3: Verify the desktop and mobile decision paths**

Open `/`, `/screener`, `/auction`, `/market?view=sectors`, `/market?view=heatmap`, `/watchlist`, `/sentiment`, `/system?tab=model`, `/system?tab=data`, and `/stock/603823.SH`.

At 1440px confirm labelled navigation, priority queue, tables, charts, and command bars stay inside their containers. At 390px confirm the drawer opens, no horizontal scroll exists, text does not overlap, and a candidate can reach the stock-detail page. Block one dashboard API request and confirm unrelated panels remain visible with only the failed panel offering recovery.

- [ ] **Step 4: Test and repair only verified defects**

For every issue found in Step 3, first add the smallest pure-helper or source-level test that fails. Repair only the affected component or token, rerun that focused test, then rerun `corepack pnpm test`. Do not make unrelated cosmetic edits during this step.

- [ ] **Step 5: Commit verification fixes only if present**

```bash
git status --short
git add apps/web
git commit -m "fix: polish market overview workbench"
```

If no verification fix is required, do not create an empty commit.
