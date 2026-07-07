import assert from "node:assert/strict";
import test from "node:test";

const {
  clampHeatmapViewport,
  createHeatmapDragState,
  heatmapStockLabelLevel,
  heatmapWheelZoomFactor,
  moveHeatmapDragState,
  zoomHeatmapViewport,
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

test("heatmap stock labels use displayed size after zoom", () => {
  const narrowStock = { x: 0, y: 0, width: 20, height: 12 };

  assert.equal(heatmapStockLabelLevel(narrowStock, 1), "none");
  assert.equal(heatmapStockLabelLevel({ ...narrowStock, width: 40, height: 70 }, 1), "name");
  assert.equal(heatmapStockLabelLevel(narrowStock, 3), "name");
  assert.equal(heatmapStockLabelLevel({ ...narrowStock, width: 28, height: 24 }, 3), "change");
});

test("heatmap wheel zoom factor follows wheel magnitude smoothly", () => {
  const tinyZoomIn = heatmapWheelZoomFactor(-1);
  const largeZoomIn = heatmapWheelZoomFactor(-120);
  const tinyZoomOut = heatmapWheelZoomFactor(1);

  assert.ok(tinyZoomIn > 1);
  assert.ok(tinyZoomIn < 1.01);
  assert.ok(largeZoomIn > tinyZoomIn);
  assert.ok(largeZoomIn <= 1.25);
  assert.ok(tinyZoomOut < 1);
  assert.equal(heatmapWheelZoomFactor(0), 1);
});

test("zoomHeatmapViewport keeps the cursor world point anchored and clamps scale", () => {
  const next = zoomHeatmapViewport(
    { scale: 1, offsetX: 0, offsetY: 0 },
    { x: 120, y: 80 },
    { x: 120, y: 80 },
    2,
    { width: 500, height: 300 },
  );

  assert.deepEqual(next, { scale: 2, offsetX: -120, offsetY: -80 });

  const clamped = zoomHeatmapViewport(
    { scale: 3, offsetX: -20, offsetY: -20 },
    { x: 120, y: 80 },
    { x: 35, y: 25 },
    2,
    { width: 500, height: 300 },
  );

  assert.equal(clamped.scale, 3);
  assert.equal(clamped.offsetX, 0);
  assert.equal(clamped.offsetY, 0);
});

test("clampHeatmapViewport keeps zoomed canvas within visible bounds", () => {
  assert.deepEqual(
    clampHeatmapViewport({ scale: 0.8, offsetX: -40, offsetY: -30 }, { width: 500, height: 300 }),
    { scale: 1, offsetX: 0, offsetY: 0 },
  );

  assert.deepEqual(
    clampHeatmapViewport({ scale: 2, offsetX: 120, offsetY: -999 }, { width: 500, height: 300 }),
    { scale: 2, offsetX: 0, offsetY: -300 },
  );

  assert.deepEqual(
    clampHeatmapViewport({ scale: 2, offsetX: -999, offsetY: 20 }, { width: 500, height: 300 }),
    { scale: 2, offsetX: -500, offsetY: 0 },
  );
});
