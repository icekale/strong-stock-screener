// @vitest-environment jsdom

import process from 'node:process';
import { readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';
import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  EtfHolderPosition,
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarMethodologyResponse,
  EtfRadarOverviewResponse
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
      ['overview', '盘中雷达'],
      ['history', '份额变化'],
      ['holders', '持有人披露'],
      ['methodology', '方法与验证']
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
  props: ['columns', 'dataSource', 'pagination', 'rowKey'],
  template: `
    <div data-testid="table-stub">
      <div v-for="column in columns" :key="column.key || column.dataIndex">{{ column.title }}</div>
      <div v-for="row in dataSource" :key="row.symbol || row.entity_name || row.trade_date">{{ Object.values(row).join(' ') }}</div>
    </div>
  `
});

const ChartStub = defineComponent({
  name: 'EChart',
  props: ['option', 'height', 'loading'],
  template: '<div data-testid="etf-history-chart" />'
});

const AlertStub = defineComponent({
  name: 'AAlert',
  props: ['title', 'message'],
  template: '<div data-testid="etf-panel-error" role="alert">{{ title || message }}</div>'
});

const ButtonStub = defineComponent({
  name: 'AButton',
  props: ['loading'],
  emits: ['click'],
  template: '<button @click="$emit(\'click\')"><slot /></button>'
});

const source = readFileSync(resolvePath(process.cwd(), 'src/views/EtfRadarView.vue'), 'utf8');

function metadata() {
  return {
    generated_at: '2026-07-18T15:05:00+08:00',
    trade_date: '2026-07-18',
    as_of: '2026-07-18T15:00:00+08:00',
    signal_stage: 'intraday' as const,
    model_version: 'etf-radar-v1.2',
    source_status: [
      { source: '上交所ETF份额', status: 'success' as const, detail: '份额快照正常' },
      { source: '交易所行情', status: 'success' as const, detail: '行情快照正常' }
    ]
  };
}

function overviewFixture(): EtfRadarOverviewResponse {
  return {
    ...metadata(),
    evidence_strength: 78.4,
    evidence_level: '较强',
    valid_etf_count: 7,
    expected_etf_count: 7,
    estimated_subscription_cny: 12_460_000_000,
    evidence: ['7/7 只有效ETF份额增加', '宽基ETF同步放量', '估算净申购与指数表现同向'],
    pool_version: 'huijin-public-v1',
    baseline_version: null,
    baseline_fingerprint: null,
    activity: {
      core_count: 7,
      available_core_count: 0,
      tenfold_increase_count: 0,
      tenfold_decrease_count: 0,
      confirmed_increase_group_count: 0,
      confirmed_decrease_group_count: 0,
      divergent_group_count: 0,
      incomplete_group_count: 0,
      strongest_symbol: null,
      strongest_baseline_change_pct: null
    },
    core_items: [],
    validation_items: [],
    validation_groups: [],
    items: Array.from({ length: 7 }, (_, index) => ({
      symbol: `51030${index}.SH`,
      name: index === 0 ? '华夏上证50ETF' : `宽基ETF${index + 1}`,
      index_name: index === 0 ? '上证50' : `指数${index + 1}`,
      total_shares: 5_000_000_000 + index * 100_000_000,
      share_change: index === 3 ? null : (index + 1) * 10_000_000,
      estimated_subscription_cny: index === 3 ? null : (index - 2) * 800_000_000,
      robust_score: 65 + index,
      same_time_turnover_ratio: 1.1 + index / 10,
      relative_index_return_pct: index === 4 ? null : (index - 2) * 0.35,
      late_session_acceleration: 0.2,
      evidence_strength: 70 + index,
      evidence: ['份额变化与成交配合']
    }))
  };
}

function historyFixture(): EtfRadarHistoryResponse {
  return {
    ...metadata(),
    points: [
      { trade_date: '2026-07-16', symbol: '510300.SH', name: '沪深300ETF', total_shares: 8_000_000_000, share_change: 40_000_000, estimated_subscription_cny: 1_200_000_000, robust_score: 71, daily_change_pct: null, baseline_change_pct: null, cumulative_baseline_change_pct: null, multiple: null },
      { trade_date: '2026-07-17', symbol: '510300.SH', name: '沪深300ETF', total_shares: 8_050_000_000, share_change: 50_000_000, estimated_subscription_cny: 1_500_000_000, robust_score: 74, daily_change_pct: null, baseline_change_pct: null, cumulative_baseline_change_pct: null, multiple: null },
      { trade_date: '2026-07-18', symbol: '510300.SH', name: '沪深300ETF', total_shares: 8_020_000_000, share_change: -30_000_000, estimated_subscription_cny: -900_000_000, robust_score: 68, daily_change_pct: null, baseline_change_pct: null, cumulative_baseline_change_pct: null, multiple: null }
    ]
  };
}

function holdersFixture(positions: EtfHolderPosition[] = [
  { symbol: '510300.SH', name: '沪深300ETF', report_period: '2026Q2', entity_name: '中央汇金投资有限责任公司', shares: 2_100_000_000, holding_pct: 8.2, change_shares: 120_000_000, source: '基金定期报告' }
]): EtfRadarHoldersResponse {
  return { ...metadata(), positions, baselines: [] };
}

function methodologyFixture(): EtfRadarMethodologyResponse {
  return {
    ...metadata(),
    pool_version: 'core-etf-2026.07',
    core_pool: ['510300.SH', '510500.SH', '159919.SZ'],
    thresholds: { evidence_strength: 60, robust_score: 65, same_time_turnover_ratio: 1.1 },
    factors: [
      { key: 'shares', name: '份额变化', description: '交易所披露份额变化', availability: '盘后确认' },
      { key: 'turnover', name: '同时间成交', description: '比较同时间窗口成交额', availability: '盘中可用' }
    ],
    limitations: ['估算申购不是申购订单流水', '持有人披露具有报告期滞后']
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
        WorkspacePlaceholder: { template: '<div data-testid="workspace-placeholder" />' },
        ATabs: TabsStub,
        ATable: TableStub,
        AAlert: AlertStub,
        AButton: ButtonStub,
        EChart: ChartStub
      }
    }
  });
  await flushPromises();
  return wrapper;
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('EtfRadarView', () => {
  it('exposes exactly four tabs and only loads the overview on mount', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();

    expect(wrapper.findAll('.etf-tab-trigger').map(tab => tab.text())).toEqual(['盘中雷达', '份额变化', '持有人披露', '方法与验证']);
    expect(api.getEtfRadarOverview).toHaveBeenCalledTimes(1);
    expect(api.getEtfRadarHistory).not.toHaveBeenCalled();
    expect(api.getEtfRadarHolders).not.toHaveBeenCalled();
    expect(api.getEtfRadarMethodology).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('证据强度');
    expect(wrapper.text()).toContain('华夏上证50ETF');
    const subscriptionMetric = wrapper.findAll('.etf-metric').find(metric => metric.text().includes('方向性估算申购'));
    expect(subscriptionMetric?.find('strong').classes()).toContain('etf-value--positive');
    wrapper.unmount();
  });

  it('loads each secondary tab once and reuses its in-memory result when revisited', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();
    const tabs = wrapper.findAll('.etf-tab-trigger');

    await tabs[1]!.trigger('click');
    await flushPromises();
    const historyTable = wrapper.findComponent(TableStub);
    const historyRowKey = historyTable.props('rowKey') as (row: { trade_date: string; symbol: string }) => string;
    expect(historyRowKey({ trade_date: '2026-07-18', symbol: '510300.SH' })).toBe('2026-07-18-510300.SH');
    expect(historyTable.props('pagination')).toEqual({ pageSize: 20, showSizeChanger: false });
    expect((historyTable.props('dataSource') as Array<{ trade_date: string }>)[0]?.trade_date).toBe('2026-07-18');
    await tabs[2]!.trigger('click');
    await flushPromises();
    const holderRowKey = wrapper.findComponent(TableStub).props('rowKey') as (row: EtfHolderPosition) => string;
    expect(holderRowKey(holdersFixture().positions[0]!)).toBe(
      '2026Q2-510300.SH-中央汇金投资有限责任公司'
    );
    await tabs[3]!.trigger('click');
    await flushPromises();
    await tabs[1]!.trigger('click');
    await flushPromises();

    expect(api.getEtfRadarHistory).toHaveBeenCalledTimes(1);
    expect(api.getEtfRadarHolders).toHaveBeenCalledTimes(1);
    expect(api.getEtfRadarMethodology).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it('refreshes only the active tab and uses force cache behavior', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();

    await wrapper.get('[data-testid="etf-refresh"]').trigger('click');
    await flushPromises();
    expect(api.getEtfRadarOverview).toHaveBeenCalledTimes(2);
    expect(api.getEtfRadarHistory).not.toHaveBeenCalled();

    await wrapper.findAll('.etf-tab-trigger')[1]!.trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="etf-refresh"]').trigger('click');
    await flushPromises();

    expect(api.getEtfRadarOverview).toHaveBeenCalledTimes(2);
    expect(api.getEtfRadarHistory).toHaveBeenCalledTimes(2);
    expect(source).toMatch(/loadTab\(activeTab,\s*true\)/);
    wrapper.unmount();
  });

  it('keeps loading failures and empty results inside the active panel', async () => {
    setDefaultApiResponses();
    api.getEtfRadarHistory.mockRejectedValueOnce(new Error('history unavailable'));
    api.getEtfRadarHolders.mockResolvedValueOnce(holdersFixture([]));
    const wrapper = await mountView();
    const tabs = wrapper.findAll('.etf-tab-trigger');

    await tabs[1]!.trigger('click');
    await flushPromises();
    expect(wrapper.find('[data-testid="etf-panel-error"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="etf-global-error"]').exists()).toBe(false);

    await tabs[2]!.trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('暂无持有人披露');
    wrapper.unmount();
  });

  it('shows a refresh error while retaining the populated active view', async () => {
    setDefaultApiResponses();
    const wrapper = await mountView();
    api.getEtfRadarOverview.mockRejectedValueOnce(new Error('overview refresh unavailable'));

    await wrapper.get('[data-testid="etf-refresh"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="etf-panel-error"]').text()).toContain('overview refresh unavailable');
    expect(wrapper.text()).toContain('华夏上证50ETF');
    expect(wrapper.text()).toContain('证据强度');
    wrapper.unmount();
  });

  it('does not render a blank chart when history has no points', async () => {
    setDefaultApiResponses();
    api.getEtfRadarHistory.mockResolvedValueOnce({ ...historyFixture(), points: [] });
    const wrapper = await mountView();

    await wrapper.findAll('.etf-tab-trigger')[1]!.trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="etf-history-chart"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('暂无份额历史');
    wrapper.unmount();
  });

  it('keeps the evidence/source contract and accessible chart contract in the view', async () => {
    expect(source).toContain('证据强度');
    expect(source).not.toContain('概率');
    expect(source).toMatch(/overflow-x\s*:\s*auto/);
    expect(source).toMatch(/min-width\s*:\s*0/);
    expect(source).toMatch(/aria:\s*\{\s*enabled:\s*true/);
    expect(source).toContain('description:');

    setDefaultApiResponses();
    const wrapper = await mountView();
    await wrapper.findAll('.etf-tab-trigger')[1]!.trigger('click');
    await flushPromises();
    const option = wrapper.findComponent(ChartStub).props('option') as { aria?: { enabled?: boolean; description?: string } };
    expect(option.aria?.enabled).toBe(true);
    expect(option.aria?.description).toContain('估算申购');
    expect(wrapper.text()).toContain('上交所ETF份额');
    wrapper.unmount();
  });
});
