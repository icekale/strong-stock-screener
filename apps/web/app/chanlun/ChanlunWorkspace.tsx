"use client";

import { AutoComplete, Alert, Button, Checkbox, Empty, Input, Skeleton, Space, Tag, Typography } from "antd";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { TickFlowKlineChart } from "../../components/TickFlowKlineChart";
import { PageFrame } from "../../components/workbench/PageFrame";
import {
  createChanlunBackfillJob,
  getChanlunAnalysis,
  getChanlunBackfillJob,
  getChanlunWorkspace,
  searchChanlunSymbols,
} from "../../lib/api";
import type {
  BackgroundJobState,
  ChanlunAvailability,
  ChanlunLayerKey,
  ChanlunPeriod,
  ChanlunWorkspaceResponse,
  SourceStatusValue,
} from "../../lib/types";
import {
  CHANLUN_PERIODS,
  describeChanlunAvailability,
  isChanlunAnalysisCurrent,
  isChanlunSymbolCurrent,
  isChanlunWorkspaceCurrent,
  normalizeChanlunSymbol,
  toChartPeriod,
  type ChanlunAvailabilityDescription,
} from "./chanlunWorkspaceHelpers";

const PERIOD_LABELS: Record<ChanlunPeriod, string> = {
  "1d": "日线",
  "60m": "60分",
  "30m": "30分",
  "5m": "5分",
};

const LAYER_LABELS: Record<ChanlunLayerKey, string> = {
  fractals: "分型",
  strokes: "笔",
  segments: "线段",
  zones: "中枢",
};

export function ChanlunWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const querySymbol = normalizeChanlunSymbol(searchParams.get("symbol") ?? "");
  const [symbol, setSymbol] = useState(querySymbol);
  const [symbolInput, setSymbolInput] = useState(querySymbol ?? "");
  const [symbolOptions, setSymbolOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [workspace, setWorkspace] = useState<ChanlunWorkspaceResponse | null>(null);
  const [analysis, setAnalysis] = useState<ChanlunWorkspaceResponse["analysis"] | null>(null);
  const [period, setPeriod] = useState<ChanlunPeriod>("1d");
  const [layers, setLayers] = useState<Record<ChanlunLayerKey, boolean>>({
    fractals: false,
    strokes: false,
    segments: true,
    zones: true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [backfillJob, setBackfillJob] = useState<BackgroundJobState | null>(null);
  const [backfillError, setBackfillError] = useState<string | null>(null);
  const [backfillLoading, setBackfillLoading] = useState(false);
  const requestId = useRef(0);
  const searchId = useRef(0);
  const mounted = useRef(true);
  const selectedSymbol = useRef<string | null>(symbol);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    selectedSymbol.current = symbol;
  }, [symbol]);

  useEffect(() => {
    if (querySymbol && querySymbol !== symbol) {
      setSymbol(querySymbol);
      setSymbolInput(querySymbol);
      setPeriod("1d");
    }
  }, [querySymbol, symbol]);

  const loadWorkspace = useCallback(async (requestedSymbol: string) => {
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;
    setLoading(true);
    setError(null);
    try {
      const nextWorkspace = await getChanlunWorkspace(requestedSymbol);
      if (!mounted.current || requestId.current !== currentRequest || !isChanlunSymbolCurrent(requestedSymbol, selectedSymbol.current)) {
        return;
      }
      setWorkspace(nextWorkspace);
      setAnalysis(nextWorkspace.analysis);
    } catch (err) {
      if (mounted.current && requestId.current === currentRequest && isChanlunSymbolCurrent(requestedSymbol, selectedSymbol.current)) {
        setError(err instanceof Error ? err.message : "读取缠论工作台失败");
      }
    } finally {
      if (mounted.current && requestId.current === currentRequest && isChanlunSymbolCurrent(requestedSymbol, selectedSymbol.current)) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (symbol) {
      void loadWorkspace(symbol);
    }
  }, [loadWorkspace, symbol]);

  useEffect(() => {
    if (!symbol || !workspace || workspace.symbol !== symbol || analysis?.period === period) {
      return;
    }
    let active = true;
    void getChanlunAnalysis(symbol, { period }).then(
      (nextAnalysis) => {
        if (active) {
          setAnalysis(nextAnalysis);
        }
      },
      (err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : "读取缠论周期分析失败");
        }
      },
    );
    return () => {
      active = false;
    };
  }, [analysis?.period, period, symbol, workspace]);

  async function handleSymbolSearch(value: string) {
    const query = value.trim();
    const currentSearch = searchId.current + 1;
    searchId.current = currentSearch;
    setSearchError(null);
    if (!query) {
      setSymbolOptions([]);
      return;
    }
    try {
      const result = await searchChanlunSymbols(query, { limit: 12 });
      if (searchId.current === currentSearch) {
        setSymbolOptions(result.items.map((item) => ({ value: item.symbol, label: `${item.name} ${item.symbol}` })));
      }
    } catch (err) {
      if (searchId.current === currentSearch) {
        setSymbolOptions([]);
        setSearchError(err instanceof Error ? err.message : "股票搜索暂不可用，可直接输入代码");
      }
    }
  }

  function selectSymbol(value: string) {
    const normalized = normalizeChanlunSymbol(value);
    if (!normalized) {
      setError("请输入六位股票代码，例如 600000.SH");
      return;
    }
    setError(null);
    setSymbolInput(normalized);
    setPeriod("1d");
    setSymbol(normalized);
    router.replace(`/chanlun?symbol=${encodeURIComponent(normalized)}`, { scroll: false });
  }

  async function pollBackfillJob(requestedSymbol: string, initialJob: BackgroundJobState) {
    let job = initialJob;
    while (job.status === "pending" || job.status === "running") {
      await sleep(1000);
      job = await getChanlunBackfillJob(requestedSymbol, job.job_id);
      if (!mounted.current || !isChanlunSymbolCurrent(requestedSymbol, selectedSymbol.current)) {
        return;
      }
      setBackfillJob(job);
    }
    if (mounted.current && job.status === "success" && isChanlunSymbolCurrent(requestedSymbol, selectedSymbol.current)) {
      await loadWorkspace(requestedSymbol);
    }
  }

  async function startBackfill() {
    if (!symbol || backfillLoading) {
      return;
    }
    setBackfillLoading(true);
    setBackfillError(null);
    try {
      const job = await createChanlunBackfillJob(symbol);
      if (!mounted.current) {
        return;
      }
      setBackfillJob(job);
      await pollBackfillJob(symbol, job);
    } catch (err) {
      if (mounted.current) {
        setBackfillError(err instanceof Error ? err.message : "启动分钟历史补齐失败");
      }
    } finally {
      if (mounted.current) {
        setBackfillLoading(false);
      }
    }
  }

  const activeAnalysis = isChanlunAnalysisCurrent(analysis, symbol, period) ? analysis : null;
  const activeWorkspace = isChanlunWorkspaceCurrent(workspace, symbol) ? workspace : null;
  const activePeriodSummary = activeWorkspace?.periods.find((item) => item.period === period) ?? null;
  const availability = activeAnalysis?.availability ?? activePeriodSummary?.availability ?? null;
  const isIntradayBackfillState = period !== "1d" && (availability === "insufficient_bars" || availability === "backfilling");
  const backfillActive = backfillLoading || backfillJob?.status === "pending" || backfillJob?.status === "running";

  return (
    <PageFrame
      actions={
        symbol ? (
          <Button disabled={loading} icon={<ReloadOutlined />} loading={loading} onClick={() => void loadWorkspace(symbol)}>
            刷新
          </Button>
        ) : undefined
      }
      context="多周期结构研究"
      status={availability ? <AvailabilityTag availability={availability} /> : undefined}
      title="缠论工作台"
    >
      <div className="space-y-4">
        <section className="compact-panel p-4">
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              selectSymbol(symbolInput);
            }}
          >
            <label className="grid min-w-[240px] flex-1 gap-1 text-sm font-semibold text-[var(--app-ink)]">
              股票代码或名称
              <AutoComplete
                aria-label="搜索股票代码或名称"
                onSearch={(value) => void handleSymbolSearch(value)}
                onSelect={selectSymbol}
                options={symbolOptions}
                value={symbolInput}
              >
                <Input
                  aria-describedby={searchError ? "chanlun-search-error" : undefined}
                  onChange={(event) => setSymbolInput(event.target.value)}
                  placeholder="输入名称或 600000.SH"
                />
              </AutoComplete>
            </label>
            <Button htmlType="submit" icon={<SearchOutlined />} type="primary">
              分析
            </Button>
          </form>
          {searchError ? <p className="mt-2 text-xs text-[var(--app-muted)]" id="chanlun-search-error">{searchError}</p> : null}
        </section>

        {!symbol ? (
          <section className="compact-panel p-8">
            <Empty description="输入股票代码或名称以查看多周期结构" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </section>
        ) : null}

        {symbol && !workspace && loading ? (
          <section className="compact-panel p-4">
            <Skeleton active paragraph={{ rows: 10 }} />
          </section>
        ) : null}

        {error ? <Alert message={error} showIcon type="error" /> : null}

        {activeWorkspace ? (
          <>
            <section aria-label="多周期结构状态" className="chanlun-status-rail">
              {CHANLUN_PERIODS.map((item) => {
                const summary = activeWorkspace.periods.find((candidate) => candidate.period === item);
                const description = summary ? describeChanlunAvailability(summary.availability) : null;
                return (
                  <button
                    aria-pressed={period === item}
                    className={period === item ? "chanlun-status-rail__item is-active" : "chanlun-status-rail__item"}
                    key={item}
                    onClick={() => setPeriod(item)}
                    type="button"
                  >
                    <span className="font-semibold text-[var(--app-ink)]">{PERIOD_LABELS[item]}</span>
                    <span>{formatDirection(summary?.direction)}</span>
                    <span>{summary?.latest_zone ? formatZoneStatus(summary.latest_zone.status) : "暂无中枢"}</span>
                    <span>{description?.text ?? "等待数据"}</span>
                    <span>{formatTime(summary?.last_closed_bar_at)}</span>
                  </button>
                );
              })}
            </section>

            {isIntradayBackfillState ? (
              <section className="app-inset flex flex-wrap items-center justify-between gap-3 p-3">
                <div className="text-sm">
                  <strong className="text-[var(--app-ink)]">{availability === "backfilling" ? "分钟历史正在补齐" : "分钟历史不足"}</strong>
                  {backfillJob ? <span className="ml-2">{backfillJob.message}</span> : null}
                </div>
                <Button disabled={backfillActive} loading={backfillActive} onClick={() => void startBackfill()} type="primary">
                  补齐分钟历史
                </Button>
                {backfillError ? <span className="w-full text-xs text-[var(--market-red-text)]">{backfillError}</span> : null}
              </section>
            ) : null}

            <section className="compact-panel min-w-0">
              <div className="compact-panel__header flex-wrap py-2">
                <Typography.Text strong>{PERIOD_LABELS[period]} K线与结构</Typography.Text>
                <Space size={12} wrap>
                  {(Object.keys(LAYER_LABELS) as ChanlunLayerKey[]).map((key) => (
                    <Checkbox
                      checked={layers[key]}
                      key={key}
                      onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))}
                    >
                      {LAYER_LABELS[key]}
                    </Checkbox>
                  ))}
                </Space>
              </div>
              <div className="chanlun-status-rail__chart">
                {activeAnalysis ? (
                  <TickFlowKlineChart
                    annotations={[]}
                    bars={activeAnalysis.bars}
                    chanlun={activeAnalysis}
                    chanlunLayers={layers}
                    height={520}
                    movingAverages={["ma5", "ma10", "ma20", "ma60"]}
                    period={toChartPeriod(period)}
                    showGsgfAnnotations={false}
                    subIndicators={[]}
                    symbol={activeAnalysis.symbol}
                  />
                ) : (
                  <Empty description="正在读取所选周期结构" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </div>
            </section>

            <section className="compact-panel">
              <div className="compact-panel__header">
                <Typography.Text strong>数据源状态</Typography.Text>
              </div>
              <div className="compact-panel__body flex flex-wrap gap-2">
                {activeAnalysis?.source_status.length ? (
                  activeAnalysis.source_status.map((item) => (
                    <Tag color={sourceStatusColor(item.status)} key={`${item.source}-${item.detail}`}>
                      {item.source} · {sourceStatusLabel(item.status)}
                    </Tag>
                  ))
                ) : (
                  <Typography.Text type="secondary">暂无数据源状态</Typography.Text>
                )}
              </div>
            </section>
          </>
        ) : null}
      </div>
    </PageFrame>
  );
}

function AvailabilityTag({ availability }: { availability: ChanlunAvailability }) {
  const description = describeChanlunAvailability(availability);
  return <Tag color={availabilityTagColor(description.tone)}>{description.text}</Tag>;
}

function availabilityTagColor(tone: ChanlunAvailabilityDescription["tone"]): string {
  return { success: "green", warning: "gold", neutral: "default", error: "red" }[tone];
}

function sourceStatusColor(status: SourceStatusValue): string {
  return { success: "green", stale: "gold", disabled: "default", missing_key: "orange", failed: "red" }[status];
}

function sourceStatusLabel(status: SourceStatusValue): string {
  return { success: "正常", stale: "过期", disabled: "未启用", missing_key: "缺配置", failed: "失败" }[status];
}

function formatDirection(direction: ChanlunWorkspaceResponse["periods"][number]["direction"] | undefined): string {
  return direction === "up" ? "向上" : direction === "down" ? "向下" : "方向待定";
}

function formatZoneStatus(status: string): string {
  return status === "final" ? "中枢已完成" : status === "confirmed" ? "中枢已确认" : "中枢观察中";
}

function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "未确认";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
