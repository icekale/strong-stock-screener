// @vitest-environment jsdom

import process from 'node:process';
import { readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';
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

const source = readFileSync(resolvePath(process.cwd(), 'src/views/HomeView.vue'), 'utf8');

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
    model_version: 'huijin-public-rule-v1',
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
      evidence: ['6/6 只有效ETF份额增加', '合计估算净申购 242.2亿'],
      activity: {
        core_count: 7,
        available_core_count: 6,
        tenfold_increase_count: 5,
        tenfold_decrease_count: 1,
        confirmed_increase_group_count: 2,
        confirmed_decrease_group_count: 0,
        divergent_group_count: 1,
        incomplete_group_count: 0,
        strongest_symbol: '159915.SZ',
        strongest_baseline_change_pct: 6.019
      }
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
    expect(Object.keys(api)).toEqual(['getCapitalSummary', 'getMarketOverview', 'getSectorRadar']);
    expect(wrapper.text()).toContain('汇金 ETF 活动');
    expect(wrapper.text()).toContain('等待 ETF 活动数据');

    overviewRequest.resolve(overviewFixture());
    await flushPromises();
    expect(wrapper.text()).toContain('上证指数');
    expect(wrapper.text()).not.toContain('融资融券余额');

    sectorRequest.resolve(sectorFlowFixture());
    capitalRequest.resolve(capitalFixture());
    await flushPromises();

    expect(wrapper.text()).toContain('融资融券余额');
    expect(wrapper.text()).toContain('十倍量增加 5');
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
    for (const heading of ['板块资金流', '两融余额', '汇金 ETF 活动']) {
      expect(wrapper.text()).toContain(heading);
    }
    for (const removed of ['板块实时曲线', '市场关注榜', '数据状态']) {
      expect(wrapper.text()).not.toContain(removed);
    }
    expect(wrapper.find('a[href="/etf-radar"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('沪深 1/2');
    expect(wrapper.text()).toContain('部分');
    expect(wrapper.text()).toContain('▼ -386.8亿');
    expect(wrapper.text()).toContain('数据日 2026-07-17');
    expect(wrapper.text()).toContain('盘后确认 · huijin-public-rule-v1');
    expect(wrapper.text()).toContain('十倍量增加 5');
    expect(wrapper.text()).toContain('十倍量减少 1');
    expect(wrapper.text()).toContain('确认增加 2组');
    expect(wrapper.text()).toContain('确认减少 0组');
    expect(wrapper.text()).toContain('方向分歧 1组');
    expect(wrapper.text()).toContain('数据不全 0组');
    expect(wrapper.text()).toContain('159915.SZ');
    expect(wrapper.text()).toContain('▲ +6.02%');
    expect(wrapper.text()).toContain('覆盖 6/7');
    for (const legacy of [
      '证据强度',
      '估算净申购',
      '宽基护盘雷达',
      '6/6 只有效ETF份额增加',
      '合计估算净申购 242.2亿'
    ]) {
      expect(wrapper.text()).not.toContain(legacy);
    }
    const etfPanel = wrapper.findAll('.home-capital-panel')[1]!;
    expect(etfPanel.get('.wb-status-tag').text()).toBe('部分');
    expect(etfPanel.get('[data-testid="tenfold-increase"]').classes()).toContain('home-positive');
    expect(etfPanel.get('[data-testid="tenfold-decrease"]').classes()).toContain('home-negative');
    expect(etfPanel.get('[data-testid="divergent-groups"]').classes()).not.toContain('home-positive');
    expect(etfPanel.get('[data-testid="divergent-groups"]').classes()).not.toContain('home-negative');
    wrapper.unmount();
  });

  it('shows an honest fallback when the strongest core ETF is unavailable', async () => {
    const capital = capitalFixture();
    capital.etf_radar.activity.strongest_symbol = null;
    capital.etf_radar.activity.strongest_baseline_change_pct = null;
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getCapitalSummary.mockResolvedValueOnce(capital);

    const { wrapper } = await mountDashboard();
    await flushPromises();

    const strongest = wrapper.get('[data-testid="strongest-core-etf"]');
    expect(strongest.text()).toContain('待确认');
    expect(strongest.text()).toContain('--');
    wrapper.unmount();
  });

  it('marks complete coverage partial when a backend ETF source is stale', async () => {
    const capital = capitalFixture();
    capital.etf_radar.activity.available_core_count = capital.etf_radar.activity.core_count;
    capital.source_status = [{ source: '深交所ETF份额', status: 'stale', detail: '使用上一交易日数据' }];
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getCapitalSummary.mockResolvedValueOnce(capital);

    const { wrapper } = await mountDashboard();
    await flushPromises();

    const etfPanel = wrapper.findAll('.home-capital-panel')[1]!;
    expect(etfPanel.get('.wb-status-tag').text()).toBe('部分');
    expect(etfPanel.text()).not.toContain('旧数据');
    wrapper.unmount();
  });

  it('caps each sector direction at six rows and stacks the main grid responsively', async () => {
    const flow = sectorFlowFixture();
    const makeRow = (index: number, direction: 1 | -1) => ({
      ...flow.inflow[0]!,
      name: `${direction > 0 ? '流入' : '流出'}${index}`,
      net_flow_cny: direction * (index + 1) * 100_000_000
    });
    flow.inflow = Array.from({ length: 8 }, (_, index) => makeRow(index, 1));
    flow.outflow = Array.from({ length: 8 }, (_, index) => makeRow(index, -1));
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getSectorRadar.mockResolvedValueOnce(flow);
    api.getCapitalSummary.mockResolvedValueOnce(capitalFixture());

    const { renderChart, wrapper } = await mountDashboard();
    await flushPromises();
    renderChart();
    await flushPromises();

    const option = wrapper.findComponent(ChartStub).props('option') as {
      series: Array<{ data: Array<{ value: number }> }>;
    };
    const values = option.series[0]!.data.map(item => item.value);
    expect(values).toHaveLength(12);
    expect(values.filter(value => value > 0)).toHaveLength(6);
    expect(values.filter(value => value < 0)).toHaveLength(6);
    expect(source).toMatch(/\.home-capital-stack\s*\{[\s\S]*?grid-template-rows: repeat\(2, minmax\(0, 1fr\)\)/);
    expect(source).toMatch(/@media \(max-width: 1023px\)[\s\S]*?\.home-main-grid[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/);
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
    expect(wrapper.text()).toContain('汇金 ETF 活动');
    expect(wrapper.text()).toContain('等待服务恢复');
    wrapper.unmount();
  });

  it('keeps capital summaries visible when market and sector resources fail', async () => {
    api.getMarketOverview.mockRejectedValueOnce(new Error('overview unavailable'));
    api.getSectorRadar.mockRejectedValueOnce(new Error('sector unavailable'));
    api.getCapitalSummary.mockResolvedValueOnce(capitalFixture());

    const { renderChart, wrapper } = await mountDashboard();
    await flushPromises();
    renderChart();
    await flushPromises();

    expect(wrapper.text()).toContain('两融余额');
    expect(wrapper.text()).toContain('汇金 ETF 活动');
    expect(wrapper.text()).toContain('市场总览暂时不可用');
    expect(wrapper.text()).toContain('板块资金流读取失败');
    wrapper.unmount();
  });

  it('keeps successful content and marks it stale after forced refresh failures', async () => {
    const capital = capitalFixture();
    capital.etf_radar.activity.available_core_count = capital.etf_radar.activity.core_count;
    api.getMarketOverview.mockResolvedValueOnce(overviewFixture());
    api.getSectorRadar.mockResolvedValueOnce(sectorFlowFixture());
    api.getCapitalSummary.mockResolvedValueOnce(capital);
    const { renderChart, wrapper } = await mountDashboard();
    await flushPromises();
    renderChart();
    await flushPromises();

    const initialEtfPanel = wrapper.findAll('.home-capital-panel')[1]!;
    expect(initialEtfPanel.get('.wb-status-tag').text()).toBe('成功');

    api.getMarketOverview.mockRejectedValueOnce(new Error('overview refresh failed'));
    api.getSectorRadar.mockRejectedValueOnce(new Error('sector refresh failed'));
    api.getCapitalSummary.mockRejectedValueOnce(new Error('capital refresh failed'));

    await wrapper.find('button').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('上证指数');
    expect(wrapper.text()).toContain('融资融券余额');
    expect(wrapper.findAll('[title="刷新失败，当前显示上次数据"]')).toHaveLength(4);
    const staleEtfPanel = wrapper.findAll('.home-capital-panel')[1]!;
    expect(staleEtfPanel.get('.wb-status-tag').text()).toBe('部分');
    expect(staleEtfPanel.text()).toContain('旧数据');
    expect(staleEtfPanel.text()).toContain('159915.SZ');
    expect(wrapper.text()).not.toContain('refresh failed');
    wrapper.unmount();
  });
});
