import { describe, expect, it } from 'vitest';
import type { EtfRadarHistoryPoint, HuijinEtfActivityItem } from '@/service/types';
import {
  buildHuijinRanking,
  buildHuijinTrajectory,
  huijinActivityDataState,
  pickDefaultHuijinSymbol
} from './huijinTrajectory';

const baseItem: HuijinEtfActivityItem = {
  symbol: '510050.SH',
  name: '上证50ETF华夏',
  index_name: '上证50',
  role: 'core',
  paired_symbol: null,
  trade_date: '2026-07-18',
  total_shares: 8_237_466_800,
  previous_total_shares: 8_150_166_800,
  share_delta: 87_300_000,
  daily_change_pct: 1.07,
  baseline_change_pct: 0.15,
  cumulative_baseline_change_pct: -85.46,
  multiple: 1.5,
  direction: 'increase',
  is_tenfold: false,
  report_period: '2025-12-31',
  baseline_total_shares: 56_663_567_693,
  confirmed_huijin_shares: 48_759_000_000,
  confirmed_huijin_holding_pct: 86.05,
  baseline_source_kind: 'derived'
};

function itemWith(overrides: Partial<HuijinEtfActivityItem> = {}) {
  return { ...baseItem, ...overrides };
}

function item(symbol: string, cumulative: number | null, reportPeriod = '2025-12-31') {
  return itemWith({ symbol, cumulative_baseline_change_pct: cumulative, report_period: reportPeriod });
}

function point(tradeDate: string, cumulative: number | null): EtfRadarHistoryPoint {
  return {
    trade_date: tradeDate,
    symbol: '510050.SH',
    name: '上证50ETF华夏',
    total_shares: 8_237_466_800,
    share_change: null,
    estimated_subscription_cny: null,
    robust_score: null,
    daily_change_pct: null,
    baseline_change_pct: null,
    cumulative_baseline_change_pct: cumulative,
    multiple: null
  };
}

describe('Huijin trajectory transforms', () => {
  it('sorts available core ETFs by absolute cumulative deviation', () => {
    const items = [
      item('510300.SH', -75.55),
      item('159915.SZ', -52.63),
      item('510050.SH', -85.46),
    ];
    const originalItems = items.map(row => ({ ...row }));

    expect(buildHuijinRanking(items).map(row => row.symbol)).toEqual(['510050.SH', '510300.SH', '159915.SZ']);
    expect(items).toEqual(originalItems);
  });

  it('excludes validators from ranking and default selection', () => {
    const items = [
      item('510050.SH', -85.46),
      itemWith({ symbol: '159919.SZ', role: 'validator', cumulative_baseline_change_pct: -99.99 }),
    ];

    expect(buildHuijinRanking(items).map(row => row.symbol)).toEqual(['510050.SH']);
    expect(pickDefaultHuijinSymbol(items)).toBe('510050.SH');
  });

  it('starts a trajectory at the report baseline and preserves real gaps', () => {
    const points = [point('2026-07-16', -84), point('2026-07-18', -85.46)];
    const realDates = ['2026-07-16', '2026-07-17', '2026-07-18'];
    const originalPoints = points.map(row => ({ ...row }));
    const originalRealDates = [...realDates];

    expect(buildHuijinTrajectory(
      item('510050.SH', -85.46, '2025-12-31'),
      points,
      realDates,
    )).toEqual({
      dates: ['2025-12-31', '2026-07-16', '2026-07-17', '2026-07-18'],
      values: [0, -84, null, -85.46],
    });
    expect(points).toEqual(originalPoints);
    expect(realDates).toEqual(originalRealDates);
  });

  it('keeps only the selected report baseline period in strict date order', () => {
    expect(buildHuijinTrajectory(
      item('510050.SH', 2, '2026-06-30'),
      [point('2026-06-27', -4), point('2026-07-01', 2)],
      ['2026-07-01', '2026-06-27'],
    )).toEqual({
      dates: ['2026-06-30', '2026-07-01'],
      values: [0, 2],
    });
  });

  it('distinguishes disclosure, daily-history, and baseline gaps', () => {
    expect(huijinActivityDataState(itemWith({ total_shares: null }))).toBe('交易所尚未披露');
    expect(huijinActivityDataState(itemWith({ previous_total_shares: null }))).toBe('日度历史积累中');
    expect(huijinActivityDataState(itemWith({ report_period: null }))).toBe('确认基线缺失');
  });

  it('picks the strongest available ETF and falls back to the first item', () => {
    expect(pickDefaultHuijinSymbol([
      item('510300.SH', null),
      item('510050.SH', -85.46),
    ])).toBe('510050.SH');
    expect(pickDefaultHuijinSymbol([item('510300.SH', null)])).toBe('510300.SH');
    expect(pickDefaultHuijinSymbol([])).toBe('');
  });
});
