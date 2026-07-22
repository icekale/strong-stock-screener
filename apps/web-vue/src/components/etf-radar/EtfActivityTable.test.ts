// @vitest-environment jsdom

import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import type { UnifiedEtfActivityRow } from '@/utils/domain/etfThreeFactor';
import EtfActivityTable from './EtfActivityTable.vue';

function row(overrides: Partial<UnifiedEtfActivityRow> = {}): UnifiedEtfActivityRow {
  return {
    symbol: '510300.SH',
    name: '华泰柏瑞沪深300ETF',
    indexName: '沪深300',
    closeChangePct: 1.2,
    dailyChangePct: 0.8,
    baselineChangePct: 12.5,
    volumeRatio: 1.8,
    signalScore: 90,
    signalLevel: 'high',
    activity: null,
    factor: null,
    ...overrides
  };
}

const rows = [
  row({ symbol: '510300.SH', name: '沪深300ETF', signalScore: 90, closeChangePct: 1.2 }),
  row({ symbol: '510050.SH', name: '上证50ETF', signalScore: 70, closeChangePct: -0.4 }),
  row({ symbol: '159915.SZ', name: '创业板ETF', signalScore: null, closeChangePct: null })
];

function mountTable() {
  return mount(EtfActivityTable, { props: { rows, selectedSymbol: '510050.SH' } });
}

function rowSymbols(wrapper: ReturnType<typeof mountTable>) {
  return wrapper.findAll('[data-testid="activity-etf-row"]').map(item => item.attributes('data-symbol'));
}

describe('EtfActivityTable', () => {
  it('renders one semantic table with the unified ETF columns and default score order', () => {
    const wrapper = mountTable();

    expect(wrapper.findAll('table')).toHaveLength(1);
    expect(wrapper.findAll('[data-testid="activity-etf-row"]')).toHaveLength(3);
    expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('三因子评分');
    expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('ETF / 指数');
    expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('收盘涨跌');
    expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('份额日变化');
    expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('报告基线偏离');
    expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('20日量比');
    expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('状态');
    expect(rowSymbols(wrapper)).toEqual(['510300.SH', '510050.SH', '159915.SZ']);
  });

  it('sorts numeric columns with null values last in both directions', async () => {
    const wrapper = mountTable();
    const header = wrapper.get('button[aria-label="收盘涨跌 可排序"]');

    await header.trigger('click');
    expect(rowSymbols(wrapper)).toEqual(['510300.SH', '510050.SH', '159915.SZ']);
    await header.trigger('click');
    expect(rowSymbols(wrapper)).toEqual(['510050.SH', '510300.SH', '159915.SZ']);

    await wrapper.get('button[aria-label="份额日变化 可排序"]').trigger('click');
    expect(rowSymbols(wrapper)).toEqual(['510300.SH', '510050.SH', '159915.SZ']);
  });

  it('marks the selected row and emits selection from click and keyboard activation', async () => {
    const wrapper = mountTable();
    const selected = wrapper.find('[data-testid="activity-etf-row"][data-symbol="510050.SH"]');

    expect(selected.classes()).toContain('etf-activity-table__row--selected');
    await wrapper.find('[data-testid="activity-etf-row"][data-symbol="510300.SH"]').trigger('click');
    await wrapper
      .find('[data-testid="activity-etf-row"][data-symbol="159915.SZ"]')
      .trigger('keydown', { key: 'Enter' });
    await wrapper.find('[data-testid="activity-etf-row"][data-symbol="510050.SH"]').trigger('keydown', { key: ' ' });

    expect(wrapper.emitted('select')).toEqual([['510300.SH'], ['159915.SZ'], ['510050.SH']]);
  });

  it('renders signed direction values and explicit rise/fall classes', () => {
    const wrapper = mount(EtfActivityTable, {
      props: {
        rows: [row({ symbol: 'RISE', closeChangePct: 1.25, dailyChangePct: -0.5, baselineChangePct: 0 })],
        selectedSymbol: 'RISE'
      }
    });

    expect(wrapper.text()).toContain('+1.25%');
    expect(wrapper.text()).toContain('-0.50%');
    expect(wrapper.find('.etf-activity-table__value--rise').exists()).toBe(true);
    expect(wrapper.find('.etf-activity-table__value--fall').exists()).toBe(true);
  });
});
