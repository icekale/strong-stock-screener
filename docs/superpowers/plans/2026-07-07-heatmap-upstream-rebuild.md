# Heatmap Upstream Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom heatmap body with a StockMaster-adapted implementation modeled on `wenyuanw/a-share-heatmap`.

**Architecture:** Keep the StockMaster `/heatmap` route, filters, API client, and side rails. Replace the canvas layout and interaction core with upstream-style binary treemap layout, sub-board grouping, clipped label drawing, bounded zoom/pan, and double-click stock navigation hooks.

**Tech Stack:** Next.js App Router, React 19, TypeScript, Ant Design shell, Canvas 2D, Node test runner.

---

### Task 1: Upstream-style layout primitives

**Files:**
- Modify: `apps/web/app/heatmap/heatmapTreemap.ts`
- Modify: `apps/web/app/heatmap/heatmapTreemap.test.ts`

- [ ] Write tests that prove the treemap uses balanced binary subdivision instead of one-dimensional slice/dice.
- [ ] Add tests for sub-board grouping from `sub_industry`.
- [ ] Implement `binaryTreemap`, sub-board rectangles, and stable hit testing.
- [ ] Run `node --experimental-strip-types --test app/heatmap/heatmapTreemap.test.ts`.

### Task 2: Upstream-style viewport interactions

**Files:**
- Modify: `apps/web/app/heatmap/heatmapCanvasInteraction.ts`
- Modify: `apps/web/app/heatmap/heatmapCanvasInteraction.test.ts`

- [ ] Write tests for clamped pan/zoom behavior.
- [ ] Implement `clampHeatmapViewport`, bounded wheel zoom, and reusable reset viewport helpers.
- [ ] Run `node --experimental-strip-types --test app/heatmap/heatmapCanvasInteraction.test.ts`.

### Task 3: Canvas body replacement

**Files:**
- Modify: `apps/web/app/heatmap/HeatmapCanvas.tsx`

- [ ] Replace board/stock drawing with upstream-style board headers, sub-board panels, heat colors, clipped text labels, and selected outline.
- [ ] Add double-click stock navigation callback while preserving single-click select and hover detail.
- [ ] Keep keyboard controls and reset behavior.

### Task 4: Workspace integration and verification

**Files:**
- Modify: `apps/web/app/heatmap/HeatmapWorkspace.tsx`

- [ ] Pass `heatmapStockHref` navigation into `HeatmapCanvas`.
- [ ] Run `./node_modules/.bin/tsc --noEmit`.
- [ ] Run `node --experimental-strip-types --test app/heatmap/*.test.ts lib/heatmap.test.ts lib/stockNavigation.test.ts`.
- [ ] Start API/web dev servers if needed and verify `/heatmap` in the browser: nonblank canvas, labels visible, drag/zoom bounded, double-click opens stock K-line route, no console errors.
