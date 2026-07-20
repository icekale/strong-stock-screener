// @vitest-environment jsdom

import process from 'node:process';
import { readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';
import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarMethodologyResponse,
  EtfRadarOverviewResponse,
  HuijinEtfActivityItem
} from '@/service/types';
import EtfRadarView from './EtfRadarView.vue';

const api = vi.hoisted(() => ({
  getEtfRadarOverview: vi.fn(),
  getEtfRadarHistory: vi.fn(),
  getEtfRadarHolders: vi.fn(),
  getEtfRadarMethodology: vi.fn()
}));

vi.mock('@/service/product-api', () => api);

const TabsStub = defineComponent({
  name: 'ATabs',
  props: { activeKey: { type: String, default: 'overview' } },
  emits: ['update:activeKey', 'change'],
  setup(props, { emit }) {
    const tabs = [
      ['overview', '今日活动'],
      ['history', '累计轨迹'],
      ['holders', '确认持仓'],
      ['methodology', '方法与数据']
    ] as const;
    function select(key: string) {
      emit('update:activeKey', key);
      emit('change', key);
    }
    return { props, tabs, select };
  },
  template: `
    <div data-testid="etf-tabs">
      <button
        v-for="tab in tabs"
        :key="tab[0]"
        class="etf-tab-trigger"
        :data-active="props.activeKey === tab[0]"
        @click="select(tab[0])"
      >{{ tab[1] }}</button>
      <slot />
    </div>
  `
});

const TableStub = defineComponent({
  name: 'ATable',
  inheritAttrs: false,
  props: ['columns', 'dataSource', 'pagination', 'rowKey', 'scroll'],
  template: `
    <table v-bind="$attrs">
      <thead><tr><th v-for="column in columns" :key="column.key">{{ column.title }}</th></tr></thead>
      <tbody>
        <tr v-for="(row, index) in dataSource" :key="index">
          <td v-for="column in columns" :key="column.key">
            <slot name="bodyCell" :column="column" :record="row">{{ row[column.dataIndex] }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  `
});

const ChartStub = defineComponent({
  name: 'EChart',
  props: ['option', 'height', 'loading'],
  template: '<div data-testid="etf-history-chart" />'
});

const SelectStub = defineComponent({
  name: 'ASelect',
  props: ['value', 'options'],
  emits: ['update:value'],
  template: `
    <select data-testid="history-select" :value="value" @change="$emit('update:value', $event.target.value)">
      <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
  `
});

const AlertStub = defineComponent({
  name: 'AAlert',
  props: ['title', 'message'],
  template: '<div data-testid="etf-panel-error" role="alert">{{ title || message }}<slot /></div>'
});

const ButtonStub = defineComponent({
  name: 'AButton',
  props: ['loading'],
  emits: ['click'],
  template: '<button data-testid="etf-refresh" @click="$emit(\'click\')"><slot /></button>'
});

const source = readFileSync(resolvePath(process.cwd(), 'src/views/EtfRadarView.vue'), 'utf8');
const BASELINE_FINGERPRINT = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

function metadata() {
  return {
    generated_at: '2026-07-18T15:05:00+08:00',
    trade_date: '2026-07-18',
    as_of: '2026-07-18T15:00:00+08:00',
    signal_stage: 'post_close' as const,
    model_version: 'huijin-public-rule-v1',
    source_status: [
      { source: '交易所ETF份额', status: 'success' as const, detail: '2026-07-18 快照完整' },
      { source: '基金定期报告', status: 'success' as const, detail: '报告期 2025-12-31' }
    ]
  };
}

function activityItem(overrides: Partial<HuijinEtfActivityItem> = {}): HuijinEtfActivityItem {
  return {
    symbol: '510050.SH',
    name: '华夏上证50ETF',
    index_name: '上证50',
    role: 'core',
    paired_symbol: null,
    trade_date: '2026-07-18',
    total_shares: 12_200_000_000,
    previous_total_shares: 12_000_000_000,
    share_delta: 200_000_000,
    daily_change_pct: 1.67,
    baseline_change_pct: 12,
    cumulative_baseline_change_pct: 14.5,
    multiple: 12,
    direction: 'increase',
    is_tenfold: true,
    report_period: '2025-12-31',
    baseline_total_shares: null,
    confirmed_huijin_shares: null,
    confirmed_huijin_holding_pct: 12.34,
    baseline_source_kind: 'reported',
    ...overrides
  };
}

function overviewFixture(): EtfRadarOverviewResponse {
  const coreItems = [
    activityItem(),
    activityItem({ symbol: '510300.SH', name: '华泰柏瑞沪深300ETF', index_name: '沪深300', paired_symbol: '159919.SZ', total_shares: 9_880_000_000, previous_total_shares: 10_000_000_000, share_delta: -120_000_000, daily_change_pct: -1.2, baseline_change_pct: -11, cumulative_baseline_change_pct: -8.4, multiple: 11, direction: 'decrease' }),
    activityItem({ symbol: '510500.SH', name: '南方中证500ETF', index_name: '中证500', paired_symbol: '159922.SZ', total_shares: 8_030_000_000, previous_total_shares: 8_000_000_000, share_delta: 30_000_000, daily_change_pct: 0.38, baseline_change_pct: 3, cumulative_baseline_change_pct: 3, multiple: 3, direction: 'increase', is_tenfold: false }),
    activityItem({ symbol: '512100.SH', name: '南方中证1000ETF', index_name: '中证1000', paired_symbol: '159845.SZ', total_shares: 6_050_000_000, previous_total_shares: 6_000_000_000, share_delta: 50_000_000, daily_change_pct: 0.83, baseline_change_pct: 10.5, cumulative_baseline_change_pct: 10.5, multiple: 10.5, direction: 'increase' }),
    activityItem({ symbol: '159915.SZ', name: '易方达创业板ETF', index_name: '创业板指', paired_symbol: null, total_shares: 4_100_000_000, previous_total_shares: null, share_delta: null, daily_change_pct: null, baseline_change_pct: 6, cumulative_baseline_change_pct: 6, multiple: null, direction: 'unknown', is_tenfold: false }),
    activityItem({ symbol: '510230.SH', name: '国泰金融ETF', index_name: '金融', paired_symbol: null, total_shares: 3_020_000_000, previous_total_shares: 3_000_000_000, share_delta: 20_000_000, daily_change_pct: 0.67, baseline_change_pct: null, cumulative_baseline_change_pct: null, multiple: null, direction: 'increase', is_tenfold: false, report_period: null, confirmed_huijin_holding_pct: null, baseline_source_kind: null }),
    activityItem({ symbol: '588080.SH', name: '易方达科创50ETF', index_name: '科创50', paired_symbol: null, total_shares: null, previous_total_shares: 5_000_000_000, share_delta: null, daily_change_pct: null, baseline_change_pct: 2, cumulative_baseline_change_pct: 2, multiple: null, direction: 'unknown', is_tenfold: false })
  ];
  const validationItems = [
    activityItem({ symbol: '159919.SZ', name: '嘉实沪深300ETF', index_name: '沪深300', role: 'validator', paired_symbol: '510300.SH', baseline_change_pct: -9.25, daily_change_pct: -0.9, multiple: 9.25, direction: 'decrease' }),
    activityItem({ symbol: '159922.SZ', name: '嘉实中证500ETF', index_name: '中证500', role: 'validator', paired_symbol: '510500.SH', baseline_change_pct: -2, daily_change_pct: -0.2, multiple: 2, direction: 'decrease', is_tenfold: false }),
    activityItem({ symbol: '159845.SZ', name: '华夏中证1000ETF', index_name: '中证1000', role: 'validator', paired_symbol: '512100.SH', baseline_change_pct: 12, daily_change_pct: 1.4, multiple: 12 })
  ];
  return {
    ...metadata(),
    evidence_strength: 99,
    evidence_level: '较强',
    valid_etf_count: 99,
    expected_etf_count: 99,
    estimated_subscription_cny: 99,
    evidence: ['OLD_GENERIC_SENTINEL'],
    items: [],
    pool_version: 'huijin-public-v1',
    baseline_version: '2025-12-31:huijin-public-v1',
    baseline_fingerprint: BASELINE_FINGERPRINT,
    activity: {
      core_count: 7,
      available_core_count: 6,
      tenfold_increase_count: 2,
      tenfold_decrease_count: 1,
      confirmed_increase_group_count: 1,
      confirmed_decrease_group_count: 1,
      divergent_group_count: 1,
      incomplete_group_count: 0,
      strongest_symbol: '510050.SH',
      strongest_baseline_change_pct: 12
    },
    core_items: coreItems,
    validation_items: validationItems,
    validation_groups: [
      { index_name: '沪深300', core_symbol: '510300.SH', validator_symbol: '159919.SZ', state: 'confirmed_decrease', conservative_daily_change_pct: -0.9, conservative_baseline_change_pct: -9.25, conservative_multiple: 9.25 },
      { index_name: '中证500', core_symbol: '510500.SH', validator_symbol: '159922.SZ', state: 'divergent', conservative_daily_change_pct: null, conservative_baseline_change_pct: null, conservative_multiple: null },
      { index_name: '中证1000', core_symbol: '512100.SH', validator_symbol: '159845.SZ', state: 'confirmed_increase', conservative_daily_change_pct: 0.83, conservative_baseline_change_pct: 10.5, conservative_multiple: 10.5 }
    ]
  };
}

function historyFixture(): EtfRadarHistoryResponse {
  return {
    ...metadata(),
    points: [
      { trade_date: '2026-07-16', symbol: '510050.SH', name: '华夏上证50ETF', total_shares: 12_000_000_000, share_change: 20_000_000, estimated_subscription_cny: 99, robust_score: 99, daily_change_pct: 0.17, baseline_change_pct: 8, cumulative_baseline_change_pct: 8, multiple: 8 },
      { trade_date: '2026-07-18', symbol: '510050.SH', name: '华夏上证50ETF', total_shares: 12_200_000_000, share_change: 200_000_000, estimated_subscription_cny: 99, robust_score: 99, daily_change_pct: 1.67, baseline_change_pct: 12, cumulative_baseline_change_pct: 14.5, multiple: 12 },
      { trade_date: '2026-07-17', symbol: '510050.SH', name: '华夏上证50ETF', total_shares: null, share_change: null, estimated_subscription_cny: 99, robust_score: 99, daily_change_pct: null, baseline_change_pct: null, cumulative_baseline_change_pct: null, multiple: null },
      { trade_date: '2026-07-16', symbol: '510300.SH', name: '华泰柏瑞沪深300ETF', total_shares: 10_000_000_000, share_change: null, estimated_subscription_cny: 99, robust_score: 99, daily_change_pct: null, baseline_change_pct: null, cumulative_baseline_change_pct: null, multiple: null },
      { trade_date: '2026-07-18', symbol: '510300.SH', name: '华泰柏瑞沪深300ETF', total_shares: 9_880_000_000, share_change: -120_000_000, estimated_subscription_cny: 99, robust_score: 99, daily_change_pct: -1.2, baseline_change_pct: null, cumulative_baseline_change_pct: null, multiple: null }
    ]
  };
}

function holdersFixture(): EtfRadarHoldersResponse {
  return {
    ...metadata(),
    baselines: [
      { baseline_id: 'b-510050', pool_version: 'huijin-public-v1', symbol: '510050.SH', name: '华夏上证50ETF', index_name: '上证50', role: 'core', paired_symbol: null, report_period: '2025-12-31', baseline_total_shares: 10_000_000_000, confirmed_huijin_shares: 1_234_000_000, confirmed_huijin_holding_pct: 12.34, source_kind: 'reported', source: '基金2025年年度报告' }
    ],
    positions: [
      { symbol: '510050.SH', name: '华夏上证50ETF', report_period: '2025-12-31', entity_name: '中央汇金投资有限责任公司', shares: 1_000_000_000, holding_pct: 10, change_shares: 80_000_000, source: '基金2025年年度报告' },
      { symbol: '510050.SH', name: '华夏上证50ETF', report_period: '2025-12-31', entity_name: '中央汇金资产管理有限责任公司', shares: 234_000_000, holding_pct: 2.34, change_shares: null, source: '基金2025年年度报告' }
    ]
  };
}

function methodologyFixture(): EtfRadarMethodologyResponse {
  return {
    ...metadata(),
    pool_version: 'huijin-public-v1',
    core_pool: ['510050.SH', '510300.SH', '510500.SH', '512100.SH', '159915.SZ', '510230.SH', '588080.SH', '159919.SZ', '159922.SZ', '159845.SZ'],
    thresholds: { tenfold_baseline_pct: 0.1 },
    factors: [
      { key: 'daily', name: '日份额变化率', description: '(今日总份额 - 前日总份额) / 前日总份额', availability: '连续交易日份额齐备时' },
      { key: 'baseline', name: '报告基线变化率', description: '(今日总份额 - 报告期总份额) / 报告期总份额', availability: '存在报告基线时' },
      { key: 'cumulative', name: '累计基线变化率', description: '各归档交易日相对同一报告基线的变化率', availability: '不前向填充' },
      { key: 'multiple', name: '变化倍数', description: '报告基线变化率绝对值 / 十倍阈值', availability: '存在报告基线时' },
      { key: 'validation_沪深300', name: '沪深300成对验证', description: '510300.SH+159919.SZ 同向确认，分歧不相加', availability: '两只 ETF 数据完整时' },
      { key: 'validation_中证500', name: '中证500成对验证', description: '510500.SH+159922.SZ 同向确认，分歧不相加', availability: '两只 ETF 数据完整时' },
      { key: 'validation_中证1000', name: '中证1000成对验证', description: '512100.SH+159845.SZ 同向确认，分歧不相加', availability: '两只 ETF 数据完整时' }
    ],
    limitations: ['份额活动只能作为申赎代理，无法识别实际买方', '付费数据 7月6日规则尚未实现']
  };
}

function setDefaultApiResponses() {
  api.getEtfRadarOverview.mockResolvedValue(overviewFixture());
  api.getEtfRadarHistory.mockResolvedValue(historyFixture());
  api.getEtfRadarHolders.mockResolvedValue(holdersFixture());
  api.getEtfRadarMethodology.mockResolvedValue(methodologyFixture());
}

async function mountView() {
  const wrapper = mount(EtfRadarView, {
    global: {
      stubs: {
        ATabs: TabsStub,
        ATabPane: true,
        ATable: TableStub,
        AAlert: AlertStub,
        AButton: ButtonStub,
        ASelect: SelectStub,
        ASkeleton: { template: '<div data-testid="etf-skeleton" />' },
        EChart: ChartStub
      }
    }
  });
  await flushPromises();
  return wrapper;
}

async function openTab(wrapper: Awaited<ReturnType<typeof mountView>>, index: number) {
  await wrapper.findAll('.etf-tab-trigger')[index]!.trigger('click');
  await flushPromises();
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('EtfRadarView', () => {
  it('renders the Huijin overview with seven core rows and three conservative validation rows', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();

    expect(wrapper.findAll('.etf-tab-trigger').map(tab => tab.text())).toEqual(['今日活动', '累计轨迹', '确认持仓', '方法与数据']);
    expect(wrapper.text()).toContain('汇金 ETF 追踪');
    expect(wrapper.text()).toContain('十倍量增加');
    expect(wrapper.text()).toContain('十倍量减少');
    expect(wrapper.text()).toContain('交叉验证');
    expect(wrapper.text()).toContain('方向分歧');
    expect(wrapper.findAll('[data-testid="core-etf-row"]')).toHaveLength(7);
    expect(wrapper.findAll('[data-testid="validation-row"]')).toHaveLength(3);
    expect(wrapper.text()).toContain('▲ +2.00亿份');
    expect(wrapper.text()).toContain('▼ -1.20亿份');
    expect(wrapper.text()).toContain('今日缺失');
    expect(wrapper.text()).toContain('缺少前日');
    expect(wrapper.text()).toContain('缺少基线');
    expect(wrapper.text()).toContain('可计算');
    expect(wrapper.text()).toContain('▲ +10.50%');
    expect(wrapper.text()).toContain('▼ -9.25%');
    expect(wrapper.text()).toContain('10.5倍');
    const fingerprint = wrapper.get('[data-testid="baseline-fingerprint"]');
    expect(fingerprint.text()).toContain('基线指纹 0123456789...');
    expect(fingerprint.attributes('title')).toBe(BASELINE_FINGERPRINT);
    expect(wrapper.text()).not.toContain(BASELINE_FINGERPRINT);
    const coreRegion = wrapper.get('[aria-label="核心 ETF 今日活动表"]');
    expect(coreRegion.attributes()).toMatchObject({ role: 'region', tabindex: '0' });
    const validationRegion = wrapper.get('[aria-label="ETF 配对交叉验证"]');
    expect(validationRegion.attributes()).toMatchObject({ role: 'region', tabindex: '0' });
    expect(wrapper.get('[data-testid="core-etf-row"] strong').attributes('title')).toBe('华夏上证50ETF');
    expect(wrapper.text()).not.toContain('OLD_GENERIC_SENTINEL');
    expect(wrapper.text()).not.toMatch(/证据强度|稳健分|同时间成交|相对指数|估算申购/);
    wrapper.unmount();
  });

  it('shows backend stale source status as partial and preserves its detail', async () => {
    setDefaultApiResponses();
    api.getEtfRadarOverview.mockResolvedValueOnce({
      ...overviewFixture(),
      source_status: [
        { source: '交易所ETF份额', status: 'stale' as const, detail: '上游不可用，沿用 2026-07-17 归档快照' }
      ]
    });

    const wrapper = await mountView();

    expect(wrapper.get('.wb-section-header .wb-status-tag').text()).toBe('部分');
    expect(wrapper.text()).toContain('上游不可用，沿用 2026-07-17 归档快照');
    expect(wrapper.findAll('.wb-status-tag').some(tag => tag.text() === '部分')).toBe(true);
    wrapper.unmount();
  });

  it('keeps divergent and incomplete validation states visually neutral and distinguishable', async () => {
    setDefaultApiResponses();
    const fixture = overviewFixture();
    fixture.activity = { ...fixture.activity, divergent_group_count: 1, incomplete_group_count: 1 };
    fixture.validation_groups = [
      fixture.validation_groups[1]!,
      {
        index_name: '科创50',
        core_symbol: '588080.SH',
        validator_symbol: '159845.SZ',
        state: 'incomplete',
        conservative_daily_change_pct: null,
        conservative_baseline_change_pct: null,
        conservative_multiple: null
      }
    ];
    api.getEtfRadarOverview.mockResolvedValueOnce(fixture);

    const wrapper = await mountView();
    const divergenceMetric = wrapper.findAll('.etf-metric').find(metric => metric.text().includes('方向分歧'))!;
    expect(divergenceMetric.get('strong').classes()).not.toContain('etf-value--warning');

    for (const label of ['方向分歧', '数据不全']) {
      const row = wrapper.findAll('[data-testid="validation-row"]').find(item => item.text().includes(label))!;
      const state = row.get('.etf-validation-state');
      const conservative = row.get('[data-testid="validation-conservative"]');
      for (const tone of ['etf-value--positive', 'etf-value--negative', 'etf-value--warning']) {
        expect(state.classes()).not.toContain(tone);
        expect(conservative.classes()).not.toContain(tone);
      }
    }
    wrapper.unmount();
  });

  it('requests only overview initially and each lazy endpoint once on first activation', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();

    expect(api.getEtfRadarOverview).toHaveBeenCalledTimes(1);
    expect(api.getEtfRadarHistory).not.toHaveBeenCalled();
    expect(api.getEtfRadarHolders).not.toHaveBeenCalled();
    expect(api.getEtfRadarMethodology).not.toHaveBeenCalled();

    await openTab(wrapper, 1);
    await openTab(wrapper, 2);
    await openTab(wrapper, 3);
    await openTab(wrapper, 1);

    expect(api.getEtfRadarHistory).toHaveBeenCalledTimes(1);
    expect(api.getEtfRadarHolders).toHaveBeenCalledTimes(1);
    expect(api.getEtfRadarMethodology).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it('charts one selected ETF against global real dates and shows only its real rows newest first', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();
    await openTab(wrapper, 1);

    const chart = wrapper.findComponent(ChartStub);
    const option = chart.props('option') as any;
    expect(chart.props('height')).toBe(304);
    expect(option.animation).toBe(false);
    expect(option.aria.enabled).toBe(true);
    expect(option.aria.description).toContain('华夏上证50ETF');
    expect(option.xAxis.data).toEqual(['2026-07-16', '2026-07-17', '2026-07-18']);
    expect(option.series[0].connectNulls).toBe(false);
    expect(option.series[0].data).toEqual([8, null, 14.5]);
    const rows = wrapper.get('[data-testid="history-table"]').findAll('tbody tr');
    expect(rows).toHaveLength(3);
    expect(rows[0]!.text()).toContain('2026-07-18');
    expect(rows[2]!.text()).toContain('2026-07-16');
    const historyTable = wrapper.findAllComponents(TableStub).find(table => table.attributes('data-testid') === 'history-table');
    expect((historyTable?.props('dataSource') as Array<{ symbol: string }>).map(row => row.symbol)).toEqual([
      '510050.SH',
      '510050.SH',
      '510050.SH'
    ]);
    wrapper.unmount();
  });

  it('shows an explicit cumulative empty state when the selected ETF has no baseline values', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();
    await openTab(wrapper, 1);

    await wrapper.get('[data-testid="history-select"]').setValue('510300.SH');
    await flushPromises();

    expect(wrapper.find('[data-testid="etf-history-chart"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="history-chart-empty"]').text()).toContain('暂无报告基线累计值');
    const historyTable = wrapper.findAllComponents(TableStub).find(table => table.attributes('data-testid') === 'history-table');
    expect((historyTable?.props('dataSource') as Array<{ symbol: string; trade_date: string }>)).toMatchObject([
      { symbol: '510300.SH', trade_date: '2026-07-18' },
      { symbol: '510300.SH', trade_date: '2026-07-16' }
    ]);
    wrapper.unmount();
  });

  it('renders independent confirmed baseline and exact-entity holder sections', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();
    await openTab(wrapper, 2);

    expect(wrapper.text()).toContain('报告期确认的法律实体持仓，不是实时资金流');
    expect(wrapper.text()).toContain('确认基线');
    expect(wrapper.text()).toContain('精确实体持仓');
    expect(wrapper.text()).toContain('报告期 2025-12-31');
    expect(wrapper.get('[data-testid="holder-baseline-table"]').text()).toContain('12.34%');
    expect(wrapper.get('[data-testid="holder-position-table"]').text()).toContain('中央汇金资产管理有限责任公司');
    wrapper.unmount();
  });

  it('renders backend methodology factors, pool, validation rules, and limitations without extra claims', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();
    await openTab(wrapper, 3);

    expect(wrapper.findAll('[data-testid="method-factor"]')).toHaveLength(4);
    expect(wrapper.text()).toContain('十倍阈值');
    expect(wrapper.text()).toContain('0.10%');
    expect(wrapper.text()).toContain('huijin-public-v1');
    expect(wrapper.text()).toContain('510050.SH');
    expect(wrapper.findAll('[data-testid="validation-rule"]')).toHaveLength(3);
    expect(wrapper.text()).toContain('510300.SH+159919.SZ 同向确认，分歧不相加');
    expect(wrapper.text()).toContain('无法识别实际买方');
    expect(wrapper.text()).toContain('付费数据 7月6日规则尚未实现');
    expect(wrapper.text()).toContain('交易所ETF份额');
    wrapper.unmount();
  });

  it('retains loaded content and marks it stale when forced refresh fails', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();
    api.getEtfRadarOverview.mockRejectedValueOnce(new Error('刷新失败：上游不可用'));

    await wrapper.get('[data-testid="etf-refresh"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('华夏上证50ETF');
    expect(wrapper.get('[data-testid="etf-panel-error"]').text()).toContain('刷新失败：上游不可用');
    expect(wrapper.get('[data-testid="etf-panel-error"]').text()).toContain('当前显示上次成功数据');
    expect(wrapper.get('.wb-section-header .wb-status-tag').text()).toBe('部分');
    wrapper.unmount();
  });

  it('keeps implementation contracts accessible, token-based, and free of old generic fields', () => {
    expect(source).toContain('icon-ic-round-refresh');
    expect(source).toContain("defineAsyncComponent(() => import('@/components/charts/EChart.vue'))");
    expect(source).not.toContain("import EChart from '@/components/charts/EChart.vue'");
    expect(source).toMatch(/overflow-x\s*:\s*auto/);
    expect(source).toMatch(/min-width\s*:\s*0/);
    expect(source).toMatch(/\.etf-panel\s+:deep\(\.wb-section-header\)\s*\{[^}]*padding:\s*12px 16px/s);
    expect(source).toMatch(/\.etf-panel\s*>\s*:deep\(\.ant-alert\)\s*\{[^}]*margin:\s*0 16px 12px/s);
    expect(source).toMatch(/aria:\s*\{\s*enabled:\s*true/);
    expect(source).toContain('connectNulls: false');
    expect(source).not.toMatch(/evidence_strength|robust_score|same_time_turnover_ratio|relative_index_return_pct|estimated_subscription_cny/);
    expect(source).not.toMatch(/#[0-9a-f]{3,8}\b/i);
  });
});
