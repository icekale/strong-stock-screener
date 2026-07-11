# Market Overview Homepage Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the market overview homepage so sector flow and key market confirmation data occupy the first viewport while the decision queue moves to the bottom.

**Architecture:** Keep the existing parallel data loader and API contracts. Add pure presentation helpers for sector-flow normalization and market-breadth ratios, then rebuild the existing overview components around a compact desktop split layout and a mobile segmented flow list. Remove the duplicate homepage market feed without deleting its reusable source file.

**Tech Stack:** Next.js 15, React 19, TypeScript 5.7, Ant Design 6, Tailwind utilities, CSS custom properties, Node test runner.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `apps/web/lib/marketOverview.ts` | Pure selection and percentage helpers for sector flow and breadth. |
| `apps/web/lib/marketOverview.test.ts` | Behavioral and source-order tests for the redesigned homepage. |
| `apps/web/components/overview/SectorHeatmapPreview.tsx` | Desktop diverging flow chart and mobile segmented flow ranking. |
| `apps/web/components/overview/MarketPulse.tsx` | Compact market-state panel and index strip. |
| `apps/web/components/overview/DecisionQueue.tsx` | Existing decision content with compact empty-state treatment. |
| `apps/web/app/MarketOverviewWorkbench.tsx` | Homepage module order and removal of duplicate `MarketFeed`. |
| `apps/web/app/globals.css` | Stable overview layout, bar geometry, responsive re-composition, and compact states. |

### Task 1: Add testable sector-flow and breadth presentation helpers

**Files:**
- Modify: `apps/web/lib/marketOverview.ts`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: Write failing helper tests**

Add imports for `buildSectorFlowRows` and `marketBreadthPercent`, then add:

```ts
test("sector flow rows ignore null values, keep four items, and normalize each direction", () => {
  const rows = buildSectorFlowRows([
    sectorItem("A", 20),
    sectorItem("B", 10),
    sectorItem("C", null),
    sectorItem("D", 5),
    sectorItem("E", 2),
    sectorItem("F", 1),
  ]);

  assert.deepEqual(rows.map((row) => [row.item.name, row.widthPercent]), [
    ["A", 100],
    ["B", 50],
    ["D", 25],
    ["E", 10],
  ]);
});

test("sector flow rows remain finite when the largest absolute flow is zero", () => {
  assert.deepEqual(buildSectorFlowRows([sectorItem("A", 0)]), [{ item: sectorItem("A", 0), widthPercent: 0 }]);
});

test("market breadth percentage excludes unchanged stocks and handles an empty denominator", () => {
  assert.equal(marketBreadthPercent(3772, 1678), 69.21);
  assert.equal(marketBreadthPercent(null, 10), 0);
  assert.equal(marketBreadthPercent(0, 0), 0);
});
```

Add this fixture near the existing fixture helpers:

```ts
function sectorItem(name: string, netFlowCny: number | null) {
  return {
    name,
    source: "test",
    change_pct: 1,
    turnover_cny: 100,
    advance_count: 1,
    decline_count: 0,
    leader: `${name} leader`,
    net_flow_cny: netFlowCny,
    strength_score: 10,
  };
}
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd apps/web
node --experimental-strip-types --test --test-name-pattern="sector flow rows|market breadth percentage" lib/marketOverview.test.ts
```

Expected: FAIL because the two helpers are not exported.

- [ ] **Step 3: Implement the minimal helpers**

In `marketOverview.ts`, import `SectorRadarItem` and add:

```ts
export type SectorFlowRow = {
  item: SectorRadarItem;
  widthPercent: number;
};

export function buildSectorFlowRows(items: SectorRadarItem[], limit = 4): SectorFlowRow[] {
  const selected = items.filter((item) => item.net_flow_cny !== null).slice(0, limit);
  const maximum = Math.max(...selected.map((item) => Math.abs(item.net_flow_cny ?? 0)), 0);

  return selected.map((item) => ({
    item,
    widthPercent: maximum === 0 ? 0 : Number(((Math.abs(item.net_flow_cny ?? 0) / maximum) * 100).toFixed(2)),
  }));
}

export function marketBreadthPercent(advanceCount: number | null, declineCount: number | null): number {
  if (advanceCount === null || declineCount === null) return 0;
  const total = advanceCount + declineCount;
  return total === 0 ? 0 : Number(((advanceCount / total) * 100).toFixed(2));
}
```

- [ ] **Step 4: Run focused and full helper tests**

Run:

```bash
cd apps/web
node --experimental-strip-types --test lib/marketOverview.test.ts
```

Expected: all `marketOverview` tests pass.

- [ ] **Step 5: Commit the helper behavior**

```bash
git add apps/web/lib/marketOverview.ts apps/web/lib/marketOverview.test.ts
git commit -m "feat: add market overview chart helpers"
```

### Task 2: Rebuild the sector-flow and market-state panels

**Files:**
- Modify: `apps/web/components/overview/SectorHeatmapPreview.tsx`
- Modify: `apps/web/components/overview/MarketPulse.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: Write failing component contract tests**

Add source tests that require the approved behavior:

```ts
test("sector flow preview uses normalized rows and a mobile direction switch", () => {
  const source = readFileSync(new URL("../components/overview/SectorHeatmapPreview.tsx", import.meta.url), "utf8");
  assert.match(source, /buildSectorFlowRows/);
  assert.match(source, /aria-pressed/);
  assert.match(source, /sector-flow-chart/);
});

test("market pulse exposes prominent breadth and compact index strip", () => {
  const source = readFileSync(new URL("../components/overview/MarketPulse.tsx", import.meta.url), "utf8");
  assert.match(source, /marketBreadthPercent/);
  assert.match(source, /market-state__value/);
  assert.match(source, /market-index-strip/);
});
```

- [ ] **Step 2: Run the focused contract tests and verify RED**

Run:

```bash
cd apps/web
node --experimental-strip-types --test --test-name-pattern="sector flow preview|market pulse exposes" lib/marketOverview.test.ts
```

Expected: FAIL because the approved class names and mobile control are absent.

- [ ] **Step 3: Rebuild `SectorHeatmapPreview`**

Use `useState<"inflow" | "outflow">("inflow")`. Build each direction independently with `buildSectorFlowRows`, render a desktop `.sector-flow-chart` with a central zero axis and mirrored rows, and render a mobile `.sector-flow-mobile` with two buttons using `aria-pressed`. Keep existing `DataState`, source/口径 subtitle, and `/market?view=sectors` link.

Each row must render:

```tsx
<div className="sector-flow-bar" style={{ "--sector-flow-width": `${row.widthPercent}%` } as CSSProperties}>
  <span>{row.item.name}</span>
  <strong>{formatCny(row.item.net_flow_cny)}</strong>
</div>
<div className="sector-flow-meta">
  {row.item.leader ?? "-"} · {formatPercent(row.item.change_pct)} · 强度 {row.item.strength_score.toFixed(1)}
</div>
```

- [ ] **Step 4: Rebuild `MarketPulse`**

Keep market and sentiment state handling independent. Render `.market-state-grid` with total turnover, breadth, limit counts, and sentiment. Use `marketBreadthPercent` for `.market-breadth__advance` width and an accessible label containing advance, decline, and unchanged counts. Render indices in `.market-index-strip` below the split first row.

- [ ] **Step 5: Add scoped responsive styles**

Add CSS for:

```css
.market-overview-lead { display:grid; grid-template-columns:minmax(0,1.65fr) minmax(280px,.85fr); gap:16px; }
.sector-flow-chart { position:relative; }
.sector-flow-axis { position:absolute; inset-block:0; left:50%; width:1px; background:var(--app-border); }
.sector-flow-bar { width:var(--sector-flow-width); min-width:3px; }
.sector-flow-mobile { display:none; }
.market-state__value { font-size:24px; line-height:30px; font-weight:700; font-variant-numeric:tabular-nums; }
.market-index-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); }
```

At `max-width: 979px`, stack `.market-overview-lead`, hide `.sector-flow-chart`, show `.sector-flow-mobile`, and use a two-column market-state/index grid. At `max-width: 560px`, keep two-column metrics but reduce spacing, never the value font below 20px.

- [ ] **Step 6: Run tests and TypeScript**

Run:

```bash
cd apps/web
corepack pnpm test
```

Expected: all web tests and `tsc --noEmit` pass.

- [ ] **Step 7: Commit the panel rebuild**

```bash
git add apps/web/components/overview/SectorHeatmapPreview.tsx apps/web/components/overview/MarketPulse.tsx apps/web/app/globals.css apps/web/lib/marketOverview.test.ts
git commit -m "feat: rebuild market overview lead panels"
```

### Task 3: Reorder the homepage and compact the decision queue

**Files:**
- Modify: `apps/web/app/MarketOverviewWorkbench.tsx`
- Modify: `apps/web/components/overview/DecisionQueue.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/lib/marketOverview.test.ts`

- [ ] **Step 1: Write the failing homepage order test**

```ts
test("homepage renders market direction before the decision queue without the duplicate feed", () => {
  const source = readFileSync(new URL("../app/MarketOverviewWorkbench.tsx", import.meta.url), "utf8");
  assert.ok(source.indexOf("SectorHeatmapPreview") < source.indexOf("DecisionQueue"));
  assert.ok(source.indexOf("MarketPulse") < source.indexOf("DecisionQueue"));
  assert.doesNotMatch(source, /<MarketFeed/);
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd apps/web
node --experimental-strip-types --test --test-name-pattern="homepage renders market direction" lib/marketOverview.test.ts
```

Expected: FAIL because `DecisionQueue` currently renders first and `MarketFeed` is present.

- [ ] **Step 3: Reorder the workbench**

Remove the `MarketFeed` import and JSX. Render:

```tsx
<div className="market-overview-layout">
  <div className="market-overview-lead">
    <SectorHeatmapPreview onRefresh={() => void refresh()} sectorRadar={sectorRadar} />
    <MarketPulse market={market} onRefresh={() => void refresh()} sentiment={sentiment} />
  </div>
  <DecisionQueue auction={auction} onRefresh={() => void refresh()} screening={screening} />
</div>
```

`MarketPulse` owns its index strip inside the right panel on desktop and spans the full lead width through CSS only when required by the final visual check; do not add another data request.

- [ ] **Step 4: Compact decision queue empty states**

Add `decision-queue` and `decision-queue__block` class names. Scope empty/loading states inside the queue to reduced padding and skeleton row count through CSS; do not alter selection or navigation logic.

- [ ] **Step 5: Run full web tests and build**

Run:

```bash
cd apps/web
corepack pnpm test
corepack pnpm build
```

Expected: all tests pass and the production build completes.

- [ ] **Step 6: Commit homepage composition**

```bash
git add apps/web/app/MarketOverviewWorkbench.tsx apps/web/components/overview/DecisionQueue.tsx apps/web/app/globals.css apps/web/lib/marketOverview.test.ts
git commit -m "feat: prioritize market direction on homepage"
```

### Task 4: Verify responsive behavior with real data

**Files:**
- Modify if required by findings: `apps/web/components/overview/SectorHeatmapPreview.tsx`
- Modify if required by findings: `apps/web/components/overview/MarketPulse.tsx`
- Modify if required by findings: `apps/web/components/overview/DecisionQueue.tsx`
- Modify if required by findings: `apps/web/app/globals.css`

- [ ] **Step 1: Start the worktree web server**

Run from `apps/web`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010 corepack pnpm dev -- --hostname 127.0.0.1 --port 3111
```

Expected: Next.js reports `http://127.0.0.1:3111` ready.

- [ ] **Step 2: Capture desktop, narrow, and mobile screenshots**

Use Playwright at `1440x1000`, `781x995`, and `390x844`. For each viewport, wait for `板块资金流`, `市场状态`, and `决策队列`; confirm `板块资金流` appears before `决策队列` in document order.

- [ ] **Step 3: Check nonblank content and geometry**

Assert:

- no horizontal document overflow;
- key labels have non-zero bounding boxes;
- sector bars have finite positive widths when their values are non-zero;
- mobile shows the direction buttons and hides the desktop middle-axis chart;
- no text overlaps adjacent metric blocks.

- [ ] **Step 4: Apply only visual fixes discovered by the checks**

Keep edits scoped to the four listed overview files. Re-run the three screenshots after every geometry change.

- [ ] **Step 5: Run final verification**

```bash
cd apps/web
corepack pnpm test
corepack pnpm build
cd ../..
git diff --check
git status --short
```

Expected: tests pass, build succeeds, diff check is clean, and only intended files differ from the branch baseline.

- [ ] **Step 6: Commit verified visual adjustments**

```bash
git add apps/web
git commit -m "fix: polish responsive market overview"
```

