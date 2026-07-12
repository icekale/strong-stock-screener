import type { ChanlunAvailability, ChanlunPeriod } from "../../lib/types";

export const CHANLUN_PERIODS = ["1d", "60m", "30m", "5m"] as const satisfies readonly ChanlunPeriod[];

export type ChanlunAvailabilityDescription = {
  actionable: boolean;
  text: string;
  tone: "success" | "warning" | "neutral" | "error";
};

export function resolveChanlunPeriod(value: string | null | undefined): ChanlunPeriod {
  return CHANLUN_PERIODS.includes(value as ChanlunPeriod) ? (value as ChanlunPeriod) : "1d";
}

export function describeChanlunAvailability(availability: ChanlunAvailability): ChanlunAvailabilityDescription {
  const descriptions: Record<ChanlunAvailability, ChanlunAvailabilityDescription> = {
    ready: { tone: "success", text: "结构就绪", actionable: true },
    backfilling: { tone: "warning", text: "历史补齐中", actionable: false },
    insufficient_bars: { tone: "neutral", text: "结构样本不足", actionable: false },
    stale: { tone: "warning", text: "结构已过期", actionable: false },
    unavailable: { tone: "error", text: "结构不可用", actionable: false },
  };
  return descriptions[availability];
}

export function normalizeChanlunSymbol(value: string): string | null {
  const [code, exchange] = value.trim().toUpperCase().split(".", 2);
  if (!code || !/^\d{6}$/.test(code) || (exchange && !["SH", "SZ", "BJ"].includes(exchange))) {
    return null;
  }
  if (exchange) {
    return `${code}.${exchange}`;
  }
  if (code.startsWith("6") || code.startsWith("9")) {
    return `${code}.SH`;
  }
  if (code.startsWith("4") || code.startsWith("8")) {
    return `${code}.BJ`;
  }
  return `${code}.SZ`;
}

export function isChanlunAnalysisCurrent(
  analysis: { period: ChanlunPeriod; symbol: string } | null,
  symbol: string | null,
  period: ChanlunPeriod,
): boolean {
  return analysis?.symbol === symbol && analysis.period === period;
}

export function isChanlunSymbolCurrent(requestedSymbol: string, selectedSymbol: string | null): boolean {
  return requestedSymbol === selectedSymbol;
}

export function isChanlunWorkspaceCurrent(
  workspace: { symbol: string } | null,
  symbol: string | null,
): boolean {
  return workspace?.symbol === symbol;
}
