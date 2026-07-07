import assert from "node:assert/strict";
import test from "node:test";

const {
  createHeatmapDragState,
  moveHeatmapDragState,
} = (await import(new URL("./heatmapCanvasInteraction.ts", import.meta.url).href)) as typeof import("./heatmapCanvasInteraction");

test("moveHeatmapDragState marks slow cumulative pan as moved", () => {
  let drag = createHeatmapDragState(7, 100, 100);

  let moved = moveHeatmapDragState(drag, 101, 101);
  assert.equal(moved.deltaX, 1);
  assert.equal(moved.deltaY, 1);
  assert.equal(moved.drag.moved, false);

  drag = moved.drag;
  moved = moveHeatmapDragState(drag, 102, 102);

  assert.equal(moved.deltaX, 1);
  assert.equal(moved.deltaY, 1);
  assert.equal(moved.drag.moved, true);
});
