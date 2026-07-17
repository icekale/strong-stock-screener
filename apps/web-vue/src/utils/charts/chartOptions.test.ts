import { describe, expect, it, vi } from 'vitest';
import type { ChanlunAnalysisResponse, GsgfChartAnnotation, KlineBar, SectorReplicaChartSeries } from '@/service/types';
import { buildKlineIndicatorOptions, buildKlineIndicatorState, buildKlinePanes } from './klineIndicatorLayout';
import { buildKlineOverlayOption, getVisibleGsgfAnnotations, runEChartLifecycle } from './klineOverlayOption';
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

const gsgfAnnotations: GsgfChartAnnotation[] = [
  {
    type: 'volume_structure',
    label: '量能结构',
    description: '近40日量能结构偏强。',
    severity: 'positive',
    date: null,
    start_date: '2026-07-15',
    end_date: '20260716',
    price: null
  },
  {
    type: 'trigger',
    label: '星线蓄势',
    description: '出现触发信号。',
    severity: 'warning',
    date: '20260716',
    start_date: null,
    end_date: null,
    price: 12
  }
];

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

  it('colors volume bars by the direction of each kline', () => {
    const option = buildKlineOverlayOption({
      bars: [bar('20260715', 10), { ...bar('20260716', 9), open: 12, close: 9 }],
      subIndicators: ['volume']
    });
    const volume = option.series.find(item => item.name === '成交量') as {
      data: Array<{ value: number; itemStyle: { color: string } }>;
    } | undefined;

    expect(volume?.data).toEqual([
      { value: 100, itemStyle: { color: '#d9363e' } },
      { value: 100, itemStyle: { color: '#07845e' } }
    ]);
  });

  it('shows the latest values in sub-pane legends and tooltip', () => {
    const option = buildKlineOverlayOption({
      bars: Array.from({ length: 40 }, (_, index) => bar(`202607${String(index + 1).padStart(2, '0')}`, 10 + index / 10)),
      subIndicators: ['macd', 'kdj']
    });
    const legends = option.legend as Array<{
      data: string[];
      formatter: (name: string) => string;
    }>;
    const tooltip = option.tooltip as { formatter: (params: unknown) => string };

    expect(legends).toHaveLength(2);
    expect(legends[0]?.data).toEqual(['MACD', 'DIF', 'DEA']);
    expect(legends[1]?.data).toEqual(['K', 'D', 'J']);
    expect(legends[0]?.formatter('DIF')).toMatch(/^DIF -?\d+\.\d{2}$/);
    expect(legends[1]?.formatter('K')).toMatch(/^K \d+\.\d{2}$/);
    expect(tooltip.formatter([
      { axisValue: '2026-07-16', seriesName: 'J', value: 64.1234 },
      { axisValue: '2026-07-16', seriesName: 'D', value: 61.5 }
    ])).toContain('J: 64.12');
    expect(tooltip.formatter([
      { axisValue: '2026-07-16', seriesName: 'K线', value: [209, 8.3, 8.2, 8.4, 8.5] }
    ])).toContain('K线: 开 8.30 收 8.20 高 8.50 低 8.40');
  });

  it('maps GSGF annotations to the main-pane mark point and mark area', () => {
    const option = buildKlineOverlayOption({
      bars: [bar('20260715', 10), bar('20260716', 12)],
      gsgfAnnotations
    });
    const annotationSeries = option.series.find(item => item.id === 'custom-gsgf-annotations') as {
      name: string;
      type: string;
      xAxisIndex: number;
      yAxisIndex: number;
      markPoint: { data: Array<Record<string, unknown>> };
      markArea: { data: Array<Array<Record<string, unknown>>> };
    } | undefined;

    expect(annotationSeries).toMatchObject({ name: 'GSGF标注', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0 });
    expect(annotationSeries?.markPoint.data).toContainEqual(expect.objectContaining({
      coord: ['2026-07-16', 12],
      name: '星线蓄势'
    }));
    expect(annotationSeries?.markArea.data).toContainEqual([
      expect.objectContaining({ name: '量能结构', xAxis: '2026-07-15' }),
      expect.objectContaining({ xAxis: '2026-07-16' })
    ]);
  });

  it('keeps GSGF annotations out of minute and disabled chart paths', () => {
    expect(getVisibleGsgfAnnotations('1d', true, gsgfAnnotations)).toEqual(gsgfAnnotations);
    expect(getVisibleGsgfAnnotations('1d', false, gsgfAnnotations)).toEqual([]);
    expect(getVisibleGsgfAnnotations('60m', true, gsgfAnnotations)).toEqual([]);
    expect(getVisibleGsgfAnnotations('30m', true, gsgfAnnotations)).toEqual([]);
    expect(getVisibleGsgfAnnotations('5m', true, gsgfAnnotations)).toEqual([]);
    expect(getVisibleGsgfAnnotations('weekly', true, gsgfAnnotations)).toEqual([]);
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

  it.each([
    ['volume'],
    ['volume', 'macd'],
    ['volume', 'macd', 'kdj']
  ] as const)('keeps grid vertical intervals strictly increasing for %s panes', (...indicators) => {
    const option = buildKlineOverlayOption({ bars: [bar('20260715', 10), bar('20260716', 12)], subIndicators: [...indicators] });
    const grids = option.grid as Array<{ top?: string; height: string; bottom?: string }>;
    const intervals = grids.map(grid => {
      expect(grid.height).toMatch(/^\d+(?:\.\d+)?%$/);
      expect(typeof grid.top === 'string' || typeof grid.bottom === 'string').toBe(true);
      const height = percent(grid.height);
      const start = grid.top ? percent(grid.top) : 100 - percent(grid.bottom ?? '0%') - height;
      return { start, end: start + height };
    });

    intervals.slice(1).forEach((interval, index) => {
      expect(interval.start).toBeGreaterThan(intervals[index]?.end ?? -1);
    });
  });

  it('caps four selected indicators at three sub panes without overlap', () => {
    const option = buildKlineOverlayOption({
      bars: [bar('20260715', 10), bar('20260716', 12)],
      subIndicators: [...(['volume', 'macd', 'kdj', 'rsi'] as const)]
    });
    const grids = option.grid as Array<{ top?: string; height: string; bottom?: string }>;
    const series = option.series as Array<{ name: string; xAxisIndex: number }>;

    expect(grids).toHaveLength(4);
    expect(gridIntervals(grids).slice(1).every((interval, index) => interval.start > (gridIntervals(grids)[index]?.end ?? -1))).toBe(true);
    expect(series.some(item => item.name === 'RSI')).toBe(false);
  });

  it('maps MACD, KDJ, and brick results to their selected sub panes', () => {
    const option = buildKlineOverlayOption({
      bars: Array.from({ length: 32 }, (_, index) => bar(`202607${String(index + 1).padStart(2, '0')}`, 10 + index / 10)),
      subIndicators: ['macd', 'kdj', 'brick']
    });
    const series = option.series as Array<{ name: string; type: string; xAxisIndex: number; yAxisIndex: number; connectNulls?: boolean }>;

    expect(series.filter(item => item.name === 'MACD')).toContainEqual(expect.objectContaining({ type: 'bar', xAxisIndex: 1, yAxisIndex: 1 }));
    expect(series.filter(item => ['DIF', 'DEA'].includes(item.name))).toHaveLength(2);
    expect(series.filter(item => ['K', 'D', 'J'].includes(item.name))).toHaveLength(3);
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

  it('executes the chart lifecycle with replace, restore, resize, and cleanup actions', () => {
    const chart = {
      setOption: vi.fn(),
      dispatchAction: vi.fn(),
      resize: vi.fn(),
      dispose: vi.fn()
    };
    const resizeObserver = { disconnect: vi.fn() };
    const option = { series: [] };

    runEChartLifecycle(chart, { type: 'setOption', option });
    runEChartLifecycle(chart, { type: 'restore' });
    runEChartLifecycle(chart, { type: 'resize' });
    runEChartLifecycle(chart, { type: 'dispose', resizeObserver });

    expect(chart.setOption).toHaveBeenCalledWith(option, true);
    expect(chart.dispatchAction).toHaveBeenCalledWith({ type: 'dataZoom', start: 0, end: 100 });
    expect(chart.resize).toHaveBeenCalledOnce();
    expect(resizeObserver.disconnect).toHaveBeenCalledOnce();
    expect(chart.dispose).toHaveBeenCalledOnce();
  });

  it('builds a sector replica option without changing the supplied axis', () => {
    const input: SectorReplicaChartSeries[] = [{ name: '计算机', type: 'line', data: [1, 2], smooth: true, showSymbol: false }];
    const option = buildSectorReplicaOption({ axis: ['09:30', '10:00'], series: input });

    expect(option.xAxis).toMatchObject({ data: ['09:30', '10:00'] });
    expect((option.series as Array<{ name: string }>)[0]?.name).toBe('计算机');
  });
});

function percent(value: string): number {
  expect(value).toMatch(/^\d+(?:\.\d+)?%$/);
  return Number.parseFloat(value);
}

function gridIntervals(grids: Array<{ top?: string; height: string; bottom?: string }>) {
  return grids.map(grid => {
    const height = percent(grid.height);
    const start = grid.top ? percent(grid.top) : 100 - percent(grid.bottom ?? '0%') - height;
    return { start, end: start + height };
  });
}
