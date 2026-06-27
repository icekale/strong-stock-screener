"use client";

import { use, useEffect, useMemo, useState } from "react";
import { TickFlowKlineChart } from "../../../components/TickFlowKlineChart";
import { getLatestScreenRun, getStockKline, getStockResearch } from "../../../lib/api";
import type { KlineBar, StockKlineResponse, StockResearchResponse, StrongStockScreeningItem } from "../../../lib/types";

type ChartTab = "day" | "week" | "info" | "strategy" | "concept" | "research";
type MovingAverageField = "ma5" | "ma10" | "ma20" | "ma60";

type StockListItem = {
  industry: string | null;
  name: string | null;
  score: number | null;
  status: StrongStockScreeningItem["status"] | null;
  symbol: string;
};

const CHART_TABS: Array<{ key: ChartTab; label: string }> = [
  { key: "day", label: "日 K 线" },
  { key: "week", label: "周线图" },
  { key: "info", label: "信息" },
  { key: "strategy", label: "战法" },
  { key: "concept", label: "概念" },
  { key: "research", label: "研究" },
];

const KLINE_CHART_HEIGHT = 680;

const MOVING_AVERAGES: Array<{ color: string; field: MovingAverageField; label: string; period: number }> = [
  { color: "#1683ff", field: "ma5", label: "MA5", period: 5 },
  { color: "#f59e0b", field: "ma10", label: "MA10", period: 10 },
  { color: "#8b5cf6", field: "ma20", label: "MA20", period: 20 },
  { color: "#64748b", field: "ma60", label: "MA60", period: 60 },
];

export default function StockKlinePage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: rawSymbol } = use(params);
  const symbol = decodeURIComponent(rawSymbol);
  const [data, setData] = useState<StockKlineResponse | null>(null);
  const [research, setResearch] = useState<StockResearchResponse | null>(null);
  const [screenItems, setScreenItems] = useState<StrongStockScreeningItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [researchLoading, setResearchLoading] = useState(true);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [activeChartTab, setActiveChartTab] = useState<ChartTab>("day");
  const [showGsgfAnnotations, setShowGsgfAnnotations] = useState(true);
  const [visibleMovingAverages, setVisibleMovingAverages] = useState<MovingAverageField[]>([
    "ma5",
    "ma10",
    "ma20",
  ]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getStockKline(symbol, 220)
      .then((response) => {
        if (!cancelled) {
          setData(response);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "读取K线失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  useEffect(() => {
    let cancelled = false;
    setResearchLoading(true);
    setResearchError(null);
    getStockResearch(symbol)
      .then((response) => {
        if (!cancelled) {
          setResearch(response);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setResearch(null);
          setResearchError(err instanceof Error ? err.message : "读取个股研究失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setResearchLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  useEffect(() => {
    let cancelled = false;
    setListLoading(true);
    getLatestScreenRun()
      .then((response) => {
        if (!cancelled) {
          setScreenItems(response.items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setScreenItems([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setListLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const bars = data?.bars ?? [];
  const dailyBars = useMemo(() => buildMovingAverageBars(bars), [bars]);
  const weeklyBars = useMemo(() => buildMovingAverageBars(buildWeeklyBars(bars)), [bars]);
  const chartBars = activeChartTab === "week" ? weeklyBars : dailyBars;
  const stockList = useMemo(() => buildStockList(symbol, screenItems), [screenItems, symbol]);
  const currentStock = stockList.find((item) => item.symbol === symbol) ?? stockList[0] ?? null;
  const currentCandidate = useMemo(
    () => screenItems.find((item) => item.symbol === symbol) ?? null,
    [screenItems, symbol],
  );
  const quote = useMemo(() => buildQuote(dailyBars), [dailyBars]);
  const isChartTab = activeChartTab === "day" || activeChartTab === "week";
  const activeTabLabel = CHART_TABS.find((item) => item.key === activeChartTab)?.label ?? "日 K 线";

  function toggleMovingAverage(field: MovingAverageField) {
    setVisibleMovingAverages((current) => {
      const next = current.includes(field) ? current.filter((item) => item !== field) : [...current, field];
      return MOVING_AVERAGES.map((item) => item.field).filter((item) => next.includes(item));
    });
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="grid min-h-screen lg:grid-cols-[248px_minmax(0,1fr)]">
        <StockListPanel currentSymbol={symbol} items={stockList} loading={listLoading} />

        <section className="min-w-0 border-l border-slate-200">
          <QuoteSummary
            bars={dailyBars}
            currentStock={currentStock}
            loading={loading}
            quote={quote}
            source={data?.source_status.source ?? "--"}
            status={data?.source_status.status ?? "disabled"}
            symbol={symbol}
          />

          <div className="grid gap-3 p-3 sm:p-4">
            {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{error}</p>}

            <article className="min-w-0 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <ChartTabs activeTab={activeChartTab} onChange={setActiveChartTab} />
              <div className="px-3 py-3 sm:px-4">
                <div className="mb-2 flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                  <div className="min-w-0">
                    <h2 className="text-sm font-black text-slate-950">{activeTabLabel}</h2>
                    <p className="mt-0.5 text-xs font-semibold text-slate-400">
                      {loading
                        ? "加载中"
                        : isChartTab
                          ? `${chartBars.length} 条数据 · ${movingAverageSummary(visibleMovingAverages)}`
                          : `${currentStock?.industry ?? "行业待补"} · ${currentStock?.symbol ?? symbol}`}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {isChartTab && (
                      <>
                        <MovingAverageControl
                          onToggle={toggleMovingAverage}
                          visibleMovingAverages={visibleMovingAverages}
                        />
                        <AnnotationControl active={showGsgfAnnotations} onToggle={() => setShowGsgfAnnotations((value) => !value)} />
                      </>
                    )}
                    <span className="inline-flex h-7 max-w-full items-center truncate rounded-md bg-slate-50 px-2.5 text-xs font-bold text-slate-600 ring-1 ring-slate-200">
                      {data?.source_status.source ?? "读取中"}
                    </span>
                  </div>
                </div>
                <div className="overflow-hidden rounded-md border border-slate-100">
                  {isChartTab ? (
                    <div className="h-[calc(100vh-236px)] min-h-[560px] bg-white">
                      <TickFlowKlineChart
                        annotations={activeChartTab === "day" ? data?.gsgf_annotations ?? [] : []}
                        bars={chartBars}
                        height={KLINE_CHART_HEIGHT}
                        movingAverages={visibleMovingAverages}
                        period={activeChartTab === "week" ? "weekly" : "daily"}
                        showGsgfAnnotations={activeChartTab === "day" && showGsgfAnnotations}
                        symbol={symbol}
                      />
                    </div>
                  ) : (
                    <StockDetailPanel
                      activeTab={activeChartTab}
                      bars={dailyBars}
                      candidate={currentCandidate}
                      currentStock={currentStock}
                      quote={quote}
                      research={research}
                      researchError={researchError}
                      researchLoading={researchLoading}
                      sameIndustryItems={stockList.filter(
                        (item) => item.industry && item.industry === currentStock?.industry,
                      )}
                    />
                  )}
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>
  );
}

function MovingAverageControl({
  onToggle,
  visibleMovingAverages,
}: {
  onToggle: (field: MovingAverageField) => void;
  visibleMovingAverages: MovingAverageField[];
}) {
  return (
    <div className="inline-flex min-h-[34px] items-center overflow-hidden rounded-md border border-slate-200 bg-white text-xs font-black">
      {MOVING_AVERAGES.map((item) => {
        const active = visibleMovingAverages.includes(item.field);
        return (
          <button
            aria-pressed={active}
            className={`min-h-[34px] border-r border-slate-200 px-3 transition last:border-r-0 ${
              active ? "bg-slate-950 text-white" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            }`}
            key={item.field}
            onClick={() => onToggle(item.field)}
            style={active ? undefined : { color: item.color }}
            title={`${active ? "隐藏" : "显示"}${item.label}`}
            type="button"
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

function AnnotationControl({ active, onToggle }: { active: boolean; onToggle: () => void }) {
  return (
    <button
      aria-pressed={active}
      className={`min-h-[34px] rounded-md border px-3 text-xs font-black transition ${
        active
          ? "border-slate-950 bg-slate-950 text-white"
          : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-900"
      }`}
      onClick={onToggle}
      title={`${active ? "隐藏" : "显示"}股是股非图表证据`}
      type="button"
    >
      GSGF 证据
    </button>
  );
}

function StockListPanel({
  currentSymbol,
  items,
  loading,
}: {
  currentSymbol: string;
  items: StockListItem[];
  loading: boolean;
}) {
  return (
    <aside className="hidden min-h-screen bg-white lg:block">
      <div className="sticky top-0 flex h-screen flex-col border-r border-slate-200">
        <div className="border-b border-slate-100 px-4 py-4">
          <a className="text-xs font-bold text-slate-500 transition hover:text-slate-950" href="/">
            返回选股工作台
          </a>
          <div className="mt-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">Candidates</p>
              <h2 className="mt-1 text-lg font-black text-slate-950">股票列表</h2>
            </div>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-black tabular-nums text-slate-600">
              {items.length}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {loading ? (
            <div className="rounded-lg bg-slate-50 px-3 py-8 text-center text-sm font-bold text-slate-500">
              读取股票列表...
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((item) => {
                const active = item.symbol === currentSymbol;
                return (
                  <a
                    className={`block rounded-lg border px-3 py-3 transition ${
                      active
                        ? "border-slate-950 bg-slate-100"
                        : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50"
                    }`}
                    href={`/stock/${encodeURIComponent(item.symbol)}`}
                    key={item.symbol}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-black text-slate-950">{item.name ?? item.symbol}</p>
                        <p className="mt-1 text-xs font-semibold text-slate-400">{item.symbol}</p>
                      </div>
                      {item.score !== null && (
                        <span className="rounded-md bg-red-50 px-2 py-1 text-xs font-black text-red-600 ring-1 ring-red-100">
                          {item.score.toFixed(1)}
                        </span>
                      )}
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-2 text-xs font-bold">
                      <span className="truncate text-slate-500">{item.industry ?? "行业待补"}</span>
                      <span className={statusTone(item.status)}>{statusLabel(item.status)}</span>
                    </div>
                  </a>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

function QuoteSummary({
  bars,
  currentStock,
  loading,
  quote,
  source,
  status,
  symbol,
}: {
  bars: KlineBar[];
  currentStock: StockListItem | null;
  loading: boolean;
  quote: QuoteSnapshot | null;
  source: string;
  status: string;
  symbol: string;
}) {
  const isUp = (quote?.change ?? 0) >= 0;
  const tone = isUp ? "text-red-500" : "text-emerald-600";

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="flex min-h-[112px] flex-col gap-3 px-4 py-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-black tracking-tight text-slate-950">{currentStock?.name ?? symbol}</h1>
            <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs font-black text-red-600 ring-1 ring-red-100">
              {marketPrefix(symbol)}
            </span>
            <span className="text-sm font-bold text-slate-500">{symbol}</span>
          </div>
          <div className="mt-2 flex items-end gap-3">
            <div className={`text-4xl font-black leading-none tabular-nums ${tone}`}>
              {quote ? formatPrice(quote.close) : "--"}
            </div>
            <div className={`pb-1 text-sm font-black tabular-nums ${tone}`}>
              {quote ? `${formatSigned(quote.change)} ${formatSigned(quote.changePct)}%` : loading ? "读取中" : "--"}
            </div>
          </div>
          <p className="mt-2 text-xs font-semibold text-slate-400">行情摘要 · {source} · {status}</p>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6 xl:min-w-0">
          <HeaderMetric label="开" value={quote ? formatPrice(quote.open) : "--"} />
          <HeaderMetric label="高" tone="text-red-500" value={quote ? formatPrice(quote.high) : "--"} />
          <HeaderMetric label="低" tone="text-emerald-600" value={quote ? formatPrice(quote.low) : "--"} />
          <HeaderMetric label="换" value="--" />
          <HeaderMetric label="量" value={quote ? formatVolume(quote.volume) : "--"} />
          <HeaderMetric label="K线" value={`${bars.length || "--"}`} />
        </div>
      </div>
    </header>
  );
}

function ChartTabs({ activeTab, onChange }: { activeTab: ChartTab; onChange: (tab: ChartTab) => void }) {
  return (
    <div className="overflow-x-auto border-b border-slate-200 bg-slate-50">
      <div className="grid min-w-[520px] grid-cols-6 text-center text-sm font-black text-slate-500">
        {CHART_TABS.map((item) => (
          <button
            aria-pressed={activeTab === item.key}
            className={`min-h-[42px] whitespace-nowrap border-b-2 px-3 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300 focus-visible:ring-inset ${
              activeTab === item.key
                ? "border-slate-950 bg-white text-slate-950"
                : "border-transparent hover:bg-white hover:text-slate-800"
            }`}
            key={item.key}
            onClick={() => onChange(item.key)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function StockDetailPanel({
  activeTab,
  bars,
  candidate,
  currentStock,
  quote,
  research,
  researchError,
  researchLoading,
  sameIndustryItems,
}: {
  activeTab: ChartTab;
  bars: KlineBar[];
  candidate: StrongStockScreeningItem | null;
  currentStock: StockListItem | null;
  quote: QuoteSnapshot | null;
  research: StockResearchResponse | null;
  researchError: string | null;
  researchLoading: boolean;
  sameIndustryItems: StockListItem[];
}) {
  const latest = bars[bars.length - 1] ?? null;

  if (activeTab === "info") {
    return (
      <div className="grid min-h-[520px] gap-3 bg-white p-4 md:grid-cols-3">
        <InfoCard label="行业" value={currentStock?.industry ?? "--"} />
        <InfoCard label="评分" value={currentStock?.score !== null && currentStock?.score !== undefined ? currentStock.score.toFixed(1) : "--"} />
        <InfoCard label="状态" value={statusLabel(currentStock?.status ?? null)} />
        <InfoCard label="最新价" tone="text-red-500" value={quote ? formatPrice(quote.close) : "--"} />
        <InfoCard label="成交量" value={quote ? formatVolume(quote.volume) : "--"} />
        <InfoCard label="K线数量" value={`${bars.length || "--"}`} />
        <InfoCard label="MA5" value={latest?.ma5 ? formatPrice(latest.ma5) : "--"} />
        <InfoCard label="MA20" value={latest?.ma20 ? formatPrice(latest.ma20) : "--"} />
        <InfoCard label="MA60" value={latest?.ma60 ? formatPrice(latest.ma60) : "--"} />
      </div>
    );
  }

  if (activeTab === "strategy") {
    const ruleHits = candidate?.rule_hits ?? [];
    const riskFlags = candidate?.risk_flags ?? [];
    return (
      <div className="min-h-[520px] space-y-4 bg-white p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <InfoCard label="候选状态" value={statusLabel(currentStock?.status ?? null)} />
          <InfoCard label="收盘 / MA5" value={latest ? comparePrice(latest.close, latest.ma5) : "--"} />
          <InfoCard label="收盘 / MA20" value={latest ? comparePrice(latest.close, latest.ma20) : "--"} />
          <InfoCard label="收盘 / MA60" value={latest ? comparePrice(latest.close, latest.ma60) : "--"} />
        </div>
        <TagSection emptyText="暂无命中规则" items={ruleHits} title="规则命中" tone="red" />
        <TagSection emptyText="暂无风险提示" items={riskFlags} title="风险提示" tone="amber" />
      </div>
    );
  }

  if (activeTab === "research") {
    return (
      <ResearchPanel
        candidate={candidate}
        currentStock={currentStock}
        error={researchError}
        loading={researchLoading}
        research={research}
      />
    );
  }

  return (
    <div className="min-h-[520px] space-y-4 bg-white p-4">
      <div className="grid gap-3 md:grid-cols-3">
        <InfoCard label="所属行业" value={currentStock?.industry ?? "--"} />
        <InfoCard label="板块强度" value={candidate?.industry_strength ?? "--"} />
        <InfoCard label="行业得分" value={candidate ? `${candidate.industry_score}` : "--"} />
      </div>
      <TagSection emptyText="暂无板块备注" items={candidate?.industry_notes ?? []} title="板块备注" tone="slate" />
      <div>
        <h3 className="mb-2 text-xs font-black text-slate-500">同板块候选</h3>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {sameIndustryItems.slice(0, 9).map((item) => (
            <a
              className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm font-bold text-slate-700 transition hover:border-slate-300 hover:bg-white"
              href={`/stock/${encodeURIComponent(item.symbol)}`}
              key={item.symbol}
            >
              <span className="truncate">{item.name ?? item.symbol}</span>
              <span className="ml-3 text-xs tabular-nums text-slate-400">{item.symbol}</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResearchPanel({
  candidate,
  currentStock,
  error,
  loading,
  research,
}: {
  candidate: StrongStockScreeningItem | null;
  currentStock: StockListItem | null;
  error: string | null;
  loading: boolean;
  research: StockResearchResponse | null;
}) {
  if (loading) {
    return (
      <div className="flex min-h-[520px] items-center justify-center bg-white text-sm font-bold text-slate-500">
        正在读取 iFinD 研究...
      </div>
    );
  }

  const sourceStatuses = research?.source_status ?? [];
  const failedSources = sourceStatuses.filter((item) => item.status !== "success");
  const sourceSummary =
    failedSources.length > 0
      ? failedSources.map((item) => `${item.source}: ${item.detail}`).join("；")
      : sourceStatuses.length > 0
        ? sourceStatuses.map((item) => item.source).join(" / ")
        : "iFinD 研究状态待读取";

  return (
    <div className="min-h-[520px] space-y-4 bg-white p-4">
      <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-sm font-black text-slate-950">iFinD 研究</h3>
            <p className="mt-1 text-xs font-bold text-slate-500">
              {error ?? sourceSummary}
            </p>
          </div>
          <span className="inline-flex w-fit rounded-md bg-white px-2.5 py-1 text-xs font-black text-slate-600 ring-1 ring-slate-200">
            不替代 TickFlow 行情
          </span>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <ResearchSection
          title="行业研究"
          payload={buildIndustryResearchPayload(research, currentStock)}
        />
        <ResearchSection title="财务指标" payload={buildFinancialResearchPayload(research)} />
        <ResearchSection title="估值指标" payload={buildValuationResearchPayload(research)} />
        <ResearchRecordsSection
          title="风险事件"
          emptyText="暂无 iFinD 风险事件"
          records={research?.events ?? []}
          tone="amber"
        />
        <ResearchRecordsSection
          title="公司公告"
          emptyText="暂无 iFinD 公司公告"
          records={research?.notices ?? []}
          tone="slate"
        />
        <ResearchRecordsSection
          title="新闻资讯"
          emptyText="暂无 iFinD 新闻资讯"
          records={research?.news ?? []}
          tone="slate"
        />
      </div>
    </div>
  );
}

function ResearchSection({ payload, title }: { payload: Record<string, unknown>; title: string }) {
  const entries = Object.entries(payload).filter(([, value]) => formatResearchValue(value) !== "--").slice(0, 10);
  return (
    <section className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <h3 className="mb-3 text-xs font-black text-slate-500">{title}</h3>
      {entries.length > 0 ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {entries.map(([key, value]) => (
            <div className="min-w-0 rounded-md bg-white px-3 py-2 ring-1 ring-slate-100" key={key}>
              <div className="truncate text-sm font-black text-slate-900">{formatResearchValue(value)}</div>
              <div className="mt-1 truncate text-xs font-bold text-slate-400">{key}</div>
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-slate-200 bg-white px-3 py-5 text-sm font-bold text-slate-400">
          暂无{title}数据
        </p>
      )}
    </section>
  );
}

function ResearchRecordsSection({
  emptyText,
  records,
  title,
  tone,
}: {
  emptyText: string;
  records: Array<Record<string, unknown>>;
  title: string;
  tone: "amber" | "slate";
}) {
  const markerClass = tone === "amber" ? "bg-amber-500" : "bg-slate-500";
  return (
    <section className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <h3 className="mb-3 text-xs font-black text-slate-500">{title}</h3>
      {records.length > 0 ? (
        <div className="space-y-2">
          {records.slice(0, 8).map((record, index) => (
            <div className="rounded-md bg-white px-3 py-3 ring-1 ring-slate-100" key={`${title}-${index}`}>
              <div className="flex items-start gap-2">
                <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${markerClass}`} />
                <div className="min-w-0">
                  <p className="line-clamp-2 text-sm font-black text-slate-900">{recordTitle(record)}</p>
                  <p className="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-slate-500">
                    {recordSummary(record)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-slate-200 bg-white px-3 py-5 text-sm font-bold text-slate-400">
          {emptyText}
        </p>
      )}
    </section>
  );
}

function buildIndustryResearchPayload(
  research: StockResearchResponse | null,
  currentStock: StockListItem | null,
): Record<string, unknown> {
  const sector = research?.sector ?? {};
  return {
    所属行业: currentStock?.industry ?? research?.profile?.["所属行业"] ?? "--",
    板块强度: candidateSectorLabel(sector["强度"]),
    板块得分: sector["得分"] ?? sector["score"] ?? "--",
    板块排名: sector["排名"] ?? sector["rank"] ?? "--",
    板块备注: sector["备注"] ?? sector["说明"] ?? sector["reason"] ?? "--",
    板块概览: sector["摘要"] ?? sector["概览"] ?? sector["summary"] ?? "--",
  };
}

function buildFinancialResearchPayload(research: StockResearchResponse | null): Record<string, unknown> {
  return research?.financials ?? {};
}

function buildValuationResearchPayload(research: StockResearchResponse | null): Record<string, unknown> {
  return research?.valuation ?? {};
}

function candidateSectorLabel(value: unknown): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return "--";
}

function InfoCard({ label, tone = "text-slate-950", value }: { label: string; tone?: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-100 bg-slate-50 px-3 py-3">
      <div className={`truncate text-base font-black tabular-nums ${tone}`}>{value}</div>
      <div className="mt-1 text-xs font-bold text-slate-400">{label}</div>
    </div>
  );
}

function TagSection({
  emptyText,
  items,
  title,
  tone,
}: {
  emptyText: string;
  items: string[];
  title: string;
  tone: "amber" | "red" | "slate";
}) {
  const toneClass =
    tone === "red"
      ? "bg-red-50 text-red-600 ring-red-100"
      : tone === "amber"
        ? "bg-amber-50 text-amber-700 ring-amber-100"
        : "bg-slate-100 text-slate-600 ring-slate-200";
  return (
    <div>
      <h3 className="mb-2 text-xs font-black text-slate-500">{title}</h3>
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span className={`rounded-md px-2.5 py-1 text-xs font-bold ring-1 ${toneClass}`} key={item}>
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="rounded-lg border border-dashed border-slate-200 px-3 py-4 text-sm font-bold text-slate-400">
          {emptyText}
        </p>
      )}
    </div>
  );
}

function HeaderMetric({ label, tone = "text-slate-950", value }: { label: string; tone?: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-slate-50 px-3 py-2 ring-1 ring-slate-100">
      <div className={`truncate text-sm font-black tabular-nums ${tone}`}>{value}</div>
      <div className="mt-1 text-xs font-bold text-slate-400">{label}</div>
    </div>
  );
}

function formatResearchValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "--";
  }
  if (typeof value === "string") {
    return value || "--";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString("zh-CN") : "--";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => formatResearchValue(item)).filter((item) => item !== "--").join(" / ") : "--";
  }
  if (typeof value === "object") {
    return "--";
  }
  return String(value);
}

function recordTitle(record: Record<string, unknown>): string {
  const candidates = [record.title, record.标题, record.name, record.名称, record.summary, record.摘要];
  for (const candidate of candidates) {
    const formatted = formatResearchValue(candidate);
    if (formatted !== "--") {
      return formatted;
    }
  }
  return "未命名记录";
}

function recordSummary(record: Record<string, unknown>): string {
  const preferredKeys = [
    "detail",
    "内容",
    "desc",
    "description",
    "summary",
    "摘要",
    "level",
    "sentiment",
    "sentiment_label",
    "source",
    "date",
    "date_time",
    "日期",
    "发布时间",
  ];
  const values = preferredKeys.map((key) => record[key]).filter((value) => value !== undefined && value !== null);
  if (values.length > 0) {
    return values.map((value) => formatResearchValue(value)).filter((item) => item !== "--").join(" · ");
  }
  const fallback = Object.entries(record)
    .filter(([key]) => !["title", "标题", "name", "名称", "summary", "摘要"].includes(key))
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${formatResearchValue(value)}`)
    .filter((item) => !item.endsWith(": --"));
  return fallback.length > 0 ? fallback.join(" · ") : "暂无摘要";
}

type QuoteSnapshot = {
  change: number;
  changePct: number;
  close: number;
  high: number;
  low: number;
  open: number;
  volume: number;
};

function buildQuote(bars: KlineBar[]): QuoteSnapshot | null {
  const latest = bars[bars.length - 1];
  if (!latest) {
    return null;
  }
  const previous = bars[bars.length - 2];
  const change = previous ? latest.close - previous.close : 0;
  const changePct = previous && previous.close !== 0 ? (change / previous.close) * 100 : 0;
  return {
    change,
    changePct,
    close: latest.close,
    high: latest.high,
    low: latest.low,
    open: latest.open,
    volume: latest.volume,
  };
}

function buildStockList(symbol: string, items: StrongStockScreeningItem[]): StockListItem[] {
  const rows: StockListItem[] = items.map((item) => ({
    industry: item.industry,
    name: item.name,
    score: item.score,
    status: item.status,
    symbol: item.symbol,
  }));
  if (!rows.some((item) => item.symbol === symbol)) {
    rows.unshift({
      industry: null,
      name: null,
      score: null,
      status: null,
      symbol,
    });
  }
  const seen = new Set<string>();
  return rows.filter((item) => {
    if (seen.has(item.symbol)) {
      return false;
    }
    seen.add(item.symbol);
    return true;
  });
}

function buildMovingAverageBars(bars: KlineBar[]): KlineBar[] {
  const closes = bars.map((bar) => bar.close);
  const averages = Object.fromEntries(
    MOVING_AVERAGES.map((item) => [item.field, movingAverage(closes, item.period)]),
  ) as Record<MovingAverageField, number[]>;
  return bars.map((bar, index) => ({
    ...bar,
    ma5: bar.ma5 ?? averages.ma5[index] ?? null,
    ma10: bar.ma10 ?? averages.ma10[index] ?? null,
    ma20: bar.ma20 ?? averages.ma20[index] ?? null,
    ma60: bar.ma60 ?? averages.ma60[index] ?? null,
  }));
}

function buildWeeklyBars(bars: KlineBar[]): KlineBar[] {
  const weekly: KlineBar[] = [];
  let currentKey = "";
  let current: KlineBar | null = null;
  for (const bar of bars) {
    const key = weekKey(bar.date);
    if (!current || key !== currentKey) {
      if (current) {
        weekly.push(current);
      }
      currentKey = key;
      current = {
        date: bar.date,
        open: bar.open,
        close: bar.close,
        high: bar.high,
        low: bar.low,
        volume: bar.volume,
        ma5: null,
        ma10: null,
        ma20: null,
        ma60: null,
      };
    } else {
      const currentWeek = current as KlineBar;
      current = {
        date: bar.date,
        open: currentWeek.open,
        close: bar.close,
        high: Math.max(currentWeek.high, bar.high),
        low: Math.min(currentWeek.low, bar.low),
        volume: currentWeek.volume + bar.volume,
        ma5: null,
        ma10: null,
        ma20: null,
        ma60: null,
      };
    }
  }
  if (current) {
    weekly.push(current);
  }
  return weekly;
}

function movingAverage(values: number[], windowSize: number): number[] {
  return values.map((_, index) => {
    const start = Math.max(0, index - windowSize + 1);
    const window = values.slice(start, index + 1);
    return window.reduce((sum, value) => sum + value, 0) / window.length;
  });
}

function weekKey(value: string): string {
  const digits = value.replace(/\D/g, "");
  const date =
    digits.length >= 8
      ? new Date(Date.UTC(Number(digits.slice(0, 4)), Number(digits.slice(4, 6)) - 1, Number(digits.slice(6, 8))))
      : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const day = date.getUTCDay() || 7;
  const monday = new Date(date);
  monday.setUTCDate(date.getUTCDate() - day + 1);
  return `${monday.getUTCFullYear()}-${monday.getUTCMonth() + 1}-${monday.getUTCDate()}`;
}

function movingAverageSummary(fields: MovingAverageField[]): string {
  if (fields.length === 0) {
    return "均线隐藏";
  }
  return MOVING_AVERAGES.filter((item) => fields.includes(item.field)).map((item) => item.label).join(" / ");
}

function comparePrice(price: number, target: number | null | undefined): string {
  if (!target) {
    return "--";
  }
  const pct = ((price - target) / target) * 100;
  return `${pct >= 0 ? "上方" : "下方"} ${Math.abs(pct).toFixed(2)}%`;
}

function statusLabel(status: StockListItem["status"]): string {
  if (status === "focus") {
    return "重点";
  }
  if (status === "wait_pullback") {
    return "等回踩";
  }
  if (status === "reduce_risk") {
    return "减仓";
  }
  if (status === "data_incomplete") {
    return "缺数据";
  }
  return "当前";
}

function statusTone(status: StockListItem["status"]): string {
  if (status === "focus") {
    return "text-red-600";
  }
  if (status === "wait_pullback") {
    return "text-sky-600";
  }
  if (status === "reduce_risk") {
    return "text-amber-600";
  }
  if (status === "data_incomplete") {
    return "text-slate-400";
  }
  return "text-slate-500";
}

function marketPrefix(symbol: string): string {
  if (symbol.endsWith(".SH")) {
    return "沪";
  }
  if (symbol.endsWith(".SZ")) {
    return "深";
  }
  if (symbol.endsWith(".BJ")) {
    return "北";
  }
  return "A";
}

function formatPrice(value: number): string {
  return value.toFixed(2);
}

function formatSigned(value: number): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}`;
}

function formatVolume(value: number): string {
  if (value >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(2)}亿`;
  }
  if (value >= 10_000) {
    return `${(value / 10_000).toFixed(1)}万`;
  }
  return `${Math.round(value)}`;
}
