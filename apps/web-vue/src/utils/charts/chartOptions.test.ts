import { describe, expect, it } from 'vitest';
import type { ChanlunAnalysisResponse, KlineBar, SectorReplicaChartSeries } from '@/service/types';
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

const chanlun: ChanlunAnalysisResponse = {
  adjustment_mode: 'raw_unadjusted',
  availability: 'ready',
  bars: [],
  calculated_at: '2026-07-16T15:00:00+08:00',
  divergences: [],
  fractals: [],
  last_closed_bar_at: null,
  period: '1d',
  rule_version: 'cl-v1',
  segments: [],
  signals: [],
  source_status: [],
  symbol: '600000.SH',
  strokes: [],
  zones: [
    {
      end_at: '2026-07-16T15:00:00+08:00',
      high: 12,
      id: 'zone-1',
      low: 9,
      start_at: '2026-07-15T15:00:00+08:00',
      status: 'confirmed',
      virtual: false
    }
  ]
};

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

  it.each([
    { indicators: ['volume'] as const, heights: ['76%', '18%'] },
    { indicators: ['volume', 'macd'] as const, heights: ['62%', '16%', '16%'] },
    { indicators: ['volume', 'macd', 'kdj'] as const, heights: ['52%', '14%', '14%', '14%'] }
  ])('builds a main grid and one grid per selected sub indicator', ({ indicators, heights }) => {
    const option = buildKlineOverlayOption({ bars: [bar('20260715', 10), bar('20260716', 12)], subIndicators: [...indicators] });
    const grids = option.grid as Array<{ height: string }>;

    expect(grids).toHaveLength(heights.length);
    expect(grids.map(grid => grid.height)).toEqual(heights);
    expect(option.xAxis).toHaveLength(heights.length);
    expect(option.yAxis).toHaveLength(heights.length);
  });

  it('maps MACD, KDJ, and brick results to their selected sub panes', () => {
    const option = buildKlineOverlayOption({
      bars: Array.from({ length: 32 }, (_, index) => bar(`202607${String(index + 1).padStart(2, '0')}`, 10 + index / 10)),
      subIndicators: ['macd', 'kdj', 'brick']
    });
    const series = option.series as Array<{ name: string; type: string; xAxisIndex: number; yAxisIndex: number; connectNulls?: boolean }>;

    expect(series.filter(item => item.name === 'MACD')).toContainEqual(expect.objectContaining({ type: 'bar', xAxisIndex: 1, yAxisIndex: 1 }));
    expect(series.filter(item => ['DIF', 'DEA'].includes(item.name))).toHaveLength(2);
    expect(series.filter(item => ['K', 'D', 'KDJ'].includes(item.name))).toHaveLength(3);
    expect(series.some(item => item.name === '砖形图' && item.type === 'candlestick' && item.xAxisIndex === 3 && item.yAxisIndex === 3)).toBe(true);
    expect(series.filter(item => item.type === 'line').every(item => item.connectNulls === false)).toBe(true);
  });

  it('synchronizes every x axis and data zoom while keeping chanlun overlays on the main pane', () => {
    const option = buildKlineOverlayOption({
      bars: [bar('20260715', 10), bar('20260716', 12)],
      subIndicators: ['volume', 'macd', 'kdj'],
      chanlun
    });
    const axes = option.xAxis as Array<{ data: string[]; gridIndex: number }>;
    const yAxes = option.yAxis as Array<{ gridIndex: number }>;
    const dataZoom = option.dataZoom as Array<{ xAxisIndex: number[] }>;
    const overlaySeries = (option.series as Array<{ name: string; xAxisIndex: number; yAxisIndex: number }>).filter(item => item.name.startsWith('缠论'));

    expect(axes.map(axis => axis.data)).toEqual([
      ['2026-07-15', '2026-07-16'],
      ['2026-07-15', '2026-07-16'],
      ['2026-07-15', '2026-07-16'],
      ['2026-07-15', '2026-07-16']
    ]);
    expect(axes.map(axis => axis.gridIndex)).toEqual([0, 1, 2, 3]);
    expect(yAxes.map(axis => axis.gridIndex)).toEqual([0, 1, 2, 3]);
    expect(dataZoom).toHaveLength(2);
    expect(dataZoom[0]?.xAxisIndex).toEqual([0, 1, 2, 3]);
    expect(dataZoom[1]?.xAxisIndex).toEqual([0, 1, 2, 3]);
    expect(overlaySeries.every(item => item.xAxisIndex === 0 && item.yAxisIndex === 0)).toBe(true);
    expect(option.tooltip).toMatchObject({ trigger: 'axis', axisPointer: { type: 'cross' } });
  });

  it('builds a sector replica option without changing the supplied axis', () => {
    const input: SectorReplicaChartSeries[] = [{ name: '计算机', type: 'line', data: [1, 2], smooth: true, showSymbol: false }];
    const option = buildSectorReplicaOption({ axis: ['09:30', '10:00'], series: input });

    expect(option.xAxis).toMatchObject({ data: ['09:30', '10:00'] });
    expect((option.series as Array<{ name: string }>)[0]?.name).toBe('计算机');
  });
});
