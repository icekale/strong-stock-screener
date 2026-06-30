"use client";

import { DownloadOutlined, SearchOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Button, Input, Tag } from "antd";
import type {
  DataSourceStatusResponse,
  MarketOverviewResponse,
  SectorRadarItem,
  SectorRadarResponse,
  SentimentSummaryResponse,
  StrongStockScreeningItem,
  StrongStockScreeningResponse,
} from "../../lib/types";
import { realtimeTurnoverSubtitles, type MarketDashboardStats } from "./types";
import {
  exportCandidatesCsv,
  formatCnyCompact,
  formatDateTime,
  formatSignedCny,
  formatSignedPercent,
  formatTurnoverChange,
  marketOverviewSourceSummary,
  realtimeTurnoverSourceLabel,
  sectorRadarSourceSummary,
  sourceSummary,
  sumNegativeSectorFlow,
  sumPositiveSectorFlow,
} from "./screenerUtils";

export function MarketOverviewPanels({
  candidates,
  generatedAt,
  marketOverview,
  onRun,
  result,
  running,
  sectorRadar,
  sentimentSummary,
  sources,
  stats,
}: {
  candidates: StrongStockScreeningItem[];
  generatedAt: string | null;
  marketOverview: MarketOverviewResponse | null;
  onRun: () => void;
  result: StrongStockScreeningResponse | null;
  running: boolean;
  sectorRadar: SectorRadarResponse | null;
  sentimentSummary: SentimentSummaryResponse | null;
  sources: DataSourceStatusResponse | null;
  stats: MarketDashboardStats;
}) {
  return (
    <>
      <MarketTickerBar
        candidates={candidates}
        generatedAt={generatedAt}
        marketOverview={marketOverview}
        onRun={onRun}
        running={running}
        sources={sources}
      />
      <MarketEnvironmentPanel
        marketOverview={marketOverview}
        result={result}
        sectorRadar={sectorRadar}
        sentimentSummary={sentimentSummary}
        sources={sources}
        stats={stats}
      />
    </>
  );
}

export function MarketTickerBar({
  candidates,
  generatedAt,
  marketOverview,
  onRun,
  running,
  sources,
}: {
  candidates: StrongStockScreeningItem[];
  generatedAt: string | null;
  marketOverview: MarketOverviewResponse | null;
  onRun: () => void;
  running: boolean;
  sources: DataSourceStatusResponse | null;
}) {
  const sourceState = sourceSummary(sources);
  const indices = marketOverview?.indices ?? [];

  return (
    <header className="rounded-lg border border-[#ddd8d0] bg-[#f8f7f4]">
      <div className="flex flex-col gap-3 px-4 py-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <MarketIndexPill index={findMarketIndex(indices, "000001.SH", "上证")} />
          <MarketIndexPill index={findMarketIndex(indices, "399001.SZ", "深证")} />
          <MarketIndexPill index={findMarketIndex(indices, "399006.SZ", "创业板")} />
          <MarketIndexPill index={findMarketIndex(indices, "000688.SH", "科创50")} />
          <span className="mx-2 hidden h-7 w-px bg-[#d6d0c7] xl:block" />
          <span className="inline-flex h-8 items-center gap-2 rounded-full px-3 text-xs font-semibold text-[#7b756d]">
            <span className={`size-2 rounded-full ${sourceState.ok ? "market-green-fill" : "bg-amber-500"}`} />
            LIVE · {generatedAt ? formatDateTime(generatedAt) : "等待筛选"}
          </span>
          <Tag className="m-0" color={sourceState.ok ? "green" : "orange"}>
            数据源 {sourceState.label}
          </Tag>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
          <Input
            className="w-full min-w-[220px] max-w-[360px] xl:w-[300px]"
            disabled
            prefix={<SearchOutlined />}
            placeholder="Search stock, code..."
          />
          <Button
            icon={<ThunderboltOutlined />}
            loading={running}
            onClick={onRun}
            type="primary"
          >
            {running ? "筛选中" : "运行 AI 筛选"}
          </Button>
          <Button
            disabled={candidates.length === 0}
            icon={<DownloadOutlined />}
            onClick={() => exportCandidatesCsv(candidates)}
          >
            导出 CSV
          </Button>
        </div>
      </div>
    </header>
  );
}

function findMarketIndex(
  indices: MarketOverviewResponse["indices"],
  symbol: string,
  fallbackName: string,
): MarketOverviewResponse["indices"][number] {
  return indices.find((item) => item.symbol === symbol) ?? {
    symbol,
    name: fallbackName,
    last_price: null,
    change_pct: null,
    turnover_cny: null,
    source: "待数据",
  };
}

function MarketIndexPill({ index }: { index: MarketOverviewResponse["indices"][number] }) {
  const changePct = index.change_pct;
  const hasChange = changePct !== null && changePct !== undefined && Number.isFinite(changePct);
  const isUp = hasChange && changePct >= 0;
  const status = hasChange ? formatSignedPercent(changePct) : "待数据";
  const price = index.last_price === null || index.last_price === undefined || !Number.isFinite(index.last_price)
    ? null
    : index.last_price.toFixed(2);

  return (
    <span
      className={`inline-flex h-9 items-center gap-2 rounded-full border px-4 text-xs font-bold ${
        !hasChange
          ? "border-[#ddd8d0] bg-[#f1efea] text-[#7b756d]"
          : isUp
            ? "border-red-200 bg-red-50 text-red-700"
            : "market-green-badge"
      }`}
      title={`${index.name} · ${index.source}`}
    >
      <span className="text-[#7b756d]">{index.name}</span>
      {price ? <span className="hidden tabular-nums sm:inline">{price}</span> : null}
      <span className="tabular-nums">{status}</span>
    </span>
  );
}

function MarketEnvironmentPanel({
  marketOverview,
  result,
  sectorRadar,
  sentimentSummary,
  sources,
  stats,
}: {
  marketOverview: MarketOverviewResponse | null;
  result: StrongStockScreeningResponse | null;
  sectorRadar: SectorRadarResponse | null;
  sentimentSummary: SentimentSummaryResponse | null;
  sources: DataSourceStatusResponse | null;
  stats: MarketDashboardStats;
}) {
  const sourceState = sourceSummary(sources);
  const sentimentMetric = buildSentimentMetric(sentimentSummary);
  const turnover = marketOverview?.turnover ?? null;
  const advanceDecline = marketOverview?.advance_decline ?? null;
  const advanceCount = advanceDecline?.advance_count ?? null;
  const declineCount = advanceDecline?.decline_count ?? null;
  const unchangedCount = advanceDecline?.unchanged_count ?? null;
  const breadthTotal = (advanceCount ?? 0) + (declineCount ?? 0) + (unchangedCount ?? 0);
  const advanceWidth = breadthTotal > 0 && advanceCount !== null ? Math.round((advanceCount / breadthTotal) * 100) : 0;
  const turnoverSourceLabel = realtimeTurnoverSourceLabel(marketOverview);

  return (
    <section className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <TerminalMetricCard
        label="总成交额 TOTAL TURNOVER"
        value={formatCnyCompact(turnover?.total_cny)}
        subValue={formatTurnoverChange(turnover)}
        footerLabel={turnoverSourceLabel ? "Source" : "Trade Date"}
        footerValue={marketOverview?.trade_date ?? result?.trade_date ?? "--"}
        helper={turnoverSourceLabel ? realtimeTurnoverSubtitles[turnoverSourceLabel] : undefined}
        tone={turnover?.change_cny === null || turnover?.change_cny === undefined ? "neutral" : turnover.change_cny >= 0 ? "positive" : "warning"}
      />
      <TerminalMetricCard
        label="情绪指数 SENTIMENT"
        value={sentimentMetric.score === null ? "--" : String(sentimentMetric.score)}
        suffix="/100"
        subValue={sentimentMetric.subValue}
        footerLabel="Short-term"
        footerValue={sentimentMetric.footerValue}
        tone={sentimentMetric.tone}
      />
      <MarketBreadthCard
        label="涨跌比 ADVANCE/DECLINE"
        advanceCount={advanceCount}
        declineCount={declineCount}
        subValue={unchangedCount === null ? "全A市场口径，等待数据" : `上涨/下跌 · 平盘 ${unchangedCount}`}
        footerLabel="Market Breadth"
        footerValue={marketOverview?.trade_date ?? "--"}
        progress={advanceWidth}
        declineProgress={breadthTotal > 0 && declineCount !== null ? Math.round((declineCount / breadthTotal) * 100) : 0}
      />
      <TerminalMetricCard
        label="数据可信 SOURCE"
        value={marketOverview || sectorRadar ? "全A" : "--"}
        subValue={sectorRadarSourceSummary(sectorRadar) || marketOverviewSourceSummary(marketOverview) || (sourceState.ok ? "数据源可用" : "数据源待配置")}
        footerLabel="Source"
        footerValue={`${sectorRadar ? sectorRadar.inflow.length + sectorRadar.outflow.length : marketOverview?.sectors.length ?? 0} 板块`}
        tone={
          (sectorRadar && sectorRadar.source_status.some((item) => item.status === "success")) ||
          (marketOverview && marketOverview.source_status.some((item) => item.status === "success"))
            ? "positive"
            : "warning"
        }
      />
    </section>
  );
}

function buildSentimentMetric(sentimentSummary: SentimentSummaryResponse | null): {
  footerValue: string;
  score: number | null;
  subValue: string;
  tone: "positive" | "neutral" | "warning";
} {
  if (!sentimentSummary) {
    return {
      footerValue: "等待短线情绪",
      score: null,
      subValue: "读取涨跌停、炸板和连板情绪中",
      tone: "neutral",
    };
  }
  const metrics = sentimentSummary.metrics;
  const sealRate = metrics.seal_rate_pct === null ? "--" : `${metrics.seal_rate_pct.toFixed(1)}%`;
  return {
    footerValue: `跌停 ${metrics.limit_down_count ?? "--"} · 封板率 ${sealRate}`,
    score: Math.round(metrics.emotion_score),
    subValue: `${metrics.emotion_level} · 涨停 ${metrics.limit_up_count} / 炸板 ${metrics.break_board_count}`,
    tone: metrics.emotion_score >= 70 ? "warning" : metrics.emotion_score >= 45 ? "neutral" : "positive",
  };
}

function MarketBreadthCard({
  advanceCount,
  declineCount,
  declineProgress,
  footerLabel,
  footerValue,
  label,
  progress,
  subValue,
}: {
  advanceCount: number | null;
  declineCount: number | null;
  declineProgress: number;
  footerLabel: string;
  footerValue: string;
  label: string;
  progress: number;
  subValue: string;
}) {
  const upWidth = Math.max(0, Math.min(100, progress));
  const downWidth = Math.max(0, Math.min(100 - upWidth, declineProgress));

  return (
    <article className="rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] p-4">
      <p className="text-xs font-semibold uppercase text-[#7b756d]">{label}</p>
      <div className="mt-2 flex items-baseline gap-1 text-3xl font-black leading-none tabular-nums">
        {advanceCount === null || declineCount === null ? (
          <span className="text-[#11100e]">--</span>
        ) : (
          <>
            <span className="text-[#d92d20]">{advanceCount}</span>
            <span className="text-[#7b756d]">/</span>
            <span className="market-green-text">{declineCount}</span>
          </>
        )}
      </div>
      <p className="mt-3 text-xs font-medium text-[#7b756d]">{subValue}</p>
      <div className="mt-3 flex h-1.5 overflow-hidden rounded-full bg-[#d9d4cb]">
        <div className="h-full bg-[#d92d20]" style={{ width: `${upWidth}%` }} />
        <div className="h-full market-green-fill" style={{ width: `${downWidth}%` }} />
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-[#ddd8d0] pt-3 text-xs">
        <span className="text-[#7b756d]">{footerLabel}</span>
        <span className="font-semibold text-[#5f5a53]">{footerValue}</span>
      </div>
    </article>
  );
}

function TerminalMetricCard({
  footerLabel,
  footerValue,
  helper,
  label,
  progress,
  suffix,
  subValue,
  tone,
  value,
}: {
  footerLabel: string;
  footerValue: string;
  helper?: string;
  label: string;
  progress?: number;
  suffix?: string;
  subValue: string;
  tone: "positive" | "neutral" | "warning";
  value: string;
}) {
  const toneClass = tone === "positive" ? "market-green-text" : tone === "warning" ? "text-[#f04438]" : "text-[#11100e]";
  return (
    <article className="rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] p-4">
      <p className="text-xs font-semibold uppercase text-[#7b756d]">{label}</p>
      <div className={`mt-2 text-3xl font-black leading-none tabular-nums ${toneClass}`}>
        {value}
        {suffix && <span className="ml-1 text-base text-[#7b756d]">{suffix}</span>}
      </div>
      <p className="mt-3 text-xs font-medium text-[#7b756d]">{subValue}</p>
      {progress !== undefined && (
        <div className="mt-3 h-1.5 rounded-full bg-[#d9d4cb]">
          <div className="h-1.5 rounded-full market-green-fill" style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
        </div>
      )}
      <div className="mt-4 flex items-center justify-between border-t border-[#ddd8d0] pt-3 text-xs">
        <span className="text-[#7b756d]">{helper ?? footerLabel}</span>
        <span className={toneClass}>{footerValue}</span>
      </div>
    </article>
  );
}

export function SectorStrengthPanel() {
  return (
    <section className="rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-black text-[#11100e]">板块强度 · Sector Strength</h2>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">等待非资金流口径模型</p>
        </div>
        <Tag className="m-0">规划中</Tag>
      </div>
      <div className="mt-4 flex min-h-[214px] items-center justify-center rounded-lg border border-dashed border-[#ddd8d0] bg-white/55 px-5 text-center">
        <div>
          <div className="text-sm font-black text-[#11100e]">板块强度待接入</div>
          <p className="mt-2 max-w-[280px] text-xs leading-5 text-[#7b756d]">
            后续将接入非资金流口径的板块强度模型，避免和左侧资金流热力重复。
          </p>
        </div>
      </div>
    </section>
  );
}

export function SectorFlowHeatmapPanel({ sectorRadar }: { sectorRadar: SectorRadarResponse | null }) {
  const inflow = sectorRadar?.inflow.slice(0, 5) ?? [];
  const outflow = sectorRadar?.outflow.slice(0, 5) ?? [];
  const inflowTotal = sumPositiveSectorFlow(sectorRadar?.inflow ?? []);
  const outflowTotal = sumNegativeSectorFlow(sectorRadar?.outflow ?? []);
  const top3Inflow = sumPositiveSectorFlow(inflow.slice(0, 3));
  const concentration = inflowTotal > 0 ? Math.round((top3Inflow / inflowTotal) * 100) : null;
  const maxFlow = Math.max(
    ...inflow.map((item) => Math.abs(item.net_flow_cny ?? 0)),
    ...outflow.map((item) => Math.abs(item.net_flow_cny ?? 0)),
    1,
  );

  return (
    <section className="rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-black text-[#11100e]">板块资金流热力 · Sector Flow</h2>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
            {sectorRadar ? `资金流口径：${sectorRadar.flow_source}` : "读取 /sectors 同源板块资金流"}
          </p>
        </div>
        <Tag className="m-0" color={sectorRadar?.capital_flow_status === "direct" ? "green" : "orange"}>
          {sectorRadar?.capital_flow_status === "direct" ? "实时资金流" : sectorRadar ? "估算资金流" : "待数据"}
        </Tag>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <SectorFlowStat label="净流入合计" tone="red" value={formatSignedCny(inflowTotal)} />
        <SectorFlowStat label="净流出合计" tone="green" value={formatSignedCny(-outflowTotal)} />
        <SectorFlowStat label="主线集中度" tone="neutral" value={concentration === null ? "--" : `${concentration}%`} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SectorFlowColumn items={inflow} maxFlow={maxFlow} title="净流入 Top5" tone="red" />
        <SectorFlowColumn items={outflow} maxFlow={maxFlow} title="净流出 Top5" tone="green" />
      </div>
    </section>
  );
}

function SectorFlowStat({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "green" | "neutral" | "red";
  value: string;
}) {
  const toneClass = tone === "red" ? "text-[#d92d20]" : tone === "green" ? "market-green-text" : "text-[#11100e]";
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2">
      <div className="text-[11px] font-black text-[#7b756d]">{label}</div>
      <div className={`mt-1 text-lg font-black tabular-nums ${toneClass}`}>{value}</div>
    </div>
  );
}

function SectorFlowColumn({
  items,
  maxFlow,
  title,
  tone,
}: {
  items: SectorRadarItem[];
  maxFlow: number;
  title: string;
  tone: "green" | "red";
}) {
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="font-black text-[#11100e]">{title}</span>
        <span className="font-semibold text-[#7b756d]">{items.length || "待数据"}</span>
      </div>
      <div className="space-y-2">
        {items.length > 0 ? (
          items.map((item) => <SectorFlowRow item={item} key={`${title}-${item.name}`} maxFlow={maxFlow} tone={tone} />)
        ) : (
          <div className="rounded-lg border border-dashed border-[#ddd8d0] px-3 py-6 text-center text-xs font-bold text-[#7b756d]">
            板块资金流暂不可用
          </div>
        )}
      </div>
    </div>
  );
}

function SectorFlowRow({
  item,
  maxFlow,
  tone,
}: {
  item: SectorRadarItem;
  maxFlow: number;
  tone: "green" | "red";
}) {
  const flow = item.net_flow_cny ?? 0;
  const width = Math.max(8, Math.min(100, (Math.abs(flow) / maxFlow) * 100));
  const barClass = tone === "red" ? "bg-[#d92d20]" : "market-green-fill";
  const valueClass = tone === "red" ? "text-[#d92d20]" : "market-green-text";

  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)_80px] items-center gap-3 text-sm">
      <span className="truncate font-bold text-[#3b3833]" title={`${item.name} · ${item.leader ?? "暂无领涨股"}`}>
        {item.name}
      </span>
      <div className="min-w-0">
        <div className="h-2 rounded-full bg-[#e6e0d7]">
          <div className={`h-2 rounded-full ${barClass}`} style={{ width: `${width}%` }} />
        </div>
        <div className="mt-1 truncate text-[10px] font-semibold text-[#9a948c]">
          {formatSignedPercent(item.change_pct)} · {item.leader ?? "暂无领涨股"}
        </div>
      </div>
      <span className={`text-right font-black tabular-nums ${valueClass}`}>{formatSignedCny(item.net_flow_cny)}</span>
    </div>
  );
}
