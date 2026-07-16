import { describe, expect, it } from 'vitest';
import type { KlineBar, SectorReplicaChartSeries } from '@/service/types';
import { buildKlineIndicatorOptions, buildKlineIndicatorState, buildKlinePanes } from './klineIndicatorLayout';
import { buildKlineOverlayOption } from './klineOverlayOption';
import { nextKlineWindowSize, sliceKlineWindow } from './klineWindow';
import { buildSectorReplicaOption } from './sectorReplicaChartOption';

const bar = (date: string, close: number): KlineBar => ({
  date,
  open: close - 1,
  close,
  high: close + 1,
  low: close - 2,
  volume: 100,
  amount: 1000,
  ma5: close - 0.5,
  ma10: null,
  ma20: null,
  ma60: null
});

describe('chart options', () => {
  it('keeps kline window bounds stable', () => {
    expect(nextKlineWindowSize(120, 'in', 220)).toBe(90);
    expect(nextKlineWindowSize(120, 'out', 220)).toBe(160);
    expect(sliceKlineWindow([1, 2, 3, 4], 2)).toEqual([3, 4]);
  });

  it('normalizes indicator state and keeps selected panes unique', () => {
    const state = buildKlineIndicatorState({ paneCount: 2, subIndicators: ['macd'] });
    const panes = buildKlinePanes(['ma5'], state.subIndicators);

    expect(state.subIndicators).toEqual(['macd', 'macd']);
    expect(panes.chartIndicators).toEqual(['ma', 'macd']);
    expect(buildKlineIndicatorOptions(['ma20']).ma).toEqual({ periods: [20], type: 'sma' });
  });

  it('builds OHLC and moving-average series from backend bars', () => {
    const option = buildKlineOverlayOption({ bars: [bar('20260715', 10), bar('20260716', 12)], movingAverages: ['ma5'] });
    const series = option.series as Array<{ name: string; data: unknown[] }>;

    expect((option.xAxis as Array<{ type: string; data: string[] }>)[0]).toMatchObject({
      type: 'category',
      data: ['2026-07-15', '2026-07-16']
    });
    expect(series[0]).toMatchObject({ type: 'candlestick', name: 'K线' });
    expect(series[0]?.data[0]).toEqual([9, 10, 8, 11]);
    expect(series.some(item => item.name === 'MA5')).toBe(true);
  });

  it('builds a sector replica option without changing the supplied axis', () => {
    const input: SectorReplicaChartSeries[] = [{ name: '计算机', type: 'line', data: [1, 2], smooth: true, showSymbol: false }];
    const option = buildSectorReplicaOption({ axis: ['09:30', '10:00'], series: input });

    expect(option.xAxis).toMatchObject({ data: ['09:30', '10:00'] });
    expect((option.series as Array<{ name: string }>)[0]?.name).toBe('计算机');
  });
});
