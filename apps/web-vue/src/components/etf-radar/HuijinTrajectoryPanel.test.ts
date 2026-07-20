// @vitest-environment jsdom

import process from 'node:process';
import { readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';
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

const source = readFileSync(resolvePath(process.cwd(), 'src/components/etf-radar/HuijinTrajectoryPanel.vue'), 'utf8');

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

function historyFixture(points?: EtfRadarHistoryPoint[]): EtfRadarHistoryResponse {
  return {
    generated_at: '2026-07-18T15:05:00+08:00',
    trade_date: '2026-07-18',
    as_of: '2026-07-18T15:00:00+08:00',
    signal_stage: 'post_close',
    model_version: 'huijin-public-rule-v1',
    source_status: [],
    points: points ?? [
      historyPoint('2026-07-16', '510050.SH', -74),
      historyPoint('2026-07-17', '510300.SH', 70),
      historyPoint('2026-07-18', '510050.SH', -75.55)
    ]
  };
}

type MountOverrides = Partial<{
  overview: EtfRadarOverviewResponse;
  history: EtfRadarHistoryResponse | null;
  selectedSymbol: string;
  historyLoading: boolean;
  historyError: string | null;
}>;

function mountPanel(overrides: MountOverrides = {}) {
  return mount(HuijinTrajectoryPanel, {
    props: {
      overview: overviewFixture(),
      history: historyFixture(),
      selectedSymbol: '510050.SH',
      historyLoading: false,
      historyError: null,
      ...overrides
    },
    global: { stubs: { EChart: ChartStub } }
  });
}

describe('HuijinTrajectoryPanel', () => {
  it('renders the approved holdings trajectory and emits ranking selection', async () => {
    const wrapper = mountPanel();

    const rankingRows = wrapper.findAll('[data-testid="huijin-ranking-row"]');
    expect(rankingRows).toHaveLength(7);
    expect(wrapper.get('[data-testid="huijin-baseline-date"]').text()).toContain('2025-12-31');
    expect(wrapper.get('[data-testid="huijin-selected-symbol"]').text()).toContain('510050.SH');
    expect(wrapper.text()).toContain('累计份额变化不能直接证明汇金增减持');
    expect(wrapper.text()).toContain('汇金确认持有份额');
    expect(wrapper.text()).toContain('报告期 ETF 总份额');
    expect(wrapper.text()).toContain('最新 ETF 总份额');
    expect(wrapper.text()).toContain('累计偏离');
    expect(rankingRows[0]!.text()).toContain('▼ -75.55%');
    expect(rankingRows[0]!.text()).toContain('收缩');
    expect(rankingRows[1]!.text()).toContain('▲ +72.00%');
    expect(rankingRows[1]!.text()).toContain('扩张');
    expect(rankingRows[0]!.attributes('aria-pressed')).toBe('true');
    expect(rankingRows[1]!.attributes('aria-pressed')).toBe('false');
    expect(rankingRows[0]!.element.parentElement?.tagName).toBe('LI');

    const tracks = wrapper.findAll('[data-testid="huijin-ranking-track"]');
    const bars = wrapper.findAll('[data-testid="huijin-ranking-bar"]');
    expect(tracks).toHaveLength(7);
    expect(bars).toHaveLength(7);
    expect(wrapper.findAll('[data-testid="huijin-ranking-zero"]')).toHaveLength(7);
    expect(tracks[0]!.attributes('aria-hidden')).toBe('true');
    expect(tracks[0]!.attributes('role')).toBeUndefined();
    expect(tracks[0]!.attributes('aria-label')).toBeUndefined();
    expect(rankingRows[0]!.findAll('[aria-label]')).toHaveLength(0);
    expect(bars[0]!.classes()).toContain('huijin-ranking__bar--decrease');
    expect(bars[0]!.attributes('style')).toContain('right: 50%');
    expect(bars[0]!.attributes('style')).toContain('width: 50%');
    expect(bars[1]!.classes()).toContain('huijin-ranking__bar--increase');
    expect(bars[1]!.attributes('style')).toContain('left: 50%');

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

    const detailRows = wrapper.findAll('[data-testid="huijin-detail-row"]');
    expect(detailRows).toHaveLength(7);
    expect(detailRows[0]!.attributes('aria-pressed')).toBe('true');
    expect(detailRows[1]!.attributes('aria-pressed')).toBe('false');
    expect(wrapper.find('[role="list"]').exists()).toBe(false);
    expect(wrapper.find('[role="table"]').exists()).toBe(false);
  });

  it('uses an async chart component and keeps the responsive overflow contract', () => {
    expect(source).toContain("defineAsyncComponent(() => import('@/components/charts/EChart.vue'))");
    expect(source).not.toContain("import EChart from '@/components/charts/EChart.vue'");
    expect(source).toContain('@media (max-width: 900px)');
    expect(source).toContain('grid-template-columns: minmax(0, 1fr);');
    expect(source).toContain('max-width: 100%;');
    expect(source).toContain('min-width: 0;');
    expect(source).toContain('overflow-x: hidden;');
    expect(source).toMatch(/\.huijin-trajectory__table\s*\{[^}]*overflow-x: auto;/s);
    expect(source).toMatch(/\.huijin-trajectory__table-head,[^{]*\{[^}]*min-width: 760px;/s);
    expect(source).not.toMatch(/\.huijin-trajectory__table-head\s*\{\s*display: none;/s);
    expect(source).toMatch(/\.huijin-ranking__zero\s*\{[^}]*z-index: 1;/s);
  });

  it('renders daily change, validation status, and data date in the detail table', () => {
    const overview = overviewFixture();
    overview.core_items[1]!.paired_symbol = '159919.SZ';
    overview.validation_groups = [
      {
        index_name: '沪深300',
        core_symbol: '510300.SH',
        validator_symbol: '159919.SZ',
        state: 'confirmed_increase',
        conservative_daily_change_pct: 0.8,
        conservative_baseline_change_pct: 72,
        conservative_multiple: 1
      }
    ];
    const wrapper = mountPanel({ overview });

    expect(wrapper.findAll('.huijin-trajectory__table-head > span').map(cell => cell.text())).toEqual([
      'ETF',
      '确认持仓比例',
      '累计偏离',
      '最近日变化',
      '验证状态',
      '数据日期'
    ]);
    const detailRows = wrapper.findAll('[data-testid="huijin-detail-row"]');
    expect(detailRows[0]!.findAll(':scope > span').map(cell => cell.text())).toEqual([
      '华夏上证50ETF510050.SH',
      '86.05%',
      '▼ -75.55% · 收缩',
      '▲ +1.07%',
      '不适用',
      '2026-07-18'
    ]);
    expect(detailRows[1]!.findAll(':scope > span')[4]!.text()).toBe('配对一致增加');
  });

  it('labels detail selection buttons with their field names and values', () => {
    const wrapper = mountPanel();
    const detailLabel = wrapper.get('[data-testid="huijin-detail-row"]').attributes('aria-label');

    expect(detailLabel).toContain('华夏上证50ETF 510050.SH');
    expect(detailLabel).toContain('确认持仓比例 86.05%');
    expect(detailLabel).toContain('累计偏离 ▼ -75.55% · 收缩');
    expect(detailLabel).toContain('最近日变化 ▲ +1.07%');
    expect(detailLabel).toContain('验证状态 不适用');
    expect(detailLabel).toContain('数据日期 2026-07-18');
  });

  it('shows an empty state instead of a baseline-only chart for empty history points', () => {
    const wrapper = mountPanel({ history: historyFixture([]) });

    expect(wrapper.findComponent(ChartStub).exists()).toBe(false);
    expect(wrapper.get('[data-testid="huijin-trajectory-empty"]').text()).toContain('暂无可用历史轨迹');
    expect(wrapper.get('[data-testid="huijin-trajectory-empty"]').attributes('aria-live')).toBe('polite');
  });

  it('shows an empty state when the selected symbol has only null history', () => {
    const wrapper = mountPanel({
      history: historyFixture([
        historyPoint('2026-07-16', '510050.SH', null),
        historyPoint('2026-07-17', '510300.SH', 70),
        historyPoint('2026-07-18', '510050.SH', null)
      ])
    });

    expect(wrapper.findComponent(ChartStub).exists()).toBe(false);
    expect(wrapper.get('[data-testid="huijin-trajectory-empty"]').text()).toContain('暂无可用历史轨迹');
  });

  it('shows loading without history and keeps a stale chart visible while loading', async () => {
    const wrapper = mountPanel({ history: null, historyLoading: true });

    expect(wrapper.findComponent(ChartStub).exists()).toBe(false);
    expect(wrapper.get('[data-testid="huijin-trajectory-empty"]').text()).toContain('历史加载中');
    expect(wrapper.get('[data-testid="huijin-trajectory-empty"]').attributes('aria-live')).toBe('polite');

    await wrapper.setProps({ history: historyFixture(), historyLoading: true });

    expect(wrapper.getComponent(ChartStub).props('loading')).toBe(true);
    expect(wrapper.find('[data-testid="huijin-trajectory-empty"]').exists()).toBe(false);
  });

  it('announces an error while retaining a stale chart', () => {
    const wrapper = mountPanel({ historyError: '历史请求失败，显示已有数据' });

    expect(wrapper.findComponent(ChartStub).exists()).toBe(true);
    expect(wrapper.get('[data-testid="huijin-history-status"]').text()).toContain('历史请求失败，显示已有数据');
    expect(wrapper.get('[data-testid="huijin-history-status"]').attributes('aria-live')).toBe('polite');
    expect(wrapper.findAll('[aria-live="polite"]')).toHaveLength(1);
  });

  it('announces an error when no chart is available', () => {
    const wrapper = mountPanel({ history: null, historyError: '历史请求失败' });

    expect(wrapper.findComponent(ChartStub).exists()).toBe(false);
    expect(wrapper.find('[data-testid="huijin-history-status"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="huijin-trajectory-empty"]').text()).toBe('历史请求失败');
    expect(wrapper.get('[data-testid="huijin-trajectory-empty"]').attributes('aria-live')).toBe('polite');
    expect(wrapper.findAll('[aria-live="polite"]')).toHaveLength(1);
  });
});
