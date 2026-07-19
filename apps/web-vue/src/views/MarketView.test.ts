// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MarketView from './MarketView.vue';

const navigation = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  route: { query: {} as Record<string, string> }
}));

const api = vi.hoisted(() => ({
  getHeatmapTreemap: vi.fn(),
  getSectorReplicaBoardStocks: vi.fn(),
  getSectorReplicaRadar: vi.fn()
}));

vi.mock('vue-router', () => ({
  useRoute: () => navigation.route,
  useRouter: () => ({ push: navigation.push, replace: navigation.replace })
}));
vi.mock('@/service/product-api', () => api);

const SegmentedStub = defineComponent({
  name: 'ASegmented',
  props: ['options', 'value'],
  emits: ['change'],
  template: `
    <div>
      <button
        v-for="option in options"
        :key="option.value"
        :data-value="option.value"
        @click="$emit('change', option.value)"
      >{{ option.label }}</button>
    </div>
  `
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('MarketView navigation', () => {
  it('opens ETF capital radar without writing it into the market view query', async () => {
    api.getSectorReplicaRadar.mockReturnValueOnce(new Promise(() => {}));
    const wrapper = mount(MarketView, {
      global: {
        stubs: {
          ASegmented: SegmentedStub,
          HeatmapTreemap: true,
          SectorRadarChart: true
        }
      }
    });

    const etfEntry = wrapper.find('button[data-value="etf"]');
    expect(etfEntry.exists()).toBe(true);

    await etfEntry.trigger('click');

    expect(navigation.push).toHaveBeenCalledWith('/etf-radar');
    expect(navigation.replace).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
