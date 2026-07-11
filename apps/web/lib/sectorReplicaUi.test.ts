import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const panelSource = readFileSync(new URL("../app/sectors/SectorReplicaPanel.tsx", import.meta.url), "utf8");
const cssSource = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
const stockPanelCss = cssSource.match(/\.market-radar-stock-panel\s*\{([^}]*)\}/)?.[1] ?? "";

test("sector radar exposes separate active-board and comparison controls", () => {
  assert.match(panelSource, /market-radar-board-list-head/);
  assert.match(panelSource, /aria-pressed/);
  assert.match(panelSource, /market-radar-selection-count/);
  assert.match(panelSource, /market-radar-tags-scroll/);
  assert.doesNotMatch(panelSource, /sector-replica-/);
});

test("sector radar layout defines desktop, tablet, and reduced-motion states", () => {
  assert.match(cssSource, /grid-template-columns: repeat\(6, minmax\(0, 1fr\)\)/);
  assert.match(cssSource, /grid-template-columns: repeat\(4, minmax\(0, 1fr\)/);
  assert.match(cssSource, /prefers-reduced-motion: reduce/);
  assert.match(cssSource, /market-radar-tags-scroll/);
  assert.doesNotMatch(cssSource, /\.sector-replica-/);
});

test("sector radar allocates spare viewport height to the work area", () => {
  assert.match(cssSource, /\.market-radar-shell\s*\{[\s\S]*display: flex;/);
  assert.match(cssSource, /\.market-radar-shell\s*\{[\s\S]*height: calc\(100vh - 16px\);/);
  assert.match(cssSource, /\.market-radar-plate-row\s*\{[\s\S]*flex: 1 1 auto;/);
  assert.match(cssSource, /\.market-radar-chart-region\s*\{[\s\S]*flex: 1 1 auto;/);
  assert.match(cssSource, /\.market-radar-board-list\s*\{[\s\S]*min-height: 0;/);
  assert.match(stockPanelCss, /flex: 0 0 auto;/);
  assert.match(cssSource, /@media \(max-width: 980px\)[\s\S]*\.market-radar-shell\s*\{[\s\S]*height: auto;/);
});
