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
  assert.match(cssSource, /grid-template-columns: repeat\(6, minmax\(0, 1fr\)\)/);
  assert.match(cssSource, /grid-template-columns: repeat\(4, minmax\(0, 1fr\)/);
  assert.match(cssSource, /prefers-reduced-motion: reduce/);
  assert.match(cssSource, /sector-replica-tags-scroll/);
});
