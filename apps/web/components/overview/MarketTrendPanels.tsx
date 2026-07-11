"use client";

import { Button } from "antd";
import Link from "next/link";
import { useMemo } from "react";
import type { PanelState } from "../../lib/marketOverview";
import { buildMarketEmotionChartOption, buildMarketEmotionTrend } from "../../lib/marketOverviewTrend";
import { buildSectorReplicaChartOption } from "../../lib/sectorReplicaChartOption";
import type { MarketEmotionSnapshotResponse, SectorReplicaRadarResponse } from "../../lib/types";
import { DataState } from "../workbench/DataState";
import { OverviewTrendChart } from "./OverviewTrendChart";

export function MarketTrendPanels({
  emotion,
  onRefreshEmotion,
  onRefreshSector,
  sector,
}: {
  emotion: PanelState<MarketEmotionSnapshotResponse> | null;
  onRefreshEmotion: () => void;
  onRefreshSector: () => void;
  sector: PanelState<SectorReplicaRadarResponse> | null;
}) {
  return (
    <div className="market-trend-grid">
      <SectorRotationPanel onRefresh={onRefreshSector} state={sector} />
      <EmotionTrendPanel onRefresh={onRefreshEmotion} state={emotion} />
    </div>
  );
}

function SectorRotationPanel({
  onRefresh,
  state,
}: {
  onRefresh: () => void;
  state: PanelState<SectorReplicaRadarResponse> | null;
}) {
  const data = state && state.kind !== "error" ? state.value : null;
  const usableSeries = useMemo(
    () => data?.series.filter((item) => item.data.some((point) => point !== null)).slice(0, 6) ?? [],
    [data],
  );
  const option = useMemo(
    () =>
      data && usableSeries.length > 0
        ? buildSectorReplicaChartOption({ axis: data.axis, compact: true, mode: "strength", series: usableSeries })
        : null,
    [data, usableSeries],
  );

  return (
    <section aria-labelledby="sector-rotation-title" className="compact-panel market-trend-panel overflow-hidden">
      <div className="compact-panel__header">
        <div className="min-w-0">
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="sector-rotation-title">板块轮动</h2>
          <p className="m-0 truncate text-xs text-[var(--app-muted)]">强势题材盘中变化 · 最多 6 条</p>
        </div>
        <Link className="shrink-0 text-xs font-medium text-[var(--app-primary)] hover:underline" href="/market?view=sectors">
          查看板块
        </Link>
      </div>
      {state?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="板块轮动" /> : null}
      {option ? <OverviewTrendChart className="market-trend-chart--sector" option={option} /> : null}
      {!option ? (
        <div className="market-trend-state">
          <DataState
            action={{ onClick: onRefresh }}
            kind={state?.kind === "error" ? "error" : data ? "empty" : "loading"}
            subject="板块轮动曲线"
          />
        </div>
      ) : null}
    </section>
  );
}

function EmotionTrendPanel({
  onRefresh,
  state,
}: {
  onRefresh: () => void;
  state: PanelState<MarketEmotionSnapshotResponse> | null;
}) {
  const data = state && state.kind !== "error" ? state.value : null;
  const trend = useMemo(() => (data ? buildMarketEmotionTrend(data) : null), [data]);
  const option = useMemo(
    () => (trend && trend.times.length >= 2 ? buildMarketEmotionChartOption(trend) : null),
    [trend],
  );

  return (
    <section aria-labelledby="emotion-trend-title" className="compact-panel market-trend-panel overflow-hidden">
      <div className="compact-panel__header">
        <div className="min-w-0">
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="emotion-trend-title">盘中情绪走势</h2>
          <p className="m-0 truncate text-xs text-[var(--app-muted)]">情绪分与上涨占比 · 0-100</p>
        </div>
        <Link className="shrink-0 text-xs font-medium text-[var(--app-primary)] hover:underline" href="/sentiment">
          查看情绪
        </Link>
      </div>
      {state?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="盘中情绪" /> : null}
      {option ? <OverviewTrendChart className="market-trend-chart--emotion" option={option} /> : null}
      {!option ? (
        <div className="market-trend-state market-trend-state--emotion">
          {data ? (
            <div className="market-trend-empty">
              <strong>盘中样本不足</strong>
              <p>仅保留交易时段采样，累计 2 个点后绘制。</p>
              <Button onClick={onRefresh} size="small">刷新</Button>
            </div>
          ) : (
            <DataState
              action={{ onClick: onRefresh }}
              kind={state?.kind === "error" ? "error" : "loading"}
              subject="盘中情绪曲线"
            />
          )}
        </div>
      ) : null}
      {trend ? (
        <div className="market-trend-summary">
          <TrendSummary label="当前情绪" value={`${formatScore(trend.latest.emotionScore)} · ${trend.latest.emotionLevel}`} />
          <TrendSummary
            label="区间变化"
            tone={trend.scoreChange === null ? "neutral" : trend.scoreChange >= 0 ? "rise" : "fall"}
            value={formatScoreChange(trend.scoreChange)}
          />
          <TrendSummary label="涨停 / 跌停" split value={`${trend.latest.limitUpCount} / ${trend.latest.limitDownCount ?? "-"}`} />
        </div>
      ) : null}
    </section>
  );
}

function TrendSummary({
  label,
  split = false,
  tone = "neutral",
  value,
}: {
  label: string;
  split?: boolean;
  tone?: "fall" | "neutral" | "rise";
  value: string;
}) {
  const toneClass = tone === "rise" ? "market-rise-text" : tone === "fall" ? "market-fall-text" : "text-[var(--app-ink)]";
  if (split) {
    const [rise, fall] = value.split(" / ");
    return (
      <div className="market-trend-summary__item">
        <span>{label}</span>
        <strong><b className="market-rise-text">{rise}</b> / <b className="market-fall-text">{fall}</b></strong>
      </div>
    );
  }
  return (
    <div className="market-trend-summary__item">
      <span>{label}</span>
      <strong className={toneClass}>{value}</strong>
    </div>
  );
}

function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function formatScoreChange(value: number | null): string {
  if (value === null) {
    return "样本不足";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}
