import type { IndicatorType, PaneConfig } from "kline-charts-react";

export type KlineSubIndicator =
  | "volume"
  | "macd"
  | "kdj"
  | "rsi"
  | "wr"
  | "bias"
  | "cci"
  | "atr"
  | "obv"
  | "roc"
  | "dmi";

export type KlineSubPaneCount = 1 | 2 | 3;

export type KlineIndicatorState = {
  paneCount: KlineSubPaneCount;
  subIndicators: KlineSubIndicator[];
};

export const KLINE_SUB_INDICATOR_OPTIONS: Array<{ label: string; value: KlineSubIndicator }> = [
  { label: "成交量", value: "volume" },
  { label: "MACD", value: "macd" },
  { label: "KDJ", value: "kdj" },
  { label: "RSI", value: "rsi" },
  { label: "WR", value: "wr" },
  { label: "BIAS", value: "bias" },
  { label: "CCI", value: "cci" },
  { label: "ATR", value: "atr" },
  { label: "OBV", value: "obv" },
  { label: "ROC", value: "roc" },
  { label: "DMI", value: "dmi" },
];

const DEFAULT_SUB_INDICATORS: KlineSubIndicator[] = ["volume", "macd", "kdj"];
const VALID_SUB_INDICATORS = new Set<KlineSubIndicator>(KLINE_SUB_INDICATOR_OPTIONS.map((item) => item.value));

export function buildKlineIndicatorState(input: {
  paneCount?: number | null;
  subIndicators?: unknown;
}): KlineIndicatorState {
  const paneCount = isSubPaneCount(input.paneCount) ? input.paneCount : 1;
  const storedIndicators = Array.isArray(input.subIndicators)
    ? input.subIndicators.filter(isSubIndicator)
    : [];
  const subIndicators = Array.from({ length: paneCount }, (_, index) => {
    return storedIndicators[index] ?? DEFAULT_SUB_INDICATORS[index] ?? DEFAULT_SUB_INDICATORS[0];
  });

  return { paneCount, subIndicators };
}

export function parseStoredKlineIndicatorState(value: string | null): KlineIndicatorState {
  if (!value) {
    return buildKlineIndicatorState({ paneCount: 1, subIndicators: [] });
  }
  try {
    const parsed = JSON.parse(value) as { paneCount?: number; subIndicators?: unknown };
    return buildKlineIndicatorState(parsed);
  } catch {
    return buildKlineIndicatorState({ paneCount: 1, subIndicators: [] });
  }
}

export function buildKlinePanes(
  movingAverages: string[],
  subIndicators: KlineSubIndicator[],
): { chartIndicators: IndicatorType[]; panes: PaneConfig[] } {
  const mainIndicators: IndicatorType[] = movingAverages.length > 0 ? ["ma"] : [];
  const layout = paneLayout(subIndicators.length);
  const panes: PaneConfig[] = [
    {
      id: "main",
      height: layout.main,
      indicators: mainIndicators,
    },
    ...subIndicators.map((indicator, index) => ({
      id: `sub_${indicator}_${index}`,
      height: layout.sub,
      indicators: [indicator],
    })),
  ];

  return {
    chartIndicators: uniqueIndicators([...mainIndicators, ...subIndicators]),
    panes,
  };
}

export function updateKlineSubPaneCount(
  current: KlineIndicatorState,
  paneCount: KlineSubPaneCount,
): KlineIndicatorState {
  return buildKlineIndicatorState({
    paneCount,
    subIndicators: current.subIndicators,
  });
}

export function updateKlineSubIndicator(
  current: KlineIndicatorState,
  index: number,
  indicator: KlineSubIndicator,
): KlineIndicatorState {
  const nextIndicators = [...current.subIndicators];
  nextIndicators[index] = indicator;
  return buildKlineIndicatorState({
    paneCount: current.paneCount,
    subIndicators: nextIndicators,
  });
}

function paneLayout(count: number): { main: string; sub: string } {
  if (count >= 3) {
    return { main: "52%", sub: "14%" };
  }
  if (count === 2) {
    return { main: "62%", sub: "16%" };
  }
  return { main: "76%", sub: "18%" };
}

function uniqueIndicators(indicators: IndicatorType[]): IndicatorType[] {
  return indicators.filter((indicator, index) => indicators.indexOf(indicator) === index);
}

function isSubPaneCount(value: unknown): value is KlineSubPaneCount {
  return value === 1 || value === 2 || value === 3;
}

function isSubIndicator(value: unknown): value is KlineSubIndicator {
  return typeof value === "string" && VALID_SUB_INDICATORS.has(value as KlineSubIndicator);
}
