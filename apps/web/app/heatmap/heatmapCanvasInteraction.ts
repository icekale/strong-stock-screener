import type { HeatmapRect, HeatmapViewport } from "./heatmapTreemap";

export type HeatmapDragState = {
  pointerId: number;
  originX: number;
  originY: number;
  lastX: number;
  lastY: number;
  moved: boolean;
};

export type HeatmapStockLabelLevel = "none" | "name" | "code" | "change";

const DEFAULT_DRAG_THRESHOLD_PX = 2;
const DEFAULT_MIN_SCALE = 1;
const DEFAULT_MAX_SCALE = 3;
const WHEEL_LINE_HEIGHT_PX = 16;
const WHEEL_PAGE_HEIGHT_PX = 320;
const MAX_WHEEL_DELTA_PX = 100;
const WHEEL_ZOOM_SENSITIVITY = 500;

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

export function heatmapStockLabelLevel(rect: Pick<HeatmapRect, "width" | "height">, scale: number): HeatmapStockLabelLevel {
  const safeScale = finitePositiveNumber(scale, 1);
  const displayedWidth = Math.max(0, finiteNumber(rect.width) * safeScale);
  const displayedHeight = Math.max(0, finiteNumber(rect.height) * safeScale);

  if (displayedWidth >= 68 && displayedHeight >= 64) {
    return "change";
  }
  if (displayedWidth >= 54 && displayedHeight >= 44) {
    return "code";
  }
  if (displayedWidth >= 34 && displayedHeight >= 24) {
    return "name";
  }
  return "none";
}

export function heatmapWheelZoomFactor(deltaY: number, deltaMode = 0): number {
  const wheelDelta = finiteNumber(deltaY);
  if (wheelDelta === 0) {
    return 1;
  }

  const pixelDelta = wheelDelta * wheelDeltaModeMultiplier(deltaMode);
  const boundedDelta = clamp(pixelDelta, -MAX_WHEEL_DELTA_PX, MAX_WHEEL_DELTA_PX);
  return Math.exp(-boundedDelta / WHEEL_ZOOM_SENSITIVITY);
}

export function zoomHeatmapViewport(
  viewport: HeatmapViewport,
  screenPoint: { x: number; y: number },
  worldPoint: { x: number; y: number },
  zoomFactor: number,
  size?: { width: number; height: number },
): HeatmapViewport {
  const currentScale = finitePositiveNumber(viewport.scale, 1);
  const nextScale = clamp(currentScale * finitePositiveNumber(zoomFactor, 1), DEFAULT_MIN_SCALE, DEFAULT_MAX_SCALE);
  const safeScreenPoint = {
    x: finiteNumber(screenPoint.x),
    y: finiteNumber(screenPoint.y),
  };
  const safeWorldPoint = {
    x: finiteNumber(worldPoint.x),
    y: finiteNumber(worldPoint.y),
  };

  const nextViewport = {
    scale: nextScale,
    offsetX: safeScreenPoint.x - safeWorldPoint.x * nextScale,
    offsetY: safeScreenPoint.y - safeWorldPoint.y * nextScale,
  };

  return size ? clampHeatmapViewport(nextViewport, size) : nextViewport;
}

export function clampHeatmapViewport(
  viewport: HeatmapViewport,
  size: { width: number; height: number },
): HeatmapViewport {
  const width = Math.max(0, finiteNumber(size.width));
  const height = Math.max(0, finiteNumber(size.height));
  const scale = clamp(finitePositiveNumber(viewport.scale, 1), DEFAULT_MIN_SCALE, DEFAULT_MAX_SCALE);

  if (scale <= 1 || width <= 0 || height <= 0) {
    return { scale: 1, offsetX: 0, offsetY: 0 };
  }

  const minX = width - width * scale;
  const minY = height - height * scale;

  return {
    scale,
    offsetX: clamp(finiteNumber(viewport.offsetX), minX, 0),
    offsetY: clamp(finiteNumber(viewport.offsetY), minY, 0),
  };
}

function wheelDeltaModeMultiplier(deltaMode: number): number {
  if (deltaMode === 1) {
    return WHEEL_LINE_HEIGHT_PX;
  }
  if (deltaMode === 2) {
    return WHEEL_PAGE_HEIGHT_PX;
  }
  return 1;
}

function finitePositiveNumber(value: number, fallback: number): number {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function finiteNumber(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
