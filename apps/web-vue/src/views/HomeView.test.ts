// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CapitalSummaryResponse, MarketOverviewResponse, SectorRadarResponse } from '@/service/types';
import type { HomeDashboardDependencies } from '@/composables/useHomeDashboard';
import HomeView from './HomeView.vue';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

const api = vi.hoisted(() => ({
  getCapitalSummary: vi.fn(),
  getMarketOverview: vi.fn(),
  getSectorRadar: vi.fn()
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

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
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
  emits: ['click'],
  template: '<button @click="$emit(\'click\')"><slot /></button>'
});

const RouterLinkStub = defineComponent({
  name: 'RouterLink',
  props: ['to'],
  template: '<a :href="to"><slot /></a>'
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
        RouterLink: RouterLinkStub,
        SectorRadarChart: ChartStub
      }
    }
  });
  await Promise.resolve();

  return {
    renderChart() {
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

function sectorFlowFixture(): SectorRadarResponse {
  return {
    trade_date: '2026-07-18',
    capital_flow_status: 'direct',
    flow_source: 'ifind',
    inflow: [
      {
        name: '半导体', source: 'ifind', change_pct: 2.1, turnover_cny: 80_000_000_000,
        advance_count: 42, decline_count: 8, leader: '中芯国际', net_flow_cny: 6_800_000_000,
        strength_score: 88
      }
    ],
    outflow: [
      {
        name: '煤炭', source: 'ifind', change_pct: -1.2, turnover_cny: 30_000_000_000,
        advance_count: 4, decline_count: 26, leader: '中国神华', net_flow_cny: -2_600_000_000,
        strength_score: -42
      }
    ],
    source_status: [{ source: 'ifind', status: 'success', detail: '资金流正常' }],
    generated_at: '2026-07-18T09:33:05+08:00'
  };
}

function capitalFixture(): CapitalSummaryResponse {
  return {
    generated_at: '2026-07-18T09:34:05+08:00',
    trade_date: '2026-07-17',
    as_of: '2026-07-18T09:34:05+08:00',
    signal_stage: 'post_close',
    model_version: 'heuristic-v1',
    source_status: [{ source: '上交所ETF份额', status: 'success', detail: '正常' }],
    margin: {
      balance_cny: 1_405_364_008_462,
      financing_balance_cny: 1_392_832_663_141,
      securities_lending_balance_cny: 12_531_345_321,
      financing_buy_cny: 107_304_029_411,
      change_cny: -38_680_784_667,
      change_pct: -2.68,
      available_markets: 1,
      expected_markets: 2
    },
    etf_radar: {
      evidence_strength: 72.5,
      evidence_level: '较强',
      valid_etf_count: 6,
      expected_etf_count: 7,
      estimated_subscription_cny: 24_218_749_900,
      evidence: ['6/6 只有效ETF份额增加', '合计估算净申购 242.2亿']
    }
  };
}

function resolveAll() {
  api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
  api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
  api.getCapitalSummary.mockResolvedValueOnce(capitalFixture());
}

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('HomeView capital dashboard', () => {
  it('starts the three resources together and renders independent results', async () => {
    const overviewRequest = deferred<MarketOverviewResponse>();
    const sectorRequest = deferred<SectorRadarResponse>();
    const capitalRequest = deferred<CapitalSummaryResponse>();
    api.getMarketOverview.mockReturnValueOnce(overviewRequest.promise);
    api.getSectorRadar.mockReturnValueOnce(sectorRequest.promise);
    api.getCapitalSummary.mockReturnValueOnce(capitalRequest.promise);

    const { wrapper } = await mountDashboard();

    expect(api.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(api.getSectorRadar).toHaveBeenCalledWith(12);
    expect(api.getCapitalSummary).toHaveBeenCalledTimes(1);

    overviewRequest.resolve(overviewFixture());
    await flushPromises();
    expect(wrapper.text()).toContain('上证指数');
    expect(wrapper.text()).not.toContain('融资融券余额');

    sectorRequest.resolve(sectorFlowFixture());
    capitalRequest.resolve(capitalFixture());
    await flushPromises();

    expect(wrapper.text()).toContain('融资融券余额');
    expect(wrapper.text()).toContain('证据强度');
    wrapper.unmount();
  });

  it('renders one sector visualization and the two capital summaries', async () => {
    resolveAll();
    const { renderChart, wrapper } = await mountDashboard();
    await flushPromises();

    expect(wrapper.findAll('[data-testid="sector-chart"]')).toHaveLength(0);
    renderChart();
    await flushPromises();

    expect(wrapper.findAll('[data-testid="sector-chart"]')).toHaveLength(1);
    for (const heading of ['板块资金流', '两融余额', '宽基护盘雷达']) {
      expect(wrapper.text()).toContain(heading);
    }
    for (const removed of ['板块实时曲线', '市场关注榜', '数据状态']) {
      expect(wrapper.text()).not.toContain(removed);
    }
    expect(wrapper.find('a[href="/etf-radar"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('沪深 1/2');
    expect(wrapper.text()).toContain('部分');
    expect(wrapper.text()).toContain('▼ -386.8亿');
    expect(wrapper.text()).toContain('▲ +242.2亿');
    wrapper.unmount();
  });

  it('keeps market and sector content when the capital summary fails', async () => {
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getCapitalSummary.mockRejectedValueOnce(new Error('capital unavailable'));

    const { renderChart, wrapper } = await mountDashboard();
    await flushPromises();
    renderChart();
    await flushPromises();

    expect(wrapper.text()).toContain('上证指数');
    expect(wrapper.findAll('[data-testid="sector-chart"]')).toHaveLength(1);
    expect(wrapper.text()).toContain('资金信号读取失败');
    wrapper.unmount();
  });

  it('keeps successful content and marks it stale after forced refresh failures', async () => {
    resolveAll();
    const { renderChart, wrapper } = await mountDashboard();
    await flushPromises();
    renderChart();
    await flushPromises();

    api.getMarketOverview.mockRejectedValueOnce(new Error('overview refresh failed'));
    api.getSectorRadar.mockRejectedValueOnce(new Error('sector refresh failed'));
    api.getCapitalSummary.mockRejectedValueOnce(new Error('capital refresh failed'));

    await wrapper.find('button').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('上证指数');
    expect(wrapper.text()).toContain('融资融券余额');
    expect(wrapper.findAll('[title="刷新失败，当前显示上次数据"]')).toHaveLength(3);
    expect(wrapper.text()).not.toContain('refresh failed');
    wrapper.unmount();
  });
});
