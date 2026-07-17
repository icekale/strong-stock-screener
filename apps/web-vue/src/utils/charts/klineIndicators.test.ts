import { describe, expect, it } from 'vitest';
import type { KlineBar } from '@/service/types';
import {
  calculateAtr,
  calculateBias,
  calculateBrick,
  calculateCci,
  calculateDmi,
  calculateKdj,
  calculateMacd,
  calculateObv,
  calculateRoc,
  calculateRsi,
  calculateWr,
  type KlineIndicatorSeries
} from './klineIndicators';

const bars: KlineBar[] = Array.from({ length: 40 }, (_, index) => {
  const close = 20 + index * 0.25 + (index % 4) * 0.4;
  return {
    date: `2026-07-${String(index + 1).padStart(2, '0')}`,
    open: close - 0.3,
    close,
    high: close + 0.8 + (index % 3) * 0.1,
    low: close - 0.9 - (index % 2) * 0.1,
    volume: 1000 + index * 35,
    amount: close * (1000 + index * 35),
    ma5: null,
    ma10: null,
    ma20: null,
    ma60: null
  };
});

function sequences(result: KlineIndicatorSeries): Array<Array<number | null>> {
  return [result.values, ...(result.lines ?? []).map(line => line.values)];
}

function expectWindowedSeries(result: KlineIndicatorSeries): void {
  const values = sequences(result);
  expect(values.length).toBeGreaterThan(0);
  values.forEach(sequence => {
    expect(sequence).toHaveLength(bars.length);
    const firstFiniteIndex = sequence.findIndex(value => value !== null);
    expect(firstFiniteIndex).toBeGreaterThan(0);
    expect(sequence.slice(0, firstFiniteIndex)).toEqual(
      Array.from({ length: firstFiniteIndex }, () => null)
    );
    sequence.forEach(value => {
      expect(value === null || Number.isFinite(value)).toBe(true);
    });
    expect(sequence.some(value => value !== null)).toBe(true);
  });
}

describe('kline indicators', () => {
  it('returns fixed-length finite MACD, KDJ, RSI, WR and BIAS series', () => {
    [
      calculateMacd(bars, { short: 3, long: 5, signal: 2 }),
      calculateKdj(bars, { period: 5, kPeriod: 3, dPeriod: 3 }),
      calculateRsi(bars, { periods: [5, 7] }),
      calculateWr(bars, { periods: [5, 7] }),
      calculateBias(bars, { periods: [5, 7] })
    ].forEach(expectWindowedSeries);
  });

  it('returns fixed-length finite CCI, ATR, OBV, ROC, DMI and brick series', () => {
    [
      calculateCci(bars, { period: 5 }),
      calculateAtr(bars, { period: 5 }),
      calculateObv(bars, { maPeriod: 5 }),
      calculateRoc(bars, { period: 5, signalPeriod: 3 }),
      calculateDmi(bars, { period: 5, adxPeriod: 3 }),
      calculateBrick(bars, { period: 4 })
    ].forEach(expectWindowedSeries);
  });
});
