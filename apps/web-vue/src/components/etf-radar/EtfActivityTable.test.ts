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

const sortableRows = [
  row({ symbol: 'A', closeChangePct: 3, dailyChangePct: -3, baselineChangePct: 30, volumeRatio: 3, signalScore: 90 }),
  row({ symbol: 'B', closeChangePct: 1, dailyChangePct: 1, baselineChangePct: 10, volumeRatio: 1, signalScore: 70 }),
  row({ symbol: 'C', closeChangePct: -1, dailyChangePct: -1, baselineChangePct: -10, volumeRatio: 2, signalScore: 50 }),
  row({
    symbol: 'NULL',
    closeChangePct: null,
    dailyChangePct: null,
    baselineChangePct: null,
    volumeRatio: null,
    signalScore: null
  })
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

  it('sorts every numeric column with null values last in both directions', async () => {
    const cases = [
      ['收盘涨跌', ['A', 'B', 'C', 'NULL'], ['C', 'B', 'A', 'NULL']],
      ['份额日变化', ['B', 'C', 'A', 'NULL'], ['A', 'C', 'B', 'NULL']],
      ['报告基线偏离', ['A', 'B', 'C', 'NULL'], ['C', 'B', 'A', 'NULL']],
      ['20日量比', ['A', 'C', 'B', 'NULL'], ['B', 'C', 'A', 'NULL']],
      ['三因子评分', ['A', 'B', 'C', 'NULL'], ['C', 'B', 'A', 'NULL']]
    ] as const;

    await Promise.all(
      cases.map(async ([label, descending, ascending]) => {
        const wrapper = mount(EtfActivityTable, { props: { rows: sortableRows, selectedSymbol: 'A' } });
        const header = wrapper.get(`button[aria-label^="${label}"]`);

        if (label === '三因子评分') {
          expect(rowSymbols(wrapper), `${label} default descending`).toEqual(descending);
        }
        await header.trigger('click');
        expect(rowSymbols(wrapper), `${label} first sort`).toEqual(label === '三因子评分' ? ascending : descending);
        await header.trigger('click');
        expect(rowSymbols(wrapper), `${label} second sort`).toEqual(label === '三因子评分' ? descending : ascending);
      })
    );
  });

  it('uses a selected identity button with native keyboard semantics and no duplicate bubbling emission', async () => {
    const wrapper = mountTable();
    const selected = wrapper.find('[data-testid="activity-etf-row"][data-symbol="510050.SH"]');
    const selectedButton = selected.get('button[data-testid="activity-etf-select"]');

    expect(selected.classes()).toContain('etf-activity-table__row--selected');
    expect(selectedButton.attributes('type')).toBe('button');
    expect(selectedButton.attributes('aria-pressed')).toBe('true');
    expect(selectedButton.attributes('aria-label')).toContain('上证50ETF');

    const unselectedButton = wrapper
      .find('[data-testid="activity-etf-row"][data-symbol="510300.SH"]')
      .get('button[data-testid="activity-etf-select"]');
    expect(unselectedButton.attributes('aria-pressed')).toBe('false');

    await wrapper.find('[data-testid="activity-etf-row"][data-symbol="510300.SH"]').trigger('click');
    expect(wrapper.emitted('select')).toEqual([['510300.SH']]);

    await unselectedButton.trigger('click');
    expect(wrapper.emitted('select')).toEqual([['510300.SH'], ['510300.SH']]);

    await unselectedButton.trigger('keydown', { key: 'Enter' });
    await unselectedButton.trigger('click');
    await unselectedButton.trigger('keydown', { key: ' ' });
    await unselectedButton.trigger('click');

    expect(wrapper.emitted('select')).toEqual([['510300.SH'], ['510300.SH'], ['510300.SH'], ['510300.SH']]);
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
