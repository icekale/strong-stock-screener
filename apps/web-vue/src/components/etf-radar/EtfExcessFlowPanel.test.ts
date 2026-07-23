// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import type { EChartsOption } from 'echarts';
import type { EtfExcessFlowResponse } from '@/service/types';
import EtfExcessFlowPanel from './EtfExcessFlowPanel.vue';

const ChartStub = defineComponent({
  name: 'EChart',
  props: ['option', 'height', 'loading'],
  template: '<div data-testid="excess-flow-chart" />'
});

function response(): EtfExcessFlowResponse {
  return {
    generated_at: '2026-07-23T15:05:00+08:00',
    trade_date: '2026-07-23',
    as_of: '2026-07-23T15:00:00+08:00',
    signal_stage: 'post_close',
    model_version: 'etf-excess-flow-v1',
    source_status: [],
    formula: 'formula',
    expected_count: 2,
    points: [
      {
        trade_date: '2026-07-23',
        net_excess_flow_cny: 120_000_000,
        excess_inflow_cny: 200_000_000,
        excess_outflow_cny: 80_000_000,
        coverage_count: 2,
        expected_count: 2,
        tenfold_increase_count: 1,
        tenfold_decrease_count: 0,
        trigger_symbols: ['510050.SH']
      }
    ]
  };
}

function mountPanel(props: Partial<{ response: EtfExcessFlowResponse | null; loading: boolean; error: string | null }> = {}) {
  return mount(EtfExcessFlowPanel, {
    props: { response: response(), loading: false, error: null, ...props },
    global: { stubs: { EChart: ChartStub } }
  });
}

describe('EtfExcessFlowPanel', () => {
  it('renders the aggregate trend and coverage without claiming confirmed activity', () => {
    const wrapper = mountPanel();
    expect(wrapper.find('[data-testid="excess-flow-chart"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('覆盖 2 / 2');
    expect(wrapper.text()).toContain('十倍量：510050.SH');
    expect(wrapper.text()).not.toContain('确认买入');
    const option = wrapper.getComponent(ChartStub).props('option') as EChartsOption;
    const series = option.series as Array<{ data?: unknown[] }>;
    expect(series).toHaveLength(4);
    expect(series[2]?.data).toEqual([-80_000_000]);
    expect(series[3]?.data).toEqual([{ value: ['2026-07-23', 120_000_000], symbols: '510050.SH' }]);
    const formatter = (option.tooltip as { formatter: (params: unknown) => string }).formatter;
    expect(formatter({ axisValue: '2026-07-23' })).toContain('覆盖：2 / 2');
    expect(formatter({ axisValue: '2026-07-23' })).toContain('十倍量：510050.SH');
  });

  it('keeps independent loading, error, and empty states', async () => {
    const wrapper = mountPanel({ response: null, loading: true });
    expect(wrapper.get('[data-testid="etf-excess-flow-loading"]').text()).toContain('正在读取');

    await wrapper.setProps({ loading: false, error: '趋势请求失败' });
    expect(wrapper.get('[data-testid="etf-excess-flow-empty"]').text()).toContain('暂无');
    expect(wrapper.text()).toContain('趋势请求失败');

    await wrapper.setProps({ response: { ...response(), points: [] } });
    expect(wrapper.find('[data-testid="etf-excess-flow-empty"]').exists()).toBe(true);

    await wrapper.setProps({
      response: {
        ...response(),
        points: [{ ...response().points[0]!, net_excess_flow_cny: null, excess_inflow_cny: null, excess_outflow_cny: null }]
      }
    });
    expect(wrapper.find('[data-testid="etf-excess-flow-empty"]').exists()).toBe(true);
  });
});
