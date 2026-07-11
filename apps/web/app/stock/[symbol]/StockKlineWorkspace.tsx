"use client";

import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { TickFlowKlineChart, type KlineChartDataSourceMode } from "../../../components/TickFlowKlineChart";
import { PageFrame } from "../../../components/workbench/PageFrame";
import { getLatestScreenRun, getStockKline, getStockQuote, getStockResearch } from "../../../lib/api";
import {
  buildKlineIndicatorState,
  KLINE_SUB_INDICATOR_OPTIONS,
  parseStoredKlineIndicatorState,
  updateKlineSubIndicator,
  updateKlineSubPaneCount,
  type KlineIndicatorState,
  type KlineSubIndicator,
  type KlineSubPaneCount,
} from "../../../lib/klineIndicatorLayout";
import { filterStockList, stockListStatusOptions, type StockListStatus } from "../../../lib/stockListFilter";
import { mergeStockIdentity, type StockIdentity } from "../../../lib/stockIdentity";
import {
  buildStockDetailHref,
  resolveStockDetailContext,
  type StockDetailContext,
  type StockDetailFrom,
} from "../../../lib/stockNavigation";
import type {
  GsgfChartAnnotation,
  KlineBar,
  StockKlineResponse,
  StockQuoteResponse,
  StockResearchResponse,
  StrongStockScreeningItem,
} from "../../../lib/types";

type ChartTab = "day" | "week" | "info" | "strategy" | "concept";
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
];

const KLINE_CHART_HEIGHT = 680;
const KLINE_INDICATOR_STORAGE_KEY = "strong-stock-screener:kline-indicator-layout";

const MOVING_AVERAGES: Array<{ color: string; field: MovingAverageField; label: string; period: number }> = [
  { color: "#1683ff", field: "ma5", label: "MA5", period: 5 },
  { color: "#f59e0b", field: "ma10", label: "MA10", period: 10 },
  { color: "#8b5cf6", field: "ma20", label: "MA20", period: 20 },
  { color: "#64748b", field: "ma60", label: "MA60", period: 60 },
];

const GSGF_MODEL_CONDITIONS = [
  "20日内有涨停，优先强势板块和高辨识度个股。",
  "趋势优先，股价在关键均线上方，尤其关注200日新高。",
  "K线红肥绿瘦，上涨放量饱满，缩量回踩不破趋势。",
  "放量上涨继续跟踪，放量滞涨或实体阴线降低评级。",
  "买绿不买红，卖红不卖绿；不冲高不卖，不跳水不买。",
  "5日线拐头向下、跌破均线、断板未修复时触发空仓纪律。",
];

export function StockKlineWorkspace({ symbol }: { symbol: string }) {
  const searchParams = useSearchParams();
  const [data, setData] = useState<StockKlineResponse | null>(null);
  const [realtimeQuote, setRealtimeQuote] = useState<StockQuoteResponse | null>(null);
  const [research, setResearch] = useState<StockResearchResponse | null>(null);
  const [screenItems, setScreenItems] = useState<StrongStockScreeningItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeChartTab, setActiveChartTab] = useState<ChartTab>("day");
  const [candidateListCollapsed, setCandidateListCollapsed] = useState(false);
  const [showGsgfAnnotations, setShowGsgfAnnotations] = useState(true);
  const chartDataSource: KlineChartDataSourceMode = "tickflow";
  const [visibleMovingAverages, setVisibleMovingAverages] = useState<MovingAverageField[]>([
    "ma5",
    "ma10",
    "ma20",
  ]);
  const [indicatorStateLoaded, setIndicatorStateLoaded] = useState(false);
  const [indicatorState, setIndicatorState] = useState<KlineIndicatorState>(() =>
    buildKlineIndicatorState({ paneCount: 1, subIndicators: [] }),
  );
  const shouldLoadResearch = activeChartTab === "info" || activeChartTab === "strategy" || activeChartTab === "concept";
  const stockDetailContext = useMemo(() => resolveStockDetailContext(searchParams), [searchParams]);

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
    setRealtimeQuote(null);
    getStockQuote(symbol)
      .then((response) => {
        if (!cancelled) {
          setRealtimeQuote(response);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRealtimeQuote(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  useEffect(() => {
    if (!shouldLoadResearch) {
      return;
    }
    if (research?.symbol === symbol) {
      return;
    }
    let cancelled = false;
    getStockResearch(symbol)
      .then((response) => {
        if (!cancelled) {
          setResearch(response);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setResearch(null);
        }
      })
    return () => {
      cancelled = true;
    };
  }, [research?.symbol, shouldLoadResearch, symbol]);

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

  useEffect(() => {
    setIndicatorState(parseStoredKlineIndicatorState(window.localStorage.getItem(KLINE_INDICATOR_STORAGE_KEY)));
    setIndicatorStateLoaded(true);
  }, []);

  useEffect(() => {
    if (indicatorStateLoaded) {
      window.localStorage.setItem(KLINE_INDICATOR_STORAGE_KEY, JSON.stringify(indicatorState));
    }
  }, [indicatorState, indicatorStateLoaded]);

  const bars = data?.bars ?? [];
  const dailyBars = useMemo(() => buildMovingAverageBars(bars), [bars]);
  const weeklyBars = useMemo(() => buildMovingAverageBars(buildWeeklyBars(bars)), [bars]);
  const chartBars = activeChartTab === "week" ? weeklyBars : dailyBars;
  const quoteIdentity = useMemo(
    () => ({ industry: realtimeQuote?.industry ?? null, name: realtimeQuote?.name ?? null }),
    [realtimeQuote?.industry, realtimeQuote?.name],
  );
  const stockList = useMemo(
    () => buildStockList(symbol, screenItems, stockDetailContext, quoteIdentity),
    [screenItems, stockDetailContext, symbol, quoteIdentity],
  );
  const currentStock = stockList.find((item) => item.symbol === symbol) ?? stockList[0] ?? null;
  const currentCandidate = useMemo(
    () => screenItems.find((item) => item.symbol === symbol) ?? null,
    [screenItems, symbol],
  );
  const quote = useMemo(() => buildQuote(dailyBars, realtimeQuote), [dailyBars, realtimeQuote]);
  const isChartTab = activeChartTab === "day" || activeChartTab === "week";
  const activeTabLabel = CHART_TABS.find((item) => item.key === activeChartTab)?.label ?? "日 K 线";
  const chartDataSourceLabel = data?.source_status.source ?? "TickFlow 读取中";
  const gsgfAnnotations = data?.gsgf_annotations ?? [];
  const annotationCount = gsgfAnnotations.length;
  const canShowGsgfAnnotations = activeChartTab === "day" && chartDataSource === "tickflow" && annotationCount > 0;

  function toggleMovingAverage(field: MovingAverageField) {
    setVisibleMovingAverages((current) => {
      const next = current.includes(field) ? current.filter((item) => item !== field) : [...current, field];
      return MOVING_AVERAGES.map((item) => item.field).filter((item) => next.includes(item));
    });
  }

  function changeSubPaneCount(paneCount: KlineSubPaneCount) {
    setIndicatorState((current) => updateKlineSubPaneCount(current, paneCount));
  }

  function changeSubIndicator(index: number, indicator: KlineSubIndicator) {
    setIndicatorState((current) => updateKlineSubIndicator(current, index, indicator));
  }

  return (
    <PageFrame
      actions={<Button href={stockDetailContext.returnHref}>{stockDetailContext.returnLabel}</Button>}
      context={currentStock?.industry ? `${currentStock.industry} · ${symbol}` : symbol}
      contentVariant="flush"
      title="个股 K 线"
    >
      <div
        className={`grid min-h-screen transition-[grid-template-columns] duration-200 ${
          candidateListCollapsed ? "lg:grid-cols-[168px_minmax(0,1fr)]" : "lg:grid-cols-[248px_minmax(0,1fr)]"
        }`}
      >
        <StockListPanel
          collapsed={candidateListCollapsed}
          currentSymbol={symbol}
          items={stockList}
          loading={listLoading}
          onToggleCollapsed={() => setCandidateListCollapsed((value) => !value)}
          sourceFrom={stockDetailContext.from}
        />

        <section className="min-w-0 border-l border-slate-200">
          <QuoteSummary
            bars={dailyBars}
            currentStock={currentStock}
            loading={loading}
            quote={quote}
            source={realtimeQuote?.source_status.source ?? data?.source_status.source ?? "--"}
            status={realtimeQuote?.source_status.status ?? data?.source_status.status ?? "disabled"}
            symbol={symbol}
          />

          <div className="grid gap-3 p-3 sm:p-4">
            {error && <Alert showIcon title={error} type="error" />}

            <Card className="border-[var(--app-border)] bg-[var(--app-surface)] min-w-0 overflow-hidden" styles={{ body: { padding: 0 } }}>
              <ChartTabs activeTab={activeChartTab} onChange={setActiveChartTab} />
              <div className="px-3 py-3 sm:px-4">
                <ChartControlBar
                  activeTabLabel={activeTabLabel}
                  chartDataSource={chartDataSource}
                  currentStock={currentStock}
                  dataSource={chartDataSourceLabel}
                  annotationCount={annotationCount}
                  canShowGsgfAnnotations={canShowGsgfAnnotations}
                  indicatorState={indicatorState}
                  isChartTab={isChartTab}
                  loading={loading}
                  movingAverageSummaryText={movingAverageSummary(visibleMovingAverages)}
                  onAnnotationToggle={() => setShowGsgfAnnotations((value) => !value)}
                  onMovingAverageToggle={toggleMovingAverage}
                  onSubIndicatorChange={changeSubIndicator}
                  onSubPaneCountChange={changeSubPaneCount}
                  showGsgfAnnotations={showGsgfAnnotations}
                  symbol={symbol}
                  chartBarCount={chartBars.length}
                  visibleMovingAverages={visibleMovingAverages}
                />
                <div className="overflow-hidden rounded-md border border-slate-100">
                  {isChartTab ? (
                    <div className="h-[calc(100vh-236px)] min-h-[560px] bg-white">
                      <GsgfEvidenceSummary
                        activeTab={activeChartTab}
                        annotations={gsgfAnnotations}
                        canShowGsgfAnnotations={canShowGsgfAnnotations}
                        chartDataSource={chartDataSource}
                        showGsgfAnnotations={showGsgfAnnotations}
                      />
                      <TickFlowKlineChart
                        annotations={
                          activeChartTab === "day" && chartDataSource === "tickflow"
                            ? gsgfAnnotations
                            : []
                        }
                        bars={chartBars}
                        dataSourceMode={chartDataSource}
                        height={KLINE_CHART_HEIGHT}
                        movingAverages={visibleMovingAverages}
                        period={activeChartTab === "week" ? "weekly" : "daily"}
                        showGsgfAnnotations={
                          canShowGsgfAnnotations && showGsgfAnnotations
                        }
                        subIndicators={indicatorState.subIndicators}
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
                      sameIndustryItems={stockList.filter(
                        (item) => item.industry && item.industry === currentStock?.industry,
                      )}
                      sourceFrom={stockDetailContext.from}
                    />
                  )}
                </div>
              </div>
            </Card>
          </div>
        </section>
      </div>
    </PageFrame>
  );
}

function SubIndicatorControl({
  indicatorState,
  onPaneCountChange,
  onSubIndicatorChange,
}: {
  indicatorState: KlineIndicatorState;
  onPaneCountChange: (paneCount: KlineSubPaneCount) => void;
  onSubIndicatorChange: (index: number, indicator: KlineSubIndicator) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented
        onChange={(value) => onPaneCountChange(value as KlineSubPaneCount)}
        options={[1, 2, 3].map((count) => ({ label: `${count}图`, value: count as KlineSubPaneCount }))}
        size="small"
        value={indicatorState.paneCount}
      />
      <div className="flex flex-wrap items-center gap-1.5">
        {indicatorState.subIndicators.map((indicator, index) => (
          <label className="inline-flex h-[34px] items-center gap-1.5 text-xs font-bold text-slate-500" key={`${index}-${indicator}`}>
            <span className="whitespace-nowrap">副图{index + 1}</span>
            <Select
              className="min-w-[96px]"
              onChange={(value) => onSubIndicatorChange(index, value)}
              options={KLINE_SUB_INDICATOR_OPTIONS}
              size="small"
              value={indicator}
            />
          </label>
        ))}
      </div>
    </div>
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
    <Space.Compact>
      {MOVING_AVERAGES.map((item) => {
        const active = visibleMovingAverages.includes(item.field);
        return (
          <Button
            key={item.field}
            onClick={() => onToggle(item.field)}
            size="small"
            style={active ? undefined : { color: item.color }}
            title={`${active ? "隐藏" : "显示"}${item.label}`}
            type={active ? "primary" : "default"}
          >
            {item.label}
          </Button>
        );
      })}
    </Space.Compact>
  );
}

function AnnotationControl({
  active,
  annotationCount,
  available,
  onToggle,
}: {
  active: boolean;
  annotationCount: number;
  available: boolean;
  onToggle: () => void;
}) {
  const label = available ? `${active ? "隐藏证据" : "显示证据"} (${annotationCount})` : `GSGF 证据 (${annotationCount})`;
  return (
    <Button
      aria-pressed={active}
      disabled={!available}
      onClick={onToggle}
      size="small"
      title={available ? `${active ? "隐藏" : "显示"}股是股非图表证据` : "GSGF 图表证据仅支持日K + TickFlow，且需要当前股票存在证据"}
      type={available && active ? "primary" : "default"}
    >
      {label}
    </Button>
  );
}

function GsgfEvidenceSummary({
  activeTab,
  annotations,
  canShowGsgfAnnotations,
  chartDataSource,
  showGsgfAnnotations,
}: {
  activeTab: ChartTab;
  annotations: GsgfChartAnnotation[];
  canShowGsgfAnnotations: boolean;
  chartDataSource: KlineChartDataSourceMode;
  showGsgfAnnotations: boolean;
}) {
  const isSupportedMode = activeTab === "day" && chartDataSource === "tickflow";
  const visibleAnnotations = canShowGsgfAnnotations && showGsgfAnnotations ? annotations.slice(0, 4) : [];

  if (!isSupportedMode) {
    return (
      <div className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-500">
        GSGF 图表证据仅支持日K + TickFlow
      </div>
    );
  }

  if (annotations.length === 0) {
    return (
      <div className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-500">
        暂无 GSGF 图表证据
      </div>
    );
  }

  if (!showGsgfAnnotations) {
    return (
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-500">
        <span>GSGF 图表证据已隐藏</span>
        <Tag className="m-0" color="default">{annotations.length} 条可显示</Tag>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-white px-3 py-2">
      <Typography.Text className="text-xs font-black text-slate-500">GSGF 证据</Typography.Text>
      {visibleAnnotations.map((item, index) => (
        <Tag className="m-0 max-w-full truncate" color={annotationTagColor(item.severity)} key={`${item.type}-${item.label}-${item.date ?? index}`}>
          {item.label} · {formatAnnotationDate(item.date ?? item.start_date ?? item.end_date)}
          {item.price !== null && item.price !== undefined ? ` · ${formatPrice(item.price)}` : ""}
        </Tag>
      ))}
      {annotations.length > visibleAnnotations.length && (
        <Typography.Text className="text-xs font-semibold text-slate-400">
          另 {annotations.length - visibleAnnotations.length} 条
        </Typography.Text>
      )}
    </div>
  );
}

function ChartControlBar({
  activeTabLabel,
  annotationCount,
  canShowGsgfAnnotations,
  chartBarCount,
  chartDataSource,
  currentStock,
  dataSource,
  indicatorState,
  isChartTab,
  loading,
  movingAverageSummaryText,
  onAnnotationToggle,
  onMovingAverageToggle,
  onSubIndicatorChange,
  onSubPaneCountChange,
  showGsgfAnnotations,
  symbol,
  visibleMovingAverages,
}: {
  activeTabLabel: string;
  annotationCount: number;
  canShowGsgfAnnotations: boolean;
  chartBarCount: number;
  chartDataSource: KlineChartDataSourceMode;
  currentStock: StockListItem | null;
  dataSource: string;
  indicatorState: KlineIndicatorState;
  isChartTab: boolean;
  loading: boolean;
  movingAverageSummaryText: string;
  onAnnotationToggle: () => void;
  onMovingAverageToggle: (field: MovingAverageField) => void;
  onSubIndicatorChange: (index: number, indicator: KlineSubIndicator) => void;
  onSubPaneCountChange: (paneCount: KlineSubPaneCount) => void;
  showGsgfAnnotations: boolean;
  symbol: string;
  visibleMovingAverages: MovingAverageField[];
}) {
  const summary = isChartTab
    ? loading
      ? "加载中"
      : `${chartBarCount} 条数据 · ${movingAverageSummaryText}`
    : `${currentStock?.industry ?? "行业待补"} · ${currentStock?.symbol ?? symbol}`;

  return (
    <div className="mb-2 flex flex-col gap-2 2xl:flex-row 2xl:items-center 2xl:justify-between">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        <Typography.Text className="text-sm font-black text-slate-950">{activeTabLabel}</Typography.Text>
        <Typography.Text className="text-xs font-semibold text-slate-500">{summary}</Typography.Text>
        <Tag className="m-0 max-w-full truncate">{dataSource}</Tag>
      </div>
      {isChartTab && (
        <div className="flex flex-wrap items-center gap-2 rounded-md bg-slate-50 px-2 py-2 ring-1 ring-slate-100">
          <div className="flex items-center gap-1.5">
            <Typography.Text className="whitespace-nowrap text-xs font-black text-slate-500">
              K线源
            </Typography.Text>
            <Tag className="m-0">TickFlow</Tag>
          </div>
          <MovingAverageControl
            onToggle={onMovingAverageToggle}
            visibleMovingAverages={visibleMovingAverages}
          />
          {chartDataSource === "tickflow" && (
            <AnnotationControl
              active={showGsgfAnnotations}
              annotationCount={annotationCount}
              available={canShowGsgfAnnotations}
              onToggle={onAnnotationToggle}
            />
          )}
          <SubIndicatorControl
            indicatorState={indicatorState}
            onPaneCountChange={onSubPaneCountChange}
            onSubIndicatorChange={onSubIndicatorChange}
          />
        </div>
      )}
    </div>
  );
}

function StockListPanel({
  collapsed,
  currentSymbol,
  items,
  loading,
  onToggleCollapsed,
  sourceFrom,
}: {
  collapsed: boolean;
  currentSymbol: string;
  items: StockListItem[];
  loading: boolean;
  onToggleCollapsed: () => void;
  sourceFrom: StockDetailFrom;
}) {
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<StockListStatus>("all");
  const visibleItems = useMemo(
    () => filterStockList(items, searchText, statusFilter),
    [items, searchText, statusFilter],
  );

  return (
    <aside className="hidden min-h-screen bg-white lg:block">
      <div className="sticky top-0 flex h-screen flex-col border-r border-slate-200">
        <div className={`${collapsed ? "px-3 py-3" : "px-4 py-4"} border-b border-slate-100`}>
          <div className="flex items-center justify-between gap-2">
            <Typography.Text className="truncate text-xs font-black text-slate-500">
              {collapsed ? "紧凑列表" : "股票列表"}
            </Typography.Text>
            <Button
              aria-label={collapsed ? "展开股票列表" : "收起股票列表"}
              onClick={onToggleCollapsed}
              size="small"
              title={collapsed ? "展开股票列表" : "收起股票列表"}
            >
              {collapsed ? "展开" : "收起"}
            </Button>
          </div>
          <div className={collapsed ? "mt-3 flex items-center justify-between gap-2" : "mt-5 flex items-center justify-between gap-3"}>
            {collapsed ? (
              <>
                <span className="truncate text-xs font-semibold text-slate-400">股票列表</span>
                <Tag className="m-0">{visibleItems.length}/{items.length}</Tag>
              </>
            ) : (
              <>
                <div>
                  <Typography.Text className="text-xs font-semibold uppercase text-slate-400">Candidates</Typography.Text>
                  <Typography.Title className="mt-1 text-lg font-black text-slate-950" level={2}>
                    股票列表
                  </Typography.Title>
                </div>
                <Tag className="m-0">{visibleItems.length}/{items.length}</Tag>
              </>
            )}
          </div>
          <div className="mt-3 space-y-2">
            <Input
              allowClear
              aria-label="搜索候选股票"
              onChange={(event) => setSearchText(event.target.value)}
              placeholder={collapsed ? "搜索" : "名称 / 代码 / 首字母"}
              size="small"
              value={searchText}
            />
            <Select
              aria-label="候选状态筛选"
              className="w-full"
              onChange={(value) => setStatusFilter(value)}
              options={stockListStatusOptions}
              size="small"
              value={statusFilter}
            />
          </div>
        </div>

        <div className={`flex-1 overflow-y-auto ${collapsed ? "p-2" : "p-3"}`}>
          {loading ? (
            <div className={`rounded-lg bg-slate-50 text-center ${collapsed ? "px-2 py-5" : "px-3 py-8"}`}>
              <Spin size="small" />
              <p className={`${collapsed ? "mt-2 text-xs" : "mt-3 text-sm"} font-bold text-slate-500`}>
                读取股票列表...
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {visibleItems.length === 0 && (
                <Empty description="没有匹配股票" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
              {visibleItems.map((item) => {
                const active = item.symbol === currentSymbol;
                return (
                  <a
                    className={`block rounded-lg border transition ${
                      active
                        ? "border-slate-950 bg-slate-100"
                        : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50"
                    } ${collapsed ? "px-2 py-2" : "px-3 py-3"}`}
                    href={buildStockDetailHref(item.symbol, {
                      from: sourceFrom,
                      industry: item.industry,
                      name: item.name,
                    })}
                    key={item.symbol}
                    title={`${item.name ?? item.symbol} ${item.symbol}`}
                  >
                    {collapsed ? (
                      <div className="min-w-0">
                        <p className="truncate text-sm font-black text-slate-950">{item.name ?? item.symbol}</p>
                        <p className="mt-0.5 truncate text-xs font-semibold tabular-nums text-slate-400">
                          {item.symbol}
                        </p>
                      </div>
                    ) : (
                      <>
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
                          <Tag className="m-0" color={statusColor(item.status)}>
                            {statusLabel(item.status)}
                          </Tag>
                        </div>
                      </>
                    )}
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
  const tone = isUp ? "text-red-500" : "market-green-text";

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="flex min-h-[112px] flex-col gap-3 px-4 py-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Typography.Title className="mb-0 text-xl font-black tracking-tight text-slate-950" level={2}>
              {currentStock?.name ?? symbol}
            </Typography.Title>
            <Tag className="m-0" color="red">{marketPrefix(symbol)}</Tag>
            {currentStock?.industry && <Tag className="m-0">{currentStock.industry}</Tag>}
            <Typography.Text className="text-sm font-bold text-slate-500">{symbol}</Typography.Text>
          </div>
          <div className="mt-2 flex items-end gap-3">
            <div className={`text-4xl font-black leading-none tabular-nums ${tone}`}>
              {quote ? formatPrice(quote.close) : "--"}
            </div>
            <div className={`pb-1 text-sm font-black tabular-nums ${tone}`}>
              {quote ? `${formatSigned(quote.change)} ${formatSigned(quote.changePct)}%` : loading ? "读取中" : "--"}
            </div>
          </div>
          <Typography.Text className="mt-2 block text-xs font-semibold text-slate-400">
            行情摘要 · {source} · {formatSourceStatus(status)}
          </Typography.Text>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6 xl:min-w-0">
          <HeaderMetric label="开" value={quote ? formatPrice(quote.open) : "--"} />
          <HeaderMetric label="高" tone="text-red-500" value={quote ? formatPrice(quote.high) : "--"} />
          <HeaderMetric label="低" tone="market-green-text" value={quote ? formatPrice(quote.low) : "--"} />
          <HeaderMetric label="换" value={formatTurnoverRate(quote?.turnoverRate ?? null)} />
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
      <div className="grid min-w-[520px] grid-cols-5 p-2 text-center text-sm font-black text-slate-500">
        <Segmented
          block
          className="col-span-5"
          onChange={(value) => onChange(value as ChartTab)}
          options={CHART_TABS.map((item) => ({ label: item.label, value: item.key }))}
          value={activeTab}
        />
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
  sameIndustryItems,
  sourceFrom,
}: {
  activeTab: ChartTab;
  bars: KlineBar[];
  candidate: StrongStockScreeningItem | null;
  currentStock: StockListItem | null;
  quote: QuoteSnapshot | null;
  research: StockResearchResponse | null;
  sameIndustryItems: StockListItem[];
  sourceFrom: StockDetailFrom;
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
        <InfoCard label="总市值" value={formatMarketCapCny(quote?.totalMarketCapCny ?? null) || pickResearchValue(research, ["总市值", "总市值(元)", "总市值（元）", "总市值(亿元)", "总市值（亿元）", "market_cap", "market_capitalization"])} />
        <InfoCard label="动态市盈率" value={formatValuationRatio(quote?.peTtm ?? null) || pickResearchValue(research, ["动态市盈率", "市盈率动态", "市盈率(动态)", "市盈率（动态）", "PE动态", "动态PE", "市盈率TTM", "PE TTM", "PE_TTM", "pe_ttm"])} />
        <InfoCard label="静态市盈率" value={formatValuationRatio(quote?.peStatic ?? null) || pickResearchValue(research, ["静态市盈率", "市盈率静态", "市盈率(静态)", "市盈率（静态）", "PE静态", "静态PE", "市盈率", "PE", "pe"])} />
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
        <ModelConditionsSection />
        <TagSection emptyText="暂无命中规则" items={ruleHits} title="规则命中" tone="red" />
        <TagSection emptyText="暂无风险提示" items={riskFlags} title="风险提示" tone="amber" />
      </div>
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
              href={buildStockDetailHref(item.symbol, {
                from: sourceFrom,
                industry: item.industry,
                name: item.name,
              })}
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

function ModelConditionsSection() {
  return (
    <div>
      <h3 className="mb-2 text-xs font-black text-slate-500">股是股非模型选股条件</h3>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {GSGF_MODEL_CONDITIONS.map((item, index) => (
          <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm font-bold leading-6 text-slate-700" key={item}>
            <span className="mr-2 font-black tabular-nums text-slate-400">{index + 1}.</span>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function pickResearchValue(research: StockResearchResponse | null, keys: string[]): string {
  const payloads = [research?.valuation, research?.financials, research?.profile];
  for (const payload of payloads) {
    if (!payload) {
      continue;
    }
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(payload, key)) {
        const value = formatResearchValue(payload[key]);
        if (value !== "--") {
          return value;
        }
      }
    }
  }
  return "--";
}

function InfoCard({ label, tone = "text-slate-950", value }: { label: string; tone?: string; value: string }) {
  return (
    <Card className="border-[var(--app-border)] bg-[var(--app-surface)]" size="small">
      <Statistic
        styles={{ content: { fontSize: 16, fontWeight: 900 } }}
        title={<span className="text-xs font-bold text-slate-400">{label}</span>}
        value={value}
        valueRender={() => <span className={`truncate tabular-nums ${tone}`}>{value}</span>}
      />
    </Card>
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
  const color = tone === "red" ? "red" : tone === "amber" ? "orange" : "default";
  return (
    <div>
      <h3 className="mb-2 text-xs font-black text-slate-500">{title}</h3>
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <Tag className="m-0" color={color} key={item}>
              {item}
            </Tag>
          ))}
        </div>
      ) : (
        <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </div>
  );
}

function HeaderMetric({ label, tone = "text-slate-950", value }: { label: string; tone?: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-slate-50 px-3 py-2 ring-1 ring-slate-100">
      <Statistic
        styles={{ content: { fontSize: 14, fontWeight: 900, lineHeight: "18px" } }}
        title={<span className="text-xs font-bold text-slate-400">{label}</span>}
        value={value}
        valueRender={() => <span className={`truncate tabular-nums ${tone}`}>{value}</span>}
      />
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

function annotationTagColor(severity: GsgfChartAnnotation["severity"]): string {
  if (severity === "positive") {
    return "red";
  }
  if (severity === "warning") {
    return "orange";
  }
  if (severity === "danger") {
    return "green";
  }
  return "default";
}

function formatAnnotationDate(value: string | null): string {
  if (!value) {
    return "日期待补";
  }
  const digits = value.replace(/\D/g, "");
  if (digits.length >= 8) {
    return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
  }
  return value;
}

type QuoteSnapshot = {
  change: number;
  changePct: number;
  close: number;
  circulatingMarketCapCny: number | null;
  high: number;
  low: number;
  open: number;
  pb: number | null;
  peStatic: number | null;
  peTtm: number | null;
  totalMarketCapCny: number | null;
  turnoverRate: number | null;
  volume: number;
};

function buildQuote(bars: KlineBar[], realtimeQuote: StockQuoteResponse | null): QuoteSnapshot | null {
  const latest = bars[bars.length - 1];
  if (!latest) {
    if (!realtimeQuote?.last_price) {
      return null;
    }
    const change = realtimeQuote.prev_close ? realtimeQuote.last_price - realtimeQuote.prev_close : 0;
    return {
      change,
      changePct: realtimeQuote.pct_change ?? (realtimeQuote.prev_close ? (change / realtimeQuote.prev_close) * 100 : 0),
      close: realtimeQuote.last_price,
      high: realtimeQuote.high_price ?? realtimeQuote.last_price,
      low: realtimeQuote.low_price ?? realtimeQuote.last_price,
      open: realtimeQuote.open_price ?? realtimeQuote.last_price,
      circulatingMarketCapCny: realtimeQuote.circulating_market_cap_cny,
      pb: realtimeQuote.pb,
      peStatic: realtimeQuote.pe_static,
      peTtm: realtimeQuote.pe_ttm,
      totalMarketCapCny: realtimeQuote.total_market_cap_cny,
      turnoverRate: realtimeQuote.turnover_rate,
      volume: realtimeQuote.volume ?? 0,
    };
  }
  const previous = bars[bars.length - 2];
  const close = realtimeQuote?.last_price ?? latest.close;
  const open = realtimeQuote?.open_price ?? latest.open;
  const high = realtimeQuote?.high_price ?? latest.high;
  const low = realtimeQuote?.low_price ?? latest.low;
  const previousClose = realtimeQuote?.prev_close ?? previous?.close ?? null;
  const change = previousClose ? close - previousClose : previous ? latest.close - previous.close : 0;
  const changePct = realtimeQuote?.pct_change ?? (previousClose ? (change / previousClose) * 100 : 0);
  return {
    change,
    changePct,
    close,
    high,
    low,
    open,
    circulatingMarketCapCny: realtimeQuote?.circulating_market_cap_cny ?? null,
    pb: realtimeQuote?.pb ?? null,
    peStatic: realtimeQuote?.pe_static ?? null,
    peTtm: realtimeQuote?.pe_ttm ?? null,
    totalMarketCapCny: realtimeQuote?.total_market_cap_cny ?? null,
    turnoverRate: realtimeQuote?.turnover_rate ?? null,
    volume: realtimeQuote?.volume ?? latest.volume,
  };
}

function buildStockList(
  symbol: string,
  items: StrongStockScreeningItem[],
  context: StockDetailContext,
  quoteIdentity: StockIdentity,
): StockListItem[] {
  const rows: StockListItem[] = items.map((item) => {
    const identity = item.symbol === symbol ? mergeStockIdentity(item, context, quoteIdentity) : mergeStockIdentity(item);
    return {
      industry: identity.industry,
      name: identity.name,
      score: item.score,
      status: item.status,
      symbol: item.symbol,
    };
  });
  if (!rows.some((item) => item.symbol === symbol)) {
    const identity = mergeStockIdentity(context, quoteIdentity);
    rows.unshift({
      industry: identity.industry,
      name: identity.name,
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

function statusColor(status: StockListItem["status"]): string {
  if (status === "focus") {
    return "red";
  }
  if (status === "wait_pullback") {
    return "blue";
  }
  if (status === "reduce_risk") {
    return "orange";
  }
  return "default";
}

function formatSourceStatus(status: string): string {
  if (status === "success") {
    return "可用";
  }
  if (status === "failed" || status === "error") {
    return "异常";
  }
  if (status === "missing_key") {
    return "缺Key";
  }
  if (status === "disabled") {
    return "未启用";
  }
  return status || "未知";
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

function formatTurnoverRate(value: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(2)}%`;
}

function formatMarketCapCny(value: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value <= 0) {
    return "";
  }
  if (value >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(2)}亿`;
  }
  if (value >= 10_000) {
    return `${(value / 10_000).toFixed(1)}万`;
  }
  return `${Math.round(value)}`;
}

function formatValuationRatio(value: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value <= 0) {
    return "";
  }
  return value.toFixed(2).replace(/\.?0+$/, "");
}
