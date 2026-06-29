import type {
  DataSourceStatusResponse,
  GsgfAnalysis,
  GsgfCalibrationBucket,
  GsgfRealCalibrationSummary,
  GsgfReviewSummary,
  GsgfTradePlan,
  MarketOverviewResponse,
  ScreenRunFilters,
  ScreenStrategy,
  SectorRadarItem,
  SectorRadarResponse,
  SourceStatusValue,
  StrongStockIntradayItem,
  StrongStockIntradaySnapshot,
  StrongStockScreeningItem,
  StrongStockScreeningResponse,
  WatchlistPoolItem,
  WatchlistRiskItem,
} from "../lib/types";
import type { ColumnsType } from "antd/es/table";
import { DownloadOutlined, SearchOutlined, ThunderboltOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Checkbox,
  Collapse,
  Empty,
  Form,
  Input,
  InputNumber,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  filterStockListByGsgf,
  type GsgfSignalFilter,
  gsgfSignalFilterOptions,
} from "../lib/stockListFilter";

type ScreenerWorkbenchProps = {
  tradeDate: string;
  sources: DataSourceStatusResponse | null;
  result: StrongStockScreeningResponse | null;
  intraday: StrongStockIntradaySnapshot | null;
  marketOverview: MarketOverviewResponse | null;
  sectorRadar: SectorRadarResponse | null;
  reviewSummary: GsgfReviewSummary | null;
  calibrationSummary: GsgfRealCalibrationSummary | null;
  running: boolean;
  reviewRunning: boolean;
  calibrationRunning: boolean;
  watchlistPoolItems: WatchlistPoolItem[];
  watchlistMessage: string | null;
  strategy: ScreenStrategy;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  error: string | null;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  onStrategyChange: (value: ScreenStrategy) => void;
  onTradeDateChange: (value: string) => void;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onAddManyToWatchlist: (items: StrongStockScreeningItem[], group: string, tags: string[]) => void;
  onRun: () => void;
  onRunGsgfCalibration: (options: {
    tradeDatesText: string;
    windowsText: string;
    scanLimit: number;
    count: number;
  }) => void;
  onRecheckGsgfReview: () => void;
  onRefreshSources: () => void;
  onSaveGsgfReviewSnapshot: () => void;
};

const statusCopy: Record<StrongStockScreeningItem["status"], { label: string; tone: string }> = {
  focus: { label: "可关注", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  wait_pullback: { label: "等回踩", tone: "bg-sky-50 text-sky-700 ring-sky-100" },
  reduce_risk: { label: "减仓风险", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  data_incomplete: { label: "数据不足", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
};

type CandidateStatusFilter = StrongStockScreeningItem["status"] | "all";

const candidateStatusFilters: Array<{ label: string; value: CandidateStatusFilter }> = [
  { label: "全部", value: "all" },
  { label: statusCopy.focus.label, value: "focus" },
  { label: statusCopy.wait_pullback.label, value: "wait_pullback" },
  { label: statusCopy.reduce_risk.label, value: "reduce_risk" },
  { label: statusCopy.data_incomplete.label, value: "data_incomplete" },
];

const strategyOptions: Array<{ label: string; value: ScreenStrategy }> = [
  { label: "强势股模型", value: "strong_stock" },
  { label: "股是股非模型", value: "gsgf" },
  { label: "综合模型", value: "combined" },
];

const riskCopy: Record<WatchlistRiskItem["risk_action"], { label: string; tone: string }> = {
  hold_watch: { label: "继续观察", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  reduce: { label: "降低关注", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  empty: { label: "空仓纪律触发", tone: "bg-red-50 text-red-700 ring-red-100" },
};

const intradayCopy: Record<StrongStockIntradayItem["action"], { label: string; tone: string }> = {
  watch: { label: "继续观察", tone: "bg-sky-50 text-sky-700 ring-sky-100" },
  low_buy_watch: { label: "低吸观察", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  reduce: { label: "减仓锁利", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  avoid_chase: { label: "避免追高", tone: "bg-red-50 text-red-700 ring-red-100" },
  data_incomplete: { label: "数据不足", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
};

const industryStrengthCopy: Record<
  NonNullable<StrongStockScreeningItem["industry_strength"]>,
  { label: string; tone: string }
> = {
  strong: { label: "强", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  neutral: { label: "中", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
  weak: { label: "弱", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
};

type MarketType = NonNullable<ScreenRunFilters["market_types"]>[number];

const marketTypeOptions: Array<{ label: string; value: MarketType }> = [
  { label: "主板", value: "main" },
  { label: "创业板", value: "gem" },
  { label: "科创板", value: "star" },
  { label: "北交所", value: "bj" },
];

const realtimeTurnoverSubtitles: Record<string, string> = {
  "iFinD 实时口径": "iFinD 实时口径 · 今日相对昨日",
  "TickFlow 实时口径": "TickFlow 实时口径 · 今日相对昨日",
};

type MarketDashboardStats = {
  dataIncompleteCount: number;
  focusCount: number;
  negativeNewsCount: number;
  reduceRiskCount: number;
  riskEmptyCount: number;
  severeWarningCount: number;
  totalCount: number;
  waitPullbackCount: number;
};

export function ScreenerWorkbench({
  tradeDate,
  sources,
  result,
  intraday,
  marketOverview,
  sectorRadar,
  reviewSummary,
  calibrationSummary,
  running,
  reviewRunning,
  calibrationRunning,
  watchlistPoolItems,
  watchlistMessage,
  strategy,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  error,
  onScanLimitChange,
  onScreenFiltersChange,
  onSaveScreenFilters,
  onStrategyChange,
  onTradeDateChange,
  onAddToWatchlist,
  onAddManyToWatchlist,
  onRun,
  onRunGsgfCalibration,
  onRecheckGsgfReview,
  onRefreshSources,
  onSaveGsgfReviewSnapshot,
}: ScreenerWorkbenchProps) {
  const candidates = result?.items ?? [];
  const { message } = App.useApp();
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  useEffect(() => {
    if (candidates.length === 0) {
      setSelectedSymbol(null);
      return;
    }
    if (!selectedSymbol || !candidates.some((item) => item.symbol === selectedSymbol)) {
      setSelectedSymbol(candidates[0].symbol);
    }
  }, [result, selectedSymbol, candidates]);

  const selectedItem = candidates.find((item) => item.symbol === selectedSymbol) ?? candidates[0] ?? null;
  const dashboardStats = useMemo(() => buildMarketDashboardStats(candidates, result), [candidates, result]);

  useEffect(() => {
    if (watchlistMessage) {
      void message.success(watchlistMessage);
    }
  }, [message, watchlistMessage]);

  return (
    <main className="min-h-screen bg-[#f5f3f0] text-[#11100e]">
      <div className="mx-auto max-w-none px-5 py-4">
        <MarketTickerBar
          candidates={candidates}
          generatedAt={marketOverview?.generated_at ?? result?.generated_at ?? null}
          onRun={onRun}
          running={running}
          sources={sources}
        />

        <MarketEnvironmentPanel
          marketOverview={marketOverview}
          result={result}
          sectorRadar={sectorRadar}
          sources={sources}
          stats={dashboardStats}
        />

        <div className="mt-4 grid items-stretch gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]">
          <SectorFlowHeatmapPanel sectorRadar={sectorRadar} />
          <SectorStrengthPanel />
        </div>

        <FilterLogicRail
          filters={screenFilters}
          onRefreshSources={onRefreshSources}
          onRun={onRun}
          onScanLimitChange={onScanLimitChange}
          onScreenFiltersChange={onScreenFiltersChange}
          onSaveScreenFilters={onSaveScreenFilters}
          onStrategyChange={onStrategyChange}
          onTradeDateChange={onTradeDateChange}
          running={running}
          scanLimit={scanLimit}
          screenFiltersSaved={screenFiltersSaved}
          sources={sources}
          strategy={strategy}
          tradeDate={tradeDate}
          visibleCount={candidates.length}
        />

        <GsgfReviewPanel
          onRecheck={onRecheckGsgfReview}
          onSaveSnapshot={onSaveGsgfReviewSnapshot}
          reviewRunning={reviewRunning}
          reviewSummary={reviewSummary}
        />

        <GsgfCalibrationPanel
          calibrationRunning={calibrationRunning}
          calibrationSummary={calibrationSummary}
          defaultTradeDate={tradeDate}
          onRunCalibration={onRunGsgfCalibration}
        />

        {error && <Alert className="mt-4" showIcon title={error} type="error" />}

        <DesignScreenerResultsTable
          generatedAt={result?.generated_at ?? null}
          items={candidates}
          onAddManyToWatchlist={onAddManyToWatchlist}
          onAddToWatchlist={onAddToWatchlist}
          onSelect={setSelectedSymbol}
          running={running}
          selectedSymbol={selectedItem?.symbol ?? null}
          watchlistMessage={watchlistMessage}
          watchlistPoolItems={watchlistPoolItems}
        />
      </div>

      <div className="border-t border-[#ddd8d0] bg-[#f5f3f0] px-5 py-3 text-xs text-[#7b756d]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="font-black text-[#11100e]">StockMaster · A股选股工作台</span>
          <span>Data: TickFlow / iFinD / 东方财富 · Delayed 15min · 仅作规则辅助，不构成投资建议</span>
        </div>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <Statistic
        styles={{ content: { color: "#0f172a", fontSize: 24, fontWeight: 900, lineHeight: "28px" } }}
        title={<span className="text-xs font-semibold text-slate-500">{label}</span>}
        value={value}
      />
    </div>
  );
}

function MarketTickerBar({
  candidates,
  generatedAt,
  onRun,
  running,
  sources,
}: {
  candidates: StrongStockScreeningItem[];
  generatedAt: string | null;
  onRun: () => void;
  running: boolean;
  sources: DataSourceStatusResponse | null;
}) {
  const sourceState = sourceSummary(sources);

  return (
    <header className="rounded-lg border border-[#ddd8d0] bg-[#f8f7f4]">
      <div className="flex flex-col gap-3 px-4 py-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <MarketIndexPill label="上证" status="待接入" />
          <MarketIndexPill label="深证" status="待接入" />
          <MarketIndexPill label="创业板" status="待接入" negative />
          <span className="mx-2 hidden h-7 w-px bg-[#d6d0c7] xl:block" />
          <span className="inline-flex h-8 items-center gap-2 rounded-full px-3 text-xs font-semibold text-[#7b756d]">
            <span className={`size-2 rounded-full ${sourceState.ok ? "bg-emerald-500" : "bg-amber-500"}`} />
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

function MarketIndexPill({
  label,
  negative = false,
  status,
}: {
  label: string;
  negative?: boolean;
  status: string;
}) {
  return (
    <span
      className={`inline-flex h-9 items-center gap-2 rounded-full border px-4 text-xs font-bold ${
        negative
          ? "border-red-200 bg-red-50 text-red-700"
          : "border-emerald-200 bg-emerald-50 text-emerald-700"
      }`}
      title="顶部指数将在市场概览 API 接入后显示实时数值"
    >
      <span className="text-[#7b756d]">{label}</span>
      <span>{status}</span>
    </span>
  );
}

function MarketEnvironmentPanel({
  marketOverview,
  result,
  sectorRadar,
  sources,
  stats,
}: {
  marketOverview: MarketOverviewResponse | null;
  result: StrongStockScreeningResponse | null;
  sectorRadar: SectorRadarResponse | null;
  sources: DataSourceStatusResponse | null;
  stats: MarketDashboardStats;
}) {
  const sourceState = sourceSummary(sources);
  const sectorSentiment = buildSectorRadarSentiment(sectorRadar);
  const turnover = marketOverview?.turnover ?? null;
  const advanceDecline = marketOverview?.advance_decline ?? null;
  const advanceCount = advanceDecline?.advance_count ?? null;
  const declineCount = advanceDecline?.decline_count ?? null;
  const unchangedCount = advanceDecline?.unchanged_count ?? null;
  const breadthTotal = (advanceCount ?? 0) + (declineCount ?? 0) + (unchangedCount ?? 0);
  const advanceWidth = breadthTotal > 0 && advanceCount !== null ? Math.round((advanceCount / breadthTotal) * 100) : 0;

  return (
    <section className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <TerminalMetricCard
        label="总成交额 TOTAL TURNOVER"
        value={formatCnyCompact(turnover?.total_cny)}
        subValue={formatTurnoverChange(turnover)}
        footerLabel="Trade Date"
        footerValue={marketOverview?.trade_date ?? result?.trade_date ?? "--"}
        tone={turnover?.change_cny === null || turnover?.change_cny === undefined ? "neutral" : turnover.change_cny >= 0 ? "positive" : "warning"}
      />
      <TerminalMetricCard
        label="情绪指数 SENTIMENT"
        value={sectorSentiment.score === null ? "--" : String(sectorSentiment.score)}
        suffix="/100"
        subValue={sectorSentiment.subValue}
        footerLabel="Sector Flow"
        footerValue={sectorSentiment.footerValue}
        tone={sectorSentiment.tone}
      />
      <TerminalMetricCard
        label="涨跌比 ADVANCE/DECLINE"
        value={advanceCount === null || declineCount === null ? "--" : `${advanceCount}/${declineCount}`}
        subValue={unchangedCount === null ? "全A市场口径，等待数据" : `上涨/下跌 · 平盘 ${unchangedCount}`}
        footerLabel="Market Breadth"
        footerValue={marketOverview?.trade_date ?? "--"}
        progress={advanceWidth}
        tone={advanceCount !== null && declineCount !== null && advanceCount >= declineCount ? "positive" : "warning"}
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
  const toneClass = tone === "positive" ? "text-[#28c840]" : tone === "warning" ? "text-[#f04438]" : "text-[#11100e]";
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
          <div className="h-1.5 rounded-full bg-[#28c840]" style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
        </div>
      )}
      <div className="mt-4 flex items-center justify-between border-t border-[#ddd8d0] pt-3 text-xs">
        <span className="text-[#7b756d]">{helper ?? footerLabel}</span>
        <span className={toneClass}>{footerValue}</span>
      </div>
    </article>
  );
}

function SectorStrengthPanel() {
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

function SectorFlowHeatmapPanel({ sectorRadar }: { sectorRadar: SectorRadarResponse | null }) {
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
  const toneClass = tone === "red" ? "text-[#d92d20]" : tone === "green" ? "text-[#0f7a3b]" : "text-[#11100e]";
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
  const barClass = tone === "red" ? "bg-[#d92d20]" : "bg-[#0f7a3b]";
  const valueClass = tone === "red" ? "text-[#d92d20]" : "text-[#0f7a3b]";

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

function FilterLogicRail({
  filters,
  onRefreshSources,
  onRun,
  onSaveScreenFilters,
  onScanLimitChange,
  onScreenFiltersChange,
  onStrategyChange,
  onTradeDateChange,
  running,
  scanLimit,
  screenFiltersSaved,
  sources,
  strategy,
  tradeDate,
  visibleCount,
}: {
  filters: ScreenRunFilters;
  onRefreshSources: () => void;
  onRun: () => void;
  onSaveScreenFilters: () => void;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onStrategyChange: (value: ScreenStrategy) => void;
  onTradeDateChange: (value: string) => void;
  running: boolean;
  scanLimit: number;
  screenFiltersSaved: boolean;
  sources: DataSourceStatusResponse | null;
  strategy: ScreenStrategy;
  tradeDate: string;
  visibleCount: number;
}) {
  return (
    <section className="mt-4 rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] px-4 py-3">
      <div className="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="mr-2 border-r border-[#d6d0c7] pr-4 text-xs font-black uppercase text-[#11100e]">FILTER LOGIC</span>
          <FilterChip active label="20日内涨停" />
          <FilterChip active label={strategyName(strategy)} />
          <FilterChip active label={`扫描 ${scanLimit}`} />
          <FilterChip active={Boolean(filters.kdj_j_max)} label={filters.kdj_j_max ? `KDJ-J < ${filters.kdj_j_max}` : "KDJ-J 不限"} />
          <FilterChip active={Boolean(filters.min_market_cap_billion || filters.max_market_cap_billion)} label={marketCapFilterLabel(filters)} />
          {(filters.market_types ?? []).map((market) => <FilterChip active key={market} label={marketTypeLabel(market)} />)}
          {(filters.industries ?? []).map((industry) => <FilterChip active key={industry} label={industry} />)}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-[#7b756d]">Matched: <b className="text-[#11100e]">{visibleCount}</b> stocks</span>
          <Button onClick={onRefreshSources} size="small">刷新源</Button>
          <Button loading={running} onClick={onRun} size="small" type="primary">运行筛选</Button>
          <Button onClick={() => onScreenFiltersChange({})} size="small">Reset</Button>
        </div>
      </div>

      <details className="mt-3 border-t border-[#ddd8d0] pt-3">
        <summary className="cursor-pointer text-xs font-bold text-[#7b756d]">编辑筛选参数</summary>
        <div className="mt-3 grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <label className="text-xs font-bold text-[#7b756d]">
              交易日
              <Input className="mt-1" onChange={(event) => onTradeDateChange(event.target.value)} value={tradeDate} />
            </label>
            <label className="text-xs font-bold text-[#7b756d]">
              策略模型
              <Segmented
                className="mt-1 w-full"
                onChange={(value) => onStrategyChange(value as ScreenStrategy)}
                options={strategyOptions}
                value={strategy}
              />
            </label>
            <label className="text-xs font-bold text-[#7b756d]">
              扫描候选数
              <InputNumber className="mt-1 w-full" max={300} min={1} onChange={(value) => onScanLimitChange(normalizeScanLimit(value))} value={scanLimit} />
            </label>
            <DataSourceStrip onRefreshSources={onRefreshSources} sources={sources} />
          </div>
          <AdvancedScreenFilters
            filters={filters}
            onChange={onScreenFiltersChange}
            onSave={onSaveScreenFilters}
            saved={screenFiltersSaved}
          />
        </div>
      </details>
    </section>
  );
}

function FilterChip({ active, label }: { active: boolean; label: string }) {
  return (
    <span className={`inline-flex h-8 items-center rounded-md border px-3 text-xs font-bold ${
      active ? "border-[#11100e] bg-[#11100e] text-white" : "border-[#ddd8d0] bg-[#f5f3f0] text-[#7b756d]"
    }`}>
      {active ? "✓ " : ""}{label}
    </span>
  );
}

function GsgfReviewPanel({
  onRecheck,
  onSaveSnapshot,
  reviewRunning,
  reviewSummary,
}: {
  onRecheck: () => void;
  onSaveSnapshot: () => void;
  reviewRunning: boolean;
  reviewSummary: GsgfReviewSummary | null;
}) {
  const buckets = reviewSummary?.buckets.slice(0, 4) ?? [];

  return (
    <section className="mt-4 rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] px-4 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-base font-black text-[#11100e]">信号复盘</h2>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
            样本 {reviewSummary?.record_count ?? 0} 条 · 窗口 {(reviewSummary?.windows ?? [1, 3, 5, 10]).join("/")} 日
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button loading={reviewRunning} onClick={onSaveSnapshot} size="small">
            保存复盘快照
          </Button>
          <Button loading={reviewRunning} onClick={onRecheck} size="small" type="primary">
            复查信号
          </Button>
        </div>
      </div>
      {buckets.length > 0 ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {buckets.map((bucket) => (
            <div className="rounded-lg border border-[#ddd8d0] bg-[#f5f3f0] p-3" key={`${bucket.signal_type}-${bucket.status}`}>
              <p className="truncate text-xs font-black text-[#11100e]" title={bucket.signal_type}>
                {bucket.signal_type}
              </p>
              <p className="mt-1 text-[11px] font-semibold text-[#7b756d]">
                {bucket.status} · 确认 {bucket.confirmed_count}/{bucket.sample_count}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <ValuePill label="收益" value={formatReviewPercent(bucket.avg_return_pct)} />
                <ValuePill label="回撤" value={formatReviewPercent(bucket.avg_max_drawdown_pct)} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-[#f5f3f0] px-3 py-2 text-sm text-[#7b756d]">
          暂无复盘样本。先运行筛选，再保存复盘快照。
        </p>
      )}
    </section>
  );
}

function GsgfCalibrationPanel({
  calibrationRunning,
  calibrationSummary,
  defaultTradeDate,
  onRunCalibration,
}: {
  calibrationRunning: boolean;
  calibrationSummary: GsgfRealCalibrationSummary | null;
  defaultTradeDate: string;
  onRunCalibration: (options: {
    tradeDatesText: string;
    windowsText: string;
    scanLimit: number;
    count: number;
  }) => void;
}) {
  const [tradeDatesText, setTradeDatesText] = useState(defaultTradeDate);
  const [windowsText, setWindowsText] = useState("1,3,5,10");
  const [scanLimit, setScanLimit] = useState(80);
  const [count, setCount] = useState(260);

  useEffect(() => {
    if (tradeDatesText.trim().length === 0) {
      setTradeDatesText(defaultTradeDate);
    }
  }, [defaultTradeDate, tradeDatesText]);

  return (
    <section className="mt-4 rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] px-4 py-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-black text-[#11100e]">真实样本校准</h2>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
            用 TickFlow 历史日K复盘“确认买点 / 低吸观察 / B区A点 / 放量突破确认”的分桶命中率
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-[minmax(220px,1fr)_120px_92px_92px_auto] xl:min-w-[760px]">
          <Input
            onChange={(event) => setTradeDatesText(event.target.value)}
            placeholder="样本日，逗号分隔"
            value={tradeDatesText}
          />
          <Input
            onChange={(event) => setWindowsText(event.target.value)}
            placeholder="窗口"
            value={windowsText}
          />
          <InputNumber
            className="w-full"
            max={300}
            min={1}
            onChange={(value) => setScanLimit(normalizeScanLimit(value))}
            value={scanLimit}
          />
          <InputNumber
            className="w-full"
            max={260}
            min={70}
            onChange={(value) => setCount(normalizeKlineCount(value))}
            value={count}
          />
          <Button
            disabled={tradeDatesText.trim().length === 0}
            loading={calibrationRunning}
            onClick={() => onRunCalibration({ tradeDatesText, windowsText, scanLimit, count })}
            type="primary"
          >
            运行校准
          </Button>
        </div>
      </div>

      {calibrationSummary ? (
        <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <CalibrationBucketTable buckets={calibrationSummary.buckets} title="样本分桶" />
          <CalibrationBucketTable buckets={calibrationSummary.unique_symbol_buckets} title="去重股票分桶" />
          <div className="xl:col-span-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-[#7b756d]">
              <Tag className="m-0">样本日 {calibrationSummary.trade_dates.join(" / ")}</Tag>
              <Tag className="m-0">扫描 {calibrationSummary.scanned_count}</Tag>
              <Tag className="m-0">目标样本 {calibrationSummary.target_sample_count}</Tag>
              <Tag className="m-0">跳过 {calibrationSummary.skipped_count}</Tag>
              <Tag className="m-0">窗口 {calibrationSummary.windows.join("/")}</Tag>
              <span>生成 {formatDateTime(calibrationSummary.generated_at)}</span>
            </div>
            {calibrationSummary.samples.length > 0 && (
              <div className="mt-3 overflow-x-auto rounded-lg border border-[#ddd8d0]">
                <table className="min-w-full divide-y divide-[#ddd8d0] text-left text-xs">
                  <thead className="bg-[#f5f3f0] text-[#7b756d]">
                    <tr>
                      <th className="px-3 py-2 font-black">样例</th>
                      <th className="px-3 py-2 font-black">分桶</th>
                      <th className="px-3 py-2 font-black">状态</th>
                      <th className="px-3 py-2 font-black">首窗收益</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e5e0d8] bg-white">
                    {calibrationSummary.samples.slice(0, 6).map((sample) => (
                      <tr key={`${sample.trade_date}-${sample.symbol}`}>
                        <td className="px-3 py-2 font-bold text-[#11100e]">
                          {sample.trade_date} · {sample.name} {sample.symbol}
                        </td>
                        <td className="px-3 py-2 text-[#7b756d]">{sample.bucket_names.join(" / ")}</td>
                        <td className="px-3 py-2 text-[#7b756d]">{sample.status}</td>
                        <td className="px-3 py-2 font-black tabular-nums text-[#11100e]">
                          {formatSignedPercent(sample.windows[0]?.realized_return_pct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-[#f5f3f0] px-3 py-2 text-sm text-[#7b756d]">
          暂无真实样本校准结果。建议先跑 3-10 个历史交易日的小样本，再逐步扩大 scan limit。
        </p>
      )}
    </section>
  );
}

function CalibrationBucketTable({
  buckets,
  title,
}: {
  buckets: GsgfCalibrationBucket[];
  title: string;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-[#ddd8d0] bg-[#f5f3f0] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-black text-[#11100e]">{title}</h3>
        <Tag className="m-0">{buckets.length || "待数据"}</Tag>
      </div>
      {buckets.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-[#7b756d]">
              <tr>
                <th className="px-2 py-2 font-black">分桶</th>
                <th className="px-2 py-2 font-black">样本</th>
                <th className="px-2 py-2 font-black">hit_rate</th>
                <th className="px-2 py-2 font-black">均收</th>
                <th className="px-2 py-2 font-black">回撤</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ddd8d0]">
              {buckets.map((bucket) => {
                const primaryWindow = bucket.windows[0] ?? null;
                return (
                  <tr key={bucket.name}>
                    <td className="px-2 py-2 font-black text-[#11100e]">{bucket.name}</td>
                    <td className="px-2 py-2 tabular-nums text-[#7b756d]">{bucket.sample_count}</td>
                    <td className="px-2 py-2 font-black tabular-nums text-[#11100e]">
                      {formatPlainPercent(primaryWindow?.hit_rate)}
                    </td>
                    <td className="px-2 py-2 tabular-nums text-[#7b756d]">
                      {formatSignedPercent(primaryWindow?.avg_return_pct)}
                    </td>
                    <td className="px-2 py-2 tabular-nums text-[#7b756d]">
                      {formatSignedPercent(primaryWindow?.avg_max_drawdown_pct)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-md bg-white px-3 py-2 text-sm text-[#7b756d]">当前样本没有命中目标分桶。</p>
      )}
    </div>
  );
}

function WorkflowPanel({
  error,
  onRefreshSources,
  onRun,
  onStrategyChange,
  onTradeDateChange,
  result,
  running,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  sources,
  strategy,
  tradeDate,
  onScanLimitChange,
  onScreenFiltersChange,
  onSaveScreenFilters,
  watchlistPoolItems,
}: {
  error: string | null;
  onRefreshSources: () => void;
  onRun: () => void;
  onStrategyChange: (value: ScreenStrategy) => void;
  onTradeDateChange: (value: string) => void;
  result: StrongStockScreeningResponse | null;
  running: boolean;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  sources: DataSourceStatusResponse | null;
  strategy: ScreenStrategy;
  tradeDate: string;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  return (
    <aside className="space-y-3">
      <Card
        className="workbench-card"
        size="small"
        title={<span className="text-base font-black text-slate-950">今日流程</span>}
        extra={error ? <Tag color="red">错误</Tag> : null}
      >
        <DataSourceStrip onRefreshSources={onRefreshSources} sources={sources} />
        {error && <Alert className="mt-3" title={error} type="error" />}

        <div className="mt-4">
          <ScreenPanel
            onRun={onRun}
            onScanLimitChange={onScanLimitChange}
            onScreenFiltersChange={onScreenFiltersChange}
            onSaveScreenFilters={onSaveScreenFilters}
            onTradeDateChange={onTradeDateChange}
            running={running}
            scanLimit={scanLimit}
            screenFilters={screenFilters}
            screenFiltersSaved={screenFiltersSaved}
            strategy={strategy}
            tradeDate={tradeDate}
            onStrategyChange={onStrategyChange}
          />
        </div>
      </Card>

      <WatchlistPanel watchlistPoolItems={watchlistPoolItems} />
    </aside>
  );
}

function DataSourceStrip({
  onRefreshSources,
  sources,
}: {
  onRefreshSources: () => void;
  sources: DataSourceStatusResponse | null;
}) {
  const items = sources?.items ?? [];
  const failed = items.filter((item) => item.status === "failed" || item.status === "missing_key");
  const summary = sources ? `${items.filter((item) => item.status === "success").length}/${items.length} 可用` : "读取中";

  return (
    <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-bold text-slate-600">数据源：{summary}</p>
          <p className="mt-1 truncate text-xs text-slate-500">TickFlow 仅用于独立选股程序。</p>
        </div>
        <Button className="shrink-0" onClick={onRefreshSources} size="small">
          刷新
        </Button>
      </div>
      {items.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {items.map((item) => (
            <Tag color={sourceTagColor(item.status)} key={item.source} title={item.detail}>
              {item.source} {item.status}
            </Tag>
          ))}
        </div>
      )}
      {failed.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-slate-200 pt-2">
          {failed.map((item) => (
            <p className="text-xs leading-5 text-red-700" key={item.source}>
              {item.source}：{item.detail}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function ScreenPanel({
  onRun,
  onScanLimitChange,
  onScreenFiltersChange,
  onSaveScreenFilters,
  onStrategyChange,
  onTradeDateChange,
  running,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  strategy,
  tradeDate,
}: {
  onRun: () => void;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  onStrategyChange: (value: ScreenStrategy) => void;
  onTradeDateChange: (value: string) => void;
  running: boolean;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  strategy: ScreenStrategy;
  tradeDate: string;
}) {
  const scanLimitOptions = [40, 160, 300];

  return (
    <section className="border-t border-slate-100 pt-4">
      <h3 className="text-sm font-black text-slate-950">1. 手动筛选</h3>
      <Form className="mt-3" layout="vertical">
        <Form.Item label="交易日">
          <Input
            id="trade-date"
            inputMode="numeric"
            onChange={(event) => onTradeDateChange(event.target.value)}
            placeholder="YYYY-MM-DD"
            value={tradeDate}
          />
        </Form.Item>
        <Form.Item label="策略模型">
          <Segmented
            block
            onChange={(value) => onStrategyChange(value as ScreenStrategy)}
            options={strategyOptions}
            value={strategy}
            vertical
          />
        </Form.Item>
        <Form.Item label="扫描候选数">
          <Space className="w-full" orientation="vertical" size={8}>
            <Segmented
              block
              onChange={(value) => onScanLimitChange(Number(value))}
              options={scanLimitOptions.map((value) => ({ label: String(value), value }))}
              value={scanLimit}
            />
            <InputNumber
              className="w-full"
              id="scan-limit"
              max={300}
              min={1}
              onChange={(value) => onScanLimitChange(normalizeScanLimit(value))}
              value={scanLimit}
            />
          </Space>
        </Form.Item>
      </Form>
      <AdvancedScreenFilters
        filters={screenFilters}
        onChange={onScreenFiltersChange}
        onSave={onSaveScreenFilters}
        saved={screenFiltersSaved}
      />
      <Button
        block
        disabled={running || tradeDate.trim().length === 0}
        loading={running}
        onClick={onRun}
        type="primary"
      >
        {running ? "筛选中..." : "运行筛选"}
      </Button>
    </section>
  );
}

function AdvancedScreenFilters({
  filters,
  onChange,
  onSave,
  saved,
}: {
  filters: ScreenRunFilters;
  onChange: (value: ScreenRunFilters) => void;
  onSave: () => void;
  saved: boolean;
}) {
  const enabledCount = activeScreenFilterCount(filters);

  function update(next: Partial<ScreenRunFilters>) {
    onChange(cleanScreenFilters({ ...filters, ...next }));
  }

  return (
    <Collapse
      className="mt-3 bg-slate-50"
      defaultActiveKey={["advanced"]}
      items={[
        {
          key: "advanced",
          label: (
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-black text-slate-950">高级筛选</span>
              <Tag variant="filled">已启用 {enabledCount}</Tag>
            </div>
          ),
          children: (
            <Space className="w-full" orientation="vertical" size={12}>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <FilterNumberInput
                  label="最小市值（亿元）"
                  min={0}
                  onChange={(value) => update({ min_market_cap_billion: normalizeOptionalNumber(value, 0) })}
                  placeholder="不限请留空"
                  value={filters.min_market_cap_billion}
                />
                <FilterNumberInput
                  label="最大市值（亿元）"
                  min={0}
                  onChange={(value) => update({ max_market_cap_billion: normalizeOptionalNumber(value, 0) })}
                  placeholder="不限请留空"
                  value={filters.max_market_cap_billion}
                />
                <FilterNumberInput
                  label="KDJ-J值（小于）"
                  onChange={(value) => update({ kdj_j_max: normalizeOptionalNumber(value) })}
                  placeholder="不限请留空"
                  value={filters.kdj_j_max}
                />
              </div>

              <DisabledFilterInput label="概念板块（多选）" placeholder="待接入概念成分数据" />
              <DisabledFilterInput label="概念叠加（多选）" placeholder="待接入概念叠加数据" />

              <Form.Item className="mb-0" label="行业板块（多选）">
                <Input
                  onChange={(event) => update({ industries: splitFilterValues(event.target.value) })}
                  placeholder="消费电子，半导体"
                  value={(filters.industries ?? []).join("，")}
                />
              </Form.Item>

              <Form.Item className="mb-0" label="市场类型">
                <Checkbox.Group
                  className="grid grid-cols-2 gap-2"
                  onChange={(values) =>
                    update({
                      market_types: marketTypeOptions
                        .map((option) => option.value)
                        .filter((option) => values.includes(option)),
                    })
                  }
                  options={marketTypeOptions}
                  value={filters.market_types ?? []}
                />
              </Form.Item>

              <div className="grid grid-cols-[1fr_auto] gap-2">
                <Button block onClick={onSave} type={saved ? "primary" : "default"}>
                  {saved ? "已保存" : "保存筛选参数"}
                </Button>
                <Button onClick={() => onChange({})}>重置</Button>
              </div>
              {saved && (
                <Alert
                  aria-live="polite"
                  showIcon
                  title="筛选参数已保存到本机"
                  type="success"
                />
              )}
            </Space>
          ),
        },
      ]}
    />
  );
}

function FilterNumberInput({
  label,
  min,
  onChange,
  placeholder,
  value,
}: {
  label: string;
  min?: number;
  onChange: (value: number | string | null) => void;
  placeholder: string;
  value: number | null | undefined;
}) {
  return (
    <Form.Item className="mb-0" label={label}>
      <InputNumber
        className="w-full"
        min={min}
        onChange={onChange}
        placeholder={placeholder}
        value={value ?? null}
      />
    </Form.Item>
  );
}

function DisabledFilterInput({ label, placeholder }: { label: string; placeholder: string }) {
  return (
    <Form.Item className="mb-0" label={label}>
      <Input disabled placeholder={placeholder} />
    </Form.Item>
  );
}

function WatchlistPanel({
  watchlistPoolItems,
}: {
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  const groups = groupWatchlistPoolItems(watchlistPoolItems);

  return (
    <Card className="workbench-card" size="small">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-black text-slate-950">结构化自选池</h3>
          <p className="mt-1 text-xs font-medium text-slate-500">完整分组、标签和备注在独立页面管理。</p>
        </div>
        <Button aria-label="打开自选股管理页" className="shrink-0" href="/watchlist" size="small" type="primary">
          管理自选股
        </Button>
      </div>
      <div className="mt-3 space-y-3">
        {groups.length > 0 ? (
          groups.map((group) => <WatchlistGroupSection group={group} key={group.name} />)
        ) : (
          <Empty description="暂无自选股，候选表或详情抽屉可加入。" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </div>
    </Card>
  );
}

function WatchlistGroupSection({
  group,
}: {
  group: {
    name: string;
    items: WatchlistPoolItem[];
  };
}) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-xs font-black text-slate-800">分组 {group.name}</h4>
        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-bold text-slate-500 ring-1 ring-slate-100">
          {group.items.length}
        </span>
      </div>
      <div className="mt-2 space-y-2">
        {group.items.map((item) => (
          <div className="rounded-md bg-white p-2 ring-1 ring-slate-100" key={item.symbol}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-xs font-black text-slate-950">{item.name ?? item.symbol}</p>
                <p className="mt-0.5 text-[11px] font-semibold text-slate-400">{item.symbol}</p>
              </div>
              {item.industry && (
                <span className="max-w-[120px] truncate rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-bold text-indigo-700 ring-1 ring-indigo-100">
                  {item.industry}
                </span>
              )}
            </div>
            {item.tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {item.tags.map((tag) => (
                  <span
                    className="inline-flex h-5 items-center rounded-full bg-slate-100 px-1.5 text-[11px] font-bold text-slate-600"
                    key={tag}
                  >
                    标签 {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

type CandidateTableProps = {
  generatedAt: string | null;
  items: StrongStockScreeningItem[];
  onAddManyToWatchlist: (items: StrongStockScreeningItem[], group: string, tags: string[]) => void;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  running: boolean;
  selectedSymbol: string | null;
  watchlistMessage: string | null;
  watchlistPoolItems: WatchlistPoolItem[];
};

function DesignScreenerResultsTable(props: CandidateTableProps) {
  return <CandidateTable {...props} />;
}

function CandidateTable({
  generatedAt,
  items,
  onAddManyToWatchlist,
  onAddToWatchlist,
  onSelect,
  running,
  selectedSymbol,
  watchlistMessage,
  watchlistPoolItems,
}: CandidateTableProps) {
  const [selectedCandidateSymbols, setSelectedCandidateSymbols] = useState<Set<string>>(() => new Set());
  const [batchGroup, setBatchGroup] = useState("");
  const [batchTagsText, setBatchTagsText] = useState("");
  const [candidateStatusFilter, setCandidateStatusFilter] = useState<CandidateStatusFilter>("all");
  const [gsgfSignalFilter, setGsgfSignalFilter] = useState<GsgfSignalFilter>("all");
  const [excludeGsgfGlobalRisk, setExcludeGsgfGlobalRisk] = useState(false);
  const [strongIndustryOnly, setStrongIndustryOnly] = useState(false);
  const statusCounts = useMemo(() => {
    const counts: Record<CandidateStatusFilter, number> = {
      all: items.length,
      data_incomplete: 0,
      focus: 0,
      reduce_risk: 0,
      wait_pullback: 0,
    };
    for (const item of items) {
      counts[item.status] += 1;
    }
    return counts;
  }, [items]);
  const strongIndustryCount = useMemo(
    () => items.filter((item) => item.industry_strength === "strong").length,
    [items],
  );
  const visibleCandidates = useMemo(
    () =>
      filterStockListByGsgf(
        items.filter(
          (item) =>
            (candidateStatusFilter === "all" || item.status === candidateStatusFilter) &&
            (!strongIndustryOnly || item.industry_strength === "strong"),
        ),
        gsgfSignalFilter,
        excludeGsgfGlobalRisk,
      ),
    [candidateStatusFilter, excludeGsgfGlobalRisk, gsgfSignalFilter, items, strongIndustryOnly],
  );
  const selectedCandidateItems = visibleCandidates.filter((item) => selectedCandidateSymbols.has(item.symbol));
  const watchlistSymbols = useMemo(
    () => new Set(watchlistPoolItems.map((item) => item.symbol)),
    [watchlistPoolItems],
  );

  useEffect(() => {
    const validSymbols = new Set(visibleCandidates.map((item) => item.symbol));
    setSelectedCandidateSymbols((current) => {
      const next = new Set(Array.from(current).filter((symbol) => validSymbols.has(symbol)));
      return next.size === current.size ? current : next;
    });
  }, [visibleCandidates]);

  function toggleCandidateSelection(symbol: string, checked: boolean) {
    setSelectedCandidateSymbols((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(symbol);
      } else {
        next.delete(symbol);
      }
      return next;
    });
  }

  function clearBatchSelection() {
    setSelectedCandidateSymbols(new Set());
  }

  function selectAllCandidates() {
    setSelectedCandidateSymbols(new Set(visibleCandidates.map((item) => item.symbol)));
  }

  function addSelectedCandidates() {
    onAddManyToWatchlist(selectedCandidateItems, batchGroup, splitTags(batchTagsText));
    clearBatchSelection();
  }

  const columns = useMemo<ColumnsType<StrongStockScreeningItem>>(
    () => [
      {
        title: "股票 STOCK",
        dataIndex: "name",
        width: 260,
        render: (_, item) => (
          <div className="min-w-0">
            <Link
              className="block font-black text-[#11100e] transition hover:text-[#f04438]"
              href={`/stock/${item.symbol}`}
              onClick={(event) => event.stopPropagation()}
            >
              {item.name}
            </Link>
            <p className="mt-1 text-xs font-medium text-[#7b756d]">{item.symbol}</p>
          </div>
        ),
      },
      {
        title: "决策 SCORE",
        width: 150,
        render: (_, item) => {
          const view = statusCopy[item.status];
          return (
            <Space orientation="vertical" size={6}>
              <span className={`inline-flex h-7 items-center whitespace-nowrap rounded-full px-2.5 text-xs font-bold ring-1 ${view.tone}`}>
                {view.label}
              </span>
              <Typography.Text className="text-xs font-black tabular-nums text-[#11100e]">
                得分 {item.score}
              </Typography.Text>
              {item.gsgf && <div className="flex max-w-[180px] flex-wrap gap-1"><GsgfSummaryPills gsgf={item.gsgf} /></div>}
            </Space>
          );
        },
      },
      {
        title: "板块 SECTOR",
        width: 170,
        render: (_, item) => (
          <div className="flex flex-wrap items-center gap-1.5">
            <IndustryBadge industry={item.industry} />
            <IndustryStrengthBadge item={item} />
          </div>
        ),
      },
      {
        title: "风险 RISK",
        width: 220,
        render: (_, item) => {
          const riskSummary = primaryRiskSummary(item);
          return <p className={`line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>{riskSummary.text}</p>;
        },
      },
      {
        title: "操作 ACTION",
        align: "right",
        fixed: "right",
        width: 180,
        render: (_, item) => {
          const alreadyAdded = watchlistSymbols.has(item.symbol);
          return (
            <Space size={8}>
              <Button
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect(item.symbol);
                }}
                size="small"
              >
                高亮
              </Button>
              <Button
                href={`/stock/${item.symbol}`}
                onClick={(event) => event.stopPropagation()}
                size="small"
              >
                K线
              </Button>
              <Button
                disabled={alreadyAdded}
                onClick={(event) => {
                  event.stopPropagation();
                  onAddToWatchlist(item, "自选", []);
                }}
                size="small"
                type={alreadyAdded ? "default" : "primary"}
              >
                {alreadyAdded ? "已在自选" : "加入自选"}
              </Button>
            </Space>
          );
        },
      },
    ],
    [onAddToWatchlist, onSelect, watchlistSymbols],
  );

  return (
    <Card className="mt-4 min-w-0 overflow-hidden rounded-xl border-[#ddd8d0] bg-[#f8f7f4]" styles={{ body: { padding: 0 } }}>
      <div className="flex flex-col gap-3 border-b border-[#ddd8d0] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-black text-[#11100e]">选股结果 · Screener Results</h2>
            <span className="rounded-md border border-[#ddd8d0] px-2 py-0.5 text-xs font-bold text-[#7b756d]">{items.length}</span>
          </div>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
            {generatedAt ? new Date(generatedAt).toLocaleString("zh-CN") : "暂无运行结果"}
          </p>
        </div>
        <span className="rounded-lg border border-[#ddd8d0] bg-[#f5f3f0] px-3 py-1.5 text-xs font-bold text-[#7b756d]">
          点击股票名称查看 K 线详情
        </span>
      </div>
      {watchlistMessage && (
        <Alert aria-live="polite" className="rounded-none border-x-0 border-t-0" showIcon title={watchlistMessage} type="success" />
      )}
      {items.length > 0 && (
        <>
          <CandidateFilterBar
            candidateStatusFilter={candidateStatusFilter}
            excludeGsgfGlobalRisk={excludeGsgfGlobalRisk}
            gsgfSignalFilter={gsgfSignalFilter}
            onExcludeGsgfGlobalRiskChange={setExcludeGsgfGlobalRisk}
            onGsgfSignalFilterChange={setGsgfSignalFilter}
            onStatusFilterChange={setCandidateStatusFilter}
            onStrongIndustryOnlyChange={setStrongIndustryOnly}
            statusCounts={statusCounts}
            strongIndustryCount={strongIndustryCount}
            strongIndustryOnly={strongIndustryOnly}
            visibleCount={visibleCandidates.length}
          />
          {visibleCandidates.length > 0 && (
            <BatchActionBar
              batchGroup={batchGroup}
              batchTagsText={batchTagsText}
              onAddSelected={addSelectedCandidates}
              onBatchGroupChange={setBatchGroup}
              onBatchTagsTextChange={setBatchTagsText}
              onClearSelection={clearBatchSelection}
              onSelectAll={selectAllCandidates}
              selectedCount={selectedCandidateItems.length}
              totalCount={visibleCandidates.length}
            />
          )}
        </>
      )}
      <div className="hidden overflow-x-auto lg:block">
        <Table
          columns={columns}
          dataSource={visibleCandidates}
          loading={running}
          locale={{
            emptyText: items.length > 0 ? <FilteredTableState /> : <EmptyTableState running={running} />,
          }}
          pagination={false}
          rowClassName={(item) => (item.symbol === selectedSymbol ? "workbench-table-row-selected" : "")}
          rowKey="symbol"
          rowSelection={{
            selectedRowKeys: Array.from(selectedCandidateSymbols),
            onChange: (keys) => setSelectedCandidateSymbols(new Set(keys.map(String))),
          }}
          onRow={(item) => ({
            onClick: () => onSelect(item.symbol),
          })}
          scroll={{ x: 900 }}
          size="small"
        />
      </div>
      <div className="border-t border-slate-100 p-3 lg:hidden">
        {items.length > 0 ? (
          visibleCandidates.length > 0 ? (
            <CandidateCardList
              isBatchSelected={(symbol) => selectedCandidateSymbols.has(symbol)}
              items={visibleCandidates}
              isInWatchlist={(symbol) => watchlistSymbols.has(symbol)}
              onAddToWatchlist={onAddToWatchlist}
              onSelect={onSelect}
              onToggleBatchSelect={toggleCandidateSelection}
              selectedSymbol={selectedSymbol}
            />
          ) : (
            <FilteredTableState />
          )
        ) : (
          <EmptyTableState running={running} />
        )}
      </div>
    </Card>
  );
}

function CandidateCardList({
  isInWatchlist,
  isBatchSelected,
  items,
  onAddToWatchlist,
  onSelect,
  onToggleBatchSelect,
  selectedSymbol,
}: {
  isInWatchlist: (symbol: string) => boolean;
  isBatchSelected: (symbol: string) => boolean;
  items: StrongStockScreeningItem[];
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  onToggleBatchSelect: (symbol: string, checked: boolean) => void;
  selectedSymbol: string | null;
}) {
  return (
    <div className="space-y-3">
      {items.map((item) => {
        const view = statusCopy[item.status];
        const riskSummary = primaryRiskSummary(item);
        const alreadyAdded = isInWatchlist(item.symbol);
        return (
          <article
            aria-selected={item.symbol === selectedSymbol}
            className={`rounded-lg border p-3 transition ${
              item.symbol === selectedSymbol ? "border-slate-950 bg-slate-50" : "border-slate-200 bg-white"
            }`}
            key={item.symbol}
          >
            <div className="flex items-start gap-3">
              <input
                aria-label={`选择 ${item.name}`}
                checked={isBatchSelected(item.symbol)}
                className="mt-1 size-4 rounded border-slate-300"
                onChange={(event) => onToggleBatchSelect(item.symbol, event.target.checked)}
                type="checkbox"
              />
              <button className="min-w-0 flex-1 text-left" onClick={() => onSelect(item.symbol)} type="button">
                <span className="block truncate text-sm font-black text-slate-950">{item.name}</span>
                <span className="mt-1 block text-xs font-semibold text-slate-400">{item.symbol}</span>
              </button>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${view.tone}`}>
                {view.label}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-2 text-[11px] font-bold text-slate-700">
                得分 {item.score}
              </span>
              <GsgfSummaryPills gsgf={item.gsgf} />
              <IndustryBadge industry={item.industry} />
              <IndustryStrengthBadge item={item} />
            </div>
            <p className={`mt-3 line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>{riskSummary.text}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <a
                className="inline-flex min-h-[36px] items-center justify-center rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200"
                href={`/stock/${item.symbol}`}
              >
                K线
              </a>
              <button
                className="min-h-[36px] rounded-md bg-slate-950 px-3 text-xs font-bold text-white disabled:cursor-not-allowed disabled:bg-emerald-100 disabled:text-emerald-700"
                disabled={alreadyAdded}
                onClick={() => onAddToWatchlist(item, "自选", [])}
                type="button"
              >
                {alreadyAdded ? "已在自选" : "加入自选"}
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function CandidateFilterBar({
  candidateStatusFilter,
  excludeGsgfGlobalRisk,
  gsgfSignalFilter,
  onExcludeGsgfGlobalRiskChange,
  onGsgfSignalFilterChange,
  onStatusFilterChange,
  onStrongIndustryOnlyChange,
  statusCounts,
  strongIndustryCount,
  strongIndustryOnly,
  visibleCount,
}: {
  candidateStatusFilter: CandidateStatusFilter;
  excludeGsgfGlobalRisk: boolean;
  gsgfSignalFilter: GsgfSignalFilter;
  onExcludeGsgfGlobalRiskChange: (value: boolean) => void;
  onGsgfSignalFilterChange: (value: GsgfSignalFilter) => void;
  onStatusFilterChange: (value: CandidateStatusFilter) => void;
  onStrongIndustryOnlyChange: (value: boolean) => void;
  statusCounts: Record<CandidateStatusFilter, number>;
  strongIndustryCount: number;
  strongIndustryOnly: boolean;
  visibleCount: number;
}) {
  return (
    <div className="border-b border-slate-100 bg-white px-5 py-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black text-slate-700">候选筛选</span>
          <Tag className="m-0" variant="filled">
            显示 {visibleCount}
          </Tag>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            onChange={(value) => onStatusFilterChange(value as CandidateStatusFilter)}
            options={candidateStatusFilters.map((filter) => ({
              label: `${filter.label} ${statusCounts[filter.value]}`,
              value: filter.value,
            }))}
            size="small"
            value={candidateStatusFilter}
          />
          <Button
            aria-pressed={strongIndustryOnly}
            onClick={() => onStrongIndustryOnlyChange(!strongIndustryOnly)}
            size="small"
            type={strongIndustryOnly ? "primary" : "default"}
          >
            强板块 {strongIndustryCount}
          </Button>
        </div>
      </div>
      <div className="mt-3 flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
        <Segmented
          onChange={(value) => onGsgfSignalFilterChange(value as GsgfSignalFilter)}
          options={gsgfSignalFilterOptions}
          size="small"
          value={gsgfSignalFilter}
        />
        <Checkbox
          checked={excludeGsgfGlobalRisk}
          onChange={(event) => onExcludeGsgfGlobalRiskChange(event.target.checked)}
        >
          排除全局阴量压制
        </Checkbox>
      </div>
    </div>
  );
}

function BatchActionBar({
  batchGroup,
  batchTagsText,
  onAddSelected,
  onBatchGroupChange,
  onBatchTagsTextChange,
  onClearSelection,
  onSelectAll,
  selectedCount,
  totalCount,
}: {
  batchGroup: string;
  batchTagsText: string;
  onAddSelected: () => void;
  onBatchGroupChange: (value: string) => void;
  onBatchTagsTextChange: (value: string) => void;
  onClearSelection: () => void;
  onSelectAll: () => void;
  selectedCount: number;
  totalCount: number;
}) {
  return (
    <div className="grid gap-2 border-b border-slate-100 bg-slate-50 px-5 py-3 lg:grid-cols-[auto_minmax(90px,120px)_minmax(120px,1fr)_auto] lg:items-center">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-600">
        <Tag className="m-0">已选 {selectedCount}</Tag>
        <Button onClick={onSelectAll} size="small" type="link">
          全选 {totalCount}
        </Button>
        <Button
          disabled={selectedCount === 0}
          onClick={onClearSelection}
          size="small"
          type="link"
        >
          清空选择
        </Button>
      </div>
      <Input
        onChange={(event) => onBatchGroupChange(event.target.value)}
        placeholder="批量分组"
        size="small"
        value={batchGroup}
      />
      <Input
        onChange={(event) => onBatchTagsTextChange(event.target.value)}
        placeholder="批量标签，逗号分隔"
        size="small"
        value={batchTagsText}
      />
      <Button
        disabled={selectedCount === 0}
        onClick={onAddSelected}
        size="small"
        type="primary"
      >
        批量加入自选
      </Button>
    </div>
  );
}

function CandidateTableRow({
  isInWatchlist,
  isBatchSelected,
  isSelected,
  item,
  onAddToWatchlist,
  onSelect,
  onToggleBatchSelect,
}: {
  isInWatchlist: boolean;
  isBatchSelected: boolean;
  isSelected: boolean;
  item: StrongStockScreeningItem;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  onToggleBatchSelect: (symbol: string, checked: boolean) => void;
}) {
  const view = statusCopy[item.status];
  const riskSummary = primaryRiskSummary(item);

  return (
    <tr
      aria-selected={isSelected}
      className={`cursor-pointer transition ${isSelected ? "bg-slate-100" : "bg-white hover:bg-slate-50"}`}
      onClick={() => onSelect(item.symbol)}
    >
      <td className="px-5 py-4 align-top">
        <div className="flex items-start gap-2">
          <input
            aria-label={`选择 ${item.name}`}
            checked={isBatchSelected}
            className="mt-1 size-4 rounded border-slate-300"
            onChange={(event) => onToggleBatchSelect(item.symbol, event.target.checked)}
            onClick={(event) => event.stopPropagation()}
            type="checkbox"
          />
          <div className="min-w-0">
            <a
              className="inline-flex items-baseline gap-2 whitespace-nowrap font-black text-slate-950 transition hover:text-slate-700"
              href={`/stock/${item.symbol}`}
              onClick={(event) => event.stopPropagation()}
            >
              {item.name}
              <span className="text-xs font-semibold text-slate-400">{item.symbol}</span>
            </a>
            <p className="mt-1 line-clamp-1 text-xs text-slate-500">{item.rule_hits[0] ?? "暂无规则说明"}</p>
          </div>
        </div>
      </td>
      <td className="px-3 py-4 align-top">
        <span className={`inline-flex h-7 items-center whitespace-nowrap rounded-full px-2.5 text-xs font-bold ring-1 ${view.tone}`}>
          {view.label}
        </span>
        <p className="mt-2 text-xs font-black tabular-nums text-slate-950">得分 {item.score}</p>
        {item.gsgf && (
          <div className="mt-2 flex max-w-[180px] flex-wrap gap-1">
            <GsgfSummaryPills gsgf={item.gsgf} />
          </div>
        )}
      </td>
      <td className="px-4 py-4 align-top">
        <div className="flex flex-wrap items-center gap-1.5">
          <IndustryBadge industry={item.industry} />
          <IndustryStrengthBadge item={item} />
        </div>
      </td>
      <td className="max-w-[220px] px-4 py-4 align-top">
        <p className={`line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>
          {riskSummary.text}
        </p>
      </td>
      <td className="px-5 py-4 text-right align-top">
        <div className="flex justify-end gap-2">
          <button
            className="min-h-[32px] whitespace-nowrap rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100 active:translate-y-px"
            onClick={(event) => {
              event.stopPropagation();
              onSelect(item.symbol);
            }}
            type="button"
          >
            详情
          </button>
          <button
            className="min-h-[32px] whitespace-nowrap rounded-md bg-slate-950 px-3 text-xs font-bold text-white transition hover:bg-slate-800 active:translate-y-px disabled:cursor-not-allowed disabled:bg-emerald-100 disabled:text-emerald-700"
            disabled={isInWatchlist}
            onClick={(event) => {
              event.stopPropagation();
              onAddToWatchlist(item, "自选", []);
            }}
            type="button"
          >
            {isInWatchlist ? "已在自选" : "加入自选"}
          </button>
        </div>
      </td>
    </tr>
  );
}

function EmptyTableState({ running }: { running: boolean }) {
  return (
    <div className="px-5 py-12 text-center">
      <Empty
        description={
          <span className="text-sm text-slate-500">
            {running ? "正在读取候选和板块强度。" : "运行筛选后显示候选。"}
          </span>
        }
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      >
        <p className="text-sm font-bold text-slate-700">{running ? "筛选中..." : "未运行筛选"}</p>
      </Empty>
    </div>
  );
}

function FilteredTableState() {
  return (
    <div className="px-5 py-12 text-center">
      <Empty
        description={<span className="text-sm text-slate-500">切换候选筛选后显示匹配股票。</span>}
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      >
        <p className="text-sm font-bold text-slate-700">当前筛选暂无候选</p>
      </Empty>
    </div>
  );
}

function CandidateDetailPanel({
  intradayItem,
  item,
  onAddToWatchlist,
  riskItem,
  watchlistPoolItems,
}: {
  intradayItem: StrongStockIntradayItem | null;
  item: StrongStockScreeningItem | null;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  riskItem: WatchlistRiskItem | null;
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  const [watchlistGroup, setWatchlistGroup] = useState("");
  const [watchlistTagsText, setWatchlistTagsText] = useState("");
  const watchlistSymbols = useMemo(
    () => new Set(watchlistPoolItems.map((poolItem) => poolItem.symbol)),
    [watchlistPoolItems],
  );

  useEffect(() => {
    setWatchlistGroup("");
    setWatchlistTagsText("");
  }, [item?.symbol]);

  if (!item) {
    return (
      <Card className="workbench-card">
        <p className="text-xs font-semibold uppercase text-slate-400">Detail</p>
        <h2 className="mt-1 text-xl font-black text-slate-950">详情抽屉</h2>
        <Empty className="mt-8" description="选择候选股票后显示结论和证据。" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const view = statusCopy[item.status];
  const riskView = riskItem ? riskCopy[riskItem.risk_action] : null;
  const intradayView = intradayItem ? intradayCopy[intradayItem.action] : null;
  const otherFlags = item.risk_flags.filter((flag) => !flag.includes("严重异动"));
  const alreadyAdded = watchlistSymbols.has(item.symbol);

  return (
    <aside className="rounded-lg border border-slate-200 bg-white shadow-sm xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto">
      <div className="border-b border-slate-100 px-5 py-4">
        <p className="text-xs font-semibold uppercase text-slate-400">Detail</p>
        <h2 className="mt-1 text-xl font-black text-slate-950">详情抽屉</h2>
      </div>
      <div className="space-y-5 p-5">
        <section>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-lg font-black text-slate-950">{item.name}</h3>
              <p className="mt-1 text-xs font-semibold text-slate-400">{item.symbol}</p>
            </div>
            <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${view.tone}`}>
              {view.label}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-2 text-xs font-bold text-slate-700">
              得分 {item.score}
            </span>
            <GsgfSummaryPills gsgf={item.gsgf} />
            <IndustryBadge industry={item.industry} />
            <IndustryStrengthBadge item={item} />
          </div>
        </section>

        <DetailSection title="股是股非结构">
          {item.gsgf ? (
            <GsgfDetail analysis={item.gsgf} />
          ) : (
            <p className="text-sm leading-6 text-slate-500">暂无股是股非结构评分。</p>
          )}
        </DetailSection>

        <DetailSection title="关键证据">
          <EvidenceList items={item.rule_hits} fallback="暂无规则说明" />
          {item.industry_notes.length > 0 && <EvidenceList items={item.industry_notes} />}
        </DetailSection>

        <DetailSection title="风险">
          <RiskCheckPanel item={item} riskItem={riskItem} />
          <EvidenceList items={otherFlags} fallback="暂无风险提示" />
          {riskItem && riskView && (
            <div className="mt-3 rounded-lg bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-500">自选股 / 持仓风控</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ring-1 ${riskView.tone}`}>
                  {riskView.label}
                </span>
              </div>
              <EvidenceList items={[...riskItem.risk_flags, ...riskItem.negative_news_flags, ...riskItem.intraday_notes]} />
            </div>
          )}
        </DetailSection>

        <DetailSection title="操作">
          <div className="space-y-2">
            <Input
              onChange={(event) => setWatchlistGroup(event.target.value)}
              placeholder="分组"
              value={watchlistGroup}
            />
            <Input
              onChange={(event) => setWatchlistTagsText(event.target.value)}
              placeholder="标签，逗号分隔"
              value={watchlistTagsText}
            />
            <Button
              block
              disabled={alreadyAdded}
              onClick={() => onAddToWatchlist(item, watchlistGroup, splitTags(watchlistTagsText))}
              type={alreadyAdded ? "default" : "primary"}
            >
              {alreadyAdded ? "已在自选" : "加入自选"}
            </Button>
          </div>
          {intradayItem && intradayView && (
            <div className="mt-3 rounded-lg bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-500">盘中监控</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ring-1 ${intradayView.tone}`}>
                  {intradayView.label}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <ValuePill label="现价" value={formatPrice(intradayItem.last_price)} />
                <ValuePill label="涨跌" value={formatPercent(intradayItem.pct_change)} />
              </div>
              <EvidenceList items={intradayItem.signals} />
              {(intradayItem.group || intradayItem.tags.length > 0) && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {intradayItem.group && (
                    <span className="inline-flex h-6 items-center rounded-full bg-slate-200 px-2 text-[11px] font-bold text-slate-700">
                      分组 {intradayItem.group}
                    </span>
                  )}
                  {intradayItem.tags.map((tag) => (
                    <span
                      className="inline-flex h-6 items-center rounded-full bg-white px-2 text-[11px] font-bold text-slate-600 ring-1 ring-slate-100"
                      key={tag}
                    >
                      标签 {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </DetailSection>

        <details className="rounded-lg border border-slate-100 bg-slate-50 p-3">
          <summary className="cursor-pointer text-xs font-bold text-slate-600">展开全部证据</summary>
          <div className="mt-3 space-y-3">
            <EvidenceBlock title="盘中备注" items={item.intraday_notes} />
            <EvidenceBlock title="数据源" items={item.source_trace} />
            <EvidenceBlock title="风控原文" items={item.risk_flags} />
          </div>
        </details>
      </div>
    </aside>
  );
}

function DetailSection({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="border-t border-slate-100 pt-4">
      <h4 className="text-sm font-black text-slate-950">{title}</h4>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function EvidenceList({ fallback, items }: { fallback?: string; items: string[] }) {
  if (items.length === 0) {
    return fallback ? <p className="text-sm leading-6 text-slate-500">{fallback}</p> : null;
  }
  return (
    <ul className="space-y-1.5">
      {items.map((item, index) => (
        <li className="text-sm leading-6 text-slate-600" key={`${item}-${index}`}>
          {item}
        </li>
      ))}
    </ul>
  );
}

function EvidenceBlock({ items, title }: { items: string[]; title: string }) {
  return (
    <div>
      <p className="text-xs font-bold text-slate-500">{title}</p>
      <EvidenceList fallback="暂无记录" items={items} />
    </div>
  );
}

function RiskCheckPanel({
  item,
  riskItem,
}: {
  item: StrongStockScreeningItem;
  riskItem: WatchlistRiskItem | null;
}) {
  const newsFlags = [...item.negative_news_flags, ...(riskItem?.negative_news_flags ?? [])];
  const severeFlags = [
    ...item.risk_flags.filter((flag) => flag.includes("严重异动")),
    ...(riskItem?.risk_flags.filter((flag) => flag.includes("严重异动")) ?? []),
  ];
  const severeStatus = riskItem?.severe_abnormal_warning === "triggered"
    ? riskItem.severe_abnormal_warning
    : item.severe_abnormal_warning;
  const newsStatus = riskItem?.negative_news_status === "triggered"
    ? riskItem.negative_news_status
    : item.negative_news_status;

  return (
    <div className="mb-3 space-y-2">
      <RiskCheckNotice
        flags={newsFlags}
        status={newsStatus}
        title="负面新闻待核验"
        unknownText="负面新闻未知，新闻源未返回有效结果"
        clearText="近20条东方财富新闻未命中负面关键词"
      />
      <RiskCheckNotice
        flags={severeFlags}
        status={severeStatus}
        title="严重异动"
        unknownText="严重异动状态未知，候选源未返回该字段"
        clearText="候选源显示未触发严重异动"
      />
    </div>
  );
}

function RiskCheckNotice({
  clearText,
  flags,
  status,
  title,
  unknownText,
}: {
  clearText: string;
  flags: string[];
  status: "triggered" | "clear" | "unknown";
  title: string;
  unknownText: string;
}) {
  if (status === "triggered") {
    return (
      <div className="rounded-lg bg-red-50 p-3 ring-1 ring-red-100">
        <p className="text-sm font-black leading-6 text-red-700">{title}</p>
        <EvidenceList items={flags.length > 0 ? flags : [title]} />
      </div>
    );
  }
  if (status === "clear") {
    return <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700">{clearText}</p>;
  }
  return <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs font-bold text-slate-500">{unknownText}</p>;
}

function GsgfSummaryPills({ gsgf }: { gsgf: GsgfAnalysis | null }) {
  if (!gsgf) {
    return null;
  }
  const riskTone =
    gsgf.action === "avoid" || gsgf.zone === "c_zone"
      ? "bg-red-50 text-red-700 ring-red-100"
      : "bg-violet-50 text-violet-700 ring-violet-100";
  const statusTone = gsgfFinalStatusTone(gsgf.final_status);
  return (
    <>
      <span className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${riskTone}`}>
        股是股非 {gsgf.total_score}
      </span>
      <span className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${statusTone}`}>
        {gsgf.final_status}
      </span>
      <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-2 text-[11px] font-bold text-slate-700 ring-1 ring-slate-200">
        {gsgfLabel(gsgf.zone)}
      </span>
      <span className="inline-flex h-6 items-center rounded-full bg-white px-2 text-[11px] font-bold text-slate-600 ring-1 ring-slate-200">
        {gsgfLabel(gsgf.action)}
      </span>
      {gsgf.setup_type && (
        <span className="inline-flex h-6 items-center rounded-full bg-emerald-50 px-2 text-[11px] font-bold text-emerald-700 ring-1 ring-emerald-100">
          setup {gsgfLabel(gsgf.setup_type)}
        </span>
      )}
      {gsgf.confirm_type && (
        <span className="inline-flex h-6 items-center rounded-full bg-sky-50 px-2 text-[11px] font-bold text-sky-700 ring-1 ring-sky-100">
          确认信号 {gsgfLabel(gsgf.confirm_type)}
        </span>
      )}
    </>
  );
}

function GsgfDetail({ analysis }: { analysis: GsgfAnalysis }) {
  const plan = analysis.trade_plan ?? fallbackGsgfTradePlan(analysis);
  const tags = [
    ...analysis.pattern_tags.map((tag) => `形态：${tag}`),
    ...analysis.trigger_tags.map((tag) => `触发：${tag}`),
    ...analysis.pressure_flags.map((flag) => `压力：${flag}`),
    ...analysis.risk_flags.map((flag) => `风险：${flag}`),
  ];

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <GsgfMetric label="总分" value={analysis.total_score} />
        <GsgfMetric label="状态" value={analysis.final_status} />
        <GsgfMetric label="区位" value={gsgfLabel(analysis.zone)} />
        <GsgfMetric label="动作" value={gsgfLabel(analysis.action)} />
        <GsgfMetric label="setup" value={gsgfLabel(analysis.setup_type)} />
        <GsgfMetric label="确认信号" value={gsgfLabel(analysis.confirm_type)} />
      </div>
      <div className="rounded-lg bg-slate-50 p-3 ring-1 ring-slate-100">
        <p className="text-xs font-bold text-slate-500">量能结构</p>
        <p className="mt-1 text-sm font-black text-slate-900">{gsgfLabel(analysis.volume_structure)}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <ValuePill label="setup分" value={String(analysis.setup_score)} />
        <ValuePill label="确认分" value={String(analysis.confirm_score)} />
        <ValuePill label="量时空" value={String(analysis.scores.safety_pressure)} />
        <ValuePill label="量厚度" value={String(analysis.scores.volume_thickness)} />
        <ValuePill label="均线" value={String(analysis.scores.ma_alignment)} />
        <ValuePill label="空间" value={String(analysis.scores.pattern_space)} />
        <ValuePill label="星线" value={String(analysis.scores.star_trigger)} />
        <ValuePill label="题材" value={String(analysis.scores.sector_theme)} />
      </div>
      <EvidenceList fallback="暂无结构标签" items={tags.length > 0 ? tags : analysis.explanation} />
      <GsgfTradePlanPanel plan={plan} />
    </div>
  );
}

function GsgfTradePlanPanel({ plan }: { plan: GsgfTradePlan }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="grid gap-3 md:grid-cols-3">
        <GsgfTradePlanColumn items={plan.holder_guidance} title="持仓计划" />
        <GsgfTradePlanColumn items={plan.empty_position_guidance} title="空仓计划" />
        <GsgfTradePlanColumn items={plan.risk_invalidation} title="失效条件" />
      </div>
      <p className="mt-3 border-t border-slate-100 pt-2 text-xs leading-5 text-slate-500">{plan.research_note}</p>
    </div>
  );
}

function GsgfTradePlanColumn({ items, title }: { items: string[]; title: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-black text-slate-500">{title}</p>
      <EvidenceList fallback="暂无计划" items={items} />
    </div>
  );
}

function GsgfMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg bg-white p-2 ring-1 ring-slate-100">
      <p className="text-[11px] font-bold text-slate-400">{label}</p>
      <p className="mt-1 truncate text-sm font-black tabular-nums text-slate-950">{value}</p>
    </div>
  );
}

function gsgfLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    strong_candidate: "强势候选",
    watch_candidate: "观察候选",
    wait_trigger: "等触发",
    avoid: "回避",
    a_zone: "A区",
    b_zone_a_point: "B区A点",
    c_zone: "C区",
    unformed: "未成型",
    unknown: "未知",
    three_yang_controls_three_yin: "三阳控三阴",
    neutral: "量形态中性",
    three_yin_controls_three_yang: "三阴控三阳",
    volume_breakout_confirmation: "放量突破确认",
  };
  return value ? labels[value] ?? value : "--";
}

function fallbackGsgfTradePlan(analysis: GsgfAnalysis): GsgfTradePlan {
  return {
    status: analysis.final_status,
    holder_guidance: ["当前数据未返回后端交易计划，请重新运行筛选刷新。"],
    empty_position_guidance: ["空仓先等待后端计划刷新，不依据旧结构文本追涨。"],
    risk_invalidation: ["后端计划缺失时，以风险 flags 和盘中确认状态为先。"],
    research_note: "规则解释仅作研究辅助，不构成收益承诺或投资建议。",
  };
}

function gsgfFinalStatusTone(status: GsgfAnalysis["final_status"]) {
  const tones: Record<GsgfAnalysis["final_status"], string> = {
    候选: "bg-sky-50 text-sky-700 ring-sky-100",
    低吸观察: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    减仓: "bg-amber-50 text-amber-700 ring-amber-100",
    回避: "bg-red-50 text-red-700 ring-red-100",
    确认买点: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    观察: "bg-slate-100 text-slate-600 ring-slate-200",
  };
  return tones[status];
}

function primaryRiskSummary(item: StrongStockScreeningItem) {
  if (item.negative_news_status === "triggered") {
    return {
      text: item.negative_news_flags[0] ?? "负面新闻待核验",
      tone: "font-black text-red-600",
    };
  }
  if (item.severe_abnormal_warning === "triggered") {
    const severeFlag = item.risk_flags.find((flag) => flag.includes("严重异动"));
    return {
      text: severeFlag ?? "严重异动",
      tone: "font-black text-red-600",
    };
  }
  const firstRisk = item.risk_flags.find((flag) => !flag.includes("严重异动"));
  return {
    text: firstRisk ?? "无明显风险",
    tone: firstRisk ? "text-slate-500" : "text-slate-400",
  };
}

function ValuePill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-white px-2 text-[11px] font-bold text-slate-600 ring-1 ring-slate-100">
      {label} {value}
    </span>
  );
}

function IndustryStrengthBadge({ item }: { item: StrongStockScreeningItem }) {
  if (!item.industry_strength) {
    return null;
  }
  const view = industryStrengthCopy[item.industry_strength];
  const scoreText = item.industry_score > 0 ? ` +${item.industry_score}` : "";
  return (
    <span className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${view.tone}`}>
      板块强度 {view.label}
      {scoreText}
    </span>
  );
}

function IndustryBadge({ industry }: { industry: string | null }) {
  if (!industry) {
    return null;
  }
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-indigo-50 px-2 text-[11px] font-bold text-indigo-700 ring-1 ring-indigo-100">
      行业 {industry}
    </span>
  );
}

function groupWatchlistPoolItems(items: WatchlistPoolItem[]) {
  const groups: Array<{ name: string; items: WatchlistPoolItem[] }> = [];
  const indexByName = new Map<string, number>();
  for (const item of items) {
    const name = item.group?.trim() || "自选";
    let index = indexByName.get(name);
    if (index === undefined) {
      index = groups.length;
      indexByName.set(name, index);
      groups.push({ name, items: [] });
    }
    groups[index].items.push(item);
  }
  return groups;
}

function buildMarketDashboardStats(
  items: StrongStockScreeningItem[],
  result: StrongStockScreeningResponse | null,
): MarketDashboardStats {
  return {
    dataIncompleteCount: items.filter((item) => item.status === "data_incomplete").length,
    focusCount: items.filter((item) => item.status === "focus").length,
    negativeNewsCount: items.filter((item) => item.negative_news_status === "triggered").length,
    reduceRiskCount: items.filter((item) => item.status === "reduce_risk").length,
    riskEmptyCount: result?.watchlist_risk_items.filter((item) => item.risk_action === "empty").length ?? 0,
    severeWarningCount: items.filter((item) => item.severe_abnormal_warning === "triggered").length,
    totalCount: items.length,
    waitPullbackCount: items.filter((item) => item.status === "wait_pullback").length,
  };
}

function sumPositiveSectorFlow(items: SectorRadarItem[]): number {
  return items.reduce((sum, item) => sum + Math.max(0, item.net_flow_cny ?? 0), 0);
}

function sumNegativeSectorFlow(items: SectorRadarItem[]): number {
  return items.reduce((sum, item) => sum + Math.abs(Math.min(0, item.net_flow_cny ?? 0)), 0);
}

function buildTurnoverSeries(turnover: MarketOverviewResponse["turnover"] | null) {
  const previous = turnover?.previous_total_cny ?? null;
  const current = turnover?.total_cny ?? null;
  if (previous === null || current === null || previous <= 0 || current <= 0) {
    return [];
  }
  const max = Math.max(previous, current);
  return [previous, current].map((value) => Math.max(18, Math.min(96, (value / max) * 86)));
}

function formatCnyCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  const absValue = Math.abs(value);
  if (absValue >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(2)}万亿`;
  }
  if (absValue >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(0)}亿`;
  }
  if (absValue >= 10_000) {
    return `${(value / 10_000).toFixed(0)}万`;
  }
  return value.toFixed(0);
}

function formatSignedCny(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatCnyCompact(value)}`;
}

function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}

function formatPlainPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(2)}%`;
}

function formatReviewPercent(value: number | null | undefined): string {
  return formatSignedPercent(value);
}

function formatTurnoverChange(turnover: MarketOverviewResponse["turnover"] | null): string {
  if (!turnover || turnover.change_cny === null || turnover.change_pct === null) {
    return "昨日对比待确认";
  }
  return `较昨日 ${formatSignedCny(turnover.change_cny)} (${formatSignedPercent(turnover.change_pct)})`;
}

function marketOverviewSourceSummary(marketOverview: MarketOverviewResponse | null): string {
  const items = marketOverview?.source_status ?? [];
  if (items.length === 0) {
    return "";
  }
  const successCount = items.filter((item) => item.status === "success").length;
  return `${successCount}/${items.length} 市场源可用`;
}

function sectorRadarSourceSummary(sectorRadar: SectorRadarResponse | null): string {
  const items = sectorRadar?.source_status ?? [];
  if (items.length === 0) {
    return "";
  }
  const successCount = items.filter((item) => item.status === "success").length;
  const flowLabel = sectorRadar?.capital_flow_status === "direct" ? "直接资金流" : "估算资金流";
  return `${successCount}/${items.length} 板块源可用 · ${flowLabel}`;
}

function buildSectorRadarSentiment(sectorRadar: SectorRadarResponse | null): {
  footerValue: string;
  score: number | null;
  subValue: string;
  tone: "positive" | "neutral" | "warning";
} {
  const inflow = sectorRadar?.inflow ?? [];
  const outflow = sectorRadar?.outflow ?? [];
  const inflowTotal = inflow.reduce((sum, item) => sum + Math.max(0, item.net_flow_cny ?? 0), 0);
  const outflowTotal = outflow.reduce((sum, item) => sum + Math.abs(Math.min(0, item.net_flow_cny ?? 0)), 0);
  const total = inflowTotal + outflowTotal;
  if (total <= 0) {
    return {
      footerValue: "等待板块资金流",
      score: null,
      subValue: "读取 /sectors 同源数据中",
      tone: "neutral",
    };
  }
  const score = Math.round((inflowTotal / total) * 100);
  return {
    footerValue: `${inflow.length}/${outflow.length}`,
    score,
    subValue: `流入 ${formatCnyCompact(inflowTotal)} · 流出 ${formatCnyCompact(outflowTotal)}`,
    tone: score >= 55 ? "positive" : score >= 45 ? "neutral" : "warning",
  };
}

function realtimeTurnoverSourceLabel(marketOverview: MarketOverviewResponse | null): string | null {
  const statuses = marketOverview?.source_status ?? [];
  if (statuses.some((item) => item.source === "iFinD 实时指数" && item.status === "success")) {
    return "iFinD 实时口径";
  }
  if (statuses.some((item) => item.source === "TickFlow 实时指数" && item.status === "success")) {
    return "TickFlow 实时口径";
  }
  return null;
}

function sourceSummary(sources: DataSourceStatusResponse | null): { label: string; ok: boolean } {
  if (!sources || sources.items.length === 0) {
    return { label: "读取中", ok: false };
  }
  const successCount = sources.items.filter((item) => item.status === "success").length;
  return {
    label: `${successCount}/${sources.items.length} 可用`,
    ok: successCount === sources.items.length,
  };
}

function exportCandidatesCsv(items: StrongStockScreeningItem[]) {
  if (typeof window === "undefined" || items.length === 0) {
    return;
  }
  const headers = ["代码", "名称", "行业", "状态", "得分", "板块强度", "风险"];
  const rows = items.map((item) => [
    item.symbol,
    item.name,
    item.industry ?? "",
    statusCopy[item.status].label,
    String(item.score),
    item.industry_strength ? industryStrengthCopy[item.industry_strength].label : "",
    primaryRiskSummary(item).text,
  ]);
  const csv = [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `strong-stock-candidates-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string) {
  return `"${value.replaceAll("\"", "\"\"")}"`;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function strategyName(strategy: ScreenStrategy): string {
  return strategyOptions.find((option) => option.value === strategy)?.label ?? strategy;
}

function marketTypeLabel(value: MarketType): string {
  return marketTypeOptions.find((option) => option.value === value)?.label ?? value;
}

function marketCapFilterLabel(filters: ScreenRunFilters): string {
  const min = filters.min_market_cap_billion;
  const max = filters.max_market_cap_billion;
  if (min !== null && min !== undefined && max !== null && max !== undefined) {
    return `市值 ${min}-${max}亿`;
  }
  if (min !== null && min !== undefined) {
    return `市值 > ${min}亿`;
  }
  if (max !== null && max !== undefined) {
    return `市值 < ${max}亿`;
  }
  return "市值不限";
}

function splitTags(value: string) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，]/)) {
    const tag = chunk.trim();
    if (tag && !seen.has(tag)) {
      seen.add(tag);
      output.push(tag);
    }
  }
  return output;
}

function splitFilterValues(value: string) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，]/)) {
    const item = chunk.trim();
    if (item && !seen.has(item)) {
      seen.add(item);
      output.push(item);
    }
  }
  return output;
}

function sourceTagColor(status: SourceStatusValue) {
  const colors: Record<SourceStatusValue, string> = {
    disabled: "default",
    failed: "red",
    missing_key: "orange",
    stale: "blue",
    success: "green",
  };
  return colors[status];
}

function normalizeOptionalNumber(value: number | string | null, minimum?: number) {
  if (value === null || String(value).trim() === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return minimum === undefined ? parsed : Math.max(minimum, parsed);
}

function cleanScreenFilters(filters: ScreenRunFilters): ScreenRunFilters {
  return {
    ...(filters.min_market_cap_billion !== null &&
      filters.min_market_cap_billion !== undefined && { min_market_cap_billion: filters.min_market_cap_billion }),
    ...(filters.max_market_cap_billion !== null &&
      filters.max_market_cap_billion !== undefined && { max_market_cap_billion: filters.max_market_cap_billion }),
    ...(filters.kdj_j_max !== null && filters.kdj_j_max !== undefined && { kdj_j_max: filters.kdj_j_max }),
    ...((filters.industries ?? []).length > 0 && { industries: filters.industries }),
    ...((filters.market_types ?? []).length > 0 && { market_types: filters.market_types }),
  };
}

function activeScreenFilterCount(filters: ScreenRunFilters) {
  let count = 0;
  if (filters.min_market_cap_billion !== null && filters.min_market_cap_billion !== undefined) {
    count += 1;
  }
  if (filters.max_market_cap_billion !== null && filters.max_market_cap_billion !== undefined) {
    count += 1;
  }
  if (filters.kdj_j_max !== null && filters.kdj_j_max !== undefined) {
    count += 1;
  }
  if ((filters.industries ?? []).length > 0) {
    count += 1;
  }
  if ((filters.market_types ?? []).length > 0) {
    count += 1;
  }
  return count;
}

function normalizeScanLimit(value: number | string | null) {
  const parsed = typeof value === "number" ? value : Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return 40;
  }
  return Math.max(1, Math.min(300, parsed));
}

function normalizeKlineCount(value: number | string | null) {
  const parsed = typeof value === "number" ? value : Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return 260;
  }
  return Math.max(70, Math.min(260, parsed));
}

function formatPrice(value: number | null) {
  if (value === null) {
    return "--";
  }
  return value.toFixed(2);
}

function formatPercent(value: number | null) {
  if (value === null) {
    return "--";
  }
  return `${value.toFixed(2)}%`;
}
