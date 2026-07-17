import type { KlineBar, StockKlinePeriod } from '@/service/types';
import { aggregateWeeklyBars } from '@/utils/charts/klinePeriod';
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

export function buildStockViewChartBars(bars: KlineBar[], period: StockKlinePeriod | 'weekly'): KlineBar[] {
  const displayedBars = period === 'weekly' ? aggregateWeeklyBars(bars) : bars;
  const periods = [5, 10, 20, 60] as const;
  const averages = Object.fromEntries(
    periods.map(size => [`ma${size}`, calculateCompleteMovingAverage(displayedBars.map(bar => bar.close), size)])
  ) as Record<`ma${(typeof periods)[number]}`, Array<number | null>>;

  return displayedBars.map((bar, index) => ({
    ...bar,
    ma5: index >= 4 ? bar.ma5 ?? averages.ma5[index] ?? null : null,
    ma10: index >= 9 ? bar.ma10 ?? averages.ma10[index] ?? null : null,
    ma20: index >= 19 ? bar.ma20 ?? averages.ma20[index] ?? null : null,
    ma60: index >= 59 ? bar.ma60 ?? averages.ma60[index] ?? null : null
  }));
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
