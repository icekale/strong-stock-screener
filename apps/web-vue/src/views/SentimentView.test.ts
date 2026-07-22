// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SentimentView from './SentimentView.vue';

const api = vi.hoisted(() => ({
  generateMarketSentimentAnalysis: vi.fn(),
  getMarketSentimentAnalysis: vi.fn(),
  getMarketSentimentPercentile: vi.fn(),
  getSentimentDecision: vi.fn(),
  getSentimentSummary: vi.fn(),
  getShortTermIntradaySentiment: vi.fn()
}));

vi.mock('@/service/product-api', () => api);

const PlainStub = defineComponent({
  props: ['title', 'items'],
  template:
    '<section><h2 v-if="title">{{ title }}</h2><slot name="meta" /><slot /><div v-for="item in items" :key="item.key">{{ item.label }} {{ item.value }}</div></section>'
});

const ButtonStub = defineComponent({
  name: 'AButton',
  props: ['loading'],
  emits: ['click'],
  template: '<button @click="$emit(\'click\')"><slot /></button>'
});

function mountView() {
  return mount(SentimentView, {
    global: {
      stubs: {
        AAlert: { props: ['title'], template: '<div role="alert">{{ title }}</div>' },
        AButton: ButtonStub,
        ADatePicker: true,
        DataList: PlainStub,
        EChart: true,
        MetricStrip: PlainStub,
        PageHeader: PlainStub,
        RouterLink: true,
        SectionHeader: PlainStub,
        StatusTag: true
      }
    }
  });
}

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false }))
  );
  api.getMarketSentimentPercentile.mockRejectedValue(new Error('percentile unavailable'));
  api.getMarketSentimentAnalysis.mockResolvedValue({ status: 'not_generated' });
  api.getSentimentSummary.mockResolvedValue({
    metrics: {
      emotion_score: 72,
      emotion_level: '主升',
      limit_up_count: 68,
      break_board_count: 12,
      max_consecutive_boards: 5,
      advance_count: 3210,
      decline_count: 1780,
      seal_rate_pct: 82
    }
  });
  api.getSentimentDecision.mockResolvedValue({
    trade_permission: '轻仓试错',
    market_state: '修复',
    risk_level: '中',
    confidence: 0.72,
    score_change: 3.1,
    main_sectors: [],
    generated_at: '2026-07-22T15:20:00+08:00'
  });
  api.getShortTermIntradaySentiment.mockResolvedValue({ items: [], generated_at: '2026-07-22T15:20:00+08:00' });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('SentimentView percentile integration', () => {
  it('keeps existing sentiment content usable when percentile loading fails', async () => {
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain('市场情绪百分位更新失败');
    expect(wrapper.text()).toContain('涨停家数 68');
    expect(wrapper.text()).toContain('轻仓试错');
    expect(wrapper.text()).toContain('主线信号');
    expect(wrapper.text()).toContain('盘中提醒');
    expect(api.getSentimentSummary).toHaveBeenCalledOnce();
    expect(api.getSentimentDecision).toHaveBeenCalledOnce();
    expect(api.getShortTermIntradaySentiment).toHaveBeenCalledOnce();
  });

  it('places the percentile panel before metrics and refreshes it only from the explicit action', async () => {
    const wrapper = mountView();
    await flushPromises();

    const percentile = wrapper.get('[data-testid="sentiment-percentile-panel"]');
    const metrics = wrapper.get('[data-testid="sentiment-metrics"]');
    expect(percentile.element.nextElementSibling).toBe(metrics.element);
    expect(api.getMarketSentimentPercentile).toHaveBeenCalledWith(expect.any(String), false);

    await wrapper.get('[data-testid="sentiment-refresh"]').trigger('click');
    await flushPromises();
    expect(api.getMarketSentimentPercentile).toHaveBeenLastCalledWith(expect.any(String), true);
  });
});
