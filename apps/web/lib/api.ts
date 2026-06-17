import type {
  DataSourceStatusResponse,
  RuntimeSettingsHealthResponse,
  RuntimeSettingsResponse,
  ScreenRunFilters,
  StockKlineResponse,
  StrongStockIntradaySnapshot,
  StrongStockScreeningResponse,
  WatchlistPoolItemRequest,
  WatchlistPoolResponse,
} from "./types";

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

export async function getRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/settings`);
  if (!response.ok) {
    throw new Error(`读取设置失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<RuntimeSettingsResponse>;
}

export async function saveRuntimeSettings(payload: {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow";
  quote_provider: "tickflow";
  tickflow_api_key?: string | null;
  tickflow_base_url: string;
  ifind_api_key?: string | null;
  ifind_base_url: string;
  ifind_service_id: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp";
  provider_timeout_seconds: number;
}): Promise<RuntimeSettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`保存设置失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<RuntimeSettingsResponse>;
}

export async function checkRuntimeSettingsHealth(symbol = "605289.SH"): Promise<RuntimeSettingsHealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/settings/health?symbol=${encodeURIComponent(symbol)}`);
  if (!response.ok) {
    throw new Error(`健康检查失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<RuntimeSettingsHealthResponse>;
}

export async function createScreenRun(
  tradeDate: string,
  limit = 30,
  scanLimit = 40,
  filters: ScreenRunFilters = {},
): Promise<StrongStockScreeningResponse> {
  const response = await fetch(`${API_BASE_URL}/api/screen/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trade_date: tradeDate, limit, scan_limit: scanLimit, filters }),
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

export async function createIntradaySnapshot({
  limit = 30,
  watchlistText = "",
  useWatchlistPool = false,
}: {
  limit?: number;
  watchlistText?: string;
  useWatchlistPool?: boolean;
} = {}): Promise<StrongStockIntradaySnapshot> {
  const response = await fetch(`${API_BASE_URL}/api/intraday/snapshot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      limit,
      watchlist_text: watchlistText,
      use_watchlist_pool: useWatchlistPool,
    }),
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
    throw new Error(`运行盘中监控失败：${response.status} ${detail}`);
  }
  return response.json() as Promise<StrongStockIntradaySnapshot>;
}

export async function getWatchlistPool(): Promise<WatchlistPoolResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/pool`);
  if (!response.ok) {
    throw new Error(`读取自选股股票池失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<WatchlistPoolResponse>;
}

export async function saveWatchlistPool(content: string): Promise<WatchlistPoolResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/pool`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    throw new Error(`保存自选股股票池失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<WatchlistPoolResponse>;
}

export async function addWatchlistPoolItem(item: WatchlistPoolItemRequest): Promise<WatchlistPoolResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/pool/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item),
  });
  if (!response.ok) {
    throw new Error(`加入自选股失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<WatchlistPoolResponse>;
}

export async function getStockKline(symbol: string, count = 220): Promise<StockKlineResponse> {
  const response = await fetch(`${API_BASE_URL}/api/stocks/${encodeURIComponent(symbol)}/kline?count=${count}`);
  if (!response.ok) {
    throw new Error(`读取K线失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<StockKlineResponse>;
}
