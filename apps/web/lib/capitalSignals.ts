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
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000) return `${prefix}${(absolute / 1_000_000_000_000).toFixed(2)}万亿`;
  if (absolute >= 100_000_000) return `${prefix}${(absolute / 100_000_000).toFixed(1)}亿`;
  if (absolute >= 10_000) return `${prefix}${(absolute / 10_000).toFixed(0)}万`;
  return `${prefix}${absolute.toFixed(0)}`;
}

export function formatEvidenceStrength(value: number | null): string {
  return value === null ? "--" : value.toFixed(1);
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

function formatShareMagnitude(value: number): string {
  const absolute = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (absolute >= 100_000_000) return `${sign}${(absolute / 100_000_000).toFixed(2)}亿份`;
  if (absolute >= 10_000) return `${sign}${(absolute / 10_000).toFixed(0)}万份`;
  return `${sign}${absolute.toFixed(0)}份`;
}
