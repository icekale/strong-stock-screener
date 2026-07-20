// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import type { EChartsOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type {
  EtfRadarHistoryPoint,
  EtfRadarHistoryResponse,
  EtfRadarOverviewResponse,
  HuijinEtfActivityItem
} from '@/service/types';
import HuijinTrajectoryPanel from './HuijinTrajectoryPanel.vue';

const ChartStub = defineComponent({
  name: 'EChart',
  props: ['option', 'height', 'loading'],
  template: '<div data-testid="huijin-trajectory-chart" />'
});

function activityItem(overrides: Partial<HuijinEtfActivityItem> = {}): HuijinEtfActivityItem {
  return {
    symbol: '510050.SH',
    name: '华夏上证50ETF',
    index_name: '上证50',
    role: 'core',
    paired_symbol: null,
    trade_date: '2026-07-18',
    total_shares: 8_237_466_800,
    previous_total_shares: 8_150_166_800,
    share_delta: 87_300_000,
    daily_change_pct: 1.07,
    baseline_change_pct: -85.46,
    cumulative_baseline_change_pct: -75.55,
    multiple: 85.46,
    direction: 'increase',
    is_tenfold: true,
    report_period: '2025-12-31',
    baseline_total_shares: 56_663_567_693,
    confirmed_huijin_shares: 48_759_000_000,
    confirmed_huijin_holding_pct: 86.05,
    baseline_source_kind: 'derived',
    ...overrides
  };
}

function overviewFixture(): EtfRadarOverviewResponse {
  const coreItems = [
    activityItem(),
    activityItem({
      symbol: '510300.SH',
      name: '华泰柏瑞沪深300ETF',
      index_name: '沪深300',
      cumulative_baseline_change_pct: 72,
      daily_change_pct: 0.8,
      direction: 'increase'
    }),
    activityItem({
      symbol: '510500.SH',
      name: '南方中证500ETF',
      index_name: '中证500',
      cumulative_baseline_change_pct: -64
    }),
    activityItem({
      symbol: '512100.SH',
      name: '南方中证1000ETF',
      index_name: '中证1000',
      cumulative_baseline_change_pct: 56
    }),
    activityItem({
      symbol: '159915.SZ',
      name: '易方达创业板ETF',
      index_name: '创业板指',
      cumulative_baseline_change_pct: -48,
      previous_total_shares: null,
      daily_change_pct: null,
      direction: 'unknown'
    }),
    activityItem({ symbol: '510230.SH', name: '国泰金融ETF', index_name: '金融', cumulative_baseline_change_pct: 32 }),
    activityItem({
      symbol: '588080.SH',
      name: '易方达科创50ETF',
      index_name: '科创50',
      cumulative_baseline_change_pct: -24
    })
  ];
  return {
    generated_at: '2026-07-18T15:05:00+08:00',
    trade_date: '2026-07-18',
    as_of: '2026-07-18T15:00:00+08:00',
    signal_stage: 'post_close',
    model_version: 'huijin-public-rule-v1',
    source_status: [
      { source: '交易所ETF份额', status: 'success', detail: '2026-07-18 快照完整' },
      { source: '基金定期报告', status: 'success', detail: '报告期 2025-12-31' }
    ],
    evidence_strength: 98,
    evidence_level: '较强',
    valid_etf_count: 7,
    expected_etf_count: 7,
    estimated_subscription_cny: null,
    evidence: [],
    items: [],
    pool_version: 'huijin-public-v1',
    baseline_version: '2025-12-31:huijin-public-v1',
    baseline_fingerprint: 'fixture',
    activity: {
      core_count: 7,
      available_core_count: 7,
      tenfold_increase_count: 2,
      tenfold_decrease_count: 1,
      confirmed_increase_group_count: 1,
      confirmed_decrease_group_count: 1,
      divergent_group_count: 0,
      incomplete_group_count: 0,
      strongest_symbol: '510050.SH',
      strongest_baseline_change_pct: -85.46
    },
    core_items: coreItems,
    validation_items: [],
    validation_groups: []
  };
}

function historyPoint(tradeDate: string, symbol: string, cumulative: number | null): EtfRadarHistoryPoint {
  return {
    trade_date: tradeDate,
    symbol,
    name: symbol === '510050.SH' ? '华夏上证50ETF' : '华泰柏瑞沪深300ETF',
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

function historyFixture(): EtfRadarHistoryResponse {
  return {
    generated_at: '2026-07-18T15:05:00+08:00',
    trade_date: '2026-07-18',
    as_of: '2026-07-18T15:00:00+08:00',
    signal_stage: 'post_close',
    model_version: 'huijin-public-rule-v1',
    source_status: [],
    points: [
      historyPoint('2026-07-16', '510050.SH', -74),
      historyPoint('2026-07-17', '510300.SH', 70),
      historyPoint('2026-07-18', '510050.SH', -75.55)
    ]
  };
}

describe('HuijinTrajectoryPanel', () => {
  it('renders the approved holdings trajectory and emits ranking selection', async () => {
    const wrapper = mount(HuijinTrajectoryPanel, {
      props: {
        overview: overviewFixture(),
        history: historyFixture(),
        selectedSymbol: '510050.SH',
        historyLoading: false,
        historyError: null
      },
      global: { stubs: { EChart: ChartStub } }
    });

    const rankingRows = wrapper.findAll('[data-testid="huijin-ranking-row"]');
    expect(rankingRows).toHaveLength(7);
    expect(wrapper.get('[data-testid="huijin-baseline-date"]').text()).toContain('2025-12-31');
    expect(wrapper.get('[data-testid="huijin-selected-symbol"]').text()).toContain('510050.SH');
    expect(wrapper.text()).toContain('累计份额变化不能直接证明汇金增减持');
    expect(wrapper.text()).toContain('汇金确认持有份额');
    expect(wrapper.text()).toContain('报告期 ETF 总份额');
    expect(wrapper.text()).toContain('最新 ETF 总份额');
    expect(wrapper.text()).toContain('累计偏离');
    expect(wrapper.text()).toContain('日度历史积累中');
    expect(rankingRows[0]!.text()).toContain('▼ -75.55%');
    expect(rankingRows[1]!.text()).toContain('▲ +72.00%');

    await rankingRows[1]!.trigger('click');
    expect(wrapper.emitted('select')?.at(-1)).toEqual(['510300.SH']);

    const chart = wrapper.getComponent(ChartStub);
    const option = chart.props('option') as EChartsOption;
    const series = (option.series as Array<{ connectNulls?: boolean; data?: unknown[] }>)[0]!;
    expect(chart.props('height')).toBe(286);
    expect(chart.props('loading')).toBe(false);
    expect(option.animation).toBe(false);
    expect(series.connectNulls).toBe(false);
    expect(series.data).toEqual([0, -74, null, -75.55]);
  });
});
