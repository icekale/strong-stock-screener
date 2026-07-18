// @vitest-environment jsdom

import process from 'node:process';
import { readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';
import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  MarketOverviewResponse,
  MarketRankingsResponse,
  SectorRadarResponse,
  SectorReplicaMode,
  SectorReplicaRadarResponse
} from '@/service/types';
import type { HomeDashboardDependencies } from '@/composables/useHomeDashboard';
import HomeView from './HomeView.vue';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const api = vi.hoisted(() => ({
  getMarketOverview: vi.fn(),
  getMarketRankings: vi.fn(),
  getSectorRadar: vi.fn(),
  getSectorReplicaRadar: vi.fn()
}));

vi.mock('@/service/product-api', () => api);
vi.mock('@/composables/useHomeDashboard', async () => {
  const dashboard = await vi.importActual<typeof import('@/composables/useHomeDashboard')>(
    '@/composables/useHomeDashboard'
  );
  const { createMemoryRequestCache } =
    await vi.importActual<typeof import('@/utils/requestCache')>('@/utils/requestCache');

  return {
    ...dashboard,
    useHomeDashboard: () =>
      dashboard.useHomeDashboard({
        dependencies: api as unknown as HomeDashboardDependencies,
        cache: createMemoryRequestCache({ ttlMs: 15_000 })
      })
  };
});
vi.mock('@/components/charts/SectorRadarChart.vue', () => ({
  default: {
    name: 'SectorRadarChart',
    props: ['height', 'loading', 'option'],
    template: '<div data-testid="sector-chart" />'
  }
}));

const source = readFileSync(resolvePath(process.cwd(), 'src/views/HomeView.vue'), 'utf8');

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(resolvePromise => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

const ChartStub = defineComponent({
  name: 'SectorRadarChart',
  props: ['height', 'loading', 'option'],
  template: '<div data-testid="sector-chart" />'
});

const AlertStub = defineComponent({
  name: 'AAlert',
  props: ['title'],
  template: '<div role="alert">{{ title }}</div>'
});

const ButtonStub = defineComponent({
  name: 'AButton',
  props: ['loading'],
  template: '<button><slot /></button>'
});

const SegmentedStub = defineComponent({
  name: 'ASegmented',
  props: ['value', 'options'],
  template: '<div data-testid="sector-mode" />'
});

async function mountDashboard() {
  let animationFrameCallback: FrameRequestCallback | undefined;
  vi.stubGlobal(
    'requestAnimationFrame',
    vi.fn((callback: FrameRequestCallback) => {
      animationFrameCallback = callback;
      return 41;
    })
  );
  vi.stubGlobal('cancelAnimationFrame', vi.fn());

  const wrapper = mount(HomeView, {
    global: {
      stubs: {
        AAlert: AlertStub,
        AButton: ButtonStub,
        ASegmented: SegmentedStub,
        SectorRadarChart: ChartStub
      }
    }
  });
  await Promise.resolve();

  return {
    renderCharts() {
      animationFrameCallback?.(0);
    },
    wrapper
  };
}

function overviewFixture(): MarketOverviewResponse {
  return {
    trade_date: '2026-07-18',
    turnover: {
      total_cny: 1_230_000_000_000,
      previous_total_cny: 1_200_000_000_000,
      change_cny: 30_000_000_000,
      change_pct: 2.5
    },
    advance_decline: {
      advance_count: 6,
      decline_count: 4,
      unchanged_count: 1,
      limit_up_count: 28,
      limit_down_count: 3
    },
    indices: [
      {
        symbol: '000001.SH',
        name: '上证指数',
        last_price: 3510.25,
        change_pct: 1.25,
        turnover_cny: 520_000_000_000,
        source: 'tencent'
      }
    ],
    sectors: [],
    source_status: [{ source: 'tencent', status: 'success', detail: '指数快照正常' }],
    generated_at: '2026-07-18T09:31:05+08:00'
  };
}

function rankingsFixture(): MarketRankingsResponse {
  return {
    trade_date: '2026-07-18',
    pct_change_rank: [
      {
        symbol: '600519.SH',
        name: '贵州茅台',
        last_price: 1600,
        pct_change: 3.2,
        turnover_rate: 0.4,
        turnover_cny: 2_000_000_000,
        volume: 120_000,
        quote_time: '09:31:00'
      }
    ],
    turnover_rank: [],
    buckets: [],
    source_status: [{ source: 'rankings', status: 'stale', detail: '排行榜延迟一分钟' }],
    generated_at: '2026-07-18T09:32:05+08:00'
  };
}

function sectorFlowFixture(): SectorRadarResponse {
  return {
    trade_date: '2026-07-18',
    capital_flow_status: 'direct',
    flow_source: 'ifind',
    inflow: [
      {
        name: '半导体',
        source: 'ifind',
        change_pct: 2.1,
        turnover_cny: 80_000_000_000,
        advance_count: 42,
        decline_count: 8,
        leader: '中芯国际',
        net_flow_cny: 6_800_000_000,
        strength_score: 88
      }
    ],
    outflow: [],
    source_status: [{ source: 'ifind', status: 'missing_key', detail: '资金流密钥缺失' }],
    generated_at: '2026-07-18T09:33:05+08:00'
  };
}

function sectorTrendFixture(mode: SectorReplicaMode = 'strength'): SectorReplicaRadarResponse {
  return {
    result: 'success',
    mode,
    trade_date: '2026-07-18',
    axis: ['09:30', '09:31'],
    qxlive: { Aaxis: ['09:30', '09:31'], zflist: [1, 2], series: { 半导体: [120_000, 130_000] } },
    plates: [],
    checkplate: [],
    legend: ['半导体'],
    series: [{ name: '半导体', type: 'line', data: [120_000, 130_000], smooth: true, showSymbol: false }],
    stocks: [],
    related_tags: [],
    source_status: [
      { source: 'tencent', status: 'failed', detail: '板块趋势接口失败' },
      { source: 'optional-trend', status: 'disabled', detail: '备用趋势源未启用' }
    ],
    generated_at: '2026-07-18T09:34:05+08:00'
  };
}

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('HomeView source contract', () => {
  it.each([
    'getAuctionModelTop3',
    'AuctionModelTop3Response',
    '竞价 Top3',
    'getMarketEmotionSnapshot',
    'MarketTrendChart',
    '盘中情绪走势',
    'useTradeDate',
    'a-date-picker'
  ])('does not contain removed homepage dependency %s', removed => {
    expect(source).not.toContain(removed);
  });

  it.each([
    'defineAsyncComponent',
    'requestAnimationFrame',
    'v-if="chartsReady"',
    'useHomeDashboard',
    'buildSectorReplicaChartOption'
  ])('contains the dashboard rendering contract %s', required => {
    expect(source).toContain(required);
  });
});

describe('HomeView dashboard', () => {
  it('starts resources together, renders them independently, and defers both charts', async () => {
    const overviewRequest = deferred<MarketOverviewResponse>();
    const rankingsRequest = deferred<MarketRankingsResponse>();
    const sectorFlowRequest = deferred<SectorRadarResponse>();
    const sectorTrendRequest = deferred<SectorReplicaRadarResponse>();
    api.getMarketOverview.mockReturnValueOnce(overviewRequest.promise);
    api.getMarketRankings.mockReturnValueOnce(rankingsRequest.promise);
    api.getSectorRadar.mockReturnValueOnce(sectorFlowRequest.promise);
    api.getSectorReplicaRadar.mockReturnValueOnce(sectorTrendRequest.promise);
    const { renderCharts, wrapper } = await mountDashboard();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(api.getMarketRankings).toHaveBeenCalledWith(12);
    expect(api.getSectorRadar).toHaveBeenCalledWith(12);
    expect(api.getSectorReplicaRadar).toHaveBeenCalledWith({ mode: 'strength', limit: 5, stockLimit: 1 });
    expect(wrapper.findAll('[data-testid="sector-chart"]')).toHaveLength(0);
    expect(wrapper.text()).toContain('主要指数');
    expect(wrapper.text()).toContain('总成交额');

    overviewRequest.resolve(overviewFixture());
    await flushPromises();

    expect(wrapper.text()).toContain('上证指数');
    expect(wrapper.text()).toContain('3510.25');
    expect(wrapper.text()).toContain('1.23万亿');
    expect(wrapper.text()).toContain('6 / 4');
    expect(wrapper.text()).toContain('偏强');
    expect(wrapper.text()).not.toContain('贵州茅台');

    rankingsRequest.resolve(rankingsFixture());
    sectorFlowRequest.resolve(sectorFlowFixture());
    sectorTrendRequest.resolve(sectorTrendFixture());
    await flushPromises();

    expect(wrapper.text()).toContain('贵州茅台');
    const duplicateSourceRows = wrapper.findAll('.home-source-row').filter(row => row.text().includes('tencent'));
    expect(duplicateSourceRows).toHaveLength(1);
    expect(duplicateSourceRows[0]?.text()).toContain('失败');
    expect(duplicateSourceRows[0]?.text()).toContain('板块趋势接口失败');

    renderCharts();
    await flushPromises();

    expect(wrapper.findAll('[data-testid="sector-chart"]')).toHaveLength(2);
    for (const heading of [
      '主要指数',
      '总成交额',
      '上涨 / 下跌',
      '涨停 / 跌停',
      '盘面状态',
      '板块资金流',
      '板块实时曲线',
      '市场关注榜',
      '数据状态'
    ]) {
      expect(wrapper.text()).toContain(heading);
    }
    expect(wrapper.text()).not.toContain('竞价 Top3');
    expect(wrapper.text()).not.toContain('盘中情绪走势');

    wrapper.unmount();
  });

  it('renders honest notes for degraded source states', async () => {
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getMarketRankings.mockResolvedValueOnce(rankingsFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getSectorReplicaRadar.mockResolvedValueOnce(sectorTrendFixture());

    const { wrapper } = await mountDashboard();
    await flushPromises();

    const sourceRows = wrapper.findAll('.home-source-row');
    expect(sourceRows.find(row => row.text().includes('rankings'))?.text()).toContain('延迟');
    expect(sourceRows.find(row => row.text().includes('ifind'))?.text()).toContain('缺少密钥');
    expect(sourceRows.find(row => row.text().includes('optional-trend'))?.text()).toContain('未启用');

    wrapper.unmount();
  });

  it('keeps successful content visible and marks it old when refreshes fail', async () => {
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getMarketRankings.mockResolvedValueOnce(rankingsFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getSectorReplicaRadar.mockResolvedValueOnce(sectorTrendFixture());

    const { renderCharts, wrapper } = await mountDashboard();
    await flushPromises();
    renderCharts();
    await flushPromises();

    expect(wrapper.findAll('[data-testid="sector-chart"]')).toHaveLength(2);
    expect(wrapper.text()).toContain('贵州茅台');

    api.getMarketOverview.mockRejectedValueOnce(new Error('overview refresh failed'));
    api.getMarketRankings.mockRejectedValueOnce(new Error('rankings refresh failed'));
    api.getSectorRadar.mockRejectedValueOnce(new Error('sector flow refresh failed'));
    api.getSectorReplicaRadar.mockRejectedValueOnce(new Error('sector trend refresh failed'));

    await wrapper.find('button').trigger('click');
    await flushPromises();

    expect(wrapper.findAll('[data-testid="sector-chart"]')).toHaveLength(2);
    expect(wrapper.text()).toContain('上证指数');
    expect(wrapper.text()).toContain('贵州茅台');
    expect(wrapper.findAll('[title="刷新失败，当前显示上次数据"]')).toHaveLength(4);
    expect(wrapper.findAll('.home-chart-state--error')).toHaveLength(0);
    const rankingPanel = wrapper.findAll('.home-panel').find(panel => panel.text().includes('市场关注榜'));
    expect(rankingPanel?.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('refresh failed');

    wrapper.unmount();
  });

  it('keeps trend formatting on the response mode until switched data arrives', async () => {
    const mainFlowRequest = deferred<SectorReplicaRadarResponse>();
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getMarketRankings.mockResolvedValueOnce(rankingsFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getSectorReplicaRadar
      .mockResolvedValueOnce(sectorTrendFixture('strength'))
      .mockReturnValueOnce(mainFlowRequest.promise);

    const { renderCharts, wrapper } = await mountDashboard();
    await flushPromises();
    renderCharts();
    await flushPromises();

    const trendFormatter = () => {
      const chart = wrapper.findAllComponents(ChartStub)[1];
      const option = chart?.props('option') as {
        yAxis: { axisLabel: { formatter: (value: number) => string } };
      };
      return option.yAxis.axisLabel.formatter;
    };

    expect(trendFormatter()(120_000)).toBe('120000');

    wrapper.findComponent(SegmentedStub).vm.$emit('change', 'main_flow');
    await Promise.resolve();
    await wrapper.vm.$nextTick();

    expect(api.getSectorReplicaRadar).toHaveBeenLastCalledWith({ mode: 'main_flow', limit: 5, stockLimit: 1 });
    expect(trendFormatter()(120_000)).toBe('120000');

    mainFlowRequest.resolve(sectorTrendFixture('main_flow'));
    await flushPromises();

    expect(trendFormatter()(120_000)).toBe('12万');

    wrapper.unmount();
  });

  it('limits sector flow value-axis labels for narrow dashboard panels', async () => {
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getMarketRankings.mockResolvedValueOnce(rankingsFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getSectorReplicaRadar.mockResolvedValueOnce(sectorTrendFixture());

    const { renderCharts, wrapper } = await mountDashboard();
    await flushPromises();
    renderCharts();
    await flushPromises();

    const chart = wrapper.findAllComponents(ChartStub)[0];
    const option = chart?.props('option') as {
      xAxis: { splitNumber?: number; axisLabel: { hideOverlap?: boolean } };
    };

    expect(option.xAxis.splitNumber).toBe(4);
    expect(option.xAxis.axisLabel.hideOverlap).toBe(true);

    wrapper.unmount();
  });
});
