export type HeatmapDragState = {
  pointerId: number;
  originX: number;
  originY: number;
  lastX: number;
  lastY: number;
  moved: boolean;
};

const DEFAULT_DRAG_THRESHOLD_PX = 2;

export function createHeatmapDragState(pointerId: number, x: number, y: number): HeatmapDragState {
  return {
    pointerId,
    originX: x,
    originY: y,
    lastX: x,
    lastY: y,
    moved: false,
  };
}

export function moveHeatmapDragState(
  drag: HeatmapDragState,
  x: number,
  y: number,
  thresholdPx = DEFAULT_DRAG_THRESHOLD_PX,
): { drag: HeatmapDragState; deltaX: number; deltaY: number } {
  const deltaX = x - drag.lastX;
  const deltaY = y - drag.lastY;
  const totalDistance = Math.abs(x - drag.originX) + Math.abs(y - drag.originY);

  return {
    deltaX,
    deltaY,
    drag: {
      ...drag,
      lastX: x,
      lastY: y,
      moved: drag.moved || totalDistance > thresholdPx,
    },
  };
}
