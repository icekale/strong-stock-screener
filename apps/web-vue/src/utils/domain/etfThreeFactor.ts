import type { EtfFactorStatus, EtfThreeFactorItem, EtfThreeFactorLevel, HuijinEtfActivityItem } from "@/service/types";

export type UnifiedEtfActivityRow = {
  symbol: string;
  name: string;
  indexName: string;
  closeChangePct: number | null;
  dailyChangePct: number | null;
  baselineChangePct: number | null;
  volumeRatio: number | null;
  signalScore: number | null;
  signalLevel: EtfThreeFactorLevel;
  activity: HuijinEtfActivityItem | null;
  factor: EtfThreeFactorItem | null;
};

export function buildUnifiedEtfActivityRows(
  activityItems: HuijinEtfActivityItem[],
  factorItems: EtfThreeFactorItem[]
): UnifiedEtfActivityRow[] {
  const activityBySymbol = new Map(activityItems.map(item => [item.symbol, item]));
  const factorBySymbol = new Map(factorItems.map(item => [item.symbol, item]));
  const symbols = [...activityItems.map(item => item.symbol)];
  for (const item of factorItems) if (!activityBySymbol.has(item.symbol)) symbols.push(item.symbol);

  return symbols.map(symbol => {
    const activity = activityBySymbol.get(symbol) ?? null;
    const factor = factorBySymbol.get(symbol) ?? null;
    return {
      symbol,
      name: activity?.name ?? factor?.name ?? symbol,
      indexName: activity?.index_name ?? factor?.index_name ?? '--',
      closeChangePct: activity?.close_change_pct ?? factor?.close_change_pct ?? null,
      dailyChangePct: activity?.daily_change_pct ?? null,
      baselineChangePct: activity?.cumulative_baseline_change_pct ?? activity?.baseline_change_pct ?? null,
      volumeRatio: factor?.volume_ratio ?? null,
      signalScore: factor?.signal_score ?? null,
      signalLevel: factor?.level ?? 'incomplete',
      activity,
      factor
    };
  });
}

export function pickDefaultEtfActivitySymbol(rows: UnifiedEtfActivityRow[]): string {
  return [...rows].sort((left, right) => (right.signalScore ?? -1) - (left.signalScore ?? -1))[0]?.symbol ?? '';
}

export type EtfSignalTone = "danger" | "warning" | "info" | "neutral";
export type CloseChangeTone = "rise" | "fall" | "flat";

export function signalLevelLabel(level: EtfThreeFactorLevel): string {
  if (level === "high") return "高确信";
  if (level === "medium") return "中确信";
  if (level === "low") return "低确信";
  return "数据不全";
}

export function factorStatusLabel(status: EtfFactorStatus): string {
  if (status === "available") return "可用";
  if (status === "pending") return "待盘后";
  if (status === "missing") return "不可用";
  return "已过期";
}

export function formatVolumeRatio(value: number | null): string {
  return value === null ? "--" : `${value.toFixed(2)}倍`;
}

export function signalTone(level: EtfThreeFactorLevel): EtfSignalTone {
  if (level === "high") return "danger";
  if (level === "medium") return "warning";
  if (level === "low") return "info";
  return "neutral";
}

export function closeChangeTone(value: number | null): CloseChangeTone {
  if (value === null || value === 0) return "flat";
  return value > 0 ? "rise" : "fall";
}
