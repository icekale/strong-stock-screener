"use client";

import * as echarts from "echarts";
import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { buildSectorReplicaChartOption } from "../../lib/sectorReplicaChartOption";
import {
  formatReplicaDateTime,
  formatReplicaMoney,
  formatReplicaNumber,
  formatReplicaPct,
  sourceStatusText,
} from "../../lib/sectorReplica";
import { buildStockDetailHref } from "../../lib/stockNavigation";
import type {
  SectorReplicaMode,
  SectorReplicaPlate,
  SectorReplicaRadarResponse,
  SectorReplicaStockRow,
} from "../../lib/types";

type SectorReplicaPanelProps = {
  activeBoardCode: string | null;
  activeSubTheme: string | null;
  error: string | null;
  loading: boolean;
  mode: SectorReplicaMode;
  onActivateBoard: (code: string) => void;
  onModeChange: (mode: SectorReplicaMode) => void;
  onSubThemeChange: (tag: string | null) => void;
  onToggleBoard: (code: string, checked: boolean) => void;
  radar: SectorReplicaRadarResponse | null;
  selectedCodes: string[];
  stockLoading: boolean;
  stocks: SectorReplicaStockRow[];
};

const MODE_LABELS: Record<SectorReplicaMode, string> = {
  strength: "板块强度",
  main_flow: "主力流入",
};

export function SectorReplicaPanel({
  activeBoardCode,
  activeSubTheme,
  error,
  loading,
  mode,
  onActivateBoard,
  onModeChange,
  onSubThemeChange,
  onToggleBoard,
  radar,
  selectedCodes,
  stockLoading,
  stocks,
}: SectorReplicaPanelProps) {
  const selectedSet = useMemo(() => new Set(selectedCodes), [selectedCodes]);
  const activePlate = radar?.plates.find((item) => item.code === activeBoardCode) ?? radar?.plates[0] ?? null;

  return (
    <section className="sector-replica-shell">
      <aside className="sector-replica-sidebar">
        <div className="sector-replica-tabs">
          {(Object.keys(MODE_LABELS) as SectorReplicaMode[]).map((item) => (
            <button
              className={item === mode ? "is-active" : ""}
              key={item}
              onClick={() => onModeChange(item)}
              type="button"
            >
              {MODE_LABELS[item]}
            </button>
          ))}
        </div>
        <div className="sector-replica-board-list">
          {(radar?.plates ?? []).map((plate) => (
            <BoardListItem
              active={activeBoardCode === plate.code}
              checked={selectedSet.has(plate.code)}
              key={plate.code}
              mode={mode}
              onActivate={() => onActivateBoard(plate.code)}
              onToggle={(checked) => onToggleBoard(plate.code, checked)}
              plate={plate}
            />
          ))}
          {!radar && (
            <div className="sector-replica-list-placeholder">
              {loading ? "正在读取板块..." : "暂无板块数据"}
            </div>
          )}
        </div>
      </aside>

      <div className="sector-replica-main">
        {error ? <div className="sector-replica-error">{error}</div> : null}
        <div className="sector-replica-chart-head">
          <div className="sector-replica-chart-title">
            {activePlate?.name ?? "板块分时"}
            <span>{mode === "strength" ? "强度曲线" : "资金曲线"}</span>
          </div>
          <div className="sector-replica-source">
            {sourceStatusText(radar?.source_status.find((item) => item.source.includes("短线侠")) ?? radar?.source_status[0])}
          </div>
        </div>
        <SectorReplicaChart loading={loading && !radar} mode={mode} radar={radar} />
        <SubThemeStrip
          activeSubTheme={activeSubTheme}
          onSubThemeChange={onSubThemeChange}
          tags={radar?.related_tags ?? []}
        />
        <StockTable
          activeBoardName={activePlate?.name ?? null}
          loading={stockLoading && stocks.length === 0}
          rows={stocks}
        />
        <div className="sector-replica-footer">
          <span>交易日 {radar?.trade_date ?? "-"}</span>
          <span>生成 {formatReplicaDateTime(radar?.generated_at)}</span>
          <span>{selectedCodes.length}/5 对比</span>
        </div>
      </div>
    </section>
  );
}

function BoardListItem({
  active,
  checked,
  mode,
  onActivate,
  onToggle,
  plate,
}: {
  active: boolean;
  checked: boolean;
  mode: SectorReplicaMode;
  onActivate: () => void;
  onToggle: (checked: boolean) => void;
  plate: SectorReplicaPlate;
}) {
  const value = mode === "main_flow" ? plate.display_value ?? formatReplicaMoney(plate.val) : formatReplicaNumber(plate.val);
  return (
    <div className={`sector-replica-board-row${active ? " is-active" : ""}${checked ? " is-checked" : ""}`}>
      <input
        aria-label={`选择${plate.name}`}
        checked={checked}
        onChange={(event) => onToggle(event.target.checked)}
        type="checkbox"
      />
      <button onClick={onActivate} type="button">
        <span className="sector-replica-board-name">{plate.name}</span>
        <span className="sector-replica-board-value">{value}</span>
        {plate.ztcount > 0 ? <span className="sector-replica-limit-badge">{plate.ztcount}涨停</span> : null}
      </button>
    </div>
  );
}

function SectorReplicaChart({
  loading,
  mode,
  radar,
}: {
  loading: boolean;
  mode: SectorReplicaMode;
  radar: SectorReplicaRadarResponse | null;
}) {
  const chartRef = useRef<HTMLDivElement>(null);
  const hasSeries = Boolean(radar?.series.some((item) => item.data.some((point) => point !== null)));

  useEffect(() => {
    if (!chartRef.current || !radar || !hasSeries) {
      return;
    }
    const chart = echarts.init(chartRef.current);
    chart.setOption(buildSectorReplicaChartOption({ axis: radar.axis, mode, series: radar.series }));
    const resize = () => chart.resize();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(resize);
      observer.observe(chartRef.current);
      return () => {
        observer.disconnect();
        chart.dispose();
      };
    }
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [hasSeries, mode, radar]);

  if (loading) {
    return <div className="sector-replica-chart-empty">正在加载分时曲线...</div>;
  }
  if (!hasSeries) {
    return <div className="sector-replica-chart-empty">暂无分时曲线，等待后台采样</div>;
  }
  return <div className="sector-replica-chart" ref={chartRef} />;
}

function SubThemeStrip({
  activeSubTheme,
  onSubThemeChange,
  tags,
}: {
  activeSubTheme: string | null;
  onSubThemeChange: (tag: string | null) => void;
  tags: string[];
}) {
  const visibleTags = tags.slice(0, 28);
  return (
    <div className="sector-replica-tags">
      <button className={activeSubTheme === null ? "is-active" : ""} onClick={() => onSubThemeChange(null)} type="button">
        全部
      </button>
      {visibleTags.map((tag) => (
        <button
          className={activeSubTheme === tag ? "is-active" : ""}
          key={tag}
          onClick={() => onSubThemeChange(tag)}
          type="button"
        >
          {tag}
        </button>
      ))}
      {visibleTags.length === 0 ? <span>暂无关联题材</span> : null}
    </div>
  );
}

function StockTable({
  activeBoardName,
  loading,
  rows,
}: {
  activeBoardName: string | null;
  loading: boolean;
  rows: SectorReplicaStockRow[];
}) {
  return (
    <div className="sector-replica-table-wrap">
      <table className="sector-replica-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>代码</th>
            <th>涨幅</th>
            <th>成交</th>
            <th>流通</th>
            <th>板数</th>
            <th>竞涨</th>
            <th>竞额</th>
            <th>竟量</th>
            <th>买成比</th>
            <th>封单</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.symbol}>
              <td className="sector-replica-name-cell">
                <Link
                  href={buildStockDetailHref(row.symbol, {
                    from: "sectors",
                    industry: row.industry ?? activeBoardName,
                    name: row.name,
                  })}
                >
                  {row.name ?? row.symbol}
                </Link>
                {row.leader_tag ? <span>{row.leader_tag}</span> : null}
              </td>
              <td>{row.code}</td>
              <td className={valueToneClass(row.pct_change)}>{formatReplicaPct(row.pct_change)}</td>
              <td>{formatReplicaMoney(row.turnover_cny)}</td>
              <td>{formatReplicaMoney(row.circulating_value_cny)}</td>
              <td>{row.board_label}</td>
              <td className={valueToneClass(row.auction_pct_change)}>{formatReplicaPct(row.auction_pct_change)}</td>
              <td>{formatReplicaMoney(row.auction_amount_cny)}</td>
              <td>{row.auction_volume_ratio === null ? "-" : row.auction_volume_ratio.toFixed(2)}</td>
              <td className={valueToneClass(row.buy_ratio_pct)}>{formatReplicaPct(row.buy_ratio_pct)}</td>
              <td>{formatReplicaMoney(row.seal_amount_cny)}</td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td className="sector-replica-empty-row" colSpan={11}>
                {loading ? "正在读取成分股..." : "暂无成分股"}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function valueToneClass(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "";
  }
  return value >= 0 ? "sector-replica-red" : "sector-replica-green";
}
