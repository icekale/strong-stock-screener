import { describe, expect, it } from 'vitest';
import type { EtfExcessFlowResponse } from '@/service/types';
import { buildExcessFlowSeries, formatExcessFlowCny, shareChangeEventLabel } from './etfExcessFlow';

function response(overrides: Partial<EtfExcessFlowResponse> = {}): EtfExcessFlowResponse {
  return {
    generated_at: '2026-07-23T15:05:00+08:00',
    trade_date: '2026-07-23',
    as_of: '2026-07-23T15:00:00+08:00',
    signal_stage: 'post_close',
    model_version: 'etf-excess-flow-v1',
    source_status: [],
    formula: 'formula',
    expected_count: 2,
    points: [
      {
        trade_date: '2026-07-21',
        net_excess_flow_cny: 120_000_000,
        excess_inflow_cny: 200_000_000,
        excess_outflow_cny: 80_000_000,
        coverage_count: 2,
        expected_count: 2,
        tenfold_increase_count: 1,
        tenfold_decrease_count: 0,
        trigger_symbols: ['510050.SH']
      },
      {
        trade_date: '2026-07-22',
        net_excess_flow_cny: null,
        excess_inflow_cny: null,
        excess_outflow_cny: null,
        coverage_count: 0,
        expected_count: 2,
        tenfold_increase_count: 0,
        tenfold_decrease_count: 0,
        trigger_symbols: []
      }
    ],
    ...overrides
  };
}

describe('etfExcessFlow', () => {
  it('builds three gap-preserving line series and event points', () => {
    const result = buildExcessFlowSeries(response());

    expect(result.dates).toEqual(['2026-07-21', '2026-07-22']);
    expect(result.series.map(item => item.name)).toEqual(['净超量资金', '申购超量', '赎回超量']);
    expect(result.series[0]?.data).toEqual([120_000_000, null]);
    expect(result.series.every(item => item.connectNulls === false)).toBe(true);
    expect(result.events).toEqual([{ date: '2026-07-21', symbols: ['510050.SH'], increase: 1, decrease: 0 }]);
  });

  it('formats money and labels tenfold direction without treating proxy as confirmed activity', () => {
    expect(formatExcessFlowCny(120_000_000)).toBe('1.20亿');
    expect(formatExcessFlowCny(null)).toBe('--');
    expect(shareChangeEventLabel({ is_tenfold_share_change: true, direction: 'increase' })).toBe('10×申购');
    expect(shareChangeEventLabel({ is_tenfold_share_change: true, direction: 'decrease' })).toBe('10×赎回');
    expect(shareChangeEventLabel({ is_tenfold_share_change: false, direction: 'increase' })).toBeNull();
  });
});
