// @vitest-environment jsdom

import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import type { HuijinEtfActivityItem } from '@/service/types';
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

  it('uses matching alignment classes for each header and data column', () => {
    const wrapper = mountTable();
    const headerCells = wrapper.findAll('thead th');
    const firstRowCells = wrapper.findAll('tbody tr')[0].findAll('th, td');

    expect(headerCells.map(cell => cell.classes())).toEqual([
      expect.arrayContaining(['etf-activity-table__cell--identity']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--status'])
    ]);
    expect(firstRowCells.map(cell => cell.classes())).toEqual([
      expect.arrayContaining(['etf-activity-table__cell--identity']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--numeric']),
      expect.arrayContaining(['etf-activity-table__cell--status'])
    ]);
  });

  it('keeps activity directions explicit as non-confirmatory proxies', () => {
    const activity = (direction: HuijinEtfActivityItem['direction']) => ({ direction }) as HuijinEtfActivityItem;
    const wrapper = mount(EtfActivityTable, {
      props: {
        rows: [
          row({ symbol: 'INCREASE', activity: activity('increase') }),
          row({ symbol: 'DECREASE', activity: activity('decrease') }),
          row({ symbol: 'FLAT', activity: activity('flat') }),
          row({ symbol: 'UNKNOWN', activity: activity('unknown') })
        ],
        selectedSymbol: 'INCREASE'
      }
    });

    const text = wrapper.get('[data-testid="etf-activity-table"]').text();
    expect(text).toContain('高确信 · +增加（申购代理）');
    expect(text).toContain('高确信 · -减少（赎回代理）');
    expect(text).not.toMatch(/· \+申购(?:\s|$)/);
    expect(text).not.toMatch(/· -赎回(?:\s|$)/);
    expect(text).toContain('高确信 · 持平');
    expect(text).toContain('高确信 · 待确认');
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

  it('shows tenfold direction tags and the 20-day multiple without shifting the columns', () => {
    const wrapper = mount(EtfActivityTable, {
      props: {
        rows: [
          row({
            symbol: 'BUY',
            activity: {
              direction: 'increase',
              is_tenfold_share_change: true,
              share_change_20d_multiple: 10
            } as HuijinEtfActivityItem
          }),
          row({
            symbol: 'SELL',
            activity: {
              direction: 'decrease',
              is_tenfold_share_change: true,
              share_change_20d_multiple: 11.25
            } as HuijinEtfActivityItem
          })
        ],
        selectedSymbol: 'BUY'
      }
    });

    expect(wrapper.get('[data-testid="activity-etf-row"][data-symbol="BUY"]').text()).toContain('10×申购');
    expect(wrapper.get('[data-testid="activity-etf-row"][data-symbol="BUY"]').text()).toContain('10.0倍');
    expect(wrapper.get('[data-testid="activity-etf-row"][data-symbol="SELL"]').text()).toContain('10×赎回');
    expect(wrapper.get('[data-testid="activity-etf-row"][data-symbol="SELL"]').text()).toContain('11.3倍');
    expect(wrapper.findAll('thead th')).toHaveLength(6 + 1);
  });
});
