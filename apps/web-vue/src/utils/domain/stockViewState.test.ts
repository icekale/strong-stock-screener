import { describe, expect, it } from 'vitest';
import type { StockKlinePeriod } from '@/service/types';
import {
  buildStockKlineQuery,
  buildStockViewDefaults,
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
    const state = { paneCount: 2 as const, subIndicators: ['volume', 'macd'] as const };

    expect(parseIndicatorState(serializeIndicatorState(state))).toEqual(state);
    expect(parseIndicatorState('{invalid json')).toEqual({ paneCount: 1, subIndicators: ['volume'] });
  });
});
