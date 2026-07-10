import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const panelSource = readFileSync(new URL("../app/sectors/SectorReplicaPanel.tsx", import.meta.url), "utf8");
const cssSource = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
const stockPanelCss = cssSource.match(/\.sector-replica-stock-panel\s*\{([^}]*)\}/)?.[1] ?? "";

test("sector radar exposes separate active-board and comparison controls", () => {
  assert.match(panelSource, /sector-replica-board-list-head/);
  assert.match(panelSource, /aria-pressed/);
  assert.match(panelSource, /sector-replica-selection-count/);
  assert.match(panelSource, /sector-replica-tags-scroll/);
});

test("sector radar layout defines desktop, tablet, and reduced-motion states", () => {
  assert.match(cssSource, /grid-template-columns: repeat\(6, minmax\(0, 1fr\)\)/);
  assert.match(cssSource, /grid-template-columns: repeat\(4, minmax\(0, 1fr\)/);
  assert.match(cssSource, /prefers-reduced-motion: reduce/);
  assert.match(cssSource, /sector-replica-tags-scroll/);
});

test("sector radar allocates spare viewport height to the work area", () => {
  assert.match(cssSource, /\.sector-replica-shell\s*\{[\s\S]*display: flex;/);
  assert.match(cssSource, /\.sector-replica-shell\s*\{[\s\S]*height: calc\(100vh - 16px\);/);
  assert.match(cssSource, /\.sector-replica-plate-row\s*\{[\s\S]*flex: 1 1 auto;/);
  assert.match(cssSource, /\.sector-replica-chart-region\s*\{[\s\S]*flex: 1 1 auto;/);
  assert.match(cssSource, /\.sector-replica-board-list\s*\{[\s\S]*min-height: 0;/);
  assert.match(stockPanelCss, /flex: 0 0 auto;/);
  assert.match(cssSource, /@media \(max-width: 980px\)[\s\S]*\.sector-replica-shell\s*\{[\s\S]*height: auto;/);
});
