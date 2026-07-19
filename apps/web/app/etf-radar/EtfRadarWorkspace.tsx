"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Table, Tabs, Tag } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { OverviewTrendChart } from "../../components/overview/OverviewTrendChart";
import { DataState } from "../../components/workbench/DataState";
import { PageFrame } from "../../components/workbench/PageFrame";
import {
  directionTone,
  formatDirectionalCny,
  formatDirectionalPercent,
  formatDirectionalShares,
  formatEvidenceStrength,
  formatPlainShares,
} from "../../lib/capitalSignals";
import {
  getEtfRadarHistory,
  getEtfRadarHolders,
  getEtfRadarMethodology,
  getEtfRadarOverview,
} from "../../lib/api";
import type {
  CapitalSignalMetadata,
  EtfHolderPosition,
  EtfRadarHistoryPoint,
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarItem,
  EtfRadarMethodologyResponse,
  EtfRadarOverviewResponse,
} from "../../lib/types";
import { createMemoryRequestCache } from "../../lib/marketOverviewCache";

type RadarView = "overview" | "shares" | "holders" | "methodology";
const etfRadarRequestCache = createMemoryRequestCache({ ttlMs: 15_000 });

export function EtfRadarWorkspace() {
  const [activeView, setActiveView] = useState<RadarView>("overview");
  const [overview, setOverview] = useState<EtfRadarOverviewResponse | null>(null);
  const [history, setHistory] = useState<EtfRadarHistoryResponse | null>(null);
  const [holders, setHolders] = useState<EtfRadarHoldersResponse | null>(null);
  const [methodology, setMethodology] = useState<EtfRadarMethodologyResponse | null>(null);
  const [loading, setLoading] = useState<Set<RadarView>>(new Set(["overview"]));
  const [errors, setErrors] = useState<Set<RadarView>>(new Set());

  const loadView = useCallback(async (view: RadarView, force = false) => {
    const existing = view === "overview" ? overview : view === "shares" ? history : view === "holders" ? holders : methodology;
    if (existing && !force) return;
    setLoading((current) => new Set(current).add(view));
    setErrors((current) => without(current, view));
    try {
      if (view === "overview") {
        setOverview(await etfRadarRequestCache.get("etf-radar:overview", getEtfRadarOverview, { force }));
      }
      if (view === "shares") {
        setHistory(await etfRadarRequestCache.get("etf-radar:history", () => getEtfRadarHistory(120), { force }));
      }
      if (view === "holders") {
        setHolders(await etfRadarRequestCache.get("etf-radar:holders", getEtfRadarHolders, { force }));
      }
      if (view === "methodology") {
        setMethodology(await etfRadarRequestCache.get("etf-radar:methodology", getEtfRadarMethodology, { force }));
      }
    } catch {
      setErrors((current) => new Set(current).add(view));
    } finally {
      setLoading((current) => without(current, view));
    }
  }, [history, holders, methodology, overview]);

  useEffect(() => {
    void loadView("overview");
  }, [loadView]);

  const currentMetadata = metadataFor(activeView, { history, holders, methodology, overview });
  const isLoading = loading.has(activeView);

  return (
    <PageFrame
      actions={
        <Button icon={<ReloadOutlined />} loading={isLoading} onClick={() => void loadView(activeView, true)}>
          刷新
        </Button>
      }
      context={currentMetadata ? `${currentMetadata.trade_date} · ${stageLabel(currentMetadata.signal_stage)} · ${formatTime(currentMetadata.as_of)}` : "交易所份额与资金代理证据"}
      status={currentMetadata ? <Tag color={metadataTone(currentMetadata)}>{currentMetadata.model_version}</Tag> : undefined}
      title="ETF资金雷达"
    >
      <div className="etf-radar-workspace">
        <Tabs
          activeKey={activeView}
          destroyOnHidden={false}
          items={[
            { key: "overview", label: "盘中雷达", children: <OverviewView data={overview} error={errors.has("overview")} loading={loading.has("overview")} onRetry={() => void loadView("overview", true)} /> },
            { key: "shares", label: "份额变化", children: <ShareHistoryView data={history} error={errors.has("shares")} loading={loading.has("shares")} onRetry={() => void loadView("shares", true)} /> },
            { key: "holders", label: "持有人披露", children: <HolderView data={holders} error={errors.has("holders")} loading={loading.has("holders")} onRetry={() => void loadView("holders", true)} /> },
            { key: "methodology", label: "方法与验证", children: <MethodologyView data={methodology} error={errors.has("methodology")} loading={loading.has("methodology")} onRetry={() => void loadView("methodology", true)} /> },
          ]}
          onChange={(key) => {
            const next = key as RadarView;
            setActiveView(next);
            void loadView(next);
          }}
        />
      </div>
    </PageFrame>
  );
}

function OverviewView({ data, error, loading, onRetry }: ViewProps<EtfRadarOverviewResponse>) {
  if (!data) return <ViewState error={error} loading={loading} onRetry={onRetry} subject="ETF资金雷达" />;
  return (
    <div className="etf-radar-view">
      <section className="compact-panel etf-radar-summary-strip">
        <SummaryMetric label="证据强度" value={formatEvidenceStrength(data.evidence_strength)} />
        <SummaryMetric label="证据等级" value={data.evidence_level ?? "待确认"} />
        <SummaryMetric label="估算净申购" tone={directionTone(data.estimated_subscription_cny)} value={formatDirectionalCny(data.estimated_subscription_cny)} />
        <SummaryMetric label="有效ETF" value={`${data.valid_etf_count}/${data.expected_etf_count}`} />
      </section>
      <section className="compact-panel">
        <div className="compact-panel__header"><div><h2 className="m-0 text-sm font-semibold">宽基ETF证据明细</h2><p className="m-0 text-xs text-[var(--app-muted)]">{stageLabel(data.signal_stage)} · 缺失因子不计分</p></div></div>
        {data.evidence.length > 0 ? <div className="etf-evidence-banner">{data.evidence.slice(0, 3).map((item) => <span key={item}>{item}</span>)}</div> : null}
        <Table<EtfRadarItem>
          columns={overviewColumns}
          dataSource={data.items}
          locale={{ emptyText: "暂无有效ETF证据" }}
          pagination={false}
          rowKey="symbol"
          scroll={{ x: 980 }}
          size="small"
        />
      </section>
      <SourceStatus metadata={data} />
    </div>
  );
}

function ShareHistoryView({ data, error, loading, onRetry }: ViewProps<EtfRadarHistoryResponse>) {
  const chartOption = useMemo(() => data && data.points.length > 0 ? historyChartOption(data.points) : null, [data]);
  if (!data) return <ViewState error={error} loading={loading} onRetry={onRetry} subject="ETF份额历史" />;
  if (data.points.length === 0) return <ViewState error={false} loading={false} onRetry={onRetry} subject="ETF份额历史" />;
  return (
    <div className="etf-radar-view">
      <section className="compact-panel overflow-hidden">
        <div className="compact-panel__header"><div><h2 className="m-0 text-sm font-semibold">估算净申购金额</h2><p className="m-0 text-xs text-[var(--app-muted)]">按交易日合计 · 份额变化 × 当日价格</p></div></div>
        {chartOption ? <OverviewTrendChart className="etf-history-chart" option={chartOption} /> : null}
      </section>
      <section className="compact-panel overflow-hidden">
        <div className="compact-panel__header"><h2 className="m-0 text-sm font-semibold">份额记录</h2></div>
        <Table<EtfRadarHistoryPoint> columns={historyColumns} dataSource={[...data.points].reverse()} pagination={{ pageSize: 20, showSizeChanger: false }} rowKey={(row) => `${row.trade_date}-${row.symbol}`} scroll={{ x: 840 }} size="small" />
      </section>
      <SourceStatus metadata={data} />
    </div>
  );
}

function HolderView({ data, error, loading, onRetry }: ViewProps<EtfRadarHoldersResponse>) {
  if (!data) return <ViewState error={error} loading={loading} onRetry={onRetry} subject="持有人披露" />;
  if (data.positions.length === 0) return <ViewState error={false} loading={false} onRetry={onRetry} subject="国家队持仓披露" />;
  return (
    <div className="etf-radar-view">
      <section className="compact-panel overflow-hidden">
        <div className="compact-panel__header"><div><h2 className="m-0 text-sm font-semibold">国家队持仓披露</h2><p className="m-0 text-xs text-[var(--app-muted)]">仅展示精确法定实体与明确报告期</p></div></div>
        <Table<EtfHolderPosition> columns={holderColumns} dataSource={data.positions} pagination={false} rowKey={(row) => `${row.report_period}-${row.symbol}-${row.entity_name}`} scroll={{ x: 860 }} size="small" />
      </section>
      <SourceStatus metadata={data} />
    </div>
  );
}

function MethodologyView({ data, error, loading, onRetry }: ViewProps<EtfRadarMethodologyResponse>) {
  if (!data) return <ViewState error={error} loading={loading} onRetry={onRetry} subject="方法定义" />;
  return (
    <div className="etf-radar-view etf-methodology-grid">
      <section className="compact-panel">
        <div className="compact-panel__header"><h2 className="m-0 text-sm font-semibold">因子定义</h2><Tag>{data.pool_version}</Tag></div>
        <div className="etf-method-list">{data.factors.map((factor) => <div key={factor.key}><strong>{factor.name}</strong><span>{factor.description}</span><Tag>{factor.availability}</Tag></div>)}</div>
      </section>
      <section className="compact-panel">
        <div className="compact-panel__header"><h2 className="m-0 text-sm font-semibold">阈值与限制</h2></div>
        <dl className="etf-threshold-list"><div><dt>观察</dt><dd>≥ {data.thresholds.watch ?? "--"}</dd></div><div><dt>疑似</dt><dd>≥ {data.thresholds.suspected ?? "--"}</dd></div><div><dt>较强</dt><dd>≥ {data.thresholds.strong ?? "--"}</dd></div></dl>
        <ul className="etf-limitations">{data.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>
      <SourceStatus metadata={data} />
    </div>
  );
}

const overviewColumns = [
  { title: "ETF", key: "etf", fixed: "left" as const, width: 150, render: (_: unknown, row: EtfRadarItem) => <div className="etf-symbol-cell"><strong>{row.name}</strong><span>{row.symbol}</span></div> },
  { title: "跟踪指数", dataIndex: "index_name", width: 110 },
  { title: "证据强度", dataIndex: "evidence_strength", width: 100, render: (value: number | null) => formatEvidenceStrength(value) },
  { title: "份额变化", dataIndex: "share_change", align: "right" as const, width: 120, render: (value: number | null) => <DirectionValue value={value} formatter={formatDirectionalShares} /> },
  { title: "估算净申购", dataIndex: "estimated_subscription_cny", align: "right" as const, width: 130, render: (value: number | null) => <DirectionValue value={value} formatter={formatDirectionalCny} /> },
  { title: "稳健标准分", dataIndex: "robust_score", align: "right" as const, width: 110, render: (value: number | null) => value === null ? "--" : value.toFixed(2) },
  { title: "同刻成交", dataIndex: "same_time_turnover_ratio", align: "right" as const, width: 100, render: (value: number | null) => value === null ? "--" : `${value.toFixed(2)}x` },
  { title: "相对指数", dataIndex: "relative_index_return_pct", align: "right" as const, width: 110, render: (value: number | null) => <DirectionValue value={value} formatter={formatDirectionalPercent} /> },
];

const historyColumns = [
  { title: "交易日", dataIndex: "trade_date", width: 110 },
  { title: "ETF", key: "etf", width: 160, render: (_: unknown, row: EtfRadarHistoryPoint) => `${row.name} · ${row.symbol}` },
  { title: "总份额", dataIndex: "total_shares", align: "right" as const, width: 130, render: formatPlainShares },
  { title: "份额变化", dataIndex: "share_change", align: "right" as const, width: 130, render: (value: number | null) => <DirectionValue value={value} formatter={formatDirectionalShares} /> },
  { title: "估算净申购", dataIndex: "estimated_subscription_cny", align: "right" as const, width: 140, render: (value: number | null) => <DirectionValue value={value} formatter={formatDirectionalCny} /> },
  { title: "稳健标准分", dataIndex: "robust_score", align: "right" as const, width: 110, render: (value: number | null) => value === null ? "--" : value.toFixed(2) },
];

const holderColumns = [
  { title: "报告期", dataIndex: "report_period", width: 110 },
  { title: "ETF", key: "etf", width: 160, render: (_: unknown, row: EtfHolderPosition) => `${row.name} · ${row.symbol}` },
  { title: "披露实体", dataIndex: "entity_name", width: 220 },
  { title: "持有份额", dataIndex: "shares", align: "right" as const, width: 120, render: formatPlainShares },
  { title: "持有比例", dataIndex: "holding_pct", align: "right" as const, width: 100, render: (value: number | null) => value === null ? "--" : `${value.toFixed(2)}%` },
  { title: "较上期", dataIndex: "change_shares", align: "right" as const, width: 120, render: (value: number | null) => <DirectionValue value={value} formatter={formatDirectionalShares} /> },
  { title: "来源", dataIndex: "source", width: 120 },
];

function SummaryMetric({ label, tone = "neutral", value }: { label: string; tone?: "fall" | "neutral" | "rise"; value: string }) {
  return <div><span>{label}</span><strong className={toneClass(tone)}>{value}</strong></div>;
}

function DirectionValue({ value, formatter }: { value: number | null; formatter: (value: number | null) => string }) {
  return <span className={toneClass(directionTone(value))}>{formatter(value)}</span>;
}

function SourceStatus({ metadata }: { metadata: CapitalSignalMetadata }) {
  return <div className="etf-source-status">{metadata.source_status.map((item) => <Tag color={item.status === "success" ? "blue" : item.status === "failed" ? "red" : "gold"} key={`${item.source}-${item.detail}`}>{item.source} · {item.detail}</Tag>)}</div>;
}

function ViewState({ error, loading, onRetry, subject }: { error: boolean; loading: boolean; onRetry: () => void; subject: string }) {
  return <section className="compact-panel"><DataState action={{ onClick: onRetry }} kind={error ? "error" : loading ? "loading" : "empty"} subject={subject} /></section>;
}

type ViewProps<T> = { data: T | null; error: boolean; loading: boolean; onRetry: () => void };

function historyChartOption(points: EtfRadarHistoryPoint[]) {
  const totals = new Map<string, number>();
  for (const point of points) {
    if (point.estimated_subscription_cny !== null) totals.set(point.trade_date, (totals.get(point.trade_date) ?? 0) + point.estimated_subscription_cny);
  }
  const dates = [...totals.keys()].sort();
  return {
    animation: false,
    grid: { left: 62, right: 22, top: 24, bottom: 34 },
    tooltip: { trigger: "axis", valueFormatter: (value: unknown) => formatDirectionalCny(typeof value === "number" ? value : null) },
    xAxis: { type: "category", data: dates, axisLabel: { color: "#697991", hideOverlap: true } },
    yAxis: { type: "value", axisLabel: { color: "#697991", formatter: (value: number) => `${(value / 100_000_000).toFixed(0)}亿` }, splitLine: { lineStyle: { color: "#e5ebf2" } } },
    series: [{ type: "bar", data: dates.map((date) => ({ value: totals.get(date), itemStyle: { color: (totals.get(date) ?? 0) >= 0 ? "#d9363e" : "#07845e" } })), barMaxWidth: 24 }],
  };
}

function metadataFor(view: RadarView, data: { overview: EtfRadarOverviewResponse | null; history: EtfRadarHistoryResponse | null; holders: EtfRadarHoldersResponse | null; methodology: EtfRadarMethodologyResponse | null }): CapitalSignalMetadata | null {
  if (view === "overview") return data.overview;
  if (view === "shares") return data.history;
  if (view === "holders") return data.holders;
  return data.methodology;
}

function without<T>(values: Set<T>, value: T): Set<T> { const next = new Set(values); next.delete(value); return next; }
function stageLabel(stage: CapitalSignalMetadata["signal_stage"]): string { return stage === "intraday" ? "盘中代理" : stage === "disclosure" ? "定期披露" : "盘后确认"; }
function metadataTone(metadata: CapitalSignalMetadata): string { return metadata.source_status.some((item) => item.status !== "success") ? "gold" : "blue"; }
function formatTime(value: string): string { return value.replace("T", " ").slice(0, 16); }
function toneClass(tone: "fall" | "neutral" | "rise"): string { return tone === "rise" ? "market-rise-text" : tone === "fall" ? "market-fall-text" : ""; }
