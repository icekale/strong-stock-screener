# Market Overview Focus and Flow Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the desktop sector-flow row alignment and remove the low-value decision queue and its data requests from the homepage.

**Architecture:** Keep all dedicated auction, screener, and watchlist pages unchanged. Narrow `MarketOverviewWorkbench` to three homepage data sources, and replace the desktop flow chart's absolute overlay labels with a normal-flow heading, track, bar, and metadata structure.

**Tech Stack:** Next.js 15, React 19, TypeScript 5.7, CSS custom properties, Node test runner, Chrome headless visual checks.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `apps/web/lib/marketOverview.test.ts` | Source contracts for homepage requests and non-overlaid chart geometry. |
| `apps/web/app/MarketOverviewWorkbench.tsx` | Homepage state, refresh requests, and visible composition. |
| `apps/web/components/overview/SectorHeatmapPreview.tsx` | Desktop flow row semantic structure. |
| `apps/web/app/globals.css` | Desktop heading, track, bar, and metadata geometry. |

### Task 1: Remove the homepage decision queue and unused requests

**Files:**
- Modify: `apps/web/lib/marketOverview.test.ts`
- Modify: `apps/web/app/MarketOverviewWorkbench.tsx`

- [ ] **Step 1: Write a failing homepage focus contract**

Add a source test that verifies the homepage does not import or render `DecisionQueue`, does not call `getLatestScreenRun` or `getAuctionModelTop3`, and still requests market overview, sector radar, and sentiment summary.

```ts
test("homepage only loads market direction data", () => {
  const source = readFileSync(new URL("../app/MarketOverviewWorkbench.tsx", import.meta.url), "utf8");

  assert.doesNotMatch(source, /DecisionQueue/);
  assert.doesNotMatch(source, /getLatestScreenRun/);
  assert.doesNotMatch(source, /getAuctionModelTop3/);
  assert.match(source, /getMarketOverview\(\)/);
  assert.match(source, /getSectorRadar\(12\)/);
  assert.match(source, /getSentimentSummary\(tradeDate, 80, false\)/);
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd apps/web
node --experimental-strip-types --test --test-name-pattern="homepage only loads market direction data" lib/marketOverview.test.ts
```

Expected: FAIL because the homepage still imports `DecisionQueue` and requests auction and screening data.

- [ ] **Step 3: Implement the minimal homepage cleanup**

In `MarketOverviewWorkbench.tsx`:

- remove `DecisionQueue`, auction API helpers, screening API helpers, and their response types;
- remove `auction` and `screening` state;
- reduce `Promise.allSettled` to market overview, sector radar, and sentiment summary;
- update the result destructuring and state application to those three results;
- remove the `DecisionQueue` JSX and the now-unused `toAuctionPanelState` helper.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit the homepage scope change**

```bash
git add apps/web/app/MarketOverviewWorkbench.tsx apps/web/lib/marketOverview.test.ts
git commit -m "refactor: focus market overview homepage"
```

### Task 2: Align desktop sector-flow content with its bars

**Files:**
- Modify: `apps/web/lib/marketOverview.test.ts`
- Modify: `apps/web/components/overview/SectorHeatmapPreview.tsx`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Write a failing chart geometry contract**

Add a source and CSS test requiring a normal-flow heading and track while rejecting the old absolute label overlay.

```ts
test("desktop sector flow keeps labels and bars in normal flow", () => {
  const source = readFileSync(new URL("../components/overview/SectorHeatmapPreview.tsx", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  assert.match(source, /sector-flow-heading/);
  assert.match(source, /sector-flow-track/);
  assert.doesNotMatch(source, /sector-flow-bar__label/);
  assert.doesNotMatch(styles, /\.sector-flow-heading\s*\{[\s\S]*?position:\s*absolute/);
  assert.match(styles, /\.sector-flow-track\s*\{[\s\S]*?display:\s*flex/);
});
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
cd apps/web
node --experimental-strip-types --test --test-name-pattern="desktop sector flow keeps labels" lib/marketOverview.test.ts
```

Expected: FAIL because the current desktop labels use `sector-flow-bar__label` and absolute positioning.

- [ ] **Step 3: Implement the semantic row structure**

Render each populated desktop cell in this order:

```tsx
<div className="sector-flow-heading">
  <span>{row.item.name}</span>
  <strong>{formatCny(row.item.net_flow_cny)}</strong>
</div>
<div className="sector-flow-track">
  <div
    className={`sector-flow-bar sector-flow-bar--${direction}`}
    style={{ "--sector-flow-width": `${row.widthPercent}%` } as CSSProperties}
  />
</div>
<div className="sector-flow-meta">
  {row.item.leader ?? "-"} · {formatPercent(row.item.change_pct)} · 强度 {row.item.strength_score.toFixed(1)}
</div>
```

- [ ] **Step 4: Replace overlay CSS with stable geometry**

Use a normal-flow heading, a full-width 10px track, and direction-aware bar alignment:

```css
.sector-flow-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-width: 0;
  color: var(--app-ink);
  font-size: 11px;
  line-height: 16px;
}

.sector-flow-track {
  display: flex;
  width: 100%;
  height: 10px;
  margin-top: 4px;
  overflow: hidden;
  border-radius: 2px;
  background: var(--app-raised);
}

.sector-flow-cell--outflow .sector-flow-track {
  justify-content: flex-end;
}

.sector-flow-bar {
  width: var(--sector-flow-width);
  height: 100%;
}
```

Keep amount colors, ellipsis, outflow metadata alignment, and the existing mobile layout. Delete only the obsolete `.sector-flow-bar__label` rules.

- [ ] **Step 5: Run focused and full web tests**

```bash
cd apps/web
node --experimental-strip-types --test --test-name-pattern="desktop sector flow keeps labels" lib/marketOverview.test.ts
corepack pnpm test
```

Expected: focused and full suites pass.

- [ ] **Step 6: Commit the alignment fix**

```bash
git add apps/web/components/overview/SectorHeatmapPreview.tsx apps/web/app/globals.css apps/web/lib/marketOverview.test.ts
git commit -m "fix: align homepage sector flow rows"
```

### Task 3: Verify production and responsive rendering

**Files:**
- Inspect: `apps/web/components/overview/SectorHeatmapPreview.tsx`
- Inspect: `apps/web/app/globals.css`
- Inspect: generated screenshots in `/tmp`

- [ ] **Step 1: Run production verification**

```bash
cd apps/web
corepack pnpm test
corepack pnpm build
cd ../..
git diff --check
```

Expected: tests and build pass; diff check reports no errors.

- [ ] **Step 2: Capture real-data screenshots**

Use Chrome headless with an 8-second virtual-time budget at `1440x1000`, `781x995`, and `390x844` against `http://127.0.0.1:3110/`.

- [ ] **Step 3: Inspect geometry and homepage scope**

Confirm:

- desktop headings, amounts, tracks, and metadata remain in the same row;
- outflow bars terminate at the center axis and inflow bars start at it;
- the mobile segmented list remains unchanged and readable;
- the page has no horizontal overflow or text overlap;
- the homepage ends after the index strip and contains no decision queue.

- [ ] **Step 4: Apply and verify only evidence-driven visual corrections**

If a correction is needed, add a failing source/CSS contract first, make the smallest change, then repeat Steps 1-3.
