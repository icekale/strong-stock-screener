import type { DataSourceStatusResponse, StrongStockScreeningResponse } from "./types";

function defaultApiBaseUrl(): string {
  if (typeof window !== "undefined" && window.location.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8010`;
  }
  return "http://localhost:8010";
}

const API_BASE_URL = process.env.NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL ?? defaultApiBaseUrl();

export async function getDataSourceStatus(): Promise<DataSourceStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/data-sources/status`);
  if (!response.ok) {
    throw new Error(`读取数据源状态失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<DataSourceStatusResponse>;
}

export async function createScreenRun(
  tradeDate: string,
  limit = 30,
): Promise<StrongStockScreeningResponse> {
  const response = await fetch(`${API_BASE_URL}/api/screen/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trade_date: tradeDate, limit }),
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      const payload = JSON.parse(detail) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Keep raw response text.
    }
    throw new Error(`运行筛选失败：${response.status} ${detail}`);
  }
  return response.json() as Promise<StrongStockScreeningResponse>;
}

export async function getLatestScreenRun(): Promise<StrongStockScreeningResponse> {
  const response = await fetch(`${API_BASE_URL}/api/screen/runs/latest`);
  if (!response.ok) {
    throw new Error(`读取最近筛选失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<StrongStockScreeningResponse>;
}

