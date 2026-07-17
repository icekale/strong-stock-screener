import type { ChanlunAnalysisResponse, ChanlunLayerKey, GsgfChartAnnotation, KlineBar, StockKlinePeriod } from '@/service/types';
import type { EChartsOption } from 'echarts';
import { buildChanlunOverlaySeries } from './chanlunOverlay';
import {
  buildKlineIndicatorOptions,
  getKlinePaneLayout,
  type IndicatorOptions,
  type KlineMovingAverage,
  type KlineSubIndicator
} from './klineIndicatorLayout';
import {
  calculateAtr,
  calculateBias,
  calculateBrick,
  calculateCci,
  calculateDmi,
  calculateKdj,
  calculateMacd,
  calculateObv,
  calculateRoc,
  calculateRsi,
  calculateWr,
  type DmiOptions,
  type KdjOptions,
  type KlineIndicatorSeries,
  type MacdOptions,
  type MultiPeriodOptions,
  type ObvOptions,
  type PeriodOptions,
  type RocOptions
} from './klineIndicators';

export type KlineOverlayOptionInput = {
  bars: KlineBar[];
  movingAverages?: KlineMovingAverage[];
  subIndicators?: KlineSubIndicator[];
  gsgfAnnotations?: GsgfChartAnnotation[];
  chanlun?: ChanlunAnalysisResponse | null;
  chanlunLayers?: Partial<Record<ChanlunLayerKey, boolean>>;
  visibleBarCount?: number;
};

export type KlineOverlayOption = {
  animation: boolean;
  backgroundColor: string;
  grid: Array<Record<string, unknown>>;
  xAxis: Array<Record<string, unknown>>;
  yAxis: Array<Record<string, unknown>>;
  dataZoom: Array<Record<string, unknown>>;
  tooltip: Record<string, unknown>;
  series: Array<Record<string, unknown>>;
};

const MA_FIELDS: Record<KlineMovingAverage, keyof KlineBar> = {
  ma5: 'ma5',
  ma10: 'ma10',
  ma20: 'ma20',
  ma60: 'ma60'
};

const MA_COLORS: Record<KlineMovingAverage, string> = {
  ma5: '#1677ff',
  ma10: '#f59e0b',
  ma20: '#7c3aed',
  ma60: '#64748b'
};

const INDICATOR_COLORS = ['#1677ff', '#f59e0b', '#7c3aed', '#0891b2'];
const MAX_SUB_INDICATORS = 3;

export type EChartLifecycleTarget = {
  setOption: (option: EChartsOption, notMerge?: boolean) => void;
  dispatchAction: (payload: { type: 'dataZoom'; start: number; end: number }) => void;
  resize: () => void;
  dispose: () => void;
};

export type EChartResizeObserver = { disconnect: () => void };

export type EChartLifecycleAction =
  | { type: 'setOption'; option: EChartsOption }
  | { type: 'restore' }
  | { type: 'resize' }
  | { type: 'dispose'; resizeObserver?: EChartResizeObserver | null };

export function runEChartLifecycle(chart: EChartLifecycleTarget, action: EChartLifecycleAction): void {
  switch (action.type) {
    case 'setOption':
      chart.setOption(action.option, true);
      return;
    case 'restore':
      chart.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
      return;
    case 'resize':
      chart.resize();
      return;
    case 'dispose':
      action.resizeObserver?.disconnect();
      chart.dispose();
  }
}

export function getVisibleGsgfAnnotations(
  period: StockKlinePeriod | 'weekly',
  enabled: boolean,
  annotations: readonly GsgfChartAnnotation[]
): GsgfChartAnnotation[] {
  return period === '1d' && enabled ? [...annotations] : [];
}

export function buildKlineOverlayOption({
  bars,
  movingAverages = [],
  subIndicators = ['volume'],
  gsgfAnnotations = [],
  chanlun,
  chanlunLayers,
  visibleBarCount
}: KlineOverlayOptionInput): KlineOverlayOption {
  const selectedSubIndicators = subIndicators.slice(0, MAX_SUB_INDICATORS);
  const dates = bars.map(bar => normalizeKlineDate(bar.date));
  const layout = getKlinePaneLayout(selectedSubIndicators.length);
  const grids = buildGrids(selectedSubIndicators.length, layout);
  const xAxes = buildXAxes(dates, grids.length);
  const yAxes = buildYAxes(grids.length);
  const series: Array<Record<string, unknown>> = [
    {
      name: 'K线',
      type: 'candlestick',
      data: bars.map(bar => [bar.open, bar.close, bar.low, bar.high]),
      xAxisIndex: 0,
      yAxisIndex: 0,
      itemStyle: { color: '#d9363e', color0: '#07845e', borderColor: '#d9363e', borderColor0: '#07845e' }
    }
  ];

  movingAverages.forEach(field => {
    series.push({
      name: field.toUpperCase(),
      type: 'line',
      data: bars.map(bar => bar[MA_FIELDS[field]]),
      showSymbol: false,
      connectNulls: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
      lineStyle: { width: 1.2, color: MA_COLORS[field] }
    });
  });

  series.push(...buildGsgfAnnotationSeries(gsgfAnnotations, bars, dates));

  const indicatorOptions = buildKlineIndicatorOptions(movingAverages);
  selectedSubIndicators.forEach((indicator, index) => {
    series.push(...buildSubIndicatorSeries(indicator, bars, index + 1, indicatorOptions));
  });

  if (chanlun) {
    series.push(
      ...buildChanlunOverlaySeries(
        chanlun,
        chanlunLayers ?? { fractals: false, segments: true, strokes: false, zones: true, divergences: true, signals: true },
        { chartDates: dates, visibleBarCount: visibleBarCount ?? bars.length }
      )
    );
  }

  return {
    animation: false,
    backgroundColor: '#ffffff',
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', xAxisIndex: axisIndexes(grids.length), start: 0, end: 100 },
      { type: 'slider', xAxisIndex: axisIndexes(grids.length), bottom: 8, height: 18 }
    ],
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, confine: true },
    series
  };
}

function buildGsgfAnnotationSeries(
  annotations: readonly GsgfChartAnnotation[],
  bars: KlineBar[],
  dates: string[]
): Array<Record<string, unknown>> {
  const points = annotations
    .filter(annotation => annotation.date != null)
    .map(annotation => {
      const index = resolveAnnotationDateIndex(annotation.date, dates);
      if (index < 0 || !bars[index]) return null;
      const price = annotation.price ?? bars[index].close;
      return {
        coord: [dates[index], price],
        itemStyle: { color: annotationColor(annotation.severity) },
        label: {
          backgroundColor: annotationColor(annotation.severity),
          borderRadius: 3,
          color: '#ffffff',
          fontSize: 11,
          fontWeight: 700,
          padding: [3, 5]
        },
        name: annotation.label,
        value: annotation.label
      };
    })
    .filter(point => point !== null);
  const ranges = annotations
    .filter(annotation => annotation.start_date != null && annotation.end_date != null)
    .map(annotation => {
      const startIndex = resolveAnnotationDateIndex(annotation.start_date, dates);
      const endIndex = resolveAnnotationDateIndex(annotation.end_date, dates);
      if (startIndex < 0 || endIndex < 0 || startIndex > endIndex) return null;
      return [
        {
          itemStyle: { color: annotationAreaColor(annotation.severity) },
          name: annotation.label,
          xAxis: dates[startIndex]
        },
        { xAxis: dates[endIndex] }
      ];
    })
    .filter(range => range !== null);

  if (points.length === 0 && ranges.length === 0) return [];
  return [{
    data: [],
    id: 'custom-gsgf-annotations',
    markArea: { data: ranges, label: { formatter: '{b}', show: true }, silent: true },
    markPoint: { data: points, label: { formatter: '{b}', show: true }, symbol: 'pin', symbolSize: 52 },
    name: 'GSGF标注',
    type: 'candlestick',
    xAxisIndex: 0,
    yAxisIndex: 0
  }];
}

function resolveAnnotationDateIndex(value: string | null, dates: string[]): number {
  if (!value) return -1;
  const normalized = normalizeKlineDate(value);
  const exactIndex = dates.indexOf(normalized);
  if (exactIndex >= 0) return exactIndex;
  const day = normalized.slice(0, 10);
  return dates.findIndex(date => date.slice(0, 10) === day);
}

function annotationColor(severity: GsgfChartAnnotation['severity']): string {
  if (severity === 'positive') return '#f43f5e';
  if (severity === 'warning') return '#f59e0b';
  if (severity === 'danger') return '#0f766e';
  return '#64748b';
}

function annotationAreaColor(severity: GsgfChartAnnotation['severity']): string {
  if (severity === 'positive') return 'rgba(244, 63, 94, 0.07)';
  if (severity === 'warning') return 'rgba(245, 158, 11, 0.09)';
  if (severity === 'danger') return 'rgba(15, 118, 110, 0.08)';
  return 'rgba(100, 116, 139, 0.07)';
}

function buildGrids(subPaneCount: number, layout: { main: string; sub: string }): Array<Record<string, unknown>> {
  const grids: Array<Record<string, unknown>> = [
    { left: 52, right: 18, top: '0%', height: layout.main, containLabel: true }
  ];
  for (let index = 0; index < subPaneCount; index += 1) {
    const isLast = index === subPaneCount - 1;
    const position = isLast ? { bottom: '0%' } : { top: gridTop(index + 1, subPaneCount) };
    grids.push({
      left: 52,
      right: 18,
      ...position,
      height: layout.sub,
      containLabel: true
    });
  }
  return grids;
}

function gridTop(paneIndex: number, subPaneCount: number): string {
  if (subPaneCount === 2) return '66%';
  if (subPaneCount === 3) return paneIndex === 1 ? '54%' : '70%';
  return `${paneIndex * 20 + 2}%`;
}

function buildXAxes(dates: string[], paneCount: number): Array<Record<string, unknown>> {
  return Array.from({ length: paneCount }, (_, gridIndex) => ({
    type: 'category',
    data: dates,
    boundaryGap: true,
    gridIndex,
    axisLabel: gridIndex === 0 ? undefined : { show: false },
    axisTick: gridIndex === 0 ? undefined : { show: false }
  }));
}

function buildYAxes(paneCount: number): Array<Record<string, unknown>> {
  return Array.from({ length: paneCount }, (_, gridIndex) => ({
    type: 'value',
    scale: true,
    gridIndex,
    axisLabel: gridIndex === 0 ? undefined : { show: false },
    splitLine: gridIndex === 0 ? undefined : { show: false }
  }));
}

function buildSubIndicatorSeries(
  indicator: KlineSubIndicator,
  bars: KlineBar[],
  axisIndex: number,
  options: IndicatorOptions
): Array<Record<string, unknown>> {
  if (indicator === 'volume') {
    return [{
      id: `kline-volume-${axisIndex}`,
      name: '成交量',
      type: 'bar',
      data: bars.map(bar => bar.volume),
      xAxisIndex: axisIndex,
      yAxisIndex: axisIndex,
      connectNulls: false,
      itemStyle: { color: '#91caff' }
    }];
  }

  const result = calculateSubIndicator(indicator, bars, options);
  if (indicator === 'brick') {
    return [{
      id: `kline-brick-${axisIndex}`,
      name: result.name,
      type: 'candlestick',
      data: toBrickCandles(result.values),
      xAxisIndex: axisIndex,
      yAxisIndex: axisIndex,
      connectNulls: false,
      itemStyle: { color: '#d9363e', color0: '#07845e', borderColor: '#d9363e', borderColor0: '#07845e' }
    }];
  }

  const series: Array<Record<string, unknown>> = [
    makeIndicatorSeries(result.name, indicator === 'macd' ? 'bar' : 'line', result.values, axisIndex, 0)
  ];
  result.lines?.forEach((line, index) => {
    series.push(makeIndicatorSeries(line.name, 'line', line.values, axisIndex, index + 1));
  });
  return series;
}

function makeIndicatorSeries(
  name: string,
  type: 'line' | 'bar',
  data: Array<number | null>,
  axisIndex: number,
  colorIndex: number
): Record<string, unknown> {
  return {
    id: `kline-${axisIndex}-${name}`,
    name,
    type,
    data,
    xAxisIndex: axisIndex,
    yAxisIndex: axisIndex,
    connectNulls: false,
    ...(type === 'line' ? { showSymbol: false } : {}),
    itemStyle: { color: INDICATOR_COLORS[colorIndex % INDICATOR_COLORS.length] },
    lineStyle: type === 'line' ? { width: 1.1, color: INDICATOR_COLORS[colorIndex % INDICATOR_COLORS.length] } : undefined
  };
}

function calculateSubIndicator(indicator: Exclude<KlineSubIndicator, 'volume'>, bars: KlineBar[], options: IndicatorOptions): KlineIndicatorSeries {
  switch (indicator) {
    case 'macd':
      return calculateMacd(bars, options.macd as MacdOptions);
    case 'kdj':
      return calculateKdj(bars, options.kdj as KdjOptions);
    case 'rsi':
      return calculateRsi(bars, options.rsi as MultiPeriodOptions);
    case 'wr':
      return calculateWr(bars, options.wr as MultiPeriodOptions);
    case 'bias':
      return calculateBias(bars, options.bias as MultiPeriodOptions);
    case 'cci':
      return calculateCci(bars, options.cci as PeriodOptions);
    case 'atr':
      return calculateAtr(bars, options.atr as PeriodOptions);
    case 'obv':
      return calculateObv(bars, options.obv as ObvOptions);
    case 'roc':
      return calculateRoc(bars, options.roc as RocOptions);
    case 'dmi':
      return calculateDmi(bars, options.dmi as DmiOptions);
    case 'brick':
      return calculateBrick(bars, { period: 4 });
  }
}

function toBrickCandles(values: Array<number | null>): Array<[number, number, number, number] | null> {
  let previous: number | null = null;
  return values.map(value => {
    if (value === null) {
      previous = null;
      return null;
    }
    const open = previous ?? value;
    previous = value;
    return [open, value, Math.min(open, value), Math.max(open, value)];
  });
}

function axisIndexes(count: number): number[] {
  return Array.from({ length: count }, (_, index) => index);
}

function normalizeKlineDate(value: string): string {
  if (/^\d{8}$/.test(value)) return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  return value.replace('T', ' ').slice(0, 16);
}
