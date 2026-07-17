import type { StockKlinePeriod } from '@/service/types';
import {
  buildKlineIndicatorState,
  parseStoredKlineIndicatorState,
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

export function buildStockKlineQuery({ period, count = 220 }: { period: StockKlinePeriod; count?: number }): StockKlineQuery {
  return {
    kline: { count, period },
    chanlun: { period, lookback: count, includeObserving: true }
  };
}

export function serializeIndicatorState(state: { paneCount: KlineIndicatorState['paneCount']; subIndicators: readonly KlineSubIndicator[] }): string {
  return JSON.stringify(state);
}

export function parseIndicatorState(value: string | null): KlineIndicatorState {
  if (!value) {
    return buildKlineIndicatorState({ paneCount: 1, subIndicators: ['volume'] });
  }
  return parseStoredKlineIndicatorState(value);
}
