import type { EtfRadarHistoryPoint, HuijinEtfActivityItem } from '@/service/types';

export function buildHuijinRanking(items: HuijinEtfActivityItem[]) {
  return [...items]
    .filter(item => item.role === 'core' && item.cumulative_baseline_change_pct !== null)
    .sort((left, right) =>
      Math.abs(right.cumulative_baseline_change_pct!) - Math.abs(left.cumulative_baseline_change_pct!)
    );
}

export function pickDefaultHuijinSymbol(items: HuijinEtfActivityItem[]) {
  return buildHuijinRanking(items)[0]?.symbol ?? items[0]?.symbol ?? '';
}

export function buildHuijinTrajectory(
  item: HuijinEtfActivityItem,
  points: EtfRadarHistoryPoint[],
  realDates: string[]
) {
  const values = new Map(
    points.filter(point => point.symbol === item.symbol)
      .map(point => [point.trade_date, point.cumulative_baseline_change_pct])
  );
  const dates = [
    ...new Set([
      ...(item.report_period ? [item.report_period] : []),
      ...realDates.filter(date => !item.report_period || date > item.report_period)
    ])
  ].sort();
  return {
    dates,
    values: dates.map(date => date === item.report_period ? 0 : values.get(date) ?? null)
  };
}

export function huijinActivityDataState(item: HuijinEtfActivityItem) {
  if (item.total_shares === null) return '交易所尚未披露';
  if (item.report_period === null || item.baseline_total_shares === null) return '确认基线缺失';
  if (item.previous_total_shares === null) return '日度历史积累中';
  return '可计算';
}
