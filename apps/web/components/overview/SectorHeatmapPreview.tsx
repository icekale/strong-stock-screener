"use client";

import Link from "next/link";
import { useState, type CSSProperties } from "react";
import { buildSectorFlowRows, type PanelState, type SectorFlowRow } from "../../lib/marketOverview";
import type { SectorRadarResponse } from "../../lib/types";
import { DataState } from "../workbench/DataState";

type SectorHeatmapPreviewProps = {
  onRefresh: () => void;
  sectorRadar: PanelState<SectorRadarResponse> | null;
};

type FlowDirection = "inflow" | "outflow";

export function SectorHeatmapPreview({ onRefresh, sectorRadar }: SectorHeatmapPreviewProps) {
  const data = sectorRadar && sectorRadar.kind !== "error" ? sectorRadar.value : null;
  const [mobileDirection, setMobileDirection] = useState<FlowDirection>("inflow");
  const inflowRows = buildSectorFlowRows(data?.inflow ?? [], 6);
  const outflowRows = buildSectorFlowRows(data?.outflow ?? [], 6);
  const mobileRows = mobileDirection === "inflow" ? inflowRows : outflowRows;

  return (
    <section aria-labelledby="sector-preview-title" className="compact-panel sector-flow-panel overflow-hidden">
      <div className="compact-panel__header">
        <div className="min-w-0">
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="sector-preview-title">
            板块资金流
          </h2>
          <p className="m-0 truncate text-xs text-[var(--app-muted)]">
            {data ? `${data.flow_source} · ${flowStatusLabel(data.capital_flow_status)}` : "资金流雷达"}
          </p>
        </div>
        <Link className="shrink-0 text-xs font-medium text-[var(--app-primary)] hover:underline" href="/market?view=sectors">
          查看板块
        </Link>
      </div>
      {!data ? <DataState action={{ onClick: onRefresh }} kind={sectorRadar?.kind === "error" ? "error" : "loading"} subject="板块资金流" /> : null}
      {sectorRadar?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="板块资金流" /> : null}
      {data ? (
        <>
          <div className="sector-flow-chart" aria-label="板块净流入与净流出对比图">
            <div aria-hidden="true" className="sector-flow-axis" />
            <div className="sector-flow-chart__labels" aria-hidden="true">
              <span>净流出</span>
              <span>净流入</span>
            </div>
            {Array.from({ length: Math.max(inflowRows.length, outflowRows.length) }, (_, index) => (
              <div className="sector-flow-pair" key={`sector-flow-${index}`}>
                <DesktopFlowCell direction="outflow" row={outflowRows[index]} />
                <DesktopFlowCell direction="inflow" row={inflowRows[index]} />
              </div>
            ))}
            {inflowRows.length === 0 && outflowRows.length === 0 ? <DataState action={{ onClick: onRefresh }} kind="empty" subject="板块资金流" /> : null}
          </div>

          <div className="sector-flow-mobile">
            <div aria-label="资金流方向" className="sector-flow-segment" role="group">
              <button aria-pressed={mobileDirection === "inflow"} onClick={() => setMobileDirection("inflow")} type="button">
                净流入
              </button>
              <button aria-pressed={mobileDirection === "outflow"} onClick={() => setMobileDirection("outflow")} type="button">
                净流出
              </button>
            </div>
            {mobileRows.length > 0 ? (
              <div className="sector-flow-mobile__list">
                {mobileRows.map((row) => (
                  <MobileFlowRow direction={mobileDirection} key={`${mobileDirection}-${row.item.name}`} row={row} />
                ))}
              </div>
            ) : (
              <DataState action={{ onClick: onRefresh }} kind="empty" subject={mobileDirection === "inflow" ? "净流入" : "净流出"} />
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}

function DesktopFlowCell({ direction, row }: { direction: FlowDirection; row: SectorFlowRow | undefined }) {
  if (!row) {
    return <div className={`sector-flow-cell sector-flow-cell--${direction}`} />;
  }

  return (
    <div
      aria-label={flowAriaLabel(direction, row)}
      className={`sector-flow-cell sector-flow-cell--${direction}`}
      title={flowAriaLabel(direction, row)}
    >
      <div className="sector-flow-heading">
        <span>{row.item.name}</span>
        <strong>{formatCny(row.item.net_flow_cny)}</strong>
      </div>
      <div className="sector-flow-track">
        <div
          className={`sector-flow-bar sector-flow-bar--${direction}`}
          style={{ "--sector-flow-width": `${row.widthPercent}%` } as CSSProperties}
        />
      </div>
      <div className="sector-flow-meta">
        {row.item.leader ?? "-"} · {formatPercent(row.item.change_pct)} · 强度 {row.item.strength_score.toFixed(1)}
      </div>
    </div>
  );
}

function MobileFlowRow({ direction, row }: { direction: FlowDirection; row: SectorFlowRow }) {
  return (
    <div aria-label={flowAriaLabel(direction, row)} className="sector-flow-mobile__row">
      <div className="sector-flow-mobile__heading">
        <span>{row.item.name}</span>
        <strong className={direction === "inflow" ? "market-rise-text" : "market-fall-text"}>{formatCny(row.item.net_flow_cny)}</strong>
      </div>
      <div className={`sector-flow-mobile__track sector-flow-mobile__track--${direction}`}>
        <span style={{ width: `${row.widthPercent}%` }} />
      </div>
      <div className="sector-flow-meta">
        {row.item.leader ?? "-"} · {formatPercent(row.item.change_pct)} · 强度 {row.item.strength_score.toFixed(1)}
      </div>
    </div>
  );
}

function flowAriaLabel(direction: FlowDirection, row: SectorFlowRow) {
  const directionLabel = direction === "inflow" ? "净流入" : "净流出";
  return `${row.item.name}，${directionLabel} ${formatCny(row.item.net_flow_cny)}，领涨 ${row.item.leader ?? "暂无"}，涨跌幅 ${formatPercent(row.item.change_pct)}，强度 ${row.item.strength_score.toFixed(1)}`;
}

function flowStatusLabel(value: SectorRadarResponse["capital_flow_status"]) {
  if (value === "direct") return "直接口径";
  if (value === "estimated") return "估算口径";
  return "不可用";
}

function formatCny(value: number | null) {
  if (value === null) return "-";
  const absolute = Math.abs(value);
  if (absolute >= 100_000_000) return `${value > 0 ? "+" : ""}${(value / 100_000_000).toFixed(1)}亿`;
  if (absolute >= 10_000) return `${value > 0 ? "+" : ""}${(value / 10_000).toFixed(0)}万`;
  return `${value > 0 ? "+" : ""}${value.toFixed(0)}`;
}

function formatPercent(value: number | null) {
  return value === null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}
