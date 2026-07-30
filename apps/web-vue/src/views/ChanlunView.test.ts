// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BackgroundJobState, ChanlunAnalysisResponse, ChanlunPeriod, ChanlunWorkspaceResponse } from '@/service/types';
import ChanlunView from './ChanlunView.vue';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const navigation = vi.hoisted(() => ({
  replace: vi.fn(),
  route: { query: {} as Record<string, string> }
}));

const api = vi.hoisted(() => ({
  approveChanlunPaperOrder: vi.fn(),
  createChanlunBackfillJob: vi.fn(),
  createChanlunPaperOrderDraft: vi.fn(),
  fillChanlunPaperOrder: vi.fn(),
  getChanlunAnalysis: vi.fn(),
  getChanlunBackfillJob: vi.fn(),
  getChanlunPaperAccount: vi.fn(),
  getChanlunWorkspace: vi.fn()
}));

vi.mock('vue-router', () => ({
  useRoute: () => navigation.route,
  useRouter: () => ({ replace: navigation.replace })
}));
vi.mock('@/service/product-api', () => api);
vi.mock('@/store/modules/theme', () => ({
  useThemeStore: () => ({ footer: { fixed: false } })
}));
vi.mock('@/components/charts/StockKlineChart.vue', () => ({
  default: defineComponent({
    name: 'StockKlineChart',
    props: ['bars', 'chanlun', 'period', 'symbol'],
    template: '<div data-testid="stock-kline-chart" />'
  })
}));

const InputStub = defineComponent({
  name: 'AInput',
  props: ['value'],
  emits: ['update:value', 'press-enter'],
  template: `<input
    data-testid="symbol-input"
    :value="value"
    @input="$emit('update:value', $event.target.value)"
    @keyup.enter="$emit('press-enter')"
  />`
});

const SegmentedStub = defineComponent({
  name: 'ASegmented',
  props: ['options', 'value'],
  emits: ['change'],
  template: `<div>
    <button
      v-for="option in options"
      :key="option.value"
      :data-period="option.value"
      @click="$emit('change', option.value)"
    >{{ option.label }}</button>
  </div>`
});

const PlainStub = defineComponent({
  props: ['items', 'title'],
  template: '<section><slot /></section>'
});

const ButtonStub = defineComponent({
  inheritAttrs: false,
  props: ['disabled'],
  template: '<button v-bind="$attrs" :disabled="disabled"><slot /></button>'
});

const CheckboxStub = defineComponent({
  inheritAttrs: false,
  props: ['checked', 'disabled'],
  template: '<label v-bind="$attrs"><input type="checkbox" :checked="checked" :disabled="disabled" /><slot /></label>'
});

const FormControlStub = defineComponent({
  inheritAttrs: false,
  props: ['children', 'options', 'prefix', 'value'],
  template: '<div />'
});

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(resolvePromise => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function analysisFixture(symbol: string, period: ChanlunPeriod): ChanlunAnalysisResponse {
  return {
    symbol,
    period,
    availability: 'ready',
    bars: [{
      date: `2026-07-29T${period === '1d' ? '15:00' : '10:00'}:00+08:00`,
      open: 10,
      close: 10.1,
      high: 10.2,
      low: 9.9,
      volume: 1000,
      ma5: null,
      ma10: null,
      ma20: null,
      ma60: null
    }],
    coverage: {
      status: 'unverified',
      required_period_bars: 0,
      available_period_bars: 0,
      required_raw_minutes: null,
      available_raw_minutes: null,
      complete_sessions: 0,
      incomplete_sessions: 0,
      missing_minutes: 0,
      earliest_at: null,
      latest_at: null,
      reason: '尚未执行覆盖审计',
      backfill_required: true
    },
    fractals: [],
    strokes: [],
    segments: [],
    zones: [],
    divergences: [],
    signals: [],
    source_status: [],
    calculated_at: '2026-07-29T15:01:00+08:00',
    last_closed_bar_at: '2026-07-29T15:00:00+08:00',
    adjustment_mode: 'raw_unadjusted',
    rule_version: 'cl-v2-visual'
  };
}

function workspaceFixture(symbol: string): ChanlunWorkspaceResponse {
  return {
    symbol,
    periods: [],
    analysis: analysisFixture(symbol, '1d'),
    confluence_signals: []
  };
}

function mountView() {
  return mount(ChanlunView, {
    global: {
      stubs: {
        AAlert: true,
        AButton: ButtonStub,
        ACheckbox: CheckboxStub,
        ADescriptions: PlainStub,
        ADescriptionsItem: PlainStub,
        AEmpty: true,
        AInput: InputStub,
        AInputNumber: FormControlStub,
        AList: PlainStub,
        AListItem: PlainStub,
        ASelect: FormControlStub,
        ASegmented: SegmentedStub,
        ASwitch: true,
        MetricStrip: PlainStub,
        PageHeader: PlainStub,
        SectionHeader: PlainStub,
        StatusTag: true
      }
    }
  });
}

function backfillJob(status: BackgroundJobState['status']): BackgroundJobState {
  return {
    job_id: 'chanlun-job-1',
    type: 'chanlun_backfill:600000.SH',
    status,
    progress_current: 0,
    progress_total: 3,
    message: status === 'running' ? '缠论分钟历史补齐中' : '缠论分钟历史补齐完成',
    started_at: null,
    finished_at: null,
    error: null,
    result_path: null,
    result: null
  };
}

beforeEach(() => {
  navigation.route.query = {};
  api.getChanlunPaperAccount.mockResolvedValue(null);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('ChanlunView request state', () => {
  it('reloads the selected non-daily period after applying another symbol', async () => {
    api.getChanlunWorkspace.mockImplementation((symbol: string) => Promise.resolve(workspaceFixture(symbol)));
    api.getChanlunAnalysis.mockImplementation((symbol: string, options: { period: ChanlunPeriod }) =>
      Promise.resolve(analysisFixture(symbol, options.period))
    );
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-period="30m"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="symbol-input"]').setValue('000001.SH');
    await wrapper.get('[data-testid="symbol-input"]').trigger('keyup.enter');
    await flushPromises();

    expect(api.getChanlunWorkspace).toHaveBeenLastCalledWith('000001.SH');
    expect(api.getChanlunAnalysis).toHaveBeenLastCalledWith('000001.SH', {
      period: '30m',
      lookback: 220,
      includeObserving: true
    });
    expect(wrapper.getComponent({ name: 'StockKlineChart' }).props('chanlun')).toMatchObject({
      symbol: '000001.SH',
      period: '30m'
    });
    wrapper.unmount();
  });

  it('shows coverage backfill and disables unvalidated derived layers', async () => {
    api.getChanlunWorkspace.mockResolvedValue(workspaceFixture('600000.SH'));
    api.createChanlunBackfillJob.mockResolvedValue(backfillJob('running'));
    const wrapper = mountView();
    await flushPromises();

    wrapper.get('[data-testid="chanlun-backfill"]');
    expect(wrapper.get('[data-layer="segments"] input').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-layer="divergences"] input').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-layer="signals"] input').attributes('disabled')).toBeDefined();

    await wrapper.get('[data-testid="chanlun-backfill"]').trigger('click');
    await flushPromises();

    expect(api.createChanlunBackfillJob).toHaveBeenCalledWith('600000.SH', {
      periods: ['5m', '30m', '60m'],
      lookback: 220
    });
    wrapper.unmount();
  });

  it('keeps stale price bars visible but removes the Chanlun overlay', async () => {
    const staleWorkspace = workspaceFixture('600000.SH');
    staleWorkspace.analysis = { ...staleWorkspace.analysis, availability: 'stale' };
    api.getChanlunWorkspace.mockResolvedValue(staleWorkspace);
    const wrapper = mountView();
    await flushPromises();

    const chart = wrapper.getComponent({ name: 'StockKlineChart' });
    expect(chart.props('bars')).toHaveLength(1);
    expect(chart.props('chanlun')).toBeNull();
    wrapper.unmount();
  });

  it('ignores a slower response from an older period request', async () => {
    const sixtyMinute = deferred<ChanlunAnalysisResponse>();
    const thirtyMinute = deferred<ChanlunAnalysisResponse>();
    api.getChanlunWorkspace.mockResolvedValue(workspaceFixture('600000.SH'));
    api.getChanlunAnalysis.mockImplementation((_symbol: string, options: { period: ChanlunPeriod }) =>
      options.period === '60m' ? sixtyMinute.promise : thirtyMinute.promise
    );
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-period="60m"]').trigger('click');
    await wrapper.get('[data-period="30m"]').trigger('click');
    thirtyMinute.resolve(analysisFixture('600000.SH', '30m'));
    await flushPromises();
    sixtyMinute.resolve(analysisFixture('600000.SH', '60m'));
    await flushPromises();

    expect(wrapper.getComponent({ name: 'StockKlineChart' }).props('chanlun')).toMatchObject({
      symbol: '600000.SH',
      period: '30m'
    });
    wrapper.unmount();
  });

  it('reloads workspace summaries when period changes during a symbol request', async () => {
    const supersededWorkspace = deferred<ChanlunWorkspaceResponse>();
    api.getChanlunWorkspace
      .mockResolvedValueOnce(workspaceFixture('600000.SH'))
      .mockReturnValueOnce(supersededWorkspace.promise)
      .mockResolvedValueOnce(workspaceFixture('000001.SH'));
    api.getChanlunAnalysis.mockResolvedValue(analysisFixture('000001.SH', '30m'));
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-testid="symbol-input"]').setValue('000001.SH');
    await wrapper.get('[data-testid="symbol-input"]').trigger('keyup.enter');
    await wrapper.get('[data-period="30m"]').trigger('click');
    await flushPromises();

    expect(api.getChanlunWorkspace.mock.calls).toEqual([
      ['600000.SH'],
      ['000001.SH'],
      ['000001.SH']
    ]);
    expect(api.getChanlunAnalysis).toHaveBeenCalledWith('000001.SH', {
      period: '30m',
      lookback: 220,
      includeObserving: true
    });
    expect(wrapper.getComponent({ name: 'StockKlineChart' }).props('chanlun')).toMatchObject({
      symbol: '000001.SH',
      period: '30m'
    });
    wrapper.unmount();
  });
});
