import { describe, expect, it } from 'vitest';
import type { EtfThreeFactorItem, HuijinEtfActivityItem } from '@/service/types';
import {
  buildUnifiedEtfActivityRows,
  closeChangeTone,
  factorStatusLabel,
  formatVolumeRatio,
  pickDefaultEtfActivitySymbol,
  signalLevelLabel,
  signalTone
} from './etfThreeFactor';

function activityItem(overrides: Partial<HuijinEtfActivityItem> = {}): HuijinEtfActivityItem {
  return {
    symbol: '510050.SH',
    name: '活动ETF',
    index_name: '活动指数',
    role: 'core',
    paired_symbol: null,
    trade_date: '2026-07-18',
    total_shares: 100,
    previous_total_shares: 90,
    share_delta: 10,
    daily_change_pct: 1.1,
    baseline_change_pct: 2.2,
    cumulative_baseline_change_pct: 3.3,
    close_change_pct: null,
    close_change_trade_date: null,
    multiple: 2,
    direction: 'increase',
    is_tenfold: false,
    report_period: '2025-12-31',
    baseline_total_shares: 80,
    confirmed_huijin_shares: 10,
    confirmed_huijin_holding_pct: 12.5,
    baseline_source_kind: 'reported',
    ...overrides
  };
}

function factorItem(overrides: Partial<EtfThreeFactorItem> = {}): EtfThreeFactorItem {
  return {
    symbol: '510050.SH',
    name: '因子ETF',
    index_name: '因子指数',
    index_symbol: '000001.SH',
    close_change_pct: 2.5,
    close_change_trade_date: '2026-07-18',
    intraday_change_pct: 1,
    index_change_pct: 0.5,
    current_volume: 1000,
    average_volume_20d: 800,
    volume_ratio: 1.25,
    share_change_pct: 0.4,
    volume_factor: { score: 80, value: 1.25, status: 'available', source: 'test', data_date: '2026-07-18', updated_at: '2026-07-18T15:00:00+08:00', detail: null },
    direction_factor: { score: 80, value: 1, status: 'available', source: 'test', data_date: '2026-07-18', updated_at: '2026-07-18T15:00:00+08:00', detail: null },
    share_factor: { score: 80, value: 0.4, status: 'available', source: 'test', data_date: '2026-07-18', updated_at: '2026-07-18T15:00:00+08:00', detail: null },
    signal_score: 70,
    mode: 'three_factor',
    level: 'medium',
    updated_at: '2026-07-18T15:00:00+08:00',
    ...overrides
  };
}

describe('ETF three-factor display helpers', () => {
  it('deduplicates symbols while preserving first-seen source order and data', () => {
    const firstActivity = activityItem({ symbol: '510050.SH', name: '首个活动' });
    const duplicateActivity = activityItem({ symbol: '510050.SH', name: '重复活动' });
    const firstFactorOnly = factorItem({ symbol: '510300.SH', name: '首个因子独有' });
    const duplicateFactorOnly = factorItem({ symbol: '510300.SH', name: '重复因子独有' });
    const rows = buildUnifiedEtfActivityRows(
      [firstActivity, duplicateActivity],
      [firstFactorOnly, duplicateFactorOnly]
    );

    expect(rows.map(row => row.symbol)).toEqual(['510050.SH', '510300.SH']);
    expect(rows[0]).toMatchObject({ name: '首个活动', activity: firstActivity });
    expect(rows[1]).toMatchObject({ name: '首个因子独有', factor: firstFactorOnly });
  });

  it('prefers negative scores over null scores and falls back to the first all-null row', () => {
    const negativeRows = buildUnifiedEtfActivityRows([], [
      factorItem({ symbol: '510050.SH', signal_score: -5 }),
      factorItem({ symbol: '510300.SH', signal_score: null })
    ]);
    const nullRows = buildUnifiedEtfActivityRows([], [
      factorItem({ symbol: '510050.SH', signal_score: null }),
      factorItem({ symbol: '510300.SH', signal_score: null })
    ]);

    expect(pickDefaultEtfActivitySymbol(negativeRows)).toBe('510050.SH');
    expect(pickDefaultEtfActivitySymbol(nullRows)).toBe('510050.SH');
  });

  it('merges activity and factor rows and selects the highest scored ETF', () => {
    const activity = activityItem({ symbol: '510050.SH', name: '活动身份', close_change_pct: 1.2 });
    const activityOnly = activityItem({ symbol: '510500.SH', name: '活动独有', close_change_pct: null });
    const factor = factorItem({ symbol: '510050.SH', name: '因子身份', signal_score: 70 });
    const factorOnly = factorItem({ symbol: '510300.SH', name: '因子独有', close_change_pct: 2.4, signal_score: 90 });
    const rows = buildUnifiedEtfActivityRows([activity, activityOnly], [factor, factorOnly]);

    expect(rows.map(row => row.symbol)).toEqual(['510050.SH', '510500.SH', '510300.SH']);
    expect(rows[0]).toMatchObject({
      name: '活动身份',
      indexName: '活动指数',
      closeChangePct: 1.2,
      signalScore: 70,
      activity,
      factor
    });
    expect(rows[1]).toMatchObject({
      symbol: '510500.SH',
      name: '活动独有',
      indexName: '活动指数',
      closeChangePct: null,
      signalScore: null,
      activity: activityOnly,
      factor: null
    });
    expect(rows[2]).toMatchObject({
      symbol: '510300.SH',
      name: '因子独有',
      indexName: '因子指数',
      closeChangePct: 2.4,
      signalScore: 90,
      activity: null,
      factor: factorOnly
    });
    expect(pickDefaultEtfActivitySymbol(rows)).toBe('510300.SH');
  });

  it('labels every signal level and assigns a visual tone', () => {
    expect(signalLevelLabel('high')).toBe('高确信');
    expect(signalLevelLabel('medium')).toBe('中确信');
    expect(signalLevelLabel('low')).toBe('低确信');
    expect(signalLevelLabel('incomplete')).toBe('数据不全');
    expect(signalTone('high')).toBe('danger');
    expect(signalTone('medium')).toBe('warning');
    expect(signalTone('low')).toBe('info');
    expect(signalTone('incomplete')).toBe('neutral');
  });

  it('distinguishes all factor data states', () => {
    expect(factorStatusLabel('available')).toBe('可用');
    expect(factorStatusLabel('pending')).toBe('待盘后');
    expect(factorStatusLabel('missing')).toBe('不可用');
    expect(factorStatusLabel('stale')).toBe('已过期');
  });

  it('formats volume ratios while preserving missing data', () => {
    expect(formatVolumeRatio(3)).toBe('3.00倍');
    expect(formatVolumeRatio(0)).toBe('0.00倍');
    expect(formatVolumeRatio(null)).toBe('--');
  });

  it('uses A-share close-change semantics', () => {
    expect(closeChangeTone(1.2)).toBe('rise');
    expect(closeChangeTone(-1.2)).toBe('fall');
    expect(closeChangeTone(0)).toBe('flat');
    expect(closeChangeTone(null)).toBe('flat');
  });
});
