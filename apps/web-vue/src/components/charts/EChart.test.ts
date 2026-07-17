// @vitest-environment jsdom

import { mount } from '@vue/test-utils';
import type { EChartsOption } from 'echarts';
import { nextTick } from 'vue';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import EChart from './EChart.vue';

const mocks = vi.hoisted(() => {
  const chart = {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispatchAction: vi.fn(),
    dispose: vi.fn(),
    on: vi.fn(),
    showLoading: vi.fn(),
    hideLoading: vi.fn()
  };
  return { chart, init: vi.fn(() => chart) };
});

vi.mock('echarts', () => ({ init: mocks.init }));

const resizeObserver = {
  callback: null as ResizeObserverCallback | null,
  observe: vi.fn(),
  disconnect: vi.fn()
};

class FakeResizeObserver {
  constructor(callback: ResizeObserverCallback) {
    resizeObserver.callback = callback;
  }

  observe(target: Element) {
    resizeObserver.observe(target);
  }

  disconnect() {
    resizeObserver.disconnect();
  }
}

beforeEach(() => {
  Object.values(mocks.chart).forEach(mock => mock.mockClear());
  mocks.init.mockClear();
  resizeObserver.callback = null;
  resizeObserver.observe.mockClear();
  resizeObserver.disconnect.mockClear();
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it('wires EChart rendering, exposed controls, and cleanup to the chart instance', async () => {
  const option = { animation: false, series: [{ type: 'line', data: [1, 2] }] } satisfies EChartsOption;
  const wrapper = mount(EChart, { props: { option } });
  await nextTick();
  await nextTick();

  expect(mocks.init).toHaveBeenCalledOnce();
  expect(mocks.chart.setOption).toHaveBeenCalledWith(option, true);
  expect(resizeObserver.observe).toHaveBeenCalledWith(wrapper.element);
  expect(resizeObserver.callback).not.toBeNull();
  resizeObserver.callback?.([] as ResizeObserverEntry[], {} as ResizeObserver);
  expect(mocks.chart.resize).toHaveBeenCalledOnce();

  const exposed = wrapper.vm as unknown as { resize: () => void; restore: () => void };
  exposed.resize();
  exposed.restore();

  expect(mocks.chart.resize).toHaveBeenCalledTimes(2);
  expect(mocks.chart.dispatchAction).toHaveBeenCalledWith({ type: 'dataZoom', start: 0, end: 100 });

  wrapper.unmount();

  expect(resizeObserver.disconnect).toHaveBeenCalledOnce();
  expect(mocks.chart.dispose).toHaveBeenCalledOnce();
});
