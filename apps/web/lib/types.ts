export type SourceStatusValue = "success" | "failed" | "disabled" | "missing_key";

export type StrongStockSourceStatus = {
  source: string;
  status: SourceStatusValue;
  detail: string;
};

export type DataSourceStatusResponse = {
  items: StrongStockSourceStatus[];
};

export type StrongStockScreeningItem = {
  symbol: string;
  name: string;
  status: "focus" | "wait_pullback" | "reduce_risk" | "data_incomplete";
  score: number;
  rule_hits: string[];
  risk_flags: string[];
  intraday_notes: string[];
  metrics: Record<string, unknown>;
  data_status: "complete" | "incomplete";
  source_trace: string[];
};

export type WatchlistRiskItem = {
  symbol: string;
  name: string;
  risk_action: "hold_watch" | "reduce" | "empty";
  risk_flags: string[];
  intraday_notes: string[];
  metrics: Record<string, unknown>;
  source_trace: string[];
};

export type StrongStockScreeningResponse = {
  trade_date: string;
  source_status: StrongStockSourceStatus[];
  items: StrongStockScreeningItem[];
  watchlist_risk_items: WatchlistRiskItem[];
  generated_at: string;
};

