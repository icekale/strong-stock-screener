// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import type { EChartsOption } from 'echarts';
import type {
  EtfFactorEvidence,
  EtfThreeFactorHistoryResponse,
  EtfThreeFactorItem,
  EtfThreeFactorResponse
} from '@/service/types';
import EtfThreeFactorPanel from './EtfThreeFactorPanel.vue';

const ChartStub = defineComponent({
  name: 'EChart',
  props: ['option', 'height', 'loading'],
  template: '<div data-testid="three-factor-chart" />'
});

function factor(overrides: Partial<EtfFactorEvidence> = {}): EtfFactorEvidence {
  return {
    score: 90,
    value: 1.25,
    status: 'available',
    source: '交易所日线',
    data_date: '2026-07-18',
    updated_at: '2026-07-18T15:00:00+08:00',
    detail: '数据完整',
    ...overrides
  };
}

function item(index: number, overrides: Partial<EtfThreeFactorItem> = {}): EtfThreeFactorItem {
  const symbol = index === 4 ? '159915.SZ' : `${510050 + index * 50}.SH`;
  return {
    symbol,
    name: `核心ETF${index + 1}`,
    index_name: `指数${index + 1}`,
    index_symbol: `0000${index + 1}.SH`,
    close_change_pct: index % 2 === 0 ? 1.2 : -0.8,
    close_change_trade_date: '2026-07-18',
    intraday_change_pct: index % 2 === 0 ? 0.4 : -0.2,
    index_change_pct: 0.3,
    current_volume: 1_200_000_000,
    average_volume_20d: 800_000_000,
    volume_ratio: 1.5,
    share_change_pct: index === 4 ? null : 0.6,
    volume_factor: factor(),
    direction_factor: factor({ value: 0.4 }),
    share_factor: factor(index === 4 ? { status: 'pending', value: null, detail: null } : { value: 0.6 }),
    signal_score: 90 - index,
    mode: 'three_factor',
    level: index === 0 ? 'high' : 'medium',
    updated_at: '2026-07-18T15:00:00+08:00',
    ...overrides
  };
}

function snapshotFixture(): EtfThreeFactorResponse {
  return {
    generated_at: '2026-07-18T15:05:00+08:00',
    trade_date: '2026-07-18',
    as_of: '2026-07-18T15:00:00+08:00',
    signal_stage: 'post_close',
    model_version: 'three-factor-v1',
    source_status: [],
    summary: { signal_score: 90, level: 'high', valid_count: 7, high_count: 1, medium_count: 6, market_state: 'high' },
    items: Array.from({ length: 7 }, (_, index) => item(index)),
    monitor_running: true,
    last_scan_at: '2026-07-18T15:00:00+08:00'
  };
}

function historyFixture(symbol = '510050.SH'): EtfThreeFactorHistoryResponse {
  return {
    generated_at: '2026-07-18T15:05:00+08:00',
    trade_date: '2026-07-18',
    as_of: '2026-07-18T15:00:00+08:00',
    signal_stage: 'post_close',
    model_version: 'three-factor-v1',
    source_status: [],
    symbol,
    points: [
      { trade_date: '2026-07-16', symbol, close_change_pct: 0.4, volume: 700_000_000, average_volume_20d: 650_000_000, volume_ratio: 1.08, total_shares: 1_000_000_000, share_change_pct: 0.2, signal_score: 65, level: 'medium' },
      { trade_date: '2026-07-17', symbol, close_change_pct: null, volume: 900_000_000, average_volume_20d: 700_000_000, volume_ratio: 1.29, total_shares: null, share_change_pct: null, signal_score: 70, level: 'medium' },
      { trade_date: '2026-07-18', symbol, close_change_pct: 1.2, volume: 1_200_000_000, average_volume_20d: 800_000_000, volume_ratio: 1.5, total_shares: 1_006_000_000, share_change_pct: 0.6, signal_score: 90, level: 'high' }
    ]
  };
}

function mountPanel() {
  return mount(EtfThreeFactorPanel, {
    props: {
      snapshot: snapshotFixture(),
      history: historyFixture(),
      selectedSymbol: '510050.SH',
      historyLoading: false,
      historyError: null
    },
    global: { stubs: { EChart: ChartStub } }
  });
}

describe('EtfThreeFactorPanel', () => {
  it('renders the approved three-factor information hierarchy without confirmation language', () => {
    const wrapper = mountPanel();

    expect(wrapper.get('[data-testid="three-factor-summary"]').text()).toContain('综合信号强度');
    expect(wrapper.findAll('[data-testid="dragon-status"]')).toHaveLength(7);
    expect(wrapper.get('[data-testid="three-factor-table"]').text()).toContain('收盘涨跌');
    expect(wrapper.get('[data-testid="three-factor-table"]').text()).toContain('20日均量');
    expect(wrapper.get('[data-testid="factor-detail"]').text()).toContain('量能因子');
    expect(wrapper.findAll('[data-testid="three-factor-chart"]')).toHaveLength(3);
    expect(wrapper.get('[data-testid="signal-timeline"]').text()).toContain('HIGH');
    expect(wrapper.text()).toContain('疑似活动');
    expect(wrapper.text()).not.toContain('确认买入');
  });

  it('emits selection from the status strip and renders pending share evidence as post-close', async () => {
    const wrapper = mountPanel();
    const statuses = wrapper.findAll('[data-testid="dragon-status"]');

    await statuses[4]!.trigger('click');
    expect(wrapper.emitted('select')).toEqual([['159915.SZ']]);

    await wrapper.setProps({ selectedSymbol: '159915.SZ', history: historyFixture('159915.SZ') });
    expect(wrapper.get('[data-testid="factor-detail"]').text()).toContain('核心ETF5');
    expect(wrapper.get('[data-testid="factor-detail"]').text()).toContain('待盘后');
  });

  it('sorts the factor table by the selected numeric column', async () => {
    const wrapper = mountPanel();
    const names = () => wrapper.findAll('[data-testid="three-factor-table"] tbody strong').map(cell => cell.text());

    expect(names()[0]).toBe('核心ETF1');
    await wrapper.get('button[aria-label="信号强度 降序"]').trigger('click');

    expect(names()[0]).toBe('核心ETF7');
    expect(wrapper.find('button[aria-label="信号强度 升序"]').exists()).toBe(true);
  });

  it('passes concrete, synchronized, gap-preserving options to ECharts', () => {
    const wrapper = mountPanel();
    const [volumeOption, shareOption, comparisonOption] = wrapper
      .findAllComponents(ChartStub)
      .map(chart => chart.props('option') as EChartsOption);
    const expectedDates = ['2026-07-16', '2026-07-17', '2026-07-18'];
    const xAxisDates = (option: EChartsOption) => (option.xAxis as { data: string[] }).data;
    const series = (option: EChartsOption) => option.series as Array<{ connectNulls?: boolean; data: unknown[] }>;

    expect([volumeOption, shareOption, comparisonOption].every(option => option!.animation === false)).toBe(true);
    expect([volumeOption, shareOption, comparisonOption].map(option => xAxisDates(option!))).toEqual([
      expectedDates,
      expectedDates,
      expectedDates
    ]);
    expect(JSON.stringify([volumeOption, shareOption, comparisonOption])).not.toContain('var(--');
    expect(series(shareOption!)[0]!.data).toContain(null);
    expect(series(comparisonOption!)[0]!.data).toContain(null);
    expect(series(comparisonOption!)[1]!.data).toEqual([null, null, 0.3]);
    expect(series(comparisonOption!).every(item => item.connectNulls === false)).toBe(true);
  });
});
