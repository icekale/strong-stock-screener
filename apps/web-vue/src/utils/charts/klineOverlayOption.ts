import type { ChanlunAnalysisResponse, ChanlunLayerKey, KlineBar } from '@/service/types';
import { buildChanlunOverlaySeries } from './chanlunOverlay';
import type { KlineMovingAverage, KlineSubIndicator } from './klineIndicatorLayout';

export type KlineOverlayOptionInput = {
  bars: KlineBar[];
  movingAverages?: KlineMovingAverage[];
  subIndicators?: KlineSubIndicator[];
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

export function buildKlineOverlayOption({
  bars,
  movingAverages = [],
  subIndicators = ['volume'],
  chanlun,
  chanlunLayers,
  visibleBarCount
}: KlineOverlayOptionInput): KlineOverlayOption {
  const dates = bars.map(bar => normalizeKlineDate(bar.date));
  const hasVolume = subIndicators.includes('volume');
  const mainGridHeight = hasVolume ? '72%' : '82%';
  const grids: Array<Record<string, unknown>> = [{ left: 52, right: 18, top: 24, height: mainGridHeight, containLabel: true }];
  const xAxes: Array<Record<string, unknown>> = [{ type: 'category', data: dates, boundaryGap: true, gridIndex: 0 }];
  const yAxes: Array<Record<string, unknown>> = [{ type: 'value', scale: true, gridIndex: 0 }];
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

  if (hasVolume) {
    grids.push({ left: 52, right: 18, bottom: 42, height: '16%', containLabel: true });
    xAxes.push({ type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false }, axisTick: { show: false } });
    yAxes.push({ type: 'value', gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } });
    series.push({
      name: '成交量',
      type: 'bar',
      data: bars.map(bar => bar.volume),
      xAxisIndex: 1,
      yAxisIndex: 1,
      itemStyle: { color: '#91caff' }
    });
  }

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
      { type: 'inside', xAxisIndex: [0, hasVolume ? 1 : 0], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, hasVolume ? 1 : 0], bottom: 8, height: 18 }
    ],
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, confine: true },
    series
  };
}

function normalizeKlineDate(value: string): string {
  if (/^\d{8}$/.test(value)) return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  return value.replace('T', ' ').slice(0, 16);
}
