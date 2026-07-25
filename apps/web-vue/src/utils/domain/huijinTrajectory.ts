import type { EtfRadarHistoryPoint, HuijinEtfActivityItem, HuijinEtfValidationGroup } from '@/service/types';

export function buildNormalizedTrend(etf: Array<number | null>, index: Array<number | null>) {
  const normalize = (values: Array<number | null>) => {
    const base = values.find(value => value !== null);
    return values.map(value =>
      value === null || base === undefined ? null : Number((100 + value - base).toFixed(6))
    );
  };
  return { etf: normalize(etf), index: normalize(index) };
}

export function buildHuijinExceptions(
  items: HuijinEtfActivityItem[],
  validationGroups: HuijinEtfValidationGroup[]
) {
  const groupByCore = new Map(validationGroups.map(group => [group.core_symbol, group]));
  return items
    .filter(item => item.role === 'core')
    .filter(item => {
      const group = groupByCore.get(item.symbol);
      return item.is_tenfold || item.total_shares === null || item.previous_total_shares === null
        || group?.state === 'divergent' || group?.state === 'incomplete';
    })
    .sort((left, right) => Math.abs(right.baseline_change_pct ?? 0) - Math.abs(left.baseline_change_pct ?? 0));
}

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

export function buildShareTrajectory(
  item: HuijinEtfActivityItem,
  points: EtfRadarHistoryPoint[],
  realDates: string[]
) {
  const values = new Map(
    points
      .filter(point => point.symbol === item.symbol)
      .map(point => [point.trade_date, point.total_shares])
  );
  const dates = [
    ...new Set([
      ...(item.report_period ? [item.report_period] : []),
      ...realDates.filter(date => !item.report_period || date > item.report_period)
    ])
  ].sort();
  return {
    dates,
    values: dates.map(date => {
      const shares = date === item.report_period ? item.baseline_total_shares : values.get(date);
      return shares === null || shares === undefined ? null : Number((shares / 100_000_000).toFixed(8));
    })
  };
}

export function huijinActivityDataState(item: HuijinEtfActivityItem) {
  if (item.total_shares === null) return '交易所尚未披露';
  if (item.report_period === null || item.baseline_total_shares === null) return '确认基线缺失';
  if (item.previous_total_shares === null) return '日度历史积累中';
  return '可计算';
}
