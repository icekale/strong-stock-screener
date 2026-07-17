import { describe, expect, it } from 'vitest';
import type { KlineBar } from '@/service/types';
import { aggregateWeeklyBars } from './klinePeriod';

const bar = (date: string, open: number, close: number, high: number, low: number, volume: number, amount: number): KlineBar => ({
  date,
  open,
  close,
  high,
  low,
  volume,
  amount,
  ma5: close - 0.1,
  ma10: close - 0.2,
  ma20: close - 0.3,
  ma60: close - 0.4
});

describe('aggregateWeeklyBars', () => {
  it('sorts daily bars and aggregates OHLCV and amount by Shanghai trading week', () => {
    const bars = aggregateWeeklyBars([
      bar('20260717', 13, 14, 15, 12, 300, 3000),
      bar('20260713', 10, 11, 12, 9, 100, 1000),
      bar('20260716', 12, 13, 14, 11, 200, 2000),
      bar('20260720', 14, 15, 16, 13, 400, 4000),
      bar('20260715', 11, 12, 13, 10, 150, 1500)
    ]);

    expect(bars).toHaveLength(2);
    expect(bars[0]).toMatchObject({
      date: '20260713',
      open: 10,
      close: 14,
      high: 15,
      low: 9,
      volume: 750,
      amount: 7500,
      ma5: null,
      ma10: null,
      ma20: null,
      ma60: null
    });
    expect(bars[1]).toMatchObject({
      date: '20260720',
      open: 14,
      close: 15,
      high: 16,
      low: 13,
      volume: 400,
      amount: 4000
    });
  });

  it('returns no phantom weekly bar for empty or incomplete input', () => {
    const incomplete = { date: '20260713', open: 10 } as KlineBar;

    expect(aggregateWeeklyBars([])).toEqual([]);
    expect(aggregateWeeklyBars([incomplete])).toEqual([]);
  });
});
