// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
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
  navigation.route.query = {};
});

function mockSectorResponses() {
  api.getSectorReplicaRadar.mockResolvedValue({
    axis: ['09:30'],
    generated_at: '2026-07-29T09:30:00+08:00',
    plates: [{ code: '801220', name: '食品饮料', val: 100, ztcount: 1, display_value: '100' }],
    series: [{ name: '食品饮料', type: 'line', data: [100], smooth: true, showSymbol: false }]
  });
  api.getSectorReplicaBoardStocks.mockResolvedValue({
    board_code: '801220',
    sub_theme: null,
    rows: [],
    related_tags: [],
    source_status: [],
    generated_at: '2026-07-29T09:30:00+08:00'
  });
}

describe('MarketView sector-only workbench', () => {
  it('ignores the legacy heatmap query and renders the sector workbench', async () => {
    navigation.route.query = { view: 'heatmap' };
    mockSectorResponses();
    const wrapper = mount(MarketView, {
      global: {
        stubs: {
          ASegmented: SegmentedStub,
          HeatmapTreemap: true,
          SectorRadarChart: true
        }
      }
    });

    await flushPromises();

    expect(wrapper.text()).not.toContain('市场热图');
    expect(api.getHeatmapTreemap).not.toHaveBeenCalled();
    expect(api.getSectorReplicaRadar).toHaveBeenCalled();
    wrapper.unmount();
  });

  it('passes the selected board name when loading constituents', async () => {
    mockSectorResponses();
    const wrapper = mount(MarketView, {
      global: {
        stubs: {
          ASegmented: SegmentedStub,
          HeatmapTreemap: true,
          SectorRadarChart: true
        }
      }
    });

    await flushPromises();

    expect(api.getSectorReplicaBoardStocks).toHaveBeenCalledWith(
      '801220',
      expect.objectContaining({ boardName: '食品饮料', mode: 'strength', limit: 50 })
    );
    wrapper.unmount();
  });
});
