import { describe, expect, it } from 'vitest';
import type { KlineBar, StockKlinePeriod } from '@/service/types';
import {
  buildStockKlineQuery,
  buildStockViewChartBars,
  buildStockViewDefaults,
  calculateCompleteMovingAverage,
  isLatestStockRequest,
  nextStockRequestId,
  parseIndicatorState,
  serializeIndicatorState
} from './stockViewState';

describe('stock view state', () => {
  it('builds the legacy stock workbench defaults', () => {
    expect(buildStockViewDefaults()).toEqual({
      visibleMovingAverages: ['ma5', 'ma10', 'ma20'],
      paneCount: 1,
      subIndicators: ['volume']
    });
  });

  it('increments request ids and accepts only the latest request', () => {
    const first = nextStockRequestId(0);
    const second = nextStockRequestId(first);

    expect(first).toBe(1);
    expect(second).toBe(2);
    expect(isLatestStockRequest(first, second)).toBe(false);
    expect(isLatestStockRequest(second, second)).toBe(true);
  });

  it('builds matching kline and chanlun period queries', () => {
    const query = buildStockKlineQuery({ period: '30m', count: 220 });

    expect(query).toEqual({
      kline: { count: 220, period: '30m' satisfies StockKlinePeriod },
      chanlun: { period: '30m', lookback: 220, includeObserving: true }
    });
  });

  it('round-trips indicator state and falls back for invalid JSON', () => {
    const state = {
      visibleMovingAverages: ['ma5', 'ma60'] as const,
      paneCount: 2 as const,
      subIndicators: ['volume', 'macd'] as const
    };

    expect(parseIndicatorState(serializeIndicatorState(state))).toEqual(state);
    expect(parseIndicatorState(JSON.stringify({ paneCount: 2, subIndicators: ['macd'] }))).toEqual({
      visibleMovingAverages: ['ma5', 'ma10', 'ma20'],
      paneCount: 2,
      subIndicators: ['macd', 'macd']
    });
    expect(parseIndicatorState('{invalid json')).toEqual({
      visibleMovingAverages: ['ma5', 'ma10', 'ma20'],
      paneCount: 1,
      subIndicators: ['volume']
    });
  });

  it('returns moving averages only after a complete window', () => {
    expect(calculateCompleteMovingAverage([1, 2, 3, 4, 5], 3)).toEqual([null, null, 2, 3, 4]);
    expect(calculateCompleteMovingAverage([1, Number.NaN, 3], 2)).toEqual([null, null, null]);
  });

  it('fills MA5 on the fifth aggregated weekly bar, not before', () => {
    const dailyBars: KlineBar[] = [];
    const cursor = new Date(Date.UTC(2026, 0, 5));
    for (let index = 0; index < 25; index += 1) {
      while (cursor.getUTCDay() === 0 || cursor.getUTCDay() === 6) cursor.setUTCDate(cursor.getUTCDate() + 1);
      const close = index + 1;
      dailyBars.push({
        date: cursor.toISOString().slice(0, 10).replaceAll('-', ''),
        open: close - 1,
        close,
        high: close + 1,
        low: close - 2,
        volume: 100,
        amount: 1000,
        ma5: null,
        ma10: null,
        ma20: null,
        ma60: null
      });
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }

    const weeklyBars = buildStockViewChartBars(dailyBars, 'weekly');

    expect(weeklyBars).toHaveLength(5);
    expect(weeklyBars.slice(0, 4).map(bar => bar.ma5)).toEqual([null, null, null, null]);
    expect(weeklyBars[4]?.ma5).toBe(15);
  });
});
