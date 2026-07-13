"use client";

import { AutoComplete, Alert, Button, Checkbox, Empty, Input, Skeleton, Space, Tag, Typography } from "antd";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { TickFlowKlineChart } from "../../components/TickFlowKlineChart";
import { PageFrame } from "../../components/workbench/PageFrame";
import {
  approveChanlunPaperOrder,
  cancelChanlunPaperOrder,
  createChanlunBackfillJob,
  createChanlunPaperOrderDraft,
  fillChanlunPaperOrder,
  getChanlunAnalysis,
  getChanlunAlerts,
  getChanlunBackfillJob,
  getChanlunBacktest,
  getChanlunPaperAccount,
  getChanlunReplay,
  getChanlunWorkspace,
  refreshChanlunAlerts,
  searchChanlunSymbols,
} from "../../lib/api";
import type {
  BackgroundJobState,
  ChanlunAlertListResponse,
  ChanlunAvailability,
  ChanlunBacktestResponse,
  ChanlunLayerKey,
  ChanlunPaperAccount,
  ChanlunPaperOrder,
  ChanlunPeriod,
  ChanlunReplayResponse,
  ChanlunWorkspaceResponse,
  SourceStatusValue,
} from "../../lib/types";
import {
  CHANLUN_PERIODS,
  DEFAULT_CHANLUN_LAYERS,
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
  divergences: "背驰",
  fractals: "分型",
  strokes: "笔",
  segments: "线段",
  signals: "买卖点",
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
  const [layers, setLayers] = useState<Record<ChanlunLayerKey, boolean>>(DEFAULT_CHANLUN_LAYERS);
  const [showMovingAverages, setShowMovingAverages] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [backfillJob, setBackfillJob] = useState<BackgroundJobState | null>(null);
  const [backfillError, setBackfillError] = useState<string | null>(null);
  const [backfillLoading, setBackfillLoading] = useState(false);
  const [replay, setReplay] = useState<ChanlunReplayResponse | null>(null);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);
  const [backtest, setBacktest] = useState<ChanlunBacktestResponse | null>(null);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [alerts, setAlerts] = useState<ChanlunAlertListResponse | null>(null);
  const [alertStatus, setAlertStatus] = useState<string | null>(null);
  const [alertError, setAlertError] = useState<string | null>(null);
  const [alertLoading, setAlertLoading] = useState(false);
  const [paperAccount, setPaperAccount] = useState<ChanlunPaperAccount | null>(null);
  const [paperError, setPaperError] = useState<string | null>(null);
  const [paperLoading, setPaperLoading] = useState(false);
  const [paperAction, setPaperAction] = useState<{ orderId: string; type: "approve" | "fill" | "cancel" } | null>(null);
  const requestId = useRef(0);
  const replayRequestId = useRef(0);
  const backtestRequestId = useRef(0);
  const alertRequestId = useRef(0);
  const searchId = useRef(0);
  const mounted = useRef(true);
  const selectedSymbol = useRef<string | null>(symbol);

  useEffect(() => {
    mounted.current = true;
    void getChanlunPaperAccount().then(
      (account) => {
        if (mounted.current) {
          setPaperAccount(account);
        }
      },
      (err: unknown) => {
        if (mounted.current) {
          setPaperError(err instanceof Error ? err.message : "读取模拟账户失败");
        }
      },
    );
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

  useEffect(() => {
    replayRequestId.current += 1;
    setReplay(null);
    setReplayError(null);
    setReplayLoading(false);
    backtestRequestId.current += 1;
    setBacktest(null);
    setBacktestError(null);
    setBacktestLoading(false);
    alertRequestId.current += 1;
    setAlerts(null);
    setAlertStatus(null);
    setAlertError(null);
    setAlertLoading(false);
    setPaperError(null);
    setPaperLoading(false);
    setPaperAction(null);
  }, [period, symbol]);

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

  async function loadReplay() {
    if (!symbol || replayLoading) {
      return;
    }
    const requestedSymbol = symbol;
    const requestedPeriod = period;
    const currentRequest = replayRequestId.current + 1;
    replayRequestId.current = currentRequest;
    setReplayLoading(true);
    setReplayError(null);
    try {
      const nextReplay = await getChanlunReplay(requestedSymbol, { period: requestedPeriod });
      if (!mounted.current || replayRequestId.current !== currentRequest) {
        return;
      }
      setReplay(nextReplay);
    } catch (err) {
      if (mounted.current && replayRequestId.current === currentRequest) {
        setReplayError(err instanceof Error ? err.message : "读取缠论历史回放失败");
      }
    } finally {
      if (mounted.current && replayRequestId.current === currentRequest) {
        setReplayLoading(false);
      }
    }
  }

  async function loadBacktest() {
    if (!symbol || backtestLoading) {
      return;
    }
    const currentRequest = backtestRequestId.current + 1;
    backtestRequestId.current = currentRequest;
    setBacktestLoading(true);
    setBacktestError(null);
    try {
      const nextBacktest = await getChanlunBacktest(symbol, { period });
      if (!mounted.current || backtestRequestId.current !== currentRequest) {
        return;
      }
      setBacktest(nextBacktest);
    } catch (err) {
      if (mounted.current && backtestRequestId.current === currentRequest) {
        setBacktestError(err instanceof Error ? err.message : "读取缠论绩效回测失败");
      }
    } finally {
      if (mounted.current && backtestRequestId.current === currentRequest) {
        setBacktestLoading(false);
      }
    }
  }

  async function checkAlerts() {
    if (!symbol || alertLoading) {
      return;
    }
    const currentRequest = alertRequestId.current + 1;
    alertRequestId.current = currentRequest;
    setAlertLoading(true);
    setAlertError(null);
    try {
      const refreshed = await refreshChanlunAlerts(symbol, { period });
      const nextAlerts = await getChanlunAlerts({ symbol, limit: 20 });
      if (!mounted.current || alertRequestId.current !== currentRequest) {
        return;
      }
      setAlerts(nextAlerts);
      setAlertStatus(
        refreshed.baselined
          ? "首次只建立基线，后续新确认信号才会记录。"
          : refreshed.created.length
            ? `新增 ${refreshed.created.length} 条确认信号预警。`
            : "没有新增确认信号预警。",
      );
    } catch (err) {
      if (mounted.current && alertRequestId.current === currentRequest) {
        setAlertError(err instanceof Error ? err.message : "刷新缠论预警失败");
      }
    } finally {
      if (mounted.current && alertRequestId.current === currentRequest) {
        setAlertLoading(false);
      }
    }
  }

  async function createPaperDraft() {
    if (!symbol || paperLoading) {
      return;
    }
    setPaperLoading(true);
    setPaperError(null);
    try {
      await createChanlunPaperOrderDraft(symbol, { quantity: 100 });
      if (!mounted.current) {
        return;
      }
      setPaperAccount(await getChanlunPaperAccount());
    } catch (err) {
      if (mounted.current) {
        setPaperError(err instanceof Error ? err.message : "创建模拟订单草案失败");
      }
    } finally {
      if (mounted.current) {
        setPaperLoading(false);
      }
    }
  }

  async function runPaperOrderAction(order: ChanlunPaperOrder, action: "approve" | "fill" | "cancel") {
    if (paperAction) {
      return;
    }
    setPaperAction({ orderId: order.id, type: action });
    setPaperError(null);
    try {
      if (action === "approve") {
        await approveChanlunPaperOrder(order.id);
      } else if (action === "fill") {
        await fillChanlunPaperOrder(order.id);
      } else {
        await cancelChanlunPaperOrder(order.id);
      }
      if (!mounted.current) {
        return;
      }
      setPaperAccount(await getChanlunPaperAccount());
    } catch (err) {
      if (mounted.current) {
        setPaperError(err instanceof Error ? err.message : "更新模拟订单失败");
      }
    } finally {
      if (mounted.current) {
        setPaperAction(null);
      }
    }
  }

  const activeAnalysis = isChanlunAnalysisCurrent(analysis, symbol, period) ? analysis : null;
  const activeWorkspace = isChanlunWorkspaceCurrent(workspace, symbol) ? workspace : null;
  const activePeriodSummary = activeWorkspace?.periods.find((item) => item.period === period) ?? null;
  const availability = activeAnalysis?.availability ?? activePeriodSummary?.availability ?? null;
  const isIntradayBackfillState = period !== "1d" && (availability === "insufficient_bars" || availability === "backfilling");
  const backfillActive = backfillLoading || backfillJob?.status === "pending" || backfillJob?.status === "running";
  const divergencesById = new Map(activeAnalysis?.divergences.map((item) => [item.id, item]) ?? []);
  const recentSignals = activeAnalysis?.signals.slice(-5).reverse() ?? [];
  const confluenceSignals = activeWorkspace?.confluence_signals.slice(-5).reverse() ?? [];

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
                    <span>{summary?.latest_signal ? formatSignalType(summary.latest_signal.type) : "暂无确认点"}</span>
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
                  <Checkbox checked={showMovingAverages} onChange={(event) => setShowMovingAverages(event.target.checked)}>
                    均线
                  </Checkbox>
                </Space>
              </div>
              <div className="chanlun-status-rail__chart">
                {activeAnalysis ? (
                  <TickFlowKlineChart
                    annotations={[]}
                    bars={activeAnalysis.bars}
                    chanlun={activeAnalysis}
                    chanlunLayers={layers}
                    height={720}
                    movingAverages={showMovingAverages ? ["ma5", "ma10", "ma20", "ma60"] : []}
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
                <Typography.Text strong>确认信号</Typography.Text>
              </div>
              <div className="compact-panel__body">
                {recentSignals.length ? (
                  <div className="divide-y divide-[var(--app-line)]">
                    {recentSignals.map((signal) => {
                      const divergence = signal.divergence_id ? divergencesById.get(signal.divergence_id) : undefined;
                      return (
                        <div className="grid gap-1 py-3 sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-3" key={signal.id}>
                          <Tag color={signal.type.endsWith("buy") ? "green" : "red"}>{formatSignalType(signal.type)}</Tag>
                          <span className="text-sm text-[var(--app-muted)]">
                            {formatSignalBasis(signal.type, divergence?.type)} · {formatTime(signal.occurred_at)}
                          </span>
                          <span className="text-sm text-[var(--app-ink)]">
                            背驰系数 <strong>{divergence ? divergence.coefficient.toFixed(2) : "--"}</strong> · {signal.price.toFixed(2)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <Typography.Text type="secondary">暂无已确认信号</Typography.Text>
                )}
              </div>
            </section>

            <section className="compact-panel">
              <div className="compact-panel__header">
                <Typography.Text strong>多周期共振</Typography.Text>
              </div>
              <div className="compact-panel__body">
                {confluenceSignals.length ? (
                  <div className="divide-y divide-[var(--app-line)]">
                    {confluenceSignals.map((signal) => (
                      <div className="grid gap-1 py-3 sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-3" key={signal.id}>
                        <Tag color={signal.type.endsWith("buy") ? "green" : "red"}>{formatConfluenceType(signal.type)}</Tag>
                        <span className="text-sm text-[var(--app-muted)]">
                          {PERIOD_LABELS[signal.higher_period]} · {PERIOD_LABELS[signal.lower_period]} · {formatTime(signal.occurred_at)}
                        </span>
                        <span className="text-sm text-[var(--app-ink)]">{signal.reason}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Typography.Text type="secondary">暂无已确认的多周期共振</Typography.Text>
                )}
              </div>
            </section>

            <section className="compact-panel">
              <div className="compact-panel__header flex-wrap gap-3">
                <Typography.Text strong>历史回放</Typography.Text>
                <Button disabled={replayLoading} loading={replayLoading} onClick={() => void loadReplay()} size="small">
                  回放
                </Button>
              </div>
              <div className="compact-panel__body">
                {replayError ? <Alert message={replayError} showIcon type="error" /> : null}
                {replayLoading ? <Skeleton active paragraph={{ rows: 3 }} title={false} /> : null}
                {!replay && !replayLoading && !replayError ? (
                  <Typography.Text type="secondary">按当前周期回放已收盘 K 线，只展示首次确认的结构事件。</Typography.Text>
                ) : null}
                {replay && !replayLoading ? (
                  replay.frames.length ? (
                    <div className="divide-y divide-[var(--app-line)]">
                      {replay.frames.map((frame) => (
                        <div className="grid gap-2 py-3 sm:grid-cols-[10rem_1fr] sm:items-start" key={frame.closed_at}>
                          <span className="text-sm text-[var(--app-muted)]">
                            {formatTime(frame.closed_at)} · {formatDirection(frame.direction)}
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {frame.new_divergences.map((divergence) => (
                              <Tag color={divergence.type === "bottom" ? "green" : "red"} key={divergence.id}>
                                {formatDivergenceType(divergence.type)} · 背驰系数 {divergence.coefficient.toFixed(2)}
                              </Tag>
                            ))}
                            {frame.new_signals.map((signal) => (
                              <Tag color={signal.type.endsWith("buy") ? "green" : "red"} key={signal.id}>
                                {formatSignalType(signal.type)} · {signal.price.toFixed(2)}
                              </Tag>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Typography.Text type="secondary">当前区间没有首次确认的结构事件。</Typography.Text>
                  )
                ) : null}
              </div>
            </section>

            <section className="compact-panel">
              <div className="compact-panel__header flex-wrap gap-3">
                <Typography.Text strong>绩效回测</Typography.Text>
                <Button disabled={backtestLoading} loading={backtestLoading} onClick={() => void loadBacktest()} size="small">
                  回测
                </Button>
              </div>
              <div className="compact-panel__body">
                {backtestError ? <Alert message={backtestError} showIcon type="error" /> : null}
                {backtestLoading ? <Skeleton active paragraph={{ rows: 3 }} title={false} /> : null}
                {!backtest && !backtestLoading && !backtestError ? (
                  <Typography.Text type="secondary">确认后的下一根 K 线开盘买入，只统计买类信号的固定持有窗口。</Typography.Text>
                ) : null}
                {backtest && !backtestLoading ? (
                  backtest.buckets.length ? (
                    <div className="space-y-4">
                      <Typography.Text type="secondary">有效样本 {backtest.sample_count} 条 · 入场口径：确认后下一根开盘</Typography.Text>
                      {backtest.buckets.map((bucket) => (
                        <div className="border-t border-[var(--app-line)] pt-3" key={bucket.signal_type}>
                          <div className="mb-2 flex items-center gap-2">
                            <Tag color="green">{formatSignalType(bucket.signal_type)}</Tag>
                            <span className="text-sm text-[var(--app-muted)]">样本 {bucket.sample_count}</span>
                          </div>
                          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                            {bucket.windows.map((window) => (
                              <div className="grid gap-1 text-sm" key={window.horizon_bars}>
                                <strong className="text-[var(--app-ink)]">{window.horizon_bars} 根K线</strong>
                                <span className="text-[var(--app-muted)]">胜率 {formatPercentage(window.win_rate_pct)}</span>
                                <span className="text-[var(--app-muted)]">均收益 {formatPercentage(window.avg_return_pct)}</span>
                                <span className="text-[var(--app-muted)]">赔率 {formatNumber(window.profit_loss_ratio)}</span>
                                <span className="text-[var(--app-muted)]">均回撤 {formatPercentage(window.avg_max_drawdown_pct)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Typography.Text type="secondary">当前区间没有可完成固定窗口统计的确认买类事件。</Typography.Text>
                  )
                ) : null}
              </div>
            </section>

            <section className="compact-panel">
              <div className="compact-panel__header flex-wrap gap-3">
                <Typography.Text strong>预警记录</Typography.Text>
                <Button disabled={alertLoading} loading={alertLoading} onClick={() => void checkAlerts()} size="small">
                  检查预警
                </Button>
              </div>
              <div className="compact-panel__body">
                {alertError ? <Alert message={alertError} showIcon type="error" /> : null}
                {alertLoading ? <Skeleton active paragraph={{ rows: 2 }} title={false} /> : null}
                {alertStatus ? <Typography.Text type="secondary">{alertStatus}</Typography.Text> : null}
                {!alerts && !alertLoading && !alertError && !alertStatus ? (
                  <Typography.Text type="secondary">检查当前周期预警，首次只建立基线，不补发历史信号。</Typography.Text>
                ) : null}
                {alerts?.items.length ? (
                  <div className="mt-3 divide-y divide-[var(--app-line)]">
                    {alerts.items.map((item) => (
                      <div className="grid gap-1 py-3 sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-3" key={item.key}>
                        <Tag color="green">{formatSignalType(item.signal_type)}</Tag>
                        <span className="text-sm text-[var(--app-muted)]">{PERIOD_LABELS[item.period]} · {formatTime(item.occurred_at)}</span>
                        <span className="text-sm text-[var(--app-ink)]">{item.price.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </section>

            <section className="compact-panel">
              <div className="compact-panel__header flex-wrap gap-3">
                <Typography.Text strong>模拟订单</Typography.Text>
                <Button disabled={paperLoading} loading={paperLoading} onClick={() => void createPaperDraft()} size="small">
                  创建草案
                </Button>
              </div>
              <div className="compact-panel__body">
                {paperError ? <Alert message={paperError} showIcon type="error" /> : null}
                {!paperAccount && !paperLoading && !paperError ? (
                  <Typography.Text type="secondary">仅本地模拟，不连接券商。草案需人工确认后才会冻结模拟资金。</Typography.Text>
                ) : null}
                {paperAccount ? (
                  <div className="space-y-3">
                    <Typography.Text type="secondary">仅本地模拟，不连接券商。更新成交按 TickFlow 最新价加 5 bps 滑点。</Typography.Text>
                    <div className="grid gap-2 text-sm sm:grid-cols-2 xl:grid-cols-4">
                      <PaperMetric label="总权益" value={formatCurrency(paperAccount.total_equity)} />
                      <PaperMetric label="可用资金" value={formatCurrency(paperAccount.available_cash)} />
                      <PaperMetric label="冻结资金" value={formatCurrency(paperAccount.reserved_cash)} />
                      <PaperMetric
                        label="持仓浮盈亏"
                        tone={
                          paperAccount.unrealized_pnl === null
                            ? undefined
                            : paperAccount.unrealized_pnl > 0
                              ? "positive"
                              : paperAccount.unrealized_pnl < 0
                                ? "negative"
                                : undefined
                        }
                        value={paperAccount.unrealized_pnl === null ? "--" : formatSignedCurrency(paperAccount.unrealized_pnl)}
                      />
                    </div>
                    {!paperAccount.valuation_complete ? (
                      <Typography.Text type="secondary">部分持仓行情暂不可用，总权益按成本暂估。</Typography.Text>
                    ) : paperAccount.valuation_time ? (
                      <Typography.Text type="secondary">估值时间 {formatTime(paperAccount.valuation_time)}</Typography.Text>
                    ) : null}
                    {paperAccount.positions.length ? (
                      <div>
                        <Typography.Text strong>当前持仓</Typography.Text>
                        <div className="mt-1 divide-y divide-[var(--app-line)]">
                          {paperAccount.positions.map((position) => (
                            <div className="grid gap-1 py-2 text-sm sm:grid-cols-[1fr_auto_auto_auto] sm:gap-4" key={position.symbol}>
                              <span>{position.symbol} · {position.quantity} 股</span>
                              <span className="text-[var(--app-muted)]">成本 {position.average_price.toFixed(2)}</span>
                              <span className="text-[var(--app-muted)]">现价 {position.latest_price?.toFixed(2) ?? "--"}</span>
                              <span className={paperValueClass(position.unrealized_pnl ?? 0)}>
                                {position.valuation_status === "live" && position.unrealized_pnl !== null && position.unrealized_pnl_pct !== null
                                  ? `${formatSignedCurrency(position.unrealized_pnl)} · ${position.unrealized_pnl_pct.toFixed(2)}%`
                                  : "行情暂不可用"}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {paperAccount.orders.length ? (
                      <div>
                        <Typography.Text strong>订单记录</Typography.Text>
                        <div className="mt-1 divide-y divide-[var(--app-line)]">
                        {paperAccount.orders.slice(0, 5).map((order) => (
                          <div className="grid gap-2 py-3 sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-3" key={order.id}>
                            <Tag color={paperOrderColor(order.status)}>{paperOrderStatusLabel(order.status)}</Tag>
                            <span className="text-sm text-[var(--app-muted)]">
                              {order.symbol} · {order.quantity} 股 · {formatCurrency(order.fill_notional ?? order.notional)}
                              {order.fill_price ? ` · 成交 ${order.fill_price.toFixed(2)}` : ""}
                              {order.quote_time ? ` · 报价 ${formatTime(order.quote_time)}` : ""}
                              {order.rejection_reason ? ` · ${order.rejection_reason}` : ""}
                            </span>
                            <Space size={4}>
                              {order.status === "awaiting_confirmation" ? (
                                <Button
                                  loading={paperAction?.orderId === order.id && paperAction.type === "approve"}
                                  onClick={() => void runPaperOrderAction(order, "approve")}
                                  size="small"
                                  type="primary"
                                >
                                  人工确认
                                </Button>
                              ) : null}
                              {order.status === "simulated_open" ? (
                                <Button
                                  loading={paperAction?.orderId === order.id && paperAction.type === "fill"}
                                  onClick={() => void runPaperOrderAction(order, "fill")}
                                  size="small"
                                  type="primary"
                                >
                                  更新成交
                                </Button>
                              ) : null}
                              {order.status === "awaiting_confirmation" || order.status === "simulated_open" ? (
                                <Button
                                  loading={paperAction?.orderId === order.id && paperAction.type === "cancel"}
                                  onClick={() => void runPaperOrderAction(order, "cancel")}
                                  size="small"
                                >
                                  撤单
                                </Button>
                              ) : null}
                            </Space>
                          </div>
                        ))}
                        </div>
                      </div>
                    ) : null}
                    {paperAccount.audit_records.length ? (
                      <div className="text-xs text-[var(--app-muted)]">
                        最近操作：{paperAuditLabel(paperAccount.audit_records[0].event)} · {formatTime(paperAccount.audit_records[0].occurred_at)}
                      </div>
                    ) : null}
                  </div>
                ) : null}
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

function PaperMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className="border-l-2 border-[var(--app-border)] pl-3">
      <div className="text-xs text-[var(--app-muted)]">{label}</div>
      <div className={`mt-0.5 font-semibold tabular-nums ${paperValueClass(tone === "positive" ? 1 : tone === "negative" ? -1 : 0)}`}>
        {value}
      </div>
    </div>
  );
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

function formatSignalType(type: ChanlunWorkspaceResponse["analysis"]["signals"][number]["type"]): string {
  return {
    one_buy: "一买",
    one_sell: "一卖",
    two_buy: "二买",
    two_sell: "二卖",
    three_buy: "三买",
    three_sell: "三卖",
  }[type];
}

function formatDivergenceType(
  type: ChanlunWorkspaceResponse["analysis"]["divergences"][number]["type"] | undefined,
): string {
  if (type === "bottom") {
    return "底背驰";
  }
  if (type === "top") {
    return "顶背驰";
  }
  return "盘整背驰";
}

function formatSignalBasis(
  type: ChanlunWorkspaceResponse["analysis"]["signals"][number]["type"],
  divergenceType: ChanlunWorkspaceResponse["analysis"]["divergences"][number]["type"] | undefined,
): string {
  if (divergenceType) {
    return formatDivergenceType(divergenceType);
  }
  if (type.startsWith("two_")) {
    return "五笔均线回抽";
  }
  if (type.startsWith("three_")) {
    return "中枢离开未回抽";
  }
  return "结构规则";
}

function formatConfluenceType(type: ChanlunWorkspaceResponse["confluence_signals"][number]["type"]): string {
  return {
    class_two_buy: "类二买",
    class_two_sell: "类二卖",
    class_three_buy: "类三买",
    class_three_sell: "类三卖",
    sub_two_buy: "次二买",
    sub_two_sell: "次二卖",
    sub_three_buy: "次三买",
    sub_three_sell: "次三卖",
  }[type];
}

function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "未确认";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function formatPercentage(value: number | null): string {
  return value === null ? "--" : `${value.toFixed(2)}%`;
}

function formatNumber(value: number | null): string {
  return value === null ? "--" : value.toFixed(2);
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

function formatSignedCurrency(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatCurrency(value)}`;
}

function paperValueClass(value: number): string {
  return value > 0 ? "market-rise-text" : value < 0 ? "market-fall-text" : "text-[var(--app-ink)]";
}

function paperAuditLabel(event: ChanlunPaperAccount["audit_records"][number]["event"]): string {
  return {
    created: "创建草案",
    approved: "人工确认",
    rejected: "订单拒绝",
    cancelled: "撤销订单",
    filled: "模拟成交",
  }[event];
}

function paperOrderStatusLabel(status: ChanlunPaperAccount["orders"][number]["status"]): string {
  return {
    draft: "草案",
    awaiting_confirmation: "待人工确认",
    simulated_open: "模拟挂单",
    filled: "模拟成交",
    rejected: "已拒绝",
    expired: "已过期",
    cancelled: "已取消",
  }[status];
}

function paperOrderColor(status: ChanlunPaperAccount["orders"][number]["status"]): string {
  return status === "rejected" || status === "cancelled" || status === "expired"
    ? "red"
    : status === "awaiting_confirmation"
      ? "gold"
      : "green";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
