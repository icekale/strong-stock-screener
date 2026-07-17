import type { KlineBar } from '@/service/types';

export type KlineIndicatorValue = number | null;
export type KlineIndicatorLine = { name: string; values: KlineIndicatorValue[] };
export type KlineIndicatorSeries = {
  name: string;
  values: KlineIndicatorValue[];
  lines?: KlineIndicatorLine[];
};

export type MacdOptions = { short?: number; long?: number; signal?: number };
export type KdjOptions = { period?: number; kPeriod?: number; dPeriod?: number };
export type MultiPeriodOptions = { periods?: number[] };
export type PeriodOptions = { period?: number };
export type ObvOptions = { maPeriod?: number };
export type RocOptions = { period?: number; signalPeriod?: number };
export type DmiOptions = { period?: number; adxPeriod?: number };

export function calculateMacd(bars: KlineBar[], options: MacdOptions = {}): KlineIndicatorSeries {
  const short = positivePeriod(options.short, 12);
  const long = Math.max(short + 1, positivePeriod(options.long, 26));
  const signal = positivePeriod(options.signal, 9);
  const closes = bars.map(bar => finiteOrNull(bar.close));
  const shortEma = exponentialAverage(closes, short);
  const longEma = exponentialAverage(closes, long);
  const dif = closes.map((_, index) => finitePair(shortEma[index], longEma[index], (left, right) => left - right));
  const dea = exponentialAverage(dif, signal);
  const macd = dif.map((value, index) => finitePair(value, dea[index], (left, right) => 2 * (left - right)));
  return {
    name: 'MACD',
    values: macd,
    lines: [
      { name: 'DIF', values: dif },
      { name: 'DEA', values: dea }
    ]
  };
}

export function calculateKdj(bars: KlineBar[], options: KdjOptions = {}): KlineIndicatorSeries {
  const period = positivePeriod(options.period, 9);
  const kPeriod = positivePeriod(options.kPeriod, 3);
  const dPeriod = positivePeriod(options.dPeriod, 3);
  const rsv = bars.map((bar, index) => {
    if (index < period - 1) {
      return null;
    }
    const window = bars.slice(index - period + 1, index + 1);
    const high = Math.max(...window.map(item => item.high));
    const low = Math.min(...window.map(item => item.low));
    if (![bar.close, high, low].every(Number.isFinite)) {
      return null;
    }
    return high === low ? 50 : finiteOrNull(((bar.close - low) / (high - low)) * 100);
  });
  const k = exponentialAverage(rsv, kPeriod);
  const d = exponentialAverage(k, dPeriod);
  const j = k.map((value, index) => finitePair(value, d[index], (left, right) => 3 * left - 2 * right));
  return { name: 'KDJ', values: j, lines: [{ name: 'K', values: k }, { name: 'D', values: d }] };
}

export function calculateRsi(bars: KlineBar[], options: MultiPeriodOptions = {}): KlineIndicatorSeries {
  const periods = normalizedPeriods(options.periods, [6, 12, 24]);
  const results = periods.map(period => calculateRsiPeriod(bars, period));
  return multiPeriodSeries('RSI', periods, results);
}

export function calculateWr(bars: KlineBar[], options: MultiPeriodOptions = {}): KlineIndicatorSeries {
  const periods = normalizedPeriods(options.periods, [6, 10]);
  const results = periods.map(period =>
    bars.map((bar, index) => {
      if (index < period - 1) {
        return null;
      }
      const window = bars.slice(index - period + 1, index + 1);
      const high = Math.max(...window.map(item => item.high));
      const low = Math.min(...window.map(item => item.low));
      if (![bar.close, high, low].every(Number.isFinite)) {
        return null;
      }
      return high === low ? 0 : finiteOrNull(((high - bar.close) / (high - low)) * -100);
    })
  );
  return multiPeriodSeries('WR', periods, results);
}

export function calculateBias(bars: KlineBar[], options: MultiPeriodOptions = {}): KlineIndicatorSeries {
  const periods = normalizedPeriods(options.periods, [6, 12, 24]);
  const results = periods.map(period =>
    bars.map((bar, index) => {
      const average = rollingAverage(bars.slice(Math.max(0, index - period + 1), index + 1).map(item => item.close), period);
      return finitePair(finiteOrNull(bar.close), average[average.length - 1], (close, ma) => ma === 0 ? 0 : ((close - ma) / ma) * 100);
    })
  );
  return multiPeriodSeries('BIAS', periods, results);
}

export function calculateCci(bars: KlineBar[], options: PeriodOptions = {}): KlineIndicatorSeries {
  const period = positivePeriod(options.period, 14);
  const values = bars.map((bar, index) => {
    if (index < period - 1) {
      return null;
    }
    const window = bars.slice(index - period + 1, index + 1);
    const typicalPrices = window.map(item => (item.high + item.low + item.close) / 3);
    if (!typicalPrices.every(Number.isFinite)) {
      return null;
    }
    const average = typicalPrices.reduce((sum, value) => sum + value, 0) / period;
    const deviation = typicalPrices.reduce((sum, value) => sum + Math.abs(value - average), 0) / period;
    const current = typicalPrices[typicalPrices.length - 1];
    return deviation === 0 ? 0 : finiteOrNull((current - average) / (0.015 * deviation));
  });
  return { name: 'CCI', values };
}

export function calculateAtr(bars: KlineBar[], options: PeriodOptions = {}): KlineIndicatorSeries {
  const period = positivePeriod(options.period, 14);
  const tr = bars.map((bar, index) => {
    if (index === 0) {
      return null;
    }
    const previousClose = bars[index - 1]?.close;
    if (![bar.high, bar.low, previousClose].every(Number.isFinite)) {
      return null;
    }
    return finiteOrNull(Math.max(bar.high - bar.low, Math.abs(bar.high - previousClose), Math.abs(bar.low - previousClose)));
  });
  const atr = rollingAverage(tr, period);
  return { name: 'ATR', values: atr, lines: [{ name: 'TR', values: tr }] };
}

export function calculateObv(bars: KlineBar[], options: ObvOptions = {}): KlineIndicatorSeries {
  const maPeriod = positivePeriod(options.maPeriod, 30);
  const obv = bars.map((bar, index) => {
    if (index === 0 || !Number.isFinite(bar.close) || !Number.isFinite(bar.volume) || bar.volume < 0) {
      return null;
    }
    const previous = bars[index - 1];
    const previousObv = index === 1 ? 0 : null;
    const priorValue = previousObv ?? (index > 1 ? obvAt(bars, index - 1) : null);
    if (priorValue === null || !Number.isFinite(previous.close)) {
      return null;
    }
    return priorValue + (bar.close > previous.close ? bar.volume : bar.close < previous.close ? -bar.volume : 0);
  });
  const obvMa = rollingAverage(obv, maPeriod);
  return { name: 'OBV', values: obv, lines: [{ name: 'OBV MA', values: obvMa }] };
}

export function calculateRoc(bars: KlineBar[], options: RocOptions = {}): KlineIndicatorSeries {
  const period = positivePeriod(options.period, 12);
  const signalPeriod = positivePeriod(options.signalPeriod, 6);
  const roc = bars.map((bar, index) => {
    const previousClose = bars[index - period]?.close;
    if (previousClose == null || !Number.isFinite(bar.close) || !Number.isFinite(previousClose) || previousClose === 0) {
      return null;
    }
    return finiteOrNull(((bar.close - previousClose) / previousClose) * 100);
  });
  return { name: 'ROC', values: roc, lines: [{ name: 'Signal', values: exponentialAverage(roc, signalPeriod) }] };
}

export function calculateDmi(bars: KlineBar[], options: DmiOptions = {}): KlineIndicatorSeries {
  const period = positivePeriod(options.period, 14);
  const adxPeriod = positivePeriod(options.adxPeriod, period);
  const trueRange = bars.map((bar, index) => index === 0 ? null : trueRangeAt(bar, bars[index - 1]));
  const plusDm = bars.map((bar, index) => directionMovement(bar, bars[index - 1], 'plus'));
  const minusDm = bars.map((bar, index) => directionMovement(bar, bars[index - 1], 'minus'));
  const smoothedTr = wilderAverage(trueRange, period);
  const smoothedPlus = wilderAverage(plusDm, period);
  const smoothedMinus = wilderAverage(minusDm, period);
  const pdi = smoothedPlus.map((value, index) => finitePair(value, smoothedTr[index], (plus, tr) => tr === 0 ? 0 : (plus / tr) * 100));
  const mdi = smoothedMinus.map((value, index) => finitePair(value, smoothedTr[index], (minus, tr) => tr === 0 ? 0 : (minus / tr) * 100));
  const dx = pdi.map((plus, index) => finitePair(plus, mdi[index], (pdiValue, mdiValue) => {
    const total = pdiValue + mdiValue;
    return total === 0 ? 0 : (Math.abs(pdiValue - mdiValue) / total) * 100;
  }));
  const adx = wilderAverage(dx, adxPeriod);
  const adxr = adx.map((value, index) => index < adxPeriod ? null : finitePair(value, adx[index - adxPeriod], (current, previous) => (current + previous) / 2));
  return {
    name: 'DMI',
    values: adx,
    lines: [
      { name: '+DI', values: pdi },
      { name: '-DI', values: mdi },
      { name: 'ADXR', values: adxr }
    ]
  };
}

export function calculateBrick(bars: KlineBar[], options: PeriodOptions = {}): KlineIndicatorSeries {
  const period = positivePeriod(options.period, 4);
  const first = bars.map((bar, index) => {
    if (index < period - 1) {
      return null;
    }
    const window = bars.slice(index - period + 1, index + 1);
    const highestHigh = Math.max(...window.map(item => item.high));
    const lowestLow = Math.min(...window.map(item => item.low));
    if (![bar.close, highestHigh, lowestLow].every(Number.isFinite)) {
      return null;
    }
    const range = highestHigh - lowestLow;
    return range === 0 ? 0 : ((highestHigh - bar.close) / range) * 100 - 90;
  });
  const second = bars.map((bar, index) => {
    if (index < period - 1) {
      return null;
    }
    const window = bars.slice(index - period + 1, index + 1);
    const highestHigh = Math.max(...window.map(item => item.high));
    const lowestLow = Math.min(...window.map(item => item.low));
    if (![bar.close, highestHigh, lowestLow].every(Number.isFinite)) {
      return null;
    }
    const range = highestHigh - lowestLow;
    return range === 0 ? 0 : ((bar.close - lowestLow) / range) * 100;
  });
  const var2 = exponentialAverage(first, 4);
  const var4 = exponentialAverage(second, 6);
  const var5 = exponentialAverage(var4, 6);
  const values = var5.map((value, index) => finitePair(value, var2[index], (slow, fast) => Math.max(0, slow + 100 - (fast + 100) - 4)));
  return { name: '砖形图', values };
}

function calculateRsiPeriod(bars: KlineBar[], period: number): KlineIndicatorValue[] {
  const values: KlineIndicatorValue[] = Array.from({ length: bars.length }, () => null);
  let averageGain: number | null = null;
  let averageLoss: number | null = null;
  for (let index = 1; index < bars.length; index += 1) {
    const current = bars[index]?.close;
    const previous = bars[index - 1]?.close;
    if (![current, previous].every(Number.isFinite)) {
      averageGain = null;
      averageLoss = null;
      continue;
    }
    const gain = Math.max(current - previous, 0);
    const loss = Math.max(previous - current, 0);
    if (index < period) {
      continue;
    }
    if (averageGain === null || averageLoss === null) {
      const changes = bars.slice(index - period, index + 1).map((bar, offset, window) => {
        if (offset === 0) {
          return [0, 0];
        }
        const difference = bar.close - window[offset - 1].close;
        return [Math.max(difference, 0), Math.max(-difference, 0)];
      });
      averageGain = changes.reduce((sum, pair) => sum + pair[0], 0) / period;
      averageLoss = changes.reduce((sum, pair) => sum + pair[1], 0) / period;
    } else {
      averageGain = (averageGain * (period - 1) + gain) / period;
      averageLoss = (averageLoss * (period - 1) + loss) / period;
    }
    values[index] = averageLoss === 0 ? (averageGain === 0 ? 50 : 100) : finiteOrNull(100 - 100 / (1 + averageGain / averageLoss));
  }
  return values;
}

function multiPeriodSeries(name: string, periods: number[], values: KlineIndicatorValue[][]): KlineIndicatorSeries {
  return {
    name,
    values: values[0] ?? [],
    lines: periods.slice(1).map((period, index) => ({ name: `${name}${period}`, values: values[index + 1] ?? [] }))
  };
}

function normalizedPeriods(periods: number[] | undefined, fallback: number[]): number[] {
  const values = periods?.filter(period => Number.isInteger(period) && period > 0) ?? fallback;
  return values.length > 0 ? values : fallback;
}

function positivePeriod(value: number | undefined, fallback: number): number {
  return Number.isInteger(value) && (value ?? 0) > 0 ? value as number : fallback;
}

function finiteOrNull(value: number): number | null {
  return Number.isFinite(value) ? value : null;
}

function finitePair(left: number | null | undefined, right: number | null | undefined, operation: (left: number, right: number) => number): number | null {
  if (left == null || right == null || !Number.isFinite(left) || !Number.isFinite(right)) {
    return null;
  }
  return finiteOrNull(operation(left, right));
}

function rollingAverage(values: KlineIndicatorValue[], period: number): KlineIndicatorValue[] {
  return values.map((_, index) => {
    if (index < period - 1) {
      return null;
    }
    const window = values.slice(index - period + 1, index + 1);
    return window.every(value => value != null && Number.isFinite(value))
      ? finiteOrNull(window.reduce((sum: number, value) => sum + (value ?? 0), 0) / period)
      : null;
  });
}

function exponentialAverage(values: KlineIndicatorValue[], period: number): KlineIndicatorValue[] {
  const result: KlineIndicatorValue[] = Array.from({ length: values.length }, () => null);
  values.forEach((value, index) => {
    if (value == null || !Number.isFinite(value)) {
      return;
    }
    const previous = result[index - 1];
    if (previous != null) {
      result[index] = finiteOrNull((value * 2 + previous * (period - 1)) / (period + 1));
      return;
    }
    const window = values.slice(index - period + 1, index + 1);
    if (window.length === period && window.every(item => item != null && Number.isFinite(item))) {
      result[index] = finiteOrNull(window.reduce((sum: number, item) => sum + (item ?? 0), 0) / period);
    }
  });
  return result;
}

function wilderAverage(values: KlineIndicatorValue[], period: number): KlineIndicatorValue[] {
  const result: KlineIndicatorValue[] = Array.from({ length: values.length }, () => null);
  values.forEach((value, index) => {
    if (value == null || !Number.isFinite(value)) {
      return;
    }
    const previous = result[index - 1];
    if (previous != null) {
      result[index] = finiteOrNull((previous * (period - 1) + value) / period);
      return;
    }
    const window = values.slice(index - period + 1, index + 1);
    if (window.length === period && window.every(item => item != null && Number.isFinite(item))) {
      result[index] = finiteOrNull(window.reduce((sum: number, item) => sum + (item ?? 0), 0) / period);
    }
  });
  return result;
}

function trueRangeAt(bar: KlineBar, previous: KlineBar | undefined): number | null {
  if (!previous || ![bar.high, bar.low, previous.close].every(Number.isFinite)) {
    return null;
  }
  return finiteOrNull(Math.max(bar.high - bar.low, Math.abs(bar.high - previous.close), Math.abs(bar.low - previous.close)));
}

function directionMovement(
  bar: KlineBar,
  previous: KlineBar | undefined,
  direction: 'plus' | 'minus'
): number | null {
  if (!previous || ![bar.high, bar.low, previous.high, previous.low].every(Number.isFinite)) {
    return null;
  }
  const upMove = bar.high - previous.high;
  const downMove = previous.low - bar.low;
  if (direction === 'plus') {
    return upMove > downMove && upMove > 0 ? upMove : 0;
  }
  return downMove > upMove && downMove > 0 ? downMove : 0;
}

function obvAt(bars: KlineBar[], index: number): number | null {
  let value = 0;
  for (let cursor = 1; cursor <= index; cursor += 1) {
    const current = bars[cursor];
    const previous = bars[cursor - 1];
    if (!current || !previous || ![current.close, previous.close, current.volume].every(Number.isFinite) || current.volume < 0) {
      return null;
    }
    value += current.close > previous.close ? current.volume : current.close < previous.close ? -current.volume : 0;
  }
  return value;
}
