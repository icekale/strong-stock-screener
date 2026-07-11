"use client";

import { ReloadOutlined } from "@ant-design/icons";
import * as echarts from "echarts";
import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { buildSectorReplicaChartOption } from "../../lib/sectorReplicaChartOption";
import {
  formatReplicaDateTime,
  formatReplicaMoney,
  formatReplicaNumber,
  formatReplicaPct,
  formatReplicaReportedMoney,
  formatReplicaReportedRatio,
  latestSectorReplicaSeriesTime,
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
  onRefresh: () => void;
  onSubThemeChange: (tag: string | null) => void;
  onToggleBoard: (code: string, checked: boolean) => void;
  radar: SectorReplicaRadarResponse | null;
  relatedTags: string[];
  selectedCodes: string[];
  stockLoading: boolean;
  stocks: SectorReplicaStockRow[];
};

const MODE_LABELS: Record<SectorReplicaMode, string> = {
  strength: "板块强度",
  main_flow: "主力流入",
};

const EMOTION_METRICS = [
  { key: "QX", label: "情绪指标", tone: "warning" },
  { key: "ZT", label: "涨停家数", tone: "danger" },
  { key: "DT", label: "跌停家数", tone: "success" },
  { key: "KQXY", label: "亏钱效应", tone: "warning" },
  { key: "HSLN", label: "主力流入", tone: "default" },
  { key: "LBGD", label: "连板高度", tone: "default" },
  { key: "SZ", label: "上涨家数", tone: "default-red" },
  { key: "XD", label: "下跌家数", tone: "default-green" },
  { key: "PB", label: "今日封板率", tone: "default" },
  { key: "ZTBX", label: "昨涨停表现", tone: "default" },
  { key: "LBBX", label: "昨连板表现", tone: "default" },
  { key: "JRLN", label: "今日5分钟量能", tone: "default" },
] as const;

export function SectorReplicaPanel({
  activeBoardCode,
  activeSubTheme,
  error,
  loading,
  mode,
  onActivateBoard,
  onModeChange,
  onRefresh,
  onSubThemeChange,
  onToggleBoard,
  radar,
  relatedTags,
  selectedCodes,
  stockLoading,
  stocks,
}: SectorReplicaPanelProps) {
  const selectedSet = useMemo(() => new Set(selectedCodes), [selectedCodes]);
  const activePlate = radar?.plates.find((item) => item.code === activeBoardCode) ?? radar?.plates[0] ?? null;
  const latestSeriesTime = radar ? latestSectorReplicaSeriesTime(radar.axis, radar.series) : null;

  return (
    <section className="market-radar-shell">
      <div className="market-radar-emotion-grid">
        {EMOTION_METRICS.map((item) => (
          <button
            aria-label={`${item.label} ${formatEmotionMetric(radar, item.key)}`}
            className={`market-radar-emotion-button is-${item.tone}`}
            key={item.key}
            type="button"
          >
            {item.label}：<span>{formatEmotionMetric(radar, item.key)}</span>
          </button>
        ))}
      </div>

      <div className="market-radar-plate-row">
        <aside className="market-radar-sidebar">
          <div className="market-radar-tabs">
            {(Object.keys(MODE_LABELS) as SectorReplicaMode[]).map((item) => (
              <button
                className={item === mode ? "is-active" : ""}
                aria-pressed={item === mode}
                key={item}
                onClick={() => onModeChange(item)}
                type="button"
              >
                {MODE_LABELS[item]}
              </button>
            ))}
          </div>
          <div className="market-radar-board-list-head">
            <div>
              <strong>{MODE_LABELS[mode]}</strong>
              <span>板块榜单</span>
            </div>
            <span className="market-radar-selection-count">
              {selectedCodes.length}/6 <small>对比</small>
            </span>
          </div>
          <div className="market-radar-board-list">
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
              <div className="market-radar-list-placeholder">
                {loading ? "正在读取板块..." : "暂无板块数据"}
              </div>
            )}
          </div>
        </aside>

        <div className="market-radar-main">
          {error ? (
            <div aria-live="polite" className="market-radar-error" role="status">
              {error}
            </div>
          ) : null}
          <div className="market-radar-chart-head">
            <div className="market-radar-chart-title">
              {activePlate?.name ?? "板块分时"}
              <span>
                {mode === "strength" ? "板块强度" : "主力流入"} · 截至 {latestSeriesTime ?? "--"}
              </span>
            </div>
            <div className="market-radar-chart-tools">
              <span>{sourceStatusText(radar?.source_status.find((source) => source.source.includes("短线侠")) ?? radar?.source_status[0])}</span>
              <button className="market-radar-refresh" disabled={loading} onClick={onRefresh} type="button">
                <ReloadOutlined />
                刷新
              </button>
            </div>
          </div>
          <div aria-busy={loading} className="market-radar-chart-region">
            <SectorReplicaChart loading={loading && !radar} mode={mode} radar={radar} />
          </div>
        </div>
      </div>

      <div aria-busy={stockLoading} className="market-radar-stock-panel">
        <SubThemeStrip
          activeSubTheme={activeSubTheme}
          onSubThemeChange={onSubThemeChange}
          tags={relatedTags}
        />
        <StockTable
          activeBoardName={activePlate?.name ?? null}
          loading={stockLoading && stocks.length === 0}
          rows={stocks}
        />
        <div className="market-radar-footer">
          <span>交易日 {radar?.trade_date ?? "-"}</span>
          <span>生成 {formatReplicaDateTime(radar?.generated_at)}</span>
          <span>{selectedCodes.length}/6 对比</span>
        </div>
      </div>
    </section>
  );
}

function formatEmotionMetric(radar: SectorReplicaRadarResponse | null, key: string): string {
  const value = latestMetricValue(radar?.qxlive.series[key]);
  if (value === null) {
    return "-";
  }
  if (key === "PB") {
    return `${value.toFixed(0)}%`;
  }
  if (key === "HSLN") {
    return formatReplicaNumber(value);
  }
  return formatReplicaNumber(value);
}

function latestMetricValue(values: Array<number | null> | undefined): number | null {
  if (!values) {
    return null;
  }
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const value = values[index];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
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
    <div className={`market-radar-board-row${active ? " is-active" : ""}${checked ? " is-checked" : ""}`}>
      <input
        aria-label={`加入对比：${plate.name}`}
        checked={checked}
        onChange={(event) => onToggle(event.target.checked)}
        type="checkbox"
      />
      <button
        aria-label={`查看${plate.name}板块`}
        aria-pressed={active}
        onClick={onActivate}
        type="button"
      >
        <span className="market-radar-board-name">{plate.name}</span>
        <span className="market-radar-board-value">{value}</span>
        {plate.ztcount > 0 ? <span className="market-radar-limit-badge">{plate.ztcount}涨停</span> : null}
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
    const getChartOption = () =>
      buildSectorReplicaChartOption({
        axis: radar.axis,
        compact: chartRef.current ? chartRef.current.clientWidth < 560 : false,
        mode,
        series: radar.series,
      });
    chart.setOption(getChartOption());
    const resize = () => {
      chart.resize();
      chart.setOption(getChartOption());
    };
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
    return <div className="market-radar-chart-empty">正在加载分时曲线...</div>;
  }
  if (!hasSeries) {
    return <div className="market-radar-chart-empty">暂无分时曲线，等待后台采样</div>;
  }
  return <div className="market-radar-chart" ref={chartRef} />;
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
    <div className="market-radar-tags-scroll">
      <div className="market-radar-tags">
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
    <div className="market-radar-table-wrap">
      <table className="market-radar-table">
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
            <th>竞量</th>
            <th>买成比</th>
            <th>封单</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.symbol}>
              <td className="market-radar-name-cell">
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
              <td>{formatReplicaReportedMoney(row.turnover_cny)}</td>
              <td>{formatReplicaMoney(row.circulating_value_cny)}</td>
              <td>{row.board_label}</td>
              <td className={valueToneClass(row.auction_pct_change)}>{formatReplicaPct(row.auction_pct_change)}</td>
              <td>{formatReplicaReportedMoney(row.auction_amount_cny)}</td>
              <td>{formatReplicaReportedNumber(row.auction_volume_ratio)}</td>
              <td className={valueToneClass(row.buy_ratio_pct)}>{formatReplicaReportedRatio(row.buy_ratio_pct)}</td>
              <td>{formatReplicaReportedMoney(row.seal_amount_cny)}</td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td className="market-radar-empty-row" colSpan={11}>
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
  return value >= 0 ? "market-radar-red" : "market-radar-green";
}

function formatReplicaReportedNumber(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value.toFixed(2) : "--";
}
