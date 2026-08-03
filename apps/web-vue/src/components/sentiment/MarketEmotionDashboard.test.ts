// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import type { MarketEmotionSnapshotResponse } from '@/service/types';
import MarketEmotionDashboard from './MarketEmotionDashboard.vue';

const EChartStub = defineComponent({
  name: 'EChart',
  props: ['option', 'height'],
  template: '<canvas data-testid="emotion-chart" />'
});

function snapshot(): MarketEmotionSnapshotResponse {
  return {
    trade_date: '2026-08-03',
    metrics: {
      emotion_score: 78,
      emotion_level: '良好',
      limit_up_count: 75,
      break_board_count: 24,
      limit_down_count: 6,
      losing_effect_score: null,
      max_consecutive_boards: 6,
      advance_count: 4005,
      decline_count: 1466,
      seal_rate_pct: 75.76,
      turnover_cny: 2_010_000_000_000,
      turnover_change_cny: null,
      turnover_change_pct: null,
      main_flow_cny: null,
      yesterday_limit_up_performance_pct: null,
      yesterday_ladder_performance_pct: null
    },
    buckets: [],
    samples: [
      {
        trade_date: '2026-08-03',
        sampled_at: '2026-08-03T10:00:00+08:00',
        emotion_score: 72,
        emotion_level: '良好',
        limit_up_count: 70,
        break_board_count: 20,
        limit_down_count: 5,
        losing_effect_score: null,
        max_consecutive_boards: 5,
        advance_count: 3800,
        decline_count: 1600,
        seal_rate_pct: 72,
        turnover_cny: 1_800_000_000_000,
        turnover_change_pct: null
      }
    ],
    source_status: [],
    notes: [],
    generated_at: '2026-08-03T10:00:00+08:00'
  };
}

function mountDashboard() {
  return mount(MarketEmotionDashboard, {
    props: { snapshot: snapshot() },
    global: {
      stubs: {
        EChart: EChartStub
      }
    }
  });
}

describe('MarketEmotionDashboard', () => {
  it('restores the market emotion hot and cold bands', () => {
    const wrapper = mountDashboard();

    expect(wrapper.find('[data-testid="market-emotion-dashboard"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('冰点');
    expect(wrapper.text()).toContain('一般');
    expect(wrapper.text()).toContain('良好');
    expect(wrapper.text()).toContain('火爆');
    expect(wrapper.text()).toContain('0 冰点 · 100 火爆');
    expect(wrapper.find('[data-testid="emotion-chart"]').exists()).toBe(true);
  });
});
