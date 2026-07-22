import { describe, expect, it } from 'vitest';
import type { SentimentPercentilePoint } from '@/service/types';
import { buildSentimentPercentileChartOption } from './sentimentPercentileChart';

function historyFixture(): SentimentPercentilePoint[] {
  return [
    createPoint({
      trade_date: '2026-07-18',
      score: 16,
      level: '冰点',
      volumeRawValue: 1_230_000_000
    }),
    createPoint({
      trade_date: '2026-07-19',
      score: 88,
      level: '过热',
      volumeRawValue: 1.75
    }),
    createPoint({
      trade_date: '2026-07-21',
      score: 52,
      level: '中性',
      volumeRawValue: 1.4
    }),
    createPoint({
      trade_date: '2026-07-22',
      score: 42,
      level: '偏冷',
      volumeRawValue: 1.2
    })
  ];
}

function createPoint({
  trade_date,
  score,
  level,
  volumeRawValue
}: {
  trade_date: string;
  score: number;
  level: SentimentPercentilePoint['level'];
  volumeRawValue: number;
}): SentimentPercentilePoint {
  return {
    trade_date,
    score,
    level,
    factors: {
      volume: { score: 72, raw_value: volumeRawValue, raw_unit: 'CNY' },
      index_move_5d: { score: 61, raw_value: 2.34, raw_unit: '%' },
      price_position: { score: 55, raw_value: 64.5, raw_unit: '%' },
      amplitude_5d: { score: 49, raw_value: 6.78, raw_unit: '%' },
      volume_trend: { score: 68, raw_value: 12.3, raw_unit: '%' }
    }
  };
}

describe('buildSentimentPercentileChartOption', () => {
  it('builds the fixed percentile scale and threshold annotations', () => {
    const option = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', false);
    const series = option.series as Array<{
      data: Array<{ symbolSize: number }>;
      markArea: { data: Array<Array<Record<string, unknown>>> };
      markLine: { data: Array<Record<string, unknown>> };
    }>;

    expect(option.xAxis).toMatchObject({
      type: 'category',
      data: ['2026-07-18', '2026-07-19', '2026-07-21', '2026-07-22']
    });
    expect(option.yAxis).toMatchObject({ type: 'value', min: 0, max: 100 });
    expect(series[0]?.markArea.data).toContainEqual([
      expect.objectContaining({ name: '冰点区', yAxis: 0 }),
      expect.objectContaining({ yAxis: 20 })
    ]);
    expect(series[0]?.markArea.data).toContainEqual([
      expect.objectContaining({ name: '过热区', yAxis: 80 }),
      expect.objectContaining({ yAxis: 100 })
    ]);
    expect(series[0]?.markLine.data).toEqual(
      expect.arrayContaining([expect.objectContaining({ yAxis: 20 }), expect.objectContaining({ yAxis: 80 })])
    );
    expect(JSON.stringify(option)).toContain('冰点区');
    expect(JSON.stringify(option)).toContain('过热区');
  });

  it('marks extreme points independently of the latest point', () => {
    const option = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', false);
    const series = option.series as Array<{
      data: Array<{ symbolSize: number; itemStyle: { color: string } }>;
    }>;

    expect(series[0]?.data[0]).toMatchObject({ symbolSize: 6, itemStyle: { color: '#16805c' } });
    expect(series[0]?.data[1]).toMatchObject({ symbolSize: 6, itemStyle: { color: '#c9363e' } });
    expect(series[0]?.data[2]).toMatchObject({ symbolSize: 0 });
  });

  it('marks a non-extreme latest point with its actual level color', () => {
    const option = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', false);
    const series = option.series as Array<{
      data: Array<{ symbolSize: number; itemStyle: { color: string } }>;
    }>;

    expect(series[0]?.data[3]).toEqual({
      value: 42,
      symbolSize: 6,
      itemStyle: { color: '#245b8a' }
    });
  });

  it('uses only resolved concrete colors in the canvas option', () => {
    const option = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', false);

    expect(JSON.stringify(option)).not.toContain('var(');
  });

  it('includes composite and all factor score and raw values in the tooltip', () => {
    const option = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', false);
    const tooltip = option.tooltip as {
      formatter: (params: { dataIndex: number }) => string;
    };
    const content = tooltip.formatter({ dataIndex: 0 });

    expect(content).toContain('综合情绪：16.0');
    expect(content).toContain('成交额：72.0 / 12.30亿');
    expect(content).toContain('5日指数涨幅：61.0 / 2.34%');
    expect(content).toContain('500日价格位置：55.0 / 64.50%');
    expect(content).toContain('5日振幅：49.0 / 6.78%');
    expect(content).toContain('量能趋势：68.0 / 12.30%');
  });

  it('keeps animation short and disables it for reduced motion', () => {
    const option = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', false);
    const reducedMotionOption = buildSentimentPercentileChartOption(historyFixture(), '2026-07-22', true);

    expect(option.animationDuration).toBeLessThanOrEqual(160);
    expect(reducedMotionOption.animationDuration).toBe(0);
  });
});
