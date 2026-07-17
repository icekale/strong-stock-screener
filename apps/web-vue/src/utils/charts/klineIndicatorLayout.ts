export type KlineMovingAverage = 'ma5' | 'ma10' | 'ma20' | 'ma60';
export type KlineSubIndicator =
  | 'volume'
  | 'macd'
  | 'kdj'
  | 'rsi'
  | 'wr'
  | 'bias'
  | 'cci'
  | 'atr'
  | 'obv'
  | 'roc'
  | 'dmi'
  | 'brick';
export type KlineSubPaneCount = 1 | 2 | 3;
export type KlineIndicatorType = KlineMovingAverage | KlineSubIndicator | 'ma';
export type IndicatorOptions = Record<string, Record<string, unknown>>;
export type PaneConfig = { id: string; height: string; indicators: KlineIndicatorType[] };
export type KlinePaneLayout = { main: string; sub: string };
export type KlineIndicatorState = { paneCount: KlineSubPaneCount; subIndicators: KlineSubIndicator[] };

export const KLINE_SUB_INDICATOR_OPTIONS: Array<{ label: string; value: KlineSubIndicator }> = [
  { label: '成交量', value: 'volume' },
  { label: 'MACD', value: 'macd' },
  { label: 'KDJ', value: 'kdj' },
  { label: 'RSI', value: 'rsi' },
  { label: 'WR', value: 'wr' },
  { label: 'BIAS', value: 'bias' },
  { label: 'CCI', value: 'cci' },
  { label: 'ATR', value: 'atr' },
  { label: 'OBV', value: 'obv' },
  { label: 'ROC', value: 'roc' },
  { label: 'DMI', value: 'dmi' },
  { label: '砖形图', value: 'brick' }
];

const DEFAULT_SUB_INDICATORS: KlineSubIndicator[] = ['volume', 'macd', 'kdj'];
const VALID_SUB_INDICATORS = new Set<KlineSubIndicator>(KLINE_SUB_INDICATOR_OPTIONS.map(item => item.value));

export function buildKlineIndicatorState(input: { paneCount?: number | null; subIndicators?: unknown }): KlineIndicatorState {
  const paneCount = isSubPaneCount(input.paneCount) ? input.paneCount : 1;
  const storedIndicators = Array.isArray(input.subIndicators) ? input.subIndicators.filter(isSubIndicator) : [];
  const subIndicators = Array.from({ length: paneCount }, (_, index) => storedIndicators[index] ?? DEFAULT_SUB_INDICATORS[index] ?? DEFAULT_SUB_INDICATORS[0]);
  return { paneCount, subIndicators };
}

export function parseStoredKlineIndicatorState(value: string | null): KlineIndicatorState {
  if (!value) return buildKlineIndicatorState({ paneCount: 1, subIndicators: [] });
  try {
    return buildKlineIndicatorState(JSON.parse(value) as { paneCount?: number; subIndicators?: unknown });
  } catch {
    return buildKlineIndicatorState({ paneCount: 1, subIndicators: [] });
  }
}

export function buildKlinePanes(movingAverages: KlineMovingAverage[], subIndicators: KlineSubIndicator[]) {
  const mainIndicators: KlineIndicatorType[] = movingAverages.length > 0 ? ['ma'] : [];
  const layout = getKlinePaneLayout(subIndicators.length);
  const panes: PaneConfig[] = [
    { id: 'main', height: layout.main, indicators: mainIndicators },
    ...subIndicators.map((indicator, index) => ({ id: `sub_${indicator}_${index}`, height: layout.sub, indicators: nativeSubIndicators(indicator) }))
  ];
  return { chartIndicators: uniqueIndicators([...mainIndicators, ...subIndicators.flatMap(nativeSubIndicators)]), panes };
}

export function buildKlineIndicatorOptions(movingAverages: KlineMovingAverage[]): IndicatorOptions {
  return {
    ma: { periods: selectedMovingAveragePeriods(movingAverages), type: 'sma' },
    macd: { short: 12, long: 26, signal: 9 },
    kdj: { dPeriod: 3, kPeriod: 3, period: 9 },
    rsi: { periods: [6, 12, 24] },
    wr: { periods: [6, 10] },
    bias: { periods: [6, 12, 24] },
    cci: { period: 14 },
    atr: { period: 14 },
    obv: { maPeriod: 30 },
    roc: { period: 12, signalPeriod: 6 },
    dmi: { adxPeriod: 6, period: 14 }
  };
}

export function updateKlineSubPaneCount(current: KlineIndicatorState, paneCount: KlineSubPaneCount): KlineIndicatorState {
  return buildKlineIndicatorState({ paneCount, subIndicators: current.subIndicators });
}

export function updateKlineSubIndicator(current: KlineIndicatorState, index: number, indicator: KlineSubIndicator): KlineIndicatorState {
  const nextIndicators = [...current.subIndicators];
  nextIndicators[index] = indicator;
  return buildKlineIndicatorState({ paneCount: current.paneCount, subIndicators: nextIndicators });
}

export function getKlinePaneLayout(count: number): KlinePaneLayout {
  if (count >= 3) return { main: '52%', sub: '14%' };
  if (count === 2) return { main: '62%', sub: '16%' };
  return { main: '76%', sub: '18%' };
}

function uniqueIndicators(indicators: KlineIndicatorType[]) {
  return indicators.filter((indicator, index) => indicators.indexOf(indicator) === index);
}

function nativeSubIndicators(indicator: KlineSubIndicator): KlineIndicatorType[] {
  return indicator === 'brick' ? [] : [indicator];
}

function selectedMovingAveragePeriods(movingAverages: KlineMovingAverage[]) {
  const selected = new Set(movingAverages);
  return ([['ma5', 5], ['ma10', 10], ['ma20', 20], ['ma60', 60]] as const)
    .filter(([field]) => selected.has(field))
    .map(([, period]) => period);
}

function isSubPaneCount(value: unknown): value is KlineSubPaneCount {
  return value === 1 || value === 2 || value === 3;
}

function isSubIndicator(value: unknown): value is KlineSubIndicator {
  return typeof value === 'string' && VALID_SUB_INDICATORS.has(value as KlineSubIndicator);
}
