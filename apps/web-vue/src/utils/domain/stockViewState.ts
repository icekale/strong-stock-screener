import type { StockKlinePeriod } from '@/service/types';
import {
  buildKlineIndicatorState,
  type KlineIndicatorState,
  type KlineMovingAverage,
  type KlineSubIndicator,
  type KlineSubPaneCount
} from '@/utils/charts/klineIndicatorLayout';

export const KLINE_INDICATOR_STORAGE_KEY = 'strong-stock-screener:kline-indicator-layout';

export type StockViewDefaults = {
  visibleMovingAverages: KlineMovingAverage[];
  paneCount: KlineSubPaneCount;
  subIndicators: KlineSubIndicator[];
};

export type StockViewIndicatorState = StockViewDefaults;

export type StockKlineQuery = {
  kline: { count: number; period: StockKlinePeriod };
  chanlun: { period: StockKlinePeriod; lookback: number; includeObserving: boolean };
};

export function buildStockViewDefaults(): StockViewDefaults {
  return {
    visibleMovingAverages: ['ma5', 'ma10', 'ma20'],
    paneCount: 1,
    subIndicators: ['volume']
  };
}

export function nextStockRequestId(current: number): number {
  return current + 1;
}

export function isLatestStockRequest(requestId: number, currentRequestId: number): boolean {
  return requestId === currentRequestId;
}

export function calculateCompleteMovingAverage(values: readonly number[], windowSize: number): Array<number | null> {
  return values.map((_, index) => {
    if (!Number.isInteger(windowSize) || windowSize <= 0 || index < windowSize - 1) return null;
    const window = values.slice(index - windowSize + 1, index + 1);
    return window.every(value => Number.isFinite(value))
      ? window.reduce((sum, value) => sum + value, 0) / windowSize
      : null;
  });
}

export function buildStockKlineQuery({ period, count = 220 }: { period: StockKlinePeriod; count?: number }): StockKlineQuery {
  return {
    kline: { count, period },
    chanlun: { period, lookback: count, includeObserving: true }
  };
}

export function serializeIndicatorState(state: {
  visibleMovingAverages?: readonly KlineMovingAverage[];
  paneCount: KlineIndicatorState['paneCount'];
  subIndicators: readonly KlineSubIndicator[];
}): string {
  return JSON.stringify({
    visibleMovingAverages: state.visibleMovingAverages ?? buildStockViewDefaults().visibleMovingAverages,
    paneCount: state.paneCount,
    subIndicators: state.subIndicators
  });
}

export function parseIndicatorState(value: string | null): StockViewIndicatorState {
  const defaults = buildStockViewDefaults();
  if (!value) return defaults;
  try {
    const parsed = JSON.parse(value) as {
      visibleMovingAverages?: unknown;
      movingAverages?: unknown;
      paneCount?: number | null;
      subIndicators?: unknown;
    };
    const layout = buildKlineIndicatorState(parsed);
    const storedMovingAverages = parsed.visibleMovingAverages ?? parsed.movingAverages;
    const visibleMovingAverages = Array.isArray(storedMovingAverages)
      ? storedMovingAverages.filter(isMovingAverage)
      : defaults.visibleMovingAverages;
    return { visibleMovingAverages, ...layout };
  } catch {
    return defaults;
  }
}

function isMovingAverage(value: unknown): value is KlineMovingAverage {
  return value === 'ma5' || value === 'ma10' || value === 'ma20' || value === 'ma60';
}
