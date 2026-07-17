import type { KlineBar } from '@/service/types';

type DatedBar = {
  bar: KlineBar;
  dateKey: string;
  dateValue: number;
  index: number;
  weekKey: string;
};

export function aggregateWeeklyBars(bars: KlineBar[]): KlineBar[] {
  const datedBars = bars
    .map((bar, index) => toDatedBar(bar, index))
    .filter((value): value is DatedBar => value !== null)
    .sort((left, right) => left.dateValue - right.dateValue || left.index - right.index);
  const groups = new Map<string, DatedBar[]>();

  datedBars.forEach(item => {
    const group = groups.get(item.weekKey) ?? [];
    group.push(item);
    groups.set(item.weekKey, group);
  });

  return Array.from(groups, ([weekKey, group]) => {
    const first = group[0].bar;
    const last = group[group.length - 1].bar;
    const amounts = group.map(item => item.bar.amount);
    const amountValues = amounts.filter((value): value is number => value != null && Number.isFinite(value));
    const amount = amountValues.length === amounts.length
      ? amountValues.reduce((sum, value) => sum + value, 0)
      : null;

    return {
      date: weekKey,
      open: first.open,
      close: last.close,
      high: Math.max(...group.map(item => item.bar.high)),
      low: Math.min(...group.map(item => item.bar.low)),
      volume: group.reduce((sum, item) => sum + item.bar.volume, 0),
      amount,
      ma5: null,
      ma10: null,
      ma20: null,
      ma60: null
    };
  });
}

function toDatedBar(bar: KlineBar, index: number): DatedBar | null {
  const dateKey = toShanghaiDateKey(bar.date);
  if (dateKey === null || !isCompleteBar(bar)) {
    return null;
  }
  const dateValue = Number(dateKey.replaceAll('-', ''));
  return { bar, dateKey, dateValue, index, weekKey: mondayKey(dateKey) };
}

function isCompleteBar(bar: KlineBar): boolean {
  const values = [bar.open, bar.close, bar.high, bar.low, bar.volume];
  if (!values.every(value => Number.isFinite(value))) {
    return false;
  }
  if (bar.amount != null && !Number.isFinite(bar.amount)) {
    return false;
  }
  return bar.low <= Math.min(bar.open, bar.close) && bar.high >= Math.max(bar.open, bar.close);
}

function toShanghaiDateKey(value: string): string | null {
  const compact = /^(\d{4})(\d{2})(\d{2})$/.exec(value);
  if (compact) {
    return validDateKey(`${compact[1]}-${compact[2]}-${compact[3]}`);
  }

  const localDate = /^(\d{4}-\d{2}-\d{2})(?:$|T|\s)/.exec(value)?.[1];
  if (localDate && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(value)) {
    return validDateKey(localDate);
  }

  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return null;
  }
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).formatToParts(timestamp);
  const year = parts.find(part => part.type === 'year')?.value;
  const month = parts.find(part => part.type === 'month')?.value;
  const day = parts.find(part => part.type === 'day')?.value;
  return year && month && day ? validDateKey(`${year}-${month}-${day}`) : null;
}

function validDateKey(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
    ? value
    : null;
}

function mondayKey(dateKey: string): string {
  const [year, month, day] = dateKey.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  const weekday = date.getUTCDay();
  const daysFromMonday = weekday === 0 ? 6 : weekday - 1;
  date.setUTCDate(date.getUTCDate() - daysFromMonday);
  return [date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate()]
    .map((value, index) => String(value).padStart(index === 0 ? 4 : 2, '0'))
    .join('');
}
