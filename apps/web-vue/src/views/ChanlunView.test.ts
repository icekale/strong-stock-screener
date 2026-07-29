// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChanlunAnalysisResponse, ChanlunPeriod, ChanlunWorkspaceResponse } from '@/service/types';
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
  createChanlunPaperOrderDraft: vi.fn(),
  fillChanlunPaperOrder: vi.fn(),
  getChanlunAnalysis: vi.fn(),
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
        AButton: true,
        ACheckbox: true,
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
