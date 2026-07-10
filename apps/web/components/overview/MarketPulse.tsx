import { DataState } from "../workbench/DataState";
import type { PanelState } from "../../lib/marketOverview";
import type { MarketOverviewResponse, SentimentSummaryResponse } from "../../lib/types";

type MarketPulseProps = {
  market: PanelState<MarketOverviewResponse> | null;
  onRefresh: () => void;
  sentiment: PanelState<SentimentSummaryResponse> | null;
};

export function MarketPulse({ market, onRefresh, sentiment }: MarketPulseProps) {
  return (
    <section aria-label="市场脉冲" className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.8fr)]">
      <MarketSnapshot onRefresh={onRefresh} state={market} />
      <SentimentSnapshot onRefresh={onRefresh} state={sentiment} />
    </section>
  );
}

function MarketSnapshot({ onRefresh, state }: { onRefresh: () => void; state: PanelState<MarketOverviewResponse> | null }) {
  const data = state && state.kind !== "error" ? state.value : null;

  return (
    <section aria-labelledby="market-pulse-title" className="compact-panel overflow-hidden">
      <div className="compact-panel__header">
        <div>
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="market-pulse-title">
            市场脉冲
          </h2>
          <p className="m-0 text-xs text-[var(--app-muted)]">指数与广度</p>
        </div>
      </div>
      {!data ? <DataState action={{ onClick: onRefresh }} kind={state?.kind === "error" ? "error" : "loading"} subject="市场概览" /> : null}
      {state?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="市场概览" /> : null}
      {data ? (
        <div className="divide-y divide-[var(--app-border)]">
          <div className="grid gap-3 p-4 sm:grid-cols-3">
            <Metric label="总成交额" value={formatCny(data.turnover.total_cny)} />
            <Metric label="上涨 / 下跌" value={`${formatCount(data.advance_decline.advance_count)} / ${formatCount(data.advance_decline.decline_count)}`} />
            <Metric label="涨停 / 跌停" value={`${formatCount(data.advance_decline.limit_up_count)} / ${formatCount(data.advance_decline.limit_down_count)}`} />
          </div>
          {data.indices.length === 0 ? <DataState action={{ onClick: onRefresh }} kind="empty" subject="指数快照" /> : null}
          {data.indices.length > 0 ? (
            <div className="grid gap-px bg-[var(--app-border)] sm:grid-cols-2 xl:grid-cols-4">
              {data.indices.map((item) => (
                <div className="min-w-0 bg-[var(--app-surface)] p-3" key={item.symbol}>
                  <div className="truncate text-xs text-[var(--app-muted)]">{item.name}</div>
                  <div className="mt-1 font-semibold tabular-nums text-[var(--app-ink)]">{formatNumber(item.last_price)}</div>
                  <div className="mt-1 text-xs tabular-nums text-[var(--app-muted)]">{formatPercent(item.change_pct)}</div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function SentimentSnapshot({ onRefresh, state }: { onRefresh: () => void; state: PanelState<SentimentSummaryResponse> | null }) {
  const data = state && state.kind !== "error" ? state.value : null;

  return (
    <section aria-labelledby="sentiment-pulse-title" className="compact-panel overflow-hidden">
      <div className="compact-panel__header">
        <div>
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="sentiment-pulse-title">
            情绪快照
          </h2>
          <p className="m-0 text-xs text-[var(--app-muted)]">短线情绪摘要</p>
        </div>
      </div>
      {!data ? <DataState action={{ onClick: onRefresh }} kind={state?.kind === "error" ? "error" : "loading"} subject="情绪摘要" /> : null}
      {state?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="情绪摘要" /> : null}
      {data ? (
        <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-1">
          <Metric label="情绪阶段" value={data.metrics.emotion_level} />
          <Metric label="情绪分" value={formatNumber(data.metrics.emotion_score)} />
          <Metric label="涨停 / 炸板" value={`${formatNumber(data.metrics.limit_up_count)} / ${formatNumber(data.metrics.break_board_count)}`} />
          <Metric label="最高连板" value={formatNumber(data.metrics.max_consecutive_boards)} />
        </div>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-[var(--app-muted)]">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold tabular-nums text-[var(--app-ink)]">{value}</div>
    </div>
  );
}

function formatCny(value: number | null) {
  if (value === null) {
    return "-";
  }
  const absolute = Math.abs(value);
  if (absolute >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(1)}亿`;
  }
  if (absolute >= 10_000) {
    return `${(value / 10_000).toFixed(0)}万`;
  }
  return value.toFixed(0);
}

function formatCount(value: number | null) {
  return value === null ? "-" : String(value);
}

function formatNumber(value: number | null) {
  return value === null ? "-" : Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function formatPercent(value: number | null) {
  return value === null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}
