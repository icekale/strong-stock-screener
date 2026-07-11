import { marketBreadthPercent, type PanelState } from "../../lib/marketOverview";
import type { MarketOverviewResponse, SentimentSummaryResponse } from "../../lib/types";
import { DataState } from "../workbench/DataState";

type MarketPulseProps = {
  market: PanelState<MarketOverviewResponse> | null;
  onRefresh: () => void;
  sentiment: PanelState<SentimentSummaryResponse> | null;
};

export function MarketPulse({ market, onRefresh, sentiment }: MarketPulseProps) {
  const marketData = market && market.kind !== "error" ? market.value : null;
  const sentimentData = sentiment && sentiment.kind !== "error" ? sentiment.value : null;
  const breadth = marketData
    ? marketBreadthPercent(marketData.advance_decline.advance_count, marketData.advance_decline.decline_count)
    : 0;

  return (
    <section aria-labelledby="market-state-title" className="compact-panel market-state-panel overflow-hidden">
      <div className="compact-panel__header">
        <div>
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="market-state-title">
            市场状态
          </h2>
          <p className="m-0 text-xs text-[var(--app-muted)]">广度、成交与短线情绪</p>
        </div>
      </div>

      {!marketData && !sentimentData ? (
        <DataState action={{ onClick: onRefresh }} kind={market?.kind === "error" && sentiment?.kind === "error" ? "error" : "loading"} subject="市场状态" />
      ) : null}
      {market?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="市场概览" /> : null}
      {sentiment?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="情绪摘要" /> : null}

      {marketData || sentimentData ? (
        <>
          <div className="market-state-grid">
            <MarketMetric
              detail={marketData ? formatTurnoverChange(marketData.turnover.change_pct) : undefined}
              label="总成交额"
              unavailable={!marketData}
              value={marketData ? formatCny(marketData.turnover.total_cny) : "读取失败"}
            />
            <MarketMetric
              detail={sentimentData?.metrics.emotion_level}
              label="情绪分"
              tone="primary"
              unavailable={!sentimentData}
              value={sentimentData ? formatNumber(sentimentData.metrics.emotion_score) : "读取失败"}
            />
            <div className="market-state__metric market-state__metric--wide">
              <div className="market-state__label">上涨 / 下跌</div>
              {marketData ? (
                <>
                  <div className="market-state__value market-state__value--split">
                    <span className="market-rise-text">{formatCount(marketData.advance_decline.advance_count)}</span>
                    <span aria-hidden="true">/</span>
                    <span className="market-fall-text">{formatCount(marketData.advance_decline.decline_count)}</span>
                  </div>
                  <div
                    aria-label={`上涨 ${formatCount(marketData.advance_decline.advance_count)}，下跌 ${formatCount(marketData.advance_decline.decline_count)}，平盘 ${formatCount(marketData.advance_decline.unchanged_count)}`}
                    className="market-breadth"
                    role="img"
                  >
                    <span className="market-breadth__advance" style={{ width: `${breadth}%` }} />
                  </div>
                </>
              ) : (
                <div className="market-state__unavailable">读取失败</div>
              )}
            </div>
            <MarketMetric
              label="涨停 / 跌停"
              split
              unavailable={!marketData}
              value={marketData ? `${formatCount(marketData.advance_decline.limit_up_count)} / ${formatCount(marketData.advance_decline.limit_down_count)}` : "读取失败"}
            />
          </div>

          {!marketData && market?.kind === "error" ? <DataState action={{ onClick: onRefresh }} kind="error" subject="市场概览" /> : null}
          {!sentimentData && sentiment?.kind === "error" ? <DataState action={{ onClick: onRefresh }} kind="error" subject="情绪摘要" /> : null}

        </>
      ) : null}
    </section>
  );
}

export function MarketIndexStrip({ market, onRefresh }: { market: PanelState<MarketOverviewResponse> | null; onRefresh: () => void }) {
  const marketData = market && market.kind !== "error" ? market.value : null;

  return (
    <section aria-label="指数快照" className="compact-panel market-index-panel overflow-hidden">
      {!marketData ? <DataState action={{ onClick: onRefresh }} kind={market?.kind === "error" ? "error" : "loading"} subject="指数快照" /> : null}
      {marketData?.indices.length === 0 ? <DataState action={{ onClick: onRefresh }} kind="empty" subject="指数快照" /> : null}
      {marketData && marketData.indices.length > 0 ? (
        <div className="market-index-strip">
          {marketData.indices.map((item) => (
            <div className="market-index-strip__item" key={item.symbol}>
              <span>{item.name}</span>
              <strong>{formatNumber(item.last_price)}</strong>
              <b className={marketTone(item.change_pct)}>{formatPercent(item.change_pct)}</b>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function MarketMetric({
  detail,
  label,
  split = false,
  tone,
  unavailable = false,
  value,
}: {
  detail?: string;
  label: string;
  split?: boolean;
  tone?: "primary";
  unavailable?: boolean;
  value: string;
}) {
  return (
    <div className="market-state__metric">
      <div className="market-state__label">{label}</div>
      {unavailable ? (
        <div className="market-state__unavailable">{value}</div>
      ) : (
        <div className={`market-state__value${tone === "primary" ? " market-state__value--primary" : ""}${split ? " market-state__value--split" : ""}`}>
          {split ? <SplitValue value={value} /> : value}
        </div>
      )}
      {detail ? <div className="market-state__detail">{detail}</div> : null}
    </div>
  );
}

function SplitValue({ value }: { value: string }) {
  const [rise, fall] = value.split(" / ");
  return (
    <>
      <span className="market-rise-text">{rise}</span>
      <span aria-hidden="true">/</span>
      <span className="market-fall-text">{fall}</span>
    </>
  );
}

function formatCny(value: number | null) {
  if (value === null) return "-";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}万亿`;
  if (absolute >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}亿`;
  if (absolute >= 10_000) return `${(value / 10_000).toFixed(0)}万`;
  return value.toFixed(0);
}

function formatTurnoverChange(value: number | null) {
  return value === null ? "昨日对比待确认" : `较昨日 ${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
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

function marketTone(value: number | null) {
  if (value === null || value === 0) return "";
  return value > 0 ? "market-rise-text" : "market-fall-text";
}
