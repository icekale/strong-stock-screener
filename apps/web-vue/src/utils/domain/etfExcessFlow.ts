import type { EtfExcessFlowResponse, HuijinEtfActivityItem } from '@/service/types';

export type ExcessFlowSeries = {
  dates: string[];
  series: Array<{ name: string; type: 'line'; data: Array<number | null>; connectNulls: false }>;
  events: Array<{ date: string; symbols: string[]; increase: number; decrease: number }>;
};

export function buildExcessFlowSeries(response: EtfExcessFlowResponse): ExcessFlowSeries {
  const points = response.points;
  return {
    dates: points.map(point => point.trade_date),
    series: [
      {
        name: '净超量资金',
        type: 'line',
        data: points.map(point => point.net_excess_flow_cny),
        connectNulls: false
      },
      {
        name: '申购超量',
        type: 'line',
        data: points.map(point => point.excess_inflow_cny),
        connectNulls: false
      },
      {
        name: '赎回超量',
        type: 'line',
        data: points.map(point => point.excess_outflow_cny === null ? null : -point.excess_outflow_cny),
        connectNulls: false
      }
    ],
    events: points
      .filter(point => point.trigger_symbols.length > 0)
      .map(point => ({
        date: point.trade_date,
        symbols: point.trigger_symbols,
        increase: point.tenfold_increase_count,
        decrease: point.tenfold_decrease_count
      }))
  };
}

export function formatExcessFlowCny(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  const absolute = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (absolute >= 100_000_000) return `${sign}${(absolute / 100_000_000).toFixed(2)}亿`;
  if (absolute >= 10_000) return `${sign}${(absolute / 10_000).toFixed(2)}万`;
  return `${value.toFixed(0)}元`;
}

export function shareChangeEventLabel(item: Pick<HuijinEtfActivityItem, 'is_tenfold_share_change' | 'direction'>): string | null {
  if (!item.is_tenfold_share_change) return null;
  if (item.direction === 'increase') return '10×申购';
  if (item.direction === 'decrease') return '10×赎回';
  return '10×异常';
}
