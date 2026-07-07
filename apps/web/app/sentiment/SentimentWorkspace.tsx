"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Progress, Select, Skeleton, Space, Tag, Typography, message } from "antd";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState, type ComponentType } from "react";
import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";
import {
  getMarketRankings,
  getSentimentDecision,
  getSentimentDetail,
  getSentimentMonitorStatus,
  getSentimentSummary,
  getSentimentWatchlistAlerts,
  getShortTermIntradaySentiment,
  getShortTermIntradaySignalDigest,
  runSentimentMonitorOnce,
  saveSentimentMonitorConfig,
  sendNotificationMessage,
  startSentimentMonitor,
  stopSentimentMonitor,
} from "../../lib/api";
import type {
  MarketEmotionBucket,
  MarketEmotionSample,
  MarketEmotionSnapshotResponse,
  MarketRankingItem,
  MarketRankingsResponse,
  SentimentDecisionResponse,
  SentimentDetailResponse,
  SentimentMonitorStatus,
  SentimentSummaryResponse,
  SentimentWatchlistAlert,
  SentimentWatchlistAlertsResponse,
  ShortTermIntradaySentimentResponse,
  ShortTermIntradaySignalDigest,
  ShortTermSentimentIndustryItem,
  ShortTermSentimentResponse,
  ShortTermSentimentStockItem,
} from "../../lib/types";
import type { IntradaySentimentPanelProps } from "./IntradaySentimentPanel";
import type { StockPoolTableProps } from "./StockPoolTables";

const IntradaySentimentPanel = dynamic(
  () => import("./IntradaySentimentPanel").then((module) => module.IntradaySentimentPanel),
  { ssr: false, loading: () => <SentimentPanelPlaceholder title="盘中情绪快照" /> },
) as ComponentType<IntradaySentimentPanelProps>;

const StockPoolTable = dynamic(
  () => import("./StockPoolTables").then((module) => module.StockPoolTable),
  { ssr: false, loading: () => <SentimentPanelPlaceholder title="股票池" /> },
) as ComponentType<StockPoolTableProps>;

function SentimentPanelPlaceholder({ title }: { title: string }) {
  return (
    <section className="workbench-panel rounded-xl border p-4">
      <div className="mb-3 text-sm font-black text-[#11100e]">{title}</div>
      <Skeleton active paragraph={{ rows: 4 }} />
    </section>
  );
}

export function SentimentWorkspace() {
  const [tradeDate, setTradeDate] = useState(defaultTradeDate());
  const [summary, setSummary] = useState<SentimentSummaryResponse | null>(null);
  const [data, setData] = useState<ShortTermSentimentResponse | null>(null);
  const [marketEmotion, setMarketEmotion] = useState<MarketEmotionSnapshotResponse | null>(null);
  const [marketRankings, setMarketRankings] = useState<MarketRankingsResponse | null>(null);
  const [decision, setDecision] = useState<SentimentDecisionResponse | null>(null);
  const [watchlistAlerts, setWatchlistAlerts] = useState<SentimentWatchlistAlertsResponse | null>(null);
  const [intraday, setIntraday] = useState<ShortTermIntradaySentimentResponse | null>(null);
  const [digest, setDigest] = useState<ShortTermIntradaySignalDigest | null>(null);
  const [monitorStatus, setMonitorStatus] = useState<SentimentMonitorStatus | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(true);
  const [rankingsLoading, setRankingsLoading] = useState(true);
  const [decisionLoading, setDecisionLoading] = useState(true);
  const [watchlistAlertsLoading, setWatchlistAlertsLoading] = useState(true);
  const [intradayLoading, setIntradayLoading] = useState(false);
  const [digestLoading, setDigestLoading] = useState(false);
  const [sendingDigest, setSendingDigest] = useState(false);
  const [monitorBusy, setMonitorBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loading = summaryLoading || detailLoading;

  useEffect(() => {
    void refresh(tradeDate);
    void refreshMonitorStatus();
  }, []);

  async function refresh(date = tradeDate, forceRefresh = false) {
    setSummaryLoading(true);
    setError(null);
    try {
      const nextSummary = await getSentimentSummary(date, 80, forceRefresh);
      setSummary(nextSummary);
      void loadSentimentDecision(date, forceRefresh);
      void loadSentimentWatchlistAlerts(date, forceRefresh);
      void loadSentimentDetail(date, forceRefresh);
      void loadMarketRankings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取短线情绪概览失败");
      setSummary(null);
      setData(null);
      setMarketEmotion(null);
      setDecision(null);
      setWatchlistAlerts(null);
      setDecisionLoading(false);
      setWatchlistAlertsLoading(false);
      setDetailLoading(false);
    } finally {
      setSummaryLoading(false);
    }
  }

  async function loadSentimentDecision(date = tradeDate, forceRefresh = false) {
    setDecisionLoading(true);
    await getSentimentDecision(date, 80, forceRefresh)
      .then((nextDecision) => setDecision(nextDecision))
      .catch((err: unknown) => {
        setDecision(null);
        setError(err instanceof Error ? err.message : "读取情绪交易许可失败");
      })
      .finally(() => setDecisionLoading(false));
  }

  async function loadSentimentWatchlistAlerts(date = tradeDate, forceRefresh = false) {
    setWatchlistAlertsLoading(true);
    await getSentimentWatchlistAlerts(date, 80, forceRefresh)
      .then((nextAlerts) => setWatchlistAlerts(nextAlerts))
      .catch((err: unknown) => {
        setWatchlistAlerts(null);
        setError(err instanceof Error ? err.message : "读取自选股情绪联动失败");
      })
      .finally(() => setWatchlistAlertsLoading(false));
  }

  async function loadMarketRankings() {
    setRankingsLoading(true);
    await getMarketRankings(20)
      .then((nextRankings) => setMarketRankings(nextRankings))
      .catch((err: unknown) => {
        setMarketRankings(null);
        setError(err instanceof Error ? err.message : "读取全A实时排行榜失败");
      })
      .finally(() => setRankingsLoading(false));
  }

  async function loadSentimentDetail(date = tradeDate, forceRefresh = false) {
    setDetailLoading(true);
    await getSentimentDetail(date, 80, forceRefresh)
      .then((nextDetail) => {
        setData(nextDetail.sentiment);
        setMarketEmotion(nextDetail.market_emotion);
        setSummary((current) => current ?? summaryFromDetail(nextDetail));
      })
      .catch((err: unknown) => {
        if (forceRefresh) {
          setError(err instanceof Error ? err.message : "读取短线情绪详情失败");
        }
        setData(null);
        setMarketEmotion(null);
      })
      .finally(() => setDetailLoading(false));
  }

  async function refreshIntraday() {
    setIntradayLoading(true);
    setError(null);
    try {
      const [nextIntraday, nextDigest] = await Promise.all([
        getShortTermIntradaySentiment(tradeDate, 80, "1m", 120),
        getShortTermIntradaySignalDigest(tradeDate, 80, "1m", 120),
      ]);
      setIntraday(nextIntraday);
      setDigest(nextDigest);
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取盘中情绪失败");
      setIntraday(null);
      setDigest(null);
    } finally {
      setIntradayLoading(false);
    }
  }

  async function refreshDigest() {
    setDigestLoading(true);
    setError(null);
    try {
      setDigest(await getShortTermIntradaySignalDigest(tradeDate, 80, "1m", 120));
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成提醒草稿失败");
      setDigest(null);
    } finally {
      setDigestLoading(false);
    }
  }

  async function copyDigest() {
    if (!digest?.message_text) {
      return;
    }
    await navigator.clipboard.writeText(digest.message_text);
    message.success("提醒草稿已复制");
  }

  async function sendDigest() {
    if (!digest?.message_text) {
      return;
    }
    setSendingDigest(true);
    setError(null);
    try {
      const result = await sendNotificationMessage({
        title: digest.title,
        message_text: digest.message_text,
      });
      const successCount = result.results.filter((item) => item.status === "success").length;
      if (successCount > 0) {
        message.success(`提醒草稿已发送：${successCount} 个渠道成功`);
      } else {
        const detail = result.results.map((item) => `${item.channel_name}: ${item.detail}`).join("；") || "没有启用的通知渠道";
        setError(`发送通知未成功：${detail}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送提醒草稿失败");
    } finally {
      setSendingDigest(false);
    }
  }

  async function refreshMonitorStatus() {
    try {
      setMonitorStatus(await getSentimentMonitorStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取后台监控状态失败");
    }
  }

  async function updateMonitorInterval(intervalMinutes: 1 | 2 | 3) {
    if (!monitorStatus) {
      return;
    }
    setMonitorBusy(true);
    setError(null);
    try {
      const next = await saveSentimentMonitorConfig({
        ...monitorStatus.config,
        interval_minutes: intervalMinutes,
      });
      setMonitorStatus(next);
      message.success(`监控频率已保存：${intervalMinutes} 分钟`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存后台监控频率失败");
    } finally {
      setMonitorBusy(false);
    }
  }

  async function handleMonitorAction(action: "start" | "stop" | "runOnce") {
    setMonitorBusy(true);
    setError(null);
    try {
      const next =
        action === "start"
          ? await startSentimentMonitor()
          : action === "stop"
            ? await stopSentimentMonitor()
            : await runSentimentMonitorOnce(tradeDate);
      setMonitorStatus(next);
      if (action === "start") {
        message.success("后台监控已启动");
      } else if (action === "stop") {
        message.success("后台监控已停止");
      } else {
        message.success("已完成一次情绪采样");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "后台监控操作失败");
    } finally {
      setMonitorBusy(false);
    }
  }

  const sourceSummary = useMemo(() => {
    if (!data) {
      return "等待数据源返回";
    }
    const success = data.source_status.filter((item) => item.status === "success").map((item) => item.source);
    return success.length > 0 ? success.join(" / ") : "暂无可用数据源";
  }, [data]);

  return (
    <WorkbenchPage
      actions={
        <Space wrap>
          <input
            className="h-8 rounded-lg border border-[#d8d2c8] bg-white px-3 text-sm font-semibold text-[#11100e]"
            onChange={(event) => setTradeDate(event.target.value)}
            type="date"
            value={tradeDate}
          />
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void refresh(tradeDate, true)} type="primary">
            刷新情绪
          </Button>
          <Button loading={intradayLoading} onClick={() => void refreshIntraday()}>
            刷新盘中
          </Button>
        </Space>
      }
      description="基于近20日涨停候选池派生涨停池、炸板池、连板天梯和主线板块关联。"
      title="短线情绪中心"
    >

      {error && <Alert className="mb-4" showIcon title={error} type="error" />}

      {summaryLoading && !summary && !data ? (
        <div className="workbench-panel rounded-xl border p-5">
          <Skeleton active paragraph={{ rows: 12 }} />
        </div>
      ) : summary || data ? (
        <div className="space-y-4">
          <SentimentDecisionCard decision={decision} loading={decisionLoading} />
          <SentimentWatchlistAlertsCard alerts={watchlistAlerts?.items ?? []} loading={watchlistAlertsLoading} />
          <MarketEmotionDashboard data={marketEmotion} loading={detailLoading} summary={summary} />
          <MarketRankingsGrid loading={rankingsLoading} rankings={marketRankings} />
          <SentimentMonitorPanel
            busy={monitorBusy}
            onIntervalChange={(value) => void updateMonitorInterval(value)}
            onRefresh={() => void refreshMonitorStatus()}
            onRunOnce={() => void handleMonitorAction("runOnce")}
            onStart={() => void handleMonitorAction("start")}
            onStop={() => void handleMonitorAction("stop")}
            status={monitorStatus}
          />
          <section className="workbench-panel rounded-xl border p-4">
            <div className="text-sm font-black text-[#11100e]">规则校准</div>
            <div className="mt-1 text-xs text-[#7b756d]">
              每日归档情绪结论，后续对照次日表现统计命中率。
            </div>
          </section>
          {summary?.snapshot_status === "missing" ? (
            <Alert
              title="暂无本交易日情绪快照"
              description="页面已快速载入。点击右上角“刷新情绪”后，会调用真实数据源生成今日快照。"
              showIcon
              type="info"
            />
          ) : null}

          <IntradaySentimentPanel
            data={intraday}
            digest={digest}
            digestLoading={digestLoading}
            loading={intradayLoading}
            onCopyDigest={() => void copyDigest()}
            onRefreshDigest={() => void refreshDigest()}
            onRefresh={() => void refreshIntraday()}
            onSendDigest={() => void sendDigest()}
            sendingDigest={sendingDigest}
          />

          <section className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
            <aside className="workbench-panel rounded-xl border">
              <div className="workbench-panel-divider border-b px-4 py-3">
                <div className="text-sm font-black text-[#11100e]">主线关联</div>
                <div className="text-xs text-[#7b756d]">
                  {(data?.trade_date ?? summary?.trade_date) || tradeDate} · 数据源：{sourceSummary}
                </div>
              </div>
              <div className="space-y-3 p-4">
                {(data?.hot_industries.length || summary?.hot_industries.length) ? (
                  (data?.hot_industries ?? summary?.hot_industries ?? []).slice(0, 10).map((item, index) => (
                    <IndustryStrengthRow item={item} key={item.name} rank={index + 1} />
                  ))
                ) : (
                  <Empty description="暂无热点行业" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </div>
            </aside>

            <section className="workbench-panel rounded-xl border">
              <div className="workbench-panel-divider border-b px-4 py-3">
                <div className="text-sm font-black text-[#11100e]">连板天梯</div>
                <div className="text-xs text-[#7b756d]">从高连板到首板展示，帮助判断空间板和接力高度。</div>
              </div>
              <div className="grid gap-3 p-4 lg:grid-cols-2 xl:grid-cols-3">
                {detailLoading && !data ? (
                  <Skeleton active className="col-span-full" paragraph={{ rows: 5 }} />
                ) : data?.ladder.length ? (
                  data.ladder.map((group) => (
                    <div className="rounded-lg border border-[#e3ddd3] bg-white p-3" key={group.board_count}>
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-base font-black text-[#11100e]">{group.label}</span>
                        <Tag color={group.board_count >= 3 ? "red" : group.board_count === 2 ? "orange" : "default"}>
                          {group.items.length} 只
                        </Tag>
                      </div>
                      <div className="space-y-2">
                        {group.items.map((item) => (
                          <StockMiniRow item={item} key={item.symbol} />
                        ))}
                      </div>
                    </div>
                  ))
                ) : (
                  <Empty className="col-span-full" description="暂无连板数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </div>
            </section>
          </section>

          <section className="grid min-w-0 gap-4 xl:grid-cols-2">
            <StockPoolTable dataSource={data?.limit_up_pool ?? []} loading={detailLoading && !data} title="涨停池" />
            <StockPoolTable dataSource={data?.break_board_pool ?? []} loading={detailLoading && !data} title="炸板池" />
          </section>
        </div>
      ) : (
        <div className="workbench-panel rounded-xl border p-8">
          <Empty description="暂无短线情绪数据" />
        </div>
      )}
    </WorkbenchPage>
  );
}

function SentimentDecisionCard({
  decision,
  loading,
}: {
  decision: SentimentDecisionResponse | null;
  loading: boolean;
}) {
  if (loading && !decision) {
    return (
      <section className="workbench-panel rounded-xl border p-4">
        <Skeleton active paragraph={{ rows: 3 }} />
      </section>
    );
  }
  const sectors = decision?.main_sectors ?? [];
  const risks = decision?.risks.length ? decision.risks : ["暂无硬风险"];
  return (
    <section className="workbench-panel rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">情绪交易许可</div>
          <div className="text-xs text-[#7b756d]">市场状态、交易许可和风险等级先行，下面再展开原始情绪数据。</div>
        </div>
        <Space wrap>
          <Tag color={marketStateColor(decision?.market_state)}>市场状态：{decision?.market_state ?? "--"}</Tag>
          <Tag color={riskLevelColor(decision?.risk_level)}>风险等级：{decision?.risk_level ?? "--"}</Tag>
          <Tag>置信度 {decision ? decision.confidence.toFixed(0) : "--"}/100</Tag>
        </Space>
      </div>
      <div className="grid gap-3 p-4 lg:grid-cols-[260px_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="rounded-lg border border-[#e3ddd3] bg-white px-4 py-3">
          <div className="text-xs font-black text-[#7b756d]">交易许可</div>
          <div className={`mt-2 text-2xl font-black ${permissionTextClass(decision?.trade_permission)}`}>
            {decision?.trade_permission ?? "--"}
          </div>
          <div className="mt-1 text-xs text-[#7b756d]">
            情绪变化 {decision?.score_change === null || decision?.score_change === undefined ? "--" : formatSigned(decision.score_change)}
          </div>
        </div>
        <div className="rounded-lg border border-[#e3ddd3] bg-white px-4 py-3">
          <div className="text-xs font-black text-[#7b756d]">成立原因</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {(decision?.reasons.length ? decision.reasons : ["等待情绪快照"]).map((item) => (
              <Tag key={item}>{item}</Tag>
            ))}
          </div>
          {sectors.length ? (
            <div className="mt-3 flex flex-wrap gap-1">
              {sectors.slice(0, 4).map((sector) => (
                <Tag color="red" key={sector.name}>
                  {sector.name} · {sector.limit_up_count}涨停
                </Tag>
              ))}
            </div>
          ) : null}
        </div>
        <div className="rounded-lg border border-[#e3ddd3] bg-white px-4 py-3">
          <div className="text-xs font-black text-[#7b756d]">风险提示</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {risks.map((item) => (
              <Tag color={item === "暂无硬风险" ? "green" : "orange"} key={item}>
                {item}
              </Tag>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function SentimentWatchlistAlertsCard({
  alerts,
  loading,
}: {
  alerts: SentimentWatchlistAlert[];
  loading: boolean;
}) {
  const groups = useMemo(
    () =>
      (["重点盯", "等确认", "风险回避"] as const).map((action) => ({
        action,
        items: alerts.filter((item) => item.action === action),
      })),
    [alerts],
  );

  if (loading && alerts.length === 0) {
    return (
      <section className="workbench-panel rounded-xl border p-4">
        <Skeleton active paragraph={{ rows: 3 }} />
      </section>
    );
  }

  return (
    <section className="workbench-panel rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">自选股联动</div>
          <div className="text-xs text-[#7b756d]">把当前情绪许可和主线方向映射到自选股池，优先处理需要盯盘的股票。</div>
        </div>
        <Space wrap>
          <Tag color="red">重点盯 {groups[0].items.length}</Tag>
          <Tag>等确认 {groups[1].items.length}</Tag>
          <Tag color="orange">风险回避 {groups[2].items.length}</Tag>
        </Space>
      </div>
      {alerts.length === 0 ? (
        <div className="p-6">
          <Empty description="暂无自选股联动结果，请先维护自选股池" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      ) : (
        <div className="grid gap-3 p-4 xl:grid-cols-3">
          {groups.map((group) => (
            <div className="rounded-lg border border-[#e3ddd3] bg-white" key={group.action}>
              <div className="flex items-center justify-between border-b border-[#efe8dd] px-3 py-2">
                <span className="text-sm font-black text-[#11100e]">{group.action}</span>
                <Tag color={watchlistActionColor(group.action)}>{group.items.length} 只</Tag>
              </div>
              <div className="space-y-2 p-3">
                {group.items.length ? (
                  group.items.slice(0, 8).map((item) => <WatchlistAlertRow item={item} key={item.symbol} />)
                ) : (
                  <div className="rounded-md bg-[#f7f3ed] px-3 py-4 text-center text-xs text-[#7b756d]">暂无股票</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function WatchlistAlertRow({ item }: { item: SentimentWatchlistAlert }) {
  return (
    <div className="rounded-md border border-[#efe8dd] bg-[#fffdf9] px-3 py-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Link className="block truncate text-sm font-black text-[#11100e]" href={`/stock/${item.symbol}`}>
            {item.name}
          </Link>
          <div className="mt-0.5 text-xs text-[#7b756d]">{item.symbol}</div>
        </div>
        {item.matched_sector ? <Tag color="red">{item.matched_sector}</Tag> : null}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {item.group ? <Tag>{item.group}</Tag> : null}
        {item.tags.slice(0, 3).map((tag) => (
          <Tag key={tag}>{tag}</Tag>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {item.reasons.slice(0, 3).map((reason) => (
          <Tag color={item.action === "风险回避" ? "orange" : item.action === "重点盯" ? "red" : "default"} key={reason}>
            {reason}
          </Tag>
        ))}
      </div>
    </div>
  );
}

function SentimentMonitorPanel({
  busy,
  onIntervalChange,
  onRefresh,
  onRunOnce,
  onStart,
  onStop,
  status,
}: {
  busy: boolean;
  onIntervalChange: (value: 1 | 2 | 3) => void;
  onRefresh: () => void;
  onRunOnce: () => void;
  onStart: () => void;
  onStop: () => void;
  status: SentimentMonitorStatus | null;
}) {
  const lastAlerts = status?.last_alerts ?? [];
  return (
    <section className="workbench-panel rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">后台监控</div>
          <div className="text-xs text-[#7b756d]">
            交易时段自动采样短线情绪，出现情绪突变时通过已配置的企业微信、飞书、Telegram 或邮件提醒。
          </div>
        </div>
        <Space wrap>
          <Tag color={status?.running ? "green" : "default"}>{status?.running ? "运行中" : "未运行"}</Tag>
          <Tag color={status?.in_trading_session ? "red" : "default"}>
            {status?.in_trading_session ? "交易时段" : "非交易时段"}
          </Tag>
          <Select
            disabled={!status || busy}
            onChange={onIntervalChange}
            options={[
              { label: "每 1 分钟", value: 1 },
              { label: "每 2 分钟", value: 2 },
              { label: "每 3 分钟", value: 3 },
            ]}
            size="small"
            value={status?.config.interval_minutes ?? 3}
            style={{ width: 112 }}
          />
          <Button loading={busy} onClick={onRefresh}>
            刷新状态
          </Button>
          <Button loading={busy} onClick={onRunOnce}>
            手动采样
          </Button>
          {status?.running ? (
            <Button danger loading={busy} onClick={onStop}>
              停止
            </Button>
          ) : (
            <Button loading={busy} onClick={onStart} type="primary">
              启动
            </Button>
          )}
        </Space>
      </div>
      <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-5">
        <SmallMetric label="采样频率" value={status?.config.interval_minutes ?? 3} />
        <MonitorInfoCard label="最后采样" value={formatDateTime(status?.last_sampled_at)} />
        <MonitorInfoCard label="最后交易日" value={status?.last_trade_date ?? "--"} />
        <MonitorInfoCard
          label="最后情绪分"
          value={status?.last_emotion_score === null || status?.last_emotion_score === undefined ? "--" : status.last_emotion_score.toFixed(0)}
        />
        <MonitorInfoCard label="最后提醒" value={formatDateTime(status?.last_notification_at)} />
      </div>
      {status?.last_error ? (
        <Alert className="mx-4 mb-4" showIcon title={status.last_error} type="warning" />
      ) : null}
      <div className="px-4 pb-4">
        {lastAlerts.length ? (
          <div className="space-y-2 rounded-lg border border-[#e3ddd3] bg-white p-3">
            {lastAlerts.slice(0, 5).map((alert) => (
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs" key={`${alert.type}-${alert.generated_at}`}>
                <span className="font-black text-[#11100e]">{alert.title}</span>
                <span className="min-w-0 flex-1 text-[#625b52]">{alert.message}</span>
                <Tag color={alert.severity === "high" ? "red" : "orange"}>{alert.severity}</Tag>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-[#e3ddd3] bg-white p-3 text-xs text-[#7b756d]">
            暂无突变提醒。后台只在 09:25-11:30、13:00-15:05 自动采样；手动采样不受交易时段限制。
          </div>
        )}
      </div>
    </section>
  );
}

function MarketRankingsGrid({
  loading,
  rankings,
}: {
  loading: boolean;
  rankings: MarketRankingsResponse | null;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-2">
      <MarketRankingPanel
        items={rankings?.pct_change_rank ?? []}
        loading={loading}
        sourceStatus={rankings?.source_status ?? []}
        title="TickFlow涨幅榜"
        valueFormatter={formatPct}
        valueLabel="涨幅"
        valueOf={(item) => item.pct_change}
      />
      <MarketRankingPanel
        items={rankings?.turnover_rank ?? []}
        loading={loading}
        sourceStatus={rankings?.source_status ?? []}
        title="TickFlow成交额榜"
        valueFormatter={formatCny}
        valueLabel="成交额"
        valueOf={(item) => item.turnover_cny}
      />
    </section>
  );
}

function MarketRankingPanel({
  items,
  loading,
  sourceStatus,
  title,
  valueFormatter,
  valueLabel,
  valueOf,
}: {
  items: MarketRankingItem[];
  loading: boolean;
  sourceStatus: Array<{ source: string; status: string; detail: string }>;
  title: string;
  valueFormatter: (value: number | null) => string;
  valueLabel: string;
  valueOf: (item: MarketRankingItem) => number | null;
}) {
  const tickflowStatus = sourceStatus.find((item) => item.source.includes("TickFlow"));
  return (
    <section className="workbench-panel rounded-xl border">
      <div className="workbench-panel-divider flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">{title}</div>
          <div className="text-xs text-[#7b756d]">全A实时 quotes 批量排序，作为情绪强弱的直接观察窗口。</div>
        </div>
        <Tag color={tickflowStatus?.status === "success" ? "green" : "default"}>
          {tickflowStatus?.status === "success" ? "实时" : "待更新"}
        </Tag>
      </div>
      <div className="p-4">
        {loading ? (
          <Skeleton active paragraph={{ rows: 5 }} />
        ) : items.length ? (
          <div className="space-y-2">
            {items.slice(0, 10).map((item, index) => {
              const value = valueOf(item);
              const isUp = (item.pct_change ?? 0) >= 0;
              return (
                <Link
                  className="grid grid-cols-[34px_minmax(0,1fr)_92px] items-center gap-3 rounded-lg border border-[#e3ddd3] bg-white px-3 py-2 no-underline transition hover:border-[#c9bca8]"
                  href={`/stock/${item.symbol}`}
                  key={`${title}-${item.symbol}`}
                >
                  <span className="text-xs font-black text-[#7b756d]">#{index + 1}</span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-black text-[#11100e]">{item.name || item.symbol}</span>
                    <span className="block truncate text-xs text-[#7b756d]">
                      {item.symbol} · 换手 {formatPct(item.turnover_rate)}
                    </span>
                  </span>
                  <span className="text-right">
                    <span className={`block text-sm font-black ${isUp ? "text-[#d92d20]" : "market-green-text"}`}>
                      {valueFormatter(value)}
                    </span>
                    <span className="block text-[11px] font-semibold text-[#7b756d]">{valueLabel}</span>
                  </span>
                </Link>
              );
            })}
          </div>
        ) : (
          <Empty description="暂无 TickFlow 排行数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </div>
    </section>
  );
}

function MonitorInfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2">
      <div className="text-xs font-black text-[#7b756d]">{label}</div>
      <div className="mt-1 truncate text-sm font-black text-[#11100e]">{value}</div>
    </div>
  );
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatSigned(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function marketStateColor(value: SentimentDecisionResponse["market_state"] | undefined): string {
  if (value === "退潮" || value === "冰点") {
    return "green";
  }
  if (value === "高潮" || value === "分歧") {
    return "orange";
  }
  if (value === "主升" || value === "修复") {
    return "red";
  }
  return "default";
}

function riskLevelColor(value: SentimentDecisionResponse["risk_level"] | undefined): string {
  if (value === "高") {
    return "red";
  }
  if (value === "中") {
    return "orange";
  }
  if (value === "低") {
    return "green";
  }
  return "default";
}

function permissionTextClass(value: SentimentDecisionResponse["trade_permission"] | undefined): string {
  if (value === "空仓等待" || value === "只低吸") {
    return "market-green-text";
  }
  if (value === "只卖不追") {
    return "text-[#b45309]";
  }
  if (value === "强势进攻" || value === "轻仓试错") {
    return "text-[#d92d20]";
  }
  return "text-[#11100e]";
}

function watchlistActionColor(value: SentimentWatchlistAlert["action"]): string {
  if (value === "重点盯") {
    return "red";
  }
  if (value === "风险回避") {
    return "orange";
  }
  return "default";
}

function summaryFromDetail(detail: SentimentDetailResponse): SentimentSummaryResponse {
  const metrics = detail.market_emotion.metrics;
  return {
    trade_date: detail.trade_date,
    snapshot_status: detail.snapshot_status === "missing" ? "fresh" : detail.snapshot_status,
    cached_at: detail.cached_at,
    metrics: {
      emotion_score: metrics.emotion_score,
      emotion_level: metrics.emotion_level,
      limit_up_count: detail.sentiment.metrics.limit_up_count,
      break_board_count: detail.sentiment.metrics.break_board_count,
      limit_down_count: metrics.limit_down_count,
      losing_effect_score: metrics.losing_effect_score,
      max_consecutive_boards: detail.sentiment.metrics.max_consecutive_boards,
      advance_count: metrics.advance_count,
      decline_count: metrics.decline_count,
      seal_rate_pct: metrics.seal_rate_pct,
      turnover_cny: metrics.turnover_cny,
      turnover_change_cny: metrics.turnover_change_cny,
      turnover_change_pct: metrics.turnover_change_pct,
    },
    hot_industries: detail.sentiment.hot_industries.slice(0, 10),
    source_status: [...detail.sentiment.source_status, ...detail.market_emotion.source_status],
    notes: detail.market_emotion.notes,
    generated_at: detail.market_emotion.generated_at,
  };
}

function MarketEmotionDashboard({
  data,
  loading,
  summary,
}: {
  data: MarketEmotionSnapshotResponse | null;
  loading: boolean;
  summary: SentimentSummaryResponse | null;
}) {
  const metrics = data?.metrics ?? summary?.metrics;
  const score = metrics?.emotion_score ?? 0;
  const level = metrics?.emotion_level ?? "冰点";
  const levelColor = emotionLevelColor(level);
  return (
    <section className="workbench-panel rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">市场情绪仪表盘</div>
          <div className="text-xs text-[#7b756d]">
            盘中实时快照：涨停/炸板 + 全A涨跌家数 + 成交额变化。曲线与涨跌分布只展示真实可得数据。
          </div>
        </div>
        <Space wrap>
          <Tag color={levelColor}>{level}</Tag>
          <Tag>{data?.trade_date ?? summary?.trade_date ?? "等待数据"}</Tag>
          {summary?.snapshot_status === "cached" ? <Tag color="blue">缓存快照</Tag> : null}
          {(data?.source_status ?? summary?.source_status ?? [])
            .filter((item) => item.status === "success")
            .slice(0, 3)
            .map((item, index) => (
              <Tag color="green" key={`${item.source}-${item.detail}-${index}`}>
                {item.source}
              </Tag>
            ))}
        </Space>
      </div>
      {loading && !data && !summary ? (
        <div className="p-4">
          <Skeleton active paragraph={{ rows: 5 }} />
        </div>
      ) : (
        <div className="space-y-4 p-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            <EmotionScoreCard score={score} level={level} />
            <RealtimeMetricCard label="涨停家数" value={metrics?.limit_up_count ?? null} suffix="只" tone="red" />
            <RealtimeMetricCard label="跌停家数" value={metrics?.limit_down_count ?? null} suffix="只" tone="green" />
            <RealtimeMetricCard
              label="亏钱效应"
              value={metrics?.losing_effect_score ?? null}
              suffix="/100"
              tone="amber"
            />
            <RealtimeMetricCard
              label="连板高度"
              value={metrics?.max_consecutive_boards ?? null}
              suffix="板"
              tone="ink"
            />
            <RealtimeMetricCard
              label="今日封板率"
              value={metrics?.seal_rate_pct ?? null}
              suffix="%"
              tone="red"
            />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <RealtimeMetricCard label="上涨家数" value={metrics?.advance_count ?? null} suffix="家" tone="red" />
            <RealtimeMetricCard label="下跌家数" value={metrics?.decline_count ?? null} suffix="家" tone="green" />
            <RealtimeMetricCard
              label="总成交额"
              value={metrics?.turnover_cny ?? null}
              formatter={formatCny}
              tone="ink"
            />
            <RealtimeMetricCard
              label="较昨日"
              value={metrics?.turnover_change_cny ?? null}
              formatter={(value) => `${formatCny(value)} (${formatPct(metrics?.turnover_change_pct ?? null)})`}
              tone={(metrics?.turnover_change_cny ?? 0) >= 0 ? "red" : "green"}
            />
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
            <DistributionPanel buckets={data?.buckets ?? []} />
            <EmotionHistoryChart level={level} samples={data?.samples ?? []} score={score} />
          </div>
          {(data?.notes.length || summary?.notes.length) ? (
            <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2 text-xs leading-5 text-[#625b52]">
              {(data?.notes ?? summary?.notes ?? []).join(" ")}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function EmotionScoreCard({ score, level }: { score: number; level: string }) {
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2">
      <div className="text-xs font-black text-[#7b756d]">情绪指标</div>
      <div className="mt-2 flex items-center gap-3">
        <Progress
          format={() => score.toFixed(0)}
          percent={Math.max(0, Math.min(score, 100))}
          size={64}
          strokeColor={emotionLevelHex(level)}
          type="circle"
        />
        <div>
          <div className="text-xl font-black text-[#11100e]">{level}</div>
          <div className="text-xs text-[#7b756d]">0 冰点 · 100 火爆</div>
        </div>
      </div>
    </div>
  );
}

function RealtimeMetricCard({
  label,
  value,
  suffix,
  tone,
  formatter,
}: {
  label: string;
  value: number | null;
  suffix?: string;
  tone: "red" | "green" | "amber" | "ink";
  formatter?: (value: number | null) => string;
}) {
  const toneClass =
    tone === "red"
      ? "text-[#d92d20]"
      : tone === "green"
        ? "market-green-text"
        : tone === "amber"
          ? "text-[#b45309]"
          : "text-[#11100e]";
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2">
      <div className="text-xs font-black text-[#7b756d]">{label}</div>
      <div className={`mt-1 flex items-baseline gap-1 text-2xl font-black ${toneClass}`}>
        {formatter ? formatter(value) : value === null ? "--" : formatNumber(value)}
        {!formatter && suffix ? <span className="text-sm font-semibold text-[#7b756d]">{suffix}</span> : null}
      </div>
    </div>
  );
}

function DistributionPanel({ buckets }: { buckets: MarketEmotionBucket[] }) {
  const maxCount = Math.max(...buckets.map((bucket) => bucket.count ?? 0), 1);
  const hasData = buckets.some((bucket) => bucket.count !== null);
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white p-3">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-black text-[#11100e]">涨跌幅分布</div>
          <div className="text-xs text-[#7b756d]">等待全市场实时个股行情源后显示真实分布。</div>
        </div>
        <Tag color={hasData ? "green" : "default"}>{hasData ? "实时" : "待接入"}</Tag>
      </div>
      <div className="space-y-2">
        {buckets.map((bucket) => {
          const width = bucket.count === null ? 0 : Math.max(4, (bucket.count / maxCount) * 100);
          const isUp = (bucket.min_pct ?? -1) >= 0;
          return (
            <div className="grid grid-cols-[70px_minmax(0,1fr)_48px] items-center gap-2" key={bucket.label}>
              <span className="text-xs font-semibold text-[#625b52]">{bucket.label}</span>
              <div className="h-3 overflow-hidden rounded-full bg-[#eee9df]">
                <div
                  className={`h-full rounded-full ${isUp ? "bg-[#d92d20]" : "market-green-fill"}`}
                  style={{ width: `${width}%` }}
                />
              </div>
              <span className="text-right text-xs font-black text-[#11100e]">
                {bucket.count === null ? "--" : bucket.count}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EmotionHistoryChart({
  samples,
  score,
  level,
}: {
  samples: MarketEmotionSample[];
  score: number;
  level: string;
}) {
  const markerLeft = `${Math.max(0, Math.min(score, 100))}%`;
  const chartSamples: MarketEmotionSample[] = samples.length
    ? samples
    : [
        {
          emotion_score: score,
          emotion_level: "冰点",
          sampled_at: "",
          trade_date: "",
          limit_up_count: 0,
          break_board_count: 0,
          limit_down_count: null,
          losing_effect_score: null,
          max_consecutive_boards: 0,
          advance_count: null,
          decline_count: null,
          seal_rate_pct: null,
          turnover_cny: null,
          turnover_change_pct: null,
        },
      ];
  const points = buildEmotionPolyline(chartSamples);
  const bands = [
    { label: "冰点", width: "25%", className: "bg-[#dbeafe]", text: "text-[#1d4ed8]" },
    { label: "一般", width: "25%", className: "bg-[#e5e7eb]", text: "text-[#4b5563]" },
    { label: "良好", width: "25%", className: "bg-[#fef3c7]", text: "text-[#92400e]" },
    { label: "火爆", width: "25%", className: "bg-[#fee2e2]", text: "text-[#b91c1c]" },
  ];
  const timelineLabels = ["竞价定调", "开盘承接", "情绪确认", "上午定性", "尾盘风险"];
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">日内情绪落点</div>
          <div className="text-xs text-[#7b756d]">
            真实采样曲线：每次刷新追加一个点，后台任务流启用后会自动变成连续曲线。
          </div>
        </div>
        <Tag color={samples.length > 1 ? "green" : "default"}>{samples.length || 1} 点</Tag>
      </div>
      <div className="relative mt-8 h-24 rounded-lg border border-[#e3ddd3] bg-[#f8f7f4] p-3">
        <div className="flex h-full overflow-hidden rounded-md">
          {bands.map((band) => (
            <div className={`${band.className} flex items-end justify-center pb-2`} key={band.label} style={{ width: band.width }}>
              <span className={`text-xs font-black ${band.text}`}>{band.label}</span>
            </div>
          ))}
        </div>
        <svg aria-hidden className="absolute inset-3 h-[calc(100%-24px)] w-[calc(100%-24px)]" preserveAspectRatio="none" viewBox="0 0 100 100">
          {points.length > 1 ? (
            <polyline
              fill="none"
              points={points.map((point) => `${point.x},${point.y}`).join(" ")}
              stroke="#11100e"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2.5"
              vectorEffect="non-scaling-stroke"
            />
          ) : null}
          {points.map((point, index) => (
            <circle
              cx={point.x}
              cy={point.y}
              fill={index === points.length - 1 ? emotionLevelHex(level) : "#11100e"}
              key={`${point.x}-${point.y}-${index}`}
              r={index === points.length - 1 ? 2.8 : 1.8}
            />
          ))}
        </svg>
        <div className="absolute top-2 h-[calc(100%-16px)] w-0.5 bg-[#11100e]" style={{ left: markerLeft }}>
          <div className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-[#11100e] px-2 py-0.5 text-xs font-black text-white">
            {score.toFixed(0)} · {level}
          </div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {timelineLabels.map((label) => (
          <Tag className="m-0 text-center" key={label}>
            {label}
          </Tag>
        ))}
      </div>
    </div>
  );
}

function buildEmotionPolyline(samples: MarketEmotionSample[]): Array<{ x: number; y: number }> {
  if (samples.length <= 1) {
    const score = Math.max(0, Math.min(samples[0]?.emotion_score ?? 0, 100));
    return [{ x: 100, y: 100 - score }];
  }
  const lastSamples = samples.slice(-80);
  const maxIndex = Math.max(1, lastSamples.length - 1);
  return lastSamples.map((sample, index) => {
    const score = Math.max(0, Math.min(sample.emotion_score, 100));
    return {
      x: Number(((index / maxIndex) * 100).toFixed(2)),
      y: Number((100 - score).toFixed(2)),
    };
  });
}

function IndustryStrengthRow({ item, rank }: { item: ShortTermSentimentIndustryItem; rank: number }) {
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-black text-[#11100e]">
            #{rank} {item.name}
          </div>
          <div className="mt-1 text-xs text-[#7b756d]">核心：{item.leader ?? "--"}</div>
        </div>
        <div className="text-right">
          <div className="text-lg font-black text-[#d92d20]">{item.strength_score.toFixed(1)}</div>
          <div className="text-[11px] text-[#7b756d]">强度</div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1">
        <Tag color="red">涨停 {item.limit_up_count}</Tag>
        <Tag color="orange">高度 {item.max_consecutive_boards}</Tag>
        <Tag color={item.break_board_count > 0 ? "green" : "default"}>炸板 {item.break_board_count}</Tag>
      </div>
    </div>
  );
}

function StockMiniRow({ item }: { item: ShortTermSentimentStockItem }) {
  return (
    <Link
      className="flex items-center justify-between gap-3 rounded-md bg-[#f8f7f4] px-3 py-2 transition hover:bg-[#eee9df]"
      href={`/stock/${item.symbol}`}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-black text-[#11100e]">{item.name}</span>
        <span className="block text-xs text-[#7b756d]">{item.symbol}</span>
      </span>
      <span className="text-right text-xs font-semibold text-[#7b756d]">{item.first_seal_time ?? "--"}</span>
    </Link>
  );
}

function SmallMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2">
      <div className="text-xs font-black text-[#7b756d]">{label}</div>
      <div className="mt-1 text-xl font-black text-[#11100e]">{value}</div>
    </div>
  );
}

function emotionLevelColor(level: string): string {
  if (level === "火爆") {
    return "red";
  }
  if (level === "良好") {
    return "orange";
  }
  if (level === "一般") {
    return "default";
  }
  return "blue";
}

function emotionLevelHex(level: string): string {
  if (level === "火爆") {
    return "#d92d20";
  }
  if (level === "良好") {
    return "#b45309";
  }
  if (level === "一般") {
    return "#625b52";
  }
  return "#2563eb";
}

function formatPct(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

function formatCny(value: number | null): string {
  if (value === null) {
    return "--";
  }
  const abs = Math.abs(value);
  if (abs >= 1_0000_0000_0000) {
    return `${(value / 1_0000_0000_0000).toFixed(2)}万亿`;
  }
  if (abs >= 1_0000_0000) {
    return `${(value / 1_0000_0000).toFixed(2)}亿`;
  }
  if (abs >= 1_0000) {
    return `${(value / 1_0000).toFixed(2)}万`;
  }
  return value.toFixed(0);
}

function defaultTradeDate(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
