// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { type VueWrapper, flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ChanlunSymbolMatch,
  ChanlunSymbolSearchResponse,
  WatchlistGsgfStatusResponse,
  WatchlistPoolResponse
} from '@/service/types';
import WatchlistView from './WatchlistView.vue';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
const api = vi.hoisted(() => ({
  addWatchlistPoolItem: vi.fn(),
  getWatchlistGsgfStatus: vi.fn(),
  getWatchlistPool: vi.fn(),
  saveWatchlistPool: vi.fn(),
  searchStockSymbols: vi.fn()
}));

vi.mock('vue-router', () => ({ useRouter: () => ({ push: navigation.push }) }));
vi.mock('@/service/product-api', () => api);

const PUFA: ChanlunSymbolMatch = { symbol: '600000.SH', name: '浦发银行' };
const PINGAN: ChanlunSymbolMatch = { symbol: '000001.SZ', name: '平安银行' };
const mountedWrappers: VueWrapper[] = [];

const AutoCompleteStub = defineComponent({
  name: 'AAutoComplete',
  inheritAttrs: false,
  props: ['loading', 'options', 'value'],
  emits: ['search', 'select', 'update:value'],
  template: `
    <div v-bind="$attrs">
      <input
        :value="value"
        @input="$emit('update:value', $event.target.value); $emit('search', $event.target.value)"
        @keydown.enter="options[0] && $emit('update:value', options[0].value); options[0] && $emit('select', options[0].value, options[0])"
      />
      <button
        v-for="option in options"
        :key="option.value"
        data-testid="symbol-option"
        type="button"
        @click="$emit('update:value', option.value); $emit('select', option.value, option)"
      >
        <slot name="option" v-bind="option">{{ option.label }}</slot>
      </button>
      <div v-if="options.length === 0"><slot name="notFoundContent" /></div>
    </div>
  `
});

const InputStub = defineComponent({
  name: 'AInput',
  inheritAttrs: false,
  props: ['value'],
  emits: ['press-enter', 'update:value'],
  template: '<input v-bind="$attrs" :value="value" @input="$emit(\'update:value\', $event.target.value)" />'
});

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  props: ['disabled', 'loading'],
  emits: ['click'],
  template: '<button v-bind="$attrs" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
});

const AlertStub = defineComponent({
  name: 'AAlert',
  props: ['title'],
  template: '<div role="alert">{{ title }}</div>'
});

const PlainStub = defineComponent({
  props: ['items', 'loading', 'title'],
  template: '<section><slot name="meta" /><slot /></section>'
});

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(resolvePromise => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function poolFixture(): WatchlistPoolResponse {
  return { content: '', items: [] };
}

function gsgfFixture(): WatchlistGsgfStatusResponse {
  return { items: [] };
}

function searchFixture(items: ChanlunSymbolMatch[] = []): ChanlunSymbolSearchResponse {
  return { items, source_status: [] };
}

async function mountView() {
  const wrapper = mount(WatchlistView, {
    global: {
      stubs: {
        AAlert: AlertStub,
        AAutoComplete: AutoCompleteStub,
        AButton: ButtonStub,
        AInput: InputStub,
        ASpaceCompact: PlainStub,
        ATextarea: InputStub,
        DataList: PlainStub,
        PageHeader: PlainStub,
        SectionHeader: PlainStub,
        StatusTag: true
      }
    }
  });
  mountedWrappers.push(wrapper);
  await flushPromises();
  return wrapper;
}

function symbolSearchInput(wrapper: VueWrapper) {
  return wrapper.get('[data-testid="symbol-search-input"]').get('input');
}

async function renderPufaCandidate(wrapper: VueWrapper) {
  api.searchStockSymbols.mockResolvedValueOnce(searchFixture([PUFA]));
  await symbolSearchInput(wrapper).setValue('PFYH');
  await vi.advanceTimersByTimeAsync(250);
  await flushPromises();
}

async function selectPufaCandidate(wrapper: VueWrapper) {
  await renderPufaCandidate(wrapper);
  await wrapper.get('[data-testid="symbol-option"]').trigger('click');
}

beforeEach(() => {
  vi.useFakeTimers();
  navigation.push.mockReset();
  api.addWatchlistPoolItem.mockReset().mockResolvedValue(poolFixture());
  api.getWatchlistGsgfStatus.mockReset().mockResolvedValue(gsgfFixture());
  api.getWatchlistPool.mockReset().mockResolvedValue(poolFixture());
  api.saveWatchlistPool.mockReset().mockResolvedValue(poolFixture());
  api.searchStockSymbols.mockReset().mockResolvedValue(searchFixture());
});

afterEach(() => {
  for (const wrapper of mountedWrappers.splice(0)) wrapper.unmount();
  vi.useRealTimers();
});

describe('WatchlistView symbol search', () => {
  it('debounces PFYH for 250ms and renders the remote candidate', async () => {
    api.searchStockSymbols.mockResolvedValueOnce(searchFixture([PUFA]));
    const wrapper = await mountView();

    await symbolSearchInput(wrapper).setValue('PFYH');
    expect(api.searchStockSymbols).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(249);
    expect(api.searchStockSymbols).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();

    expect(api.searchStockSymbols).toHaveBeenCalledWith('PFYH', { limit: 20 });
    expect(wrapper.text()).toContain('浦发银行');
    expect(wrapper.text()).toContain('600000.SH');
  });

  it('adds the selected normalized candidate with its name', async () => {
    const wrapper = await mountView();
    await selectPufaCandidate(wrapper);

    await wrapper.get('[data-testid="add-symbol"]').trigger('click');
    await flushPromises();

    expect(api.addWatchlistPoolItem).toHaveBeenCalledWith({
      symbol: '600000.SH',
      name: '浦发银行',
      group: '人工关注',
      tags: []
    });
  });

  it('keeps add disabled for unmatched input and shows the empty result', async () => {
    api.searchStockSymbols.mockResolvedValueOnce(searchFixture());
    const wrapper = await mountView();
    const input = symbolSearchInput(wrapper);

    await input.setValue('不存在股票');
    expect(wrapper.text()).toContain('搜索中…');
    expect(wrapper.get('[data-testid="add-symbol"]').attributes('disabled')).toBeDefined();

    await vi.advanceTimersByTimeAsync(250);
    await flushPromises();

    expect(wrapper.text()).toContain('未找到匹配股票');
    await wrapper.get('[data-testid="add-symbol"]').trigger('click');
    expect(api.addWatchlistPoolItem).not.toHaveBeenCalled();
  });

  it('does not let an older PFYH response overwrite newer PAYH results', async () => {
    const firstRequest = deferred<ChanlunSymbolSearchResponse>();
    api.searchStockSymbols
      .mockReset()
      .mockReturnValueOnce(firstRequest.promise)
      .mockResolvedValueOnce(searchFixture([PINGAN]));
    const wrapper = await mountView();
    const input = symbolSearchInput(wrapper);

    await input.setValue('PFYH');
    await vi.advanceTimersByTimeAsync(250);
    expect(api.searchStockSymbols).toHaveBeenNthCalledWith(1, 'PFYH', { limit: 20 });

    await input.setValue('PAYH');
    await vi.advanceTimersByTimeAsync(250);
    await flushPromises();
    expect(wrapper.text()).toContain('平安银行');
    expect(wrapper.text()).not.toContain('浦发银行');

    firstRequest.resolve(searchFixture([PUFA]));
    await flushPromises();
    expect(wrapper.text()).toContain('平安银行');
    expect(wrapper.text()).not.toContain('浦发银行');
  });

  it('renders the current search error message', async () => {
    api.searchStockSymbols.mockRejectedValueOnce(new Error('远程搜索不可用'));
    const wrapper = await mountView();

    await symbolSearchInput(wrapper).setValue('PFYH');
    await vi.advanceTimersByTimeAsync(250);
    await flushPromises();

    expect(wrapper.text()).toContain('远程搜索不可用');
  });

  it.each([
    ['clearing', ''],
    ['changing', 'PAYH']
  ])('%s input after selection disables add again', async (_label, nextInput) => {
    const wrapper = await mountView();
    await selectPufaCandidate(wrapper);
    expect(wrapper.get('[data-testid="add-symbol"]').attributes('disabled')).toBeUndefined();

    await symbolSearchInput(wrapper).setValue(nextInput);

    expect(wrapper.get('[data-testid="add-symbol"]').attributes('disabled')).toBeDefined();
    await wrapper.get('[data-testid="add-symbol"]').trigger('click');
    expect(api.addWatchlistPoolItem).not.toHaveBeenCalled();
  });

  it('adds the selected candidate when Enter is pressed', async () => {
    const wrapper = await mountView();
    await selectPufaCandidate(wrapper);

    await symbolSearchInput(wrapper).trigger('keydown', { key: 'Enter' });
    await flushPromises();

    expect(api.addWatchlistPoolItem).toHaveBeenCalledWith({
      symbol: '600000.SH',
      name: '浦发银行',
      group: '人工关注',
      tags: []
    });
  });

  it('requires one Enter to select before a later Enter can add', async () => {
    const wrapper = await mountView();
    await renderPufaCandidate(wrapper);
    const input = symbolSearchInput(wrapper);

    await input.trigger('keydown', { key: 'Enter' });
    await flushPromises();

    expect(api.addWatchlistPoolItem).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="add-symbol"]').attributes('disabled')).toBeUndefined();
    expect((input.element as HTMLInputElement).value).toBe('600000.SH');

    await input.trigger('keydown', { key: 'Enter' });
    await flushPromises();

    expect(api.addWatchlistPoolItem).toHaveBeenCalledWith({
      symbol: '600000.SH',
      name: '浦发银行',
      group: '人工关注',
      tags: []
    });
  });

  it('cancels a queued search when the view unmounts', async () => {
    const wrapper = await mountView();
    await symbolSearchInput(wrapper).setValue('PFYH');

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(250);

    expect(api.searchStockSymbols).not.toHaveBeenCalled();
  });
});
