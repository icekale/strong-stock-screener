# Homepage Market Trends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lazy-loaded homepage trend band with sector rotation and market emotion curves while preserving the existing market snapshot first row.

**Architecture:** `MarketOverviewWorkbench` owns activation and independent panel states. Pure helpers in `marketOverviewTrend.ts` normalize emotion samples and build the chart option. `MarketTrendPanels.tsx` owns presentation, while a small lazy ECharts renderer keeps the chart bundle outside the initial snapshot render.

**Tech Stack:** Next.js 15, React 19, TypeScript, ECharts 5, node:test, existing product CSS tokens.

---

### Task 1: Trend Data Contracts

**Files:**
- Create: `apps/web/lib/marketOverviewTrend.ts`
- Create: `apps/web/lib/marketOverviewTrend.test.ts`

- [ ] **Step 1: Write failing normalization tests**

Test that emotion samples are sorted by timestamp, duplicate timestamps keep the newest sample, breadth is `advance / (advance + decline) * 100`, and null counts produce null breadth.

```ts
test("market emotion trend sorts samples and calculates breadth", () => {
  const trend = buildMarketEmotionTrend(snapshot([
    sample("2026-07-10T10:00:00+08:00", 52, 3000, 2000),
    sample("2026-07-10T09:30:00+08:00", 41, 2000, 3000),
  ]));
  assert.deepEqual(trend.times, ["09:30", "10:00"]);
  assert.deepEqual(trend.breadth, [40, 60]);
});
```

- [ ] **Step 2: Verify RED**

Run:

```bash
cd apps/web
node --experimental-strip-types --test lib/marketOverviewTrend.test.ts
```

Expected: FAIL because `marketOverviewTrend.ts` and `buildMarketEmotionTrend` do not exist.

- [ ] **Step 3: Implement the minimal pure helpers**

Return a serializable view model:

```ts
export type MarketEmotionTrend = {
  breadth: Array<number | null>;
  emotion: number[];
  firstScore: number | null;
  latestScore: number | null;
  times: string[];
};
```

Add `buildMarketEmotionChartOption(trend)` using the existing product palette, a 0-100 y-axis, compact legend, confined tooltip, no area gradient, and no symbols except the final point.

- [ ] **Step 4: Verify GREEN**

Run the focused test and confirm all cases pass.

### Task 2: Trend Panels And Lazy Chart Renderer

**Files:**
- Create: `apps/web/components/overview/OverviewTrendChart.tsx`
- Create: `apps/web/components/overview/MarketTrendPanels.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: Write failing presentation contracts**

Assert that the trend panels expose `板块轮动`, `盘中情绪走势`, links to `/market?view=sectors` and `/sentiment`, and scoped classes `market-trend-grid`, `market-trend-chart`, and `market-trend-summary`.

- [ ] **Step 2: Verify RED**

Run `node --experimental-strip-types --test lib/marketOverview.test.ts` and confirm the new assertions fail because the components are absent.

- [ ] **Step 3: Implement the panels**

Use the existing sector chart option helper:

```ts
buildSectorReplicaChartOption({
  axis: data.axis,
  compact: true,
  mode: "strength",
  series: data.series.filter(hasUsablePoints).slice(0, 6),
});
```

Render local loading, empty, stale, and error states through `DataState`. The generic chart renderer dynamically imports `echarts`, attaches `ResizeObserver`, and disposes the chart on cleanup.

- [ ] **Step 4: Add stable responsive geometry**

Add a two-column desktop grid, one-column layout below 960px, stable chart heights, wrapping summary rows, and no shadows or nested cards.

- [ ] **Step 5: Verify GREEN**

Run the focused market overview tests.

### Task 3: Homepage Activation And Data Flow

**Files:**
- Modify: `apps/web/app/MarketOverviewWorkbench.tsx`
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: Write failing lazy-load contracts**

Assert that the homepage imports `getSectorReplicaRadar` and `getMarketEmotionSnapshot`, renders `MarketTrendPanels`, uses `IntersectionObserver`, and does not restore `DecisionQueue`, `getLatestScreenRun`, or `getAuctionModelTop3`.

- [ ] **Step 2: Verify RED**

Run the focused test and confirm the new API and activation assertions fail.

- [ ] **Step 3: Implement independent trend refresh**

Add two `PanelState` values, a trend request generation ref, activation state, and a `refreshTrends` callback using `Promise.allSettled` plus `executeLatestOnly`. Activate it once the anchor approaches the viewport.

```ts
const observer = new IntersectionObserver(
  ([entry]) => entry?.isIntersecting && setTrendsActivated(true),
  { rootMargin: "240px" },
);
```

The main refresh button calls the existing snapshot refresh and refreshes trends only when activated.

- [ ] **Step 4: Update the loading placeholder**

Add two compact trend placeholders below the index snapshot so the initial layout matches the final page structure without blocking the first market data request.

- [ ] **Step 5: Verify GREEN**

Run the focused tests, then `corepack pnpm test`.

### Task 4: Visual And Production Verification

**Files:**
- Inspect all files changed above.

- [ ] **Step 1: Run production checks**

```bash
cd apps/web
corepack pnpm test
corepack pnpm build
cd ../..
git diff --check
```

- [ ] **Step 2: Verify real-data rendering**

Open `/` against the local API and check desktop `1440x1100`, tablet `781x995`, and mobile `390x844`. Confirm the trend band loads, each panel can fail independently, legends remain readable, and `documentElement.scrollWidth === clientWidth`.

- [ ] **Step 3: Commit implementation**

Stage only the homepage trend files and commit:

```bash
git commit -m "feat: add homepage market trend panels"
```
