# Sector Page UI Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework `/sectors` into a faster, clearer two-column intraday radar while keeping all 12 emotion metrics, existing data behavior, and current stock navigation intact.

**Architecture:** Keep `SectorReplicaWorkspace` as the state owner and `SectorReplicaPanel` as the rendering boundary. Add only presentation-level markup hooks and accessibility state to the panel, then express the responsive composition in the existing sector-specific section of `apps/web/app/globals.css`. Do not change API calls, cache keys, polling intervals, chart data, or backend services.

**Tech Stack:** Next.js 15, React 19, TypeScript, ECharts, node:test, Playwright smoke script, existing CSS custom properties.

---

### Task 1: Add UI contract tests for the approved layout

**Files:**
- Create: `apps/web/lib/sectorReplicaUi.test.ts`
- Reference: `apps/web/app/sectors/SectorReplicaPanel.tsx`
- Reference: `apps/web/app/globals.css`

- [ ] **Step 1: Write the failing source-contract tests**

Create a small node:test file that reads the panel and CSS source and asserts the approved structure exists:

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const panelSource = readFileSync(new URL("../app/sectors/SectorReplicaPanel.tsx", import.meta.url), "utf8");
const cssSource = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

test("sector radar exposes separate active-board and comparison controls", () => {
  assert.match(panelSource, /sector-replica-board-list-head/);
  assert.match(panelSource, /aria-pressed/);
  assert.match(panelSource, /sector-replica-selection-count/);
  assert.match(panelSource, /sector-replica-tags-scroll/);
});

test("sector radar layout defines desktop, tablet, and reduced-motion states", () => {
  assert.match(cssSource, /grid-template-columns: repeat\\(6, minmax\\(0, 1fr\\)\\)/);
  assert.match(cssSource, /grid-template-columns: repeat\\(4, minmax\\(0, 1fr\\)/);
  assert.match(cssSource, /prefers-reduced-motion: reduce/);
  assert.match(cssSource, /sector-replica-tags-scroll/);
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test lib/sectorReplicaUi.test.ts
```

Expected: FAIL because the new layout hooks and responsive CSS do not exist yet.

### Task 2: Refine `SectorReplicaPanel` markup and interaction state

**Files:**
- Modify: `apps/web/app/sectors/SectorReplicaPanel.tsx`

- [ ] **Step 1: Add the board-list context header**

Place this immediately above `.sector-replica-board-list`, without changing the existing data mapping:

```tsx
<div className="sector-replica-board-list-head">
  <div>
    <strong>{MODE_LABELS[mode]}</strong>
    <span>当前板块点击查看，勾选加入曲线</span>
  </div>
  <span className="sector-replica-selection-count">{selectedCodes.length}/6</span>
</div>
```

- [ ] **Step 2: Make mode and board controls expose selected state**

Add `aria-pressed={item === mode}` to the mode buttons. Add `aria-pressed={active}` and an `aria-label` describing the active-board action to the board name button. Keep the checkbox as the comparison action and preserve its existing `onChange` handler.

- [ ] **Step 3: Add explicit loading and status hooks without replacing data**

Add `aria-live="polite"` to the inline error region when present. Add `aria-busy={loading}` to the chart main region and `aria-busy={stockLoading}` to the stock panel. Keep cached chart/table contents visible while background refresh is running.

- [ ] **Step 4: Wrap sub-theme buttons in a scroll rail**

Change the sub-theme return shape to:

```tsx
return (
  <div className="sector-replica-tags-scroll">
    <div className="sector-replica-tags">
      {/* existing 全部 and tag buttons */}
    </div>
  </div>
);
```

Preserve `全部`, active state, tag order, and the empty label.

- [ ] **Step 5: Run TypeScript to verify the markup changes compile**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm run lint
```

Expected: exit 0.

### Task 3: Implement the responsive two-column visual system

**Files:**
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Replace the emotion grid sizing**

Update the sector-specific grid rules so the desktop baseline is:

```css
.sector-replica-emotion-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
}
```

Keep the existing semantic tone classes and compact button height; add `:focus-visible` styling so keyboard focus remains visible.

- [ ] **Step 2: Add list header and distinguish state treatments**

Add styles for `.sector-replica-board-list-head`, `.sector-replica-selection-count`, and `aria-pressed` board/mode controls. The active board uses the red-tinted row background; checked comparison rows use a subtle checked treatment; do not use the same visual treatment for both.

- [ ] **Step 3: Make the desktop composition stable**

Set the desktop plate grid to a near-280px sidebar and flexible chart column. Keep list and chart heights stable, and ensure the chart header can shrink without text overlap:

```css
.sector-replica-plate-row {
  grid-template-columns: minmax(268px, 280px) minmax(0, 1fr);
}

.sector-replica-chart-head {
  min-width: 0;
}

.sector-replica-chart-title,
.sector-replica-chart-tools {
  min-width: 0;
}
```

- [ ] **Step 4: Convert the sub-theme area to bounded horizontal overflow**

Add `.sector-replica-tags-scroll` with `overflow-x: auto`, hide vertical overflow, and keep the inner `.sector-replica-tags` on one line with `flex-wrap: nowrap` and `width: max-content`. Keep the stock table independently scrollable.

- [ ] **Step 5: Add tablet, mobile, focus, and reduced-motion rules**

Use the existing `980px` breakpoint for the 4-column metric grid and stacked list/chart layout. Add a narrower breakpoint around `640px` for compact metric sizing and bounded horizontal rails. Add:

```css
@media (prefers-reduced-motion: reduce) {
  .sector-replica-shell *,
  .sector-replica-shell *::before,
  .sector-replica-shell *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}
```

- [ ] **Step 6: Run the focused UI contract test**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
node --experimental-strip-types --test lib/sectorReplicaUi.test.ts
```

Expected: PASS.

### Task 4: Verify behavior, build, and visual responsiveness

**Files:**
- No new source files.
- Inspect: `apps/web/app/sectors/SectorReplicaPanel.tsx`, `apps/web/app/globals.css`, `apps/web/lib/sectorReplicaUi.test.ts`

- [ ] **Step 1: Run the complete frontend test suite**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm test
```

Expected: TypeScript succeeds and all node:test files pass.

- [ ] **Step 2: Run the production build**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener/apps/web
npm run build
```

Expected: Next.js production build exits 0.

- [ ] **Step 3: Run the UI smoke test against the existing local server**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
SMOKE_UI_BASE_URL=http://127.0.0.1:3110 npm --prefix apps/web run smoke:ui
```

Expected: `/sectors` returns successfully at 1440x900 and 390x844 with no Next.js overlay, console errors, failed responses, or uncontrolled horizontal overflow.

- [ ] **Step 4: Perform manual interaction checks**

At `http://127.0.0.1:3110/sectors`, verify:

1. All 12 metrics are visible or reachable without being removed.
2. Clicking a board changes the active board and stock context without toggling comparison.
3. Checking a board changes the comparison set and chart series.
4. Switching mode preserves the page and updates values.
5. Selecting a sub-theme changes the stock rows while the tag rail remains one line.
6. Refresh keeps cached content visible while loading.
7. The stock table remains usable by horizontal scrolling on mobile.

- [ ] **Step 5: Check the final diff**

Run:

```bash
cd /Users/kale/Documents/strong-stock-screener
git diff --check
git status --short
```

Expected: only the intended sector UI files are changed in addition to the pre-existing cache-fix files; no generated preview files are included.

