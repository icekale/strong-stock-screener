import { Tag } from "antd";
import Link from "next/link";
import { DataState } from "../workbench/DataState";
import { statusCopy } from "../screener/types";
import { selectScreenCandidates, selectTop3, selectWatchlistRisks, type PanelState } from "../../lib/marketOverview";
import { buildStockDetailHref } from "../../lib/stockNavigation";
import type { AuctionModelTop3Response, StrongStockScreeningResponse } from "../../lib/types";

type DecisionQueueProps = {
  auction: PanelState<AuctionModelTop3Response> | null;
  onRefresh: () => void;
  screening: PanelState<StrongStockScreeningResponse> | null;
};

const riskActionCopy = {
  hold_watch: "继续观察",
  reduce: "减仓",
  empty: "清仓",
} as const;

export function DecisionQueue({ auction, onRefresh, screening }: DecisionQueueProps) {
  return (
    <section aria-labelledby="decision-queue-title" className="compact-panel overflow-hidden">
      <div className="compact-panel__header">
        <div>
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="decision-queue-title">
            决策队列
          </h2>
          <p className="m-0 text-xs text-[var(--app-muted)]">竞价、筛选和自选风险</p>
        </div>
      </div>
      <div className="grid divide-y divide-[var(--app-border)] xl:grid-cols-3 xl:divide-x xl:divide-y-0">
        <AuctionBlock onRefresh={onRefresh} state={auction} />
        <ScreeningBlock onRefresh={onRefresh} state={screening} />
        <WatchlistRiskBlock onRefresh={onRefresh} state={screening} />
      </div>
    </section>
  );
}

function AuctionBlock({ onRefresh, state }: { onRefresh: () => void; state: PanelState<AuctionModelTop3Response> | null }) {
  const data = state && state.kind !== "error" ? state.value : null;

  return (
    <article className="min-w-0 p-4">
      <BlockTitle title="竞价 Top3" />
      {!data ? <DataState action={{ onClick: onRefresh }} kind={state?.kind === "error" ? "error" : "loading"} subject="竞价模型" /> : null}
      {state?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="竞价模型" /> : null}
      {data ? (
        <div className="space-y-2">
          {selectTop3(data.items).length === 0 ? <DataState action={{ onClick: onRefresh }} kind="empty" subject="竞价候选" /> : null}
          {selectTop3(data.items).map((item) => (
            <Link
              className="block rounded-md border border-[var(--app-border)] px-3 py-2 transition-colors hover:bg-[var(--app-raised)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--app-primary)]"
              href={buildStockDetailHref(item.symbol, { from: "auction-model" })}
              key={item.symbol}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="min-w-0 font-semibold text-[var(--app-ink)]">
                  #{item.rank ?? "-"} {item.name}
                </span>
                <span className="shrink-0 font-semibold tabular-nums text-[var(--app-ink)]">{formatProbability(item.prob_3pct)}</span>
              </div>
              <div className="mt-1 truncate text-xs text-[var(--app-muted)]">{item.symbol}</div>
              <div className="mt-1 text-xs leading-5 text-[var(--app-muted)]">{item.strategy_note ?? "-"}</div>
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function ScreeningBlock({ onRefresh, state }: { onRefresh: () => void; state: PanelState<StrongStockScreeningResponse> | null }) {
  const data = state && state.kind !== "error" ? state.value : null;

  return (
    <article className="min-w-0 p-4">
      <BlockTitle title="强势选股" />
      {!data ? <DataState action={{ onClick: onRefresh }} kind={state?.kind === "error" ? "error" : "loading"} subject="筛选结果" /> : null}
      {state?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="筛选结果" /> : null}
      {data ? (
        <div className="space-y-2">
          {selectScreenCandidates(data).length === 0 ? <DataState action={{ onClick: onRefresh }} kind="empty" subject="强势候选" /> : null}
          {selectScreenCandidates(data).map((item) => (
            <Link
              className="block rounded-md border border-[var(--app-border)] px-3 py-2 transition-colors hover:bg-[var(--app-raised)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--app-primary)]"
              href={buildStockDetailHref(item.symbol)}
              key={item.symbol}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="truncate font-semibold text-[var(--app-ink)]">{item.name}</span>
                <Tag bordered={false} className="m-0 shrink-0" color={item.status === "reduce_risk" ? "orange" : "blue"}>
                  {statusCopy[item.status].label}
                </Tag>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--app-muted)]">
                <span>{item.symbol}</span>
                <span>评分 {formatScore(item.score)}</span>
                <span>{item.industry ?? "-"}</span>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function WatchlistRiskBlock({ onRefresh, state }: { onRefresh: () => void; state: PanelState<StrongStockScreeningResponse> | null }) {
  const data = state && state.kind !== "error" ? state.value : null;

  return (
    <article className="min-w-0 p-4">
      <BlockTitle title="自选风险" />
      {!data ? <DataState action={{ onClick: onRefresh }} kind={state?.kind === "error" ? "error" : "loading"} subject="自选风险" /> : null}
      {state?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="自选风险" /> : null}
      {data ? (
        <div className="space-y-2">
          {selectWatchlistRisks(data).length === 0 ? <DataState action={{ onClick: onRefresh }} kind="empty" subject="自选风险" /> : null}
          {selectWatchlistRisks(data).map((item) => (
            <Link
              className="block rounded-md border border-[var(--app-border)] px-3 py-2 transition-colors hover:bg-[var(--app-raised)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--app-primary)]"
              href="/watchlist"
              key={item.symbol}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="truncate font-semibold text-[var(--app-ink)]">{item.name}</span>
                <Tag bordered={false} className="m-0 shrink-0" color={item.risk_action === "hold_watch" ? "blue" : "orange"}>
                  {riskActionCopy[item.risk_action]}
                </Tag>
              </div>
              <div className="mt-1 text-xs text-[var(--app-muted)]">{item.symbol}</div>
              <div className="mt-1 truncate text-xs text-[var(--app-muted)]">{item.risk_flags[0] ?? "-"}</div>
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function BlockTitle({ title }: { title: string }) {
  return <h3 className="mb-3 text-sm font-semibold text-[var(--app-ink)]">{title}</h3>;
}

function formatProbability(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatScore(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
