import type { SentimentPercentileFactor, SentimentPercentileLevel, SentimentPercentilePoint } from '@/service/types';

const COLORS = {
  primary: '#245b8a',
  positive: '#c9363e',
  negative: '#16805c',
  warning: '#a66a00',
  muted: '#617184',
  border: '#d9e2ea',
  surface: '#ffffff'
};

const FACTOR_LABELS: Array<[keyof SentimentPercentilePoint['factors'], string]> = [
  ['volume', '成交额'],
  ['index_move_5d', '5日指数涨幅'],
  ['price_position', '500日价格位置'],
  ['amplitude_5d', '5日振幅'],
  ['volume_trend', '量能趋势']
];

export function buildSentimentPercentileChartOption(
  history: SentimentPercentilePoint[],
  latestTradeDate: string,
  reducedMotion: boolean,
  selectedTradeDate: string = latestTradeDate
) {
  return {
    animation: !reducedMotion,
    animationDuration: reducedMotion ? 0 : 160,
    animationDurationUpdate: reducedMotion ? 0 : 160,
    backgroundColor: COLORS.surface,
    grid: { left: 46, right: 18, top: 22, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: COLORS.border,
      borderWidth: 1,
      textStyle: { color: '#1f2d3d', fontSize: 12 },
      formatter: (params: { dataIndex?: number } | Array<{ dataIndex?: number }>) => {
        const dataIndex = Array.isArray(params) ? params[0]?.dataIndex : params.dataIndex;
        const point = typeof dataIndex === 'number' ? history[dataIndex] : undefined;
        return point ? formatTooltip(point) : '';
      }
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: history.map(point => point.trade_date),
      axisLine: { lineStyle: { color: COLORS.border } },
      axisTick: { show: false },
      axisLabel: { color: COLORS.muted, fontSize: 11, hideOverlap: true }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      interval: 20,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: COLORS.muted, fontSize: 11 },
      splitLine: { lineStyle: { color: COLORS.border } }
    },
    series: [
      {
        name: '市场情绪百分位',
        type: 'line',
        smooth: 0.28,
        showSymbol: true,
        symbol: 'circle',
        lineStyle: { color: COLORS.primary, width: 2 },
        data: history.map(point => ({
          value: point.score,
          symbolSize:
            point.trade_date === latestTradeDate || point.trade_date === selectedTradeDate || isExtreme(point.level)
              ? 6
              : 0,
          itemStyle: { color: levelColor(point.level) }
        })),
        markArea: {
          silent: true,
          label: { color: COLORS.muted, fontSize: 11 },
          data: [
            [
              {
                name: '冰点区',
                yAxis: 0,
                itemStyle: { color: 'rgba(22, 128, 92, 0.08)' }
              },
              { yAxis: 20 }
            ],
            [
              {
                name: '过热区',
                yAxis: 80,
                itemStyle: { color: 'rgba(201, 54, 62, 0.08)' }
              },
              { yAxis: 100 }
            ]
          ]
        },
        markLine: {
          silent: true,
          symbol: ['none', 'none'],
          label: { show: false },
          lineStyle: { color: COLORS.muted, type: 'dashed' },
          data: [{ yAxis: 20 }, { yAxis: 80 }]
        }
      }
    ]
  };
}

function isExtreme(level: SentimentPercentileLevel): boolean {
  return level === '冰点' || level === '过热';
}

function levelColor(level: SentimentPercentileLevel): string {
  if (level === '冰点') return COLORS.negative;
  if (level === '偏冷') return COLORS.primary;
  if (level === '偏热') return COLORS.warning;
  if (level === '过热') return COLORS.positive;
  return COLORS.muted;
}

function formatTooltip(point: SentimentPercentilePoint): string {
  const factorLines = FACTOR_LABELS.map(([key, label]) => formatFactorLine(label, point.factors[key]));
  return [
    `<strong>${point.trade_date}</strong>`,
    `综合情绪：${point.score.toFixed(1)}（${point.level}）`,
    ...factorLines
  ].join('<br/>');
}

function formatFactorLine(label: string, factor: SentimentPercentileFactor): string {
  return `${label}：${factor.score.toFixed(1)} / ${formatRawValue(factor)}`;
}

function formatRawValue(factor: SentimentPercentileFactor): string {
  if (factor.raw_unit === 'CNY') {
    if (Math.abs(factor.raw_value) >= 100_000_000) {
      return `${(factor.raw_value / 100_000_000).toFixed(2)}亿`;
    }
    if (Math.abs(factor.raw_value) >= 10_000) {
      return `${(factor.raw_value / 10_000).toFixed(2)}万`;
    }
    return factor.raw_value.toFixed(2);
  }
  return `${factor.raw_value.toFixed(2)}${factor.raw_unit}`;
}
