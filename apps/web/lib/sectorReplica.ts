import type {
  SectorReplicaChartSeries,
  SectorReplicaRadarResponse,
  SectorReplicaStocksResponse,
  StrongStockSourceStatus,
} from "./types";

export function isSectorReplicaRadarCache(value: unknown): value is SectorReplicaRadarResponse {
  return Boolean(
    isRecord(value) &&
      Array.isArray(value.axis) &&
      Array.isArray(value.plates) &&
      Array.isArray(value.checkplate) &&
      Array.isArray(value.series) &&
      Array.isArray(value.stocks) &&
      Array.isArray(value.related_tags) &&
      Array.isArray(value.source_status) &&
      isRecord(value.qxlive) &&
      isRecord(value.qxlive.series),
  );
}

export function isSectorReplicaStocksCache(value: unknown): value is SectorReplicaStocksResponse {
  return Boolean(
    isRecord(value) &&
      Array.isArray(value.rows) &&
      Array.isArray(value.related_tags) &&
      Array.isArray(value.source_status),
  );
}

export function nextSectorReplicaSelection(
  current: string[],
  code: string,
  checked: boolean,
  maxCount = 6,
): string[] {
  if (!checked) {
    return current.length <= 1 ? current : current.filter((item) => item !== code);
  }
  if (current.includes(code)) {
    return current;
  }
  return [...current, code].slice(0, maxCount);
}

export function formatReplicaPct(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function formatReplicaMoney(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 100_000_000) {
    return `${sign}${(abs / 100_000_000).toFixed(2).replace(/\.?0+$/, "")}亿`;
  }
  if (abs >= 10_000) {
    return `${sign}${(abs / 10_000).toFixed(2).replace(/\.?0+$/, "")}万`;
  }
  return `${sign}${abs.toFixed(0)}`;
}

export function formatReplicaReportedMoney(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return formatReplicaMoney(value);
}

export function formatReplicaReportedRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return `${value.toFixed(2)}%`;
}

export function isSectorReplicaStocksForSelection(
  stocks: Pick<SectorReplicaStocksResponse, "board_code" | "sub_theme"> | null,
  activeBoardCode: string | null,
  activeSubTheme: string | null,
): boolean {
  return Boolean(
    stocks &&
      activeBoardCode &&
      stocks.board_code === activeBoardCode &&
      (stocks.sub_theme ?? null) === activeSubTheme,
  );
}

export function latestSectorReplicaSeriesTime(
  axis: string[],
  series: Array<Pick<SectorReplicaChartSeries, "data">>,
): string | null {
  let latestIndex = -1;
  for (const item of series) {
    for (let index = Math.min(item.data.length, axis.length) - 1; index >= 0; index -= 1) {
      const value = item.data[index];
      if (typeof value === "number" && Number.isFinite(value)) {
        latestIndex = Math.max(latestIndex, index);
        break;
      }
    }
  }
  return latestIndex >= 0 ? axis[latestIndex] : null;
}

export function formatReplicaNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  if (Math.abs(value) >= 1000) {
    return value.toFixed(0);
  }
  return value.toFixed(1).replace(".0", "");
}

export function formatReplicaDateTime(value: string | null | undefined): string {
  return value ? value.replace("T", " ").slice(0, 16) : "-";
}

export function sourceStatusText(status: StrongStockSourceStatus | null | undefined): string {
  if (!status) {
    return "数据源待确认";
  }
  const label =
    status.status === "success"
      ? "正常"
      : status.status === "stale"
        ? "缓存/估算"
        : status.status === "disabled"
          ? "未启用"
          : status.status === "missing_key"
            ? "缺配置"
            : "失败";
  return `${status.source} · ${label}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
