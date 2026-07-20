import type { CapitalSignalStage, EtfActivityDirection, EtfValidationState } from "@/service/types";

export type DirectionTone = "fall" | "neutral" | "rise";

export function directionTone(value: number | null): DirectionTone {
  if (value === null || value === 0) return "neutral";
  return value > 0 ? "rise" : "fall";
}

export function formatDirectionalPercent(value: number | null): string {
  if (value === null) return "--";
  if (value === 0) return "0.00%";
  return `${value > 0 ? "▲ +" : "▼ -"}${Math.abs(value).toFixed(2)}%`;
}

export function formatDirectionalCny(value: number | null): string {
  if (value === null) return "--";
  if (value === 0) return "0";
  const prefix = value > 0 ? "▲ +" : "▼ -";
  return `${prefix}${formatCnyMagnitude(Math.abs(value))}`;
}

export function formatPlainCny(value: number | null): string {
  if (value === null) return "--";
  return formatCnyMagnitude(value);
}

export function formatEvidenceStrength(value: number | null): string {
  return value === null ? "--" : value.toFixed(1);
}

export function formatActivityMultiple(value: number | null): string {
  return value === null ? "--" : `${value.toFixed(1)}倍`;
}

export function activityDirectionLabel(value: EtfActivityDirection): string {
  if (value === "increase") return "申购";
  if (value === "decrease") return "赎回";
  if (value === "flat") return "持平";
  return "待确认";
}

export function validationStateLabel(value: EtfValidationState): string {
  if (value === "confirmed_increase") return "配对一致增加";
  if (value === "confirmed_decrease") return "配对一致减少";
  if (value === "divergent") return "方向分歧";
  return "数据不全";
}

export function validationStateTone(value: EtfValidationState): DirectionTone {
  if (value === "confirmed_increase") return "rise";
  if (value === "confirmed_decrease") return "fall";
  return "neutral";
}

export function formatPlainShares(value: number | null): string {
  if (value === null) return "--";
  return formatShareMagnitude(value);
}

export function formatDirectionalShares(value: number | null): string {
  if (value === null) return "--";
  if (value === 0) return "0份";
  return `${value > 0 ? "▲ +" : "▼ -"}${formatShareMagnitude(Math.abs(value))}`;
}

export function stageLabel(stage: CapitalSignalStage): string {
  if (stage === "intraday") return "盘中代理";
  if (stage === "disclosure") return "定期披露";
  return "盘后确认";
}

function formatCnyMagnitude(value: number): string {
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000 || roundsToNextUnit(absolute, 100_000_000, 1)) {
    return `${(value / 1_000_000_000_000).toFixed(2)}万亿`;
  }
  if (absolute >= 100_000_000 || roundsToNextUnit(absolute, 10_000, 0)) {
    return `${(value / 100_000_000).toFixed(1)}亿`;
  }
  if (absolute >= 10_000 || roundsToNextUnit(absolute, 1, 0)) return `${(value / 10_000).toFixed(0)}万`;
  return value.toFixed(0);
}

function formatShareMagnitude(value: number): string {
  const absolute = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (absolute >= 100_000_000 || roundsToNextUnit(absolute, 10_000, 0)) {
    return `${sign}${(absolute / 100_000_000).toFixed(2)}亿份`;
  }
  if (absolute >= 10_000 || roundsToNextUnit(absolute, 1, 0)) {
    return `${sign}${(absolute / 10_000).toFixed(0)}万份`;
  }
  return `${sign}${absolute.toFixed(0)}份`;
}

function roundsToNextUnit(value: number, divisor: number, fractionDigits: number): boolean {
  return Number((value / divisor).toFixed(fractionDigits)) >= 10_000;
}
