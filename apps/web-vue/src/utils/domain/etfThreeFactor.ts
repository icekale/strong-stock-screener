import type { EtfFactorStatus, EtfThreeFactorLevel } from "@/service/types";

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
