export type KlineZoomAction = "all" | "in" | "out";

const MIN_WINDOW_SIZE = 30;
const DEFAULT_WINDOW_SIZE = 120;

export function nextKlineWindowSize(current: number, action: KlineZoomAction, total: number): number {
  const max = Math.max(MIN_WINDOW_SIZE, total);
  if (action === "all") {
    return max;
  }
  if (action === "in") {
    return Math.max(MIN_WINDOW_SIZE, Math.round(current * 0.75));
  }
  return Math.min(max, Math.round((current * 4) / 3));
}

export function defaultKlineWindowSize(total: number): number {
  return Math.min(Math.max(MIN_WINDOW_SIZE, total), DEFAULT_WINDOW_SIZE);
}

export function sliceKlineWindow<T>(bars: T[], windowSize: number): T[] {
  return bars.slice(-Math.max(1, windowSize));
}
