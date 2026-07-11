import type {
  AuctionModelPredictionItem,
  StrongStockScreeningResponse,
  WatchlistRiskItem,
} from "./types";

export type MarketSession = "盘前竞价" | "盘中" | "收盘复盘" | "休市";

export type PanelState<T> =
  | { kind: "ready"; value: T }
  | { kind: "stale"; value: T }
  | { kind: "missing"; value: null }
  | { kind: "error"; value: null };

export function selectTop3(items: AuctionModelPredictionItem[]): AuctionModelPredictionItem[] {
  return items
    .filter((item) => item.bucket === "selected")
    .sort((left, right) => (left.rank ?? Infinity) - (right.rank ?? Infinity))
    .slice(0, 3);
}

export function selectScreenCandidates(
  response: StrongStockScreeningResponse | null,
): StrongStockScreeningResponse["items"] {
  return (response?.items ?? []).filter((item) => item.status !== "data_incomplete").slice(0, 6);
}

export function selectWatchlistRisks(response: StrongStockScreeningResponse | null): WatchlistRiskItem[] {
  return (response?.watchlist_risk_items ?? []).slice(0, 3);
}

export function toPanelState<T>(result: PromiseSettledResult<T>, previous: T | null = null): PanelState<T> {
  if (result.status === "fulfilled") {
    return { kind: "ready", value: result.value };
  }
  if (previous !== null) {
    return { kind: "stale", value: previous };
  }
  return { kind: "error", value: null };
}

export function nextRequestGeneration(currentGeneration: number): number {
  return currentGeneration + 1;
}

export function isLatestRequestGeneration(requestGeneration: number, currentGeneration: number): boolean {
  return requestGeneration === currentGeneration;
}

export async function executeLatestOnly<T>({
  apply,
  currentGeneration,
  execute,
  finishLoading,
  generation,
}: {
  apply: (result: T) => void;
  currentGeneration: () => number;
  execute: () => Promise<T>;
  finishLoading: () => void;
  generation: number;
}): Promise<boolean> {
  const result = await execute();
  if (!isLatestRequestGeneration(generation, currentGeneration())) {
    return false;
  }
  apply(result);
  finishLoading();
  return true;
}

export function getShanghaiTradeDate(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));

  return `${values.year}-${values.month}-${values.day}`;
}

export function getAuctionCacheTradeDate(now = new Date()): string {
  const tradeDate = getShanghaiTradeDate(now);
  const weekday = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    weekday: "short",
  }).format(now);

  if (weekday !== "Sat" && weekday !== "Sun") {
    return tradeDate;
  }

  const date = new Date(`${tradeDate}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() - (weekday === "Sat" ? 1 : 2));
  return date.toISOString().slice(0, 10);
}

export function getMarketSession(now = new Date()): MarketSession {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const minutes = Number(values.hour) * 60 + Number(values.minute);

  if (values.weekday === "Sat" || values.weekday === "Sun") {
    return "休市";
  }

  const morningOpen = 9 * 60 + 30;
  const morningClose = 11 * 60 + 30;
  const afternoonOpen = 13 * 60;
  const afternoonClose = 15 * 60;

  if (minutes < morningOpen) {
    return "盘前竞价";
  }
  if ((minutes >= morningOpen && minutes < morningClose) || (minutes >= afternoonOpen && minutes < afternoonClose)) {
    return "盘中";
  }
  return "收盘复盘";
}
