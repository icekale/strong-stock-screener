"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Alert, App, Button, Empty, InputNumber, Progress, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { addWatchlistPoolItem, getAuctionSnapshot } from "../../lib/api";
import type { AuctionSnapshotItem, AuctionSnapshotResponse } from "../../lib/types";

type AuctionTierFilter = "all" | AuctionSnapshotItem["tier"];
type IndustryAuctionStat = {
  avgOpenGapPct: number | null;
  count: number;
  industry: string;
  strongCount: number;
  turnoverCny: number;
};

const TIER_FILTERS: Array<{ label: string; value: AuctionTierFilter }> = [
  { label: "全部", value: "all" },
  { label: "强势高开", value: "strong_high_open" },
  { label: "放量活跃", value: "volume_leader" },
  { label: "高开过热", value: "risk_overheat" },
  { label: "低开观察", value: "reversal_watch" },
  { label: "低开偏弱", value: "weak_low_open" },
];

export function AuctionWorkspace() {
  const { message } = App.useApp();
  const [data, setData] = useState<AuctionSnapshotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<AuctionTierFilter>("all");
  const [industryFilter, setIndustryFilter] = useState<string>("all");
  const [highOpenRiskThreshold, setHighOpenRiskThreshold] = useState(7);
  const [watchlistSavingSymbol, setWatchlistSavingSymbol] = useState<string | null>(null);
  const refreshPromiseRef = useRef<Promise<void> | null>(null);

  const refresh = useCallback(async () => {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }
    setLoading(true);
    setError(null);
    const promise = getAuctionSnapshot(100)
      .then((snapshot) => {
        setData(snapshot);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "读取竞价雷达失败");
        setData(null);
      })
      .finally(() => {
        setLoading(false);
        refreshPromiseRef.current = null;
      });
    refreshPromiseRef.current = promise;
    return promise;
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const observationItems = useMemo(
    () =>
      (data?.items ?? [])
        .filter(
          (item) =>
            item.risk_flags.length > 0 ||
            item.tier === "reversal_watch" ||
            (item.open_gap_pct ?? 0) >= highOpenRiskThreshold,
        )
        .slice(0, 12),
    [data, highOpenRiskThreshold],
  );
  const visibleItems = useMemo(
    () =>
      (data?.items ?? []).filter(
        (item) =>
          (tierFilter === "all" || item.tier === tierFilter) &&
          (industryFilter === "all" || (item.industry || "未标注") === industryFilter),
      ),
    [data, industryFilter, tierFilter],
  );
  const industryStats = useMemo(() => buildIndustryStats(data?.items ?? []), [data]);
  const concentration = useMemo(() => buildIndustryConcentration(industryStats, data?.items.length ?? 0), [data, industryStats]);

  async function handleAddToWatchlist(item: AuctionSnapshotItem) {
    setWatchlistSavingSymbol(item.symbol);
    setError(null);
    try {
      await addWatchlistPoolItem({
        symbol: item.symbol,
        name: item.name,
        industry: item.industry,
        group: "竞价雷达",
        tags: ["竞价", item.industry || "未标注", tierLabel(item.tier)],
        note: buildAuctionWatchlistNote(item),
      });
      void message.success(`已加入自选：${item.name || item.symbol}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加入自选股失败");
    } finally {
      setWatchlistSavingSymbol(null);
    }
  }

  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Typography.Title className="m-0 text-[#11100e]" level={3}>
            竞价雷达
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            基于 TickFlow 全A实时行情快照，区分开盘幅度、当前涨幅、量能活跃度和风险分层。
          </Typography.Text>
        </div>
        <Space wrap>
          <Tag color={sessionColor(data?.session)}>{sessionLabel(data?.session)}</Tag>
          <Tag>{data?.trade_date ?? "等待数据"}</Tag>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void refresh()} type="primary">
            刷新竞价
          </Button>
        </Space>
      </div>

      {error && <Alert className="mb-4" showIcon title={error} type="error" />}

      <section className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="竞价候选" value={data?.metrics.candidate_count ?? null} suffix="只" />
        <MetricCard label="强势高开" value={data?.metrics.strong_high_open_count ?? null} suffix="只" tone="red" />
        <MetricCard label="高开风险" value={data?.metrics.high_risk_count ?? null} suffix="只" tone="amber" />
        <MetricCard label="候选成交额" value={data?.metrics.total_turnover_cny ?? null} formatter={formatCny} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="workbench-panel rounded-xl border">
          <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div>
              <div className="text-sm font-black text-[#11100e]">竞价强度榜</div>
              <div className="text-xs text-[#7b756d]">
                按开盘幅度、当前涨幅、成交额和换手强度综合排序，当前显示 {visibleItems.length}/{data?.items.length ?? 0} 只。
              </div>
            </div>
            <Space align="center" wrap>
              {TIER_FILTERS.map((item) => (
                <Button
                  key={item.value}
                  onClick={() => setTierFilter(item.value)}
                  size="small"
                  type={tierFilter === item.value ? "primary" : "default"}
                >
                  {item.label}
                </Button>
              ))}
              <span className="text-xs font-black text-[#7b756d]">行业筛选</span>
              <Button
                onClick={() => setIndustryFilter("all")}
                size="small"
                type={industryFilter === "all" ? "primary" : "default"}
              >
                全部行业
              </Button>
              {industryStats.slice(0, 6).map((item) => (
                <Button
                  key={item.industry}
                  onClick={() => setIndustryFilter(item.industry)}
                  size="small"
                  type={industryFilter === item.industry ? "primary" : "default"}
                >
                  {item.industry}
                </Button>
              ))}
            </Space>
          </div>
          <div className="workbench-panel-divider flex flex-wrap items-center gap-3 border-b px-4 py-3 text-xs text-[#7b756d]">
            <span className="font-black text-[#11100e]">高开风险阈值</span>
            <InputNumber
              className="w-[96px]"
              max={20}
              min={1}
              onChange={(value) => setHighOpenRiskThreshold(Number(value ?? 7))}
              precision={1}
              size="small"
              step={0.5}
              value={highOpenRiskThreshold}
            />
            <span>% 以上纳入风险观察。{concentration.message}</span>
          </div>
          <div className="p-4">
            <AuctionTable
              items={visibleItems}
              loading={loading}
              onAddToWatchlist={handleAddToWatchlist}
              savingSymbol={watchlistSavingSymbol}
            />
          </div>
        </section>

        <aside className="space-y-4">
          <section className="workbench-panel rounded-xl border">
            <div className="workbench-panel-divider border-b px-4 py-3">
              <div className="text-sm font-black text-[#11100e]">风险与观察</div>
              <div className="text-xs text-[#7b756d]">高开过热、低开偏弱和低开转强观察集中在这里。</div>
            </div>
            <div className="space-y-2 p-4">
              {loading ? (
                <SkeletonRows />
              ) : observationItems.length ? (
                observationItems.map((item) => <RiskRow item={item} key={item.symbol} />)
              ) : (
                <Empty description="暂无风险或观察提示" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>
          </section>

          <section className="workbench-panel rounded-xl border">
            <div className="workbench-panel-divider border-b px-4 py-3">
              <div className="text-sm font-black text-[#11100e]">行业聚合</div>
              <div className="text-xs text-[#7b756d]">主线集中度：{concentration.label}。点击行业可筛选左侧表格。</div>
            </div>
            <div className="space-y-3 p-4">
              {loading ? (
                <SkeletonRows />
              ) : industryStats.length ? (
                industryStats.map((item) => (
                  <IndustryRow
                    active={industryFilter === item.industry}
                    item={item}
                    key={item.industry}
                    onClick={() => setIndustryFilter(item.industry)}
                    totalCount={data?.items.length ?? 0}
                  />
                ))
              ) : (
                <Empty description="暂无行业数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </div>
          </section>

          <section className="workbench-panel rounded-xl border">
            <div className="workbench-panel-divider border-b px-4 py-3">
              <div className="text-sm font-black text-[#11100e]">数据源状态</div>
              <div className="text-xs text-[#7b756d]">第一版为 REST 快照，自动采样和 WebSocket 留到下一版。</div>
            </div>
            <div className="space-y-2 p-4">
              {(data?.source_status ?? []).map((item, index) => (
                <div className="rounded-lg border border-[#e3ddd3] bg-white p-3 text-xs" key={`${item.source}-${index}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-black text-[#11100e]">{item.source}</span>
                    <Tag color={item.status === "success" ? "green" : "orange"}>{item.status}</Tag>
                  </div>
                  <div className="mt-1 leading-5 text-[#7b756d]">{item.detail}</div>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function IndustryRow({
  active,
  item,
  onClick,
  totalCount,
}: {
  active: boolean;
  item: IndustryAuctionStat;
  onClick: () => void;
  totalCount: number;
}) {
  const percent = totalCount > 0 ? Math.round((item.count / totalCount) * 100) : 0;
  return (
    <button
      className={`w-full rounded-lg border bg-white p-3 text-left text-xs transition ${
        active ? "border-[#d92d20]" : "border-[#e3ddd3] hover:border-[#c9bca8]"
      }`}
      onClick={onClick}
      type="button"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-black text-[#11100e]">{item.industry}</span>
        <span className="font-black text-[#d92d20]">{item.count} 只</span>
      </div>
      <Progress className="my-2" percent={percent} showInfo={false} strokeColor="#d92d20" />
      <div className="grid grid-cols-3 gap-2 text-[#7b756d]">
        <span>均开 {formatPct(item.avgOpenGapPct)}</span>
        <span>强势 {item.strongCount}</span>
        <span>{formatCny(item.turnoverCny)}</span>
      </div>
    </button>
  );
}

function AuctionTable({
  items,
  loading,
  onAddToWatchlist,
  savingSymbol,
}: {
  items: AuctionSnapshotItem[];
  loading: boolean;
  onAddToWatchlist: (item: AuctionSnapshotItem) => void;
  savingSymbol: string | null;
}) {
  return (
    <Table<AuctionSnapshotItem>
      columns={[
        {
          title: "股票",
          dataIndex: "name",
          render: (_, item) => (
            <Link className="font-black text-[#11100e]" href={`/stock/${item.symbol}`}>
              {item.name || item.symbol}
              <span className="ml-2 text-xs font-semibold text-[#7b756d]">{item.symbol}</span>
            </Link>
          ),
        },
        {
          title: "行业",
          dataIndex: "industry",
          render: (value: string | null) => (
            <Typography.Text className="text-xs text-[#7b756d]">{value || "--"}</Typography.Text>
          ),
        },
        {
          title: "竞价强度",
          dataIndex: "auction_score",
          render: (value: number) => (
            <div className="min-w-[120px]">
              <Progress percent={Math.max(0, Math.min(value, 100))} showInfo={false} strokeColor="#d92d20" />
              <div className="mt-1 text-xs font-black text-[#11100e]">{value.toFixed(1)}</div>
            </div>
          ),
          sorter: (a, b) => a.auction_score - b.auction_score,
        },
        {
          title: "当前涨幅",
          dataIndex: "current_pct_change",
          render: (value: number | null) => <PctValue value={value} />,
          sorter: (a, b) => (a.current_pct_change ?? -999) - (b.current_pct_change ?? -999),
        },
        {
          title: "开盘幅度",
          dataIndex: "open_gap_pct",
          render: (value: number | null) => <PctValue value={value} />,
          sorter: (a, b) => (a.open_gap_pct ?? -999) - (b.open_gap_pct ?? -999),
        },
        {
          title: "成交额",
          dataIndex: "turnover_cny",
          render: (value: number | null) => formatCny(value),
          sorter: (a, b) => (a.turnover_cny ?? 0) - (b.turnover_cny ?? 0),
        },
        {
          title: "分层",
          dataIndex: "tier",
          render: (_, item) => (
            <div className="min-w-[180px]">
              <Tag color={tierColor(item.tier)}>{tierLabel(item.tier)}</Tag>
              <div className="mt-1 line-clamp-2 text-xs leading-5 text-[#7b756d]">{item.action_note}</div>
            </div>
          ),
        },
        {
          title: "操作",
          dataIndex: "symbol",
          render: (_, item) => (
            <Button
              loading={savingSymbol === item.symbol}
              onClick={() => onAddToWatchlist(item)}
              size="small"
              type="link"
            >
              加入自选
            </Button>
          ),
        },
      ]}
      dataSource={items}
      loading={loading}
      pagination={{ pageSize: 20, showSizeChanger: true, size: "small" }}
      rowKey="symbol"
      size="small"
    />
  );
}

function RiskRow({ item }: { item: AuctionSnapshotItem }) {
  return (
    <Link
      className="block rounded-lg border border-[#e3ddd3] bg-white p-3 no-underline transition hover:border-[#c9bca8]"
      href={`/stock/${item.symbol}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-black text-[#11100e]">{item.name || item.symbol}</span>
        <span className="text-xs font-black text-[#d92d20]">{formatPct(item.open_gap_pct)}</span>
      </div>
      <div className="mt-1 text-xs text-[#7b756d]">{item.symbol}</div>
      <div className="mt-1 text-xs text-[#7b756d]">行业 {item.industry || "--"}</div>
      <div className="mt-2 flex flex-wrap gap-1">
        {item.risk_flags.map((flag) => (
          <Tag color="orange" key={flag}>
            {flag}
          </Tag>
        ))}
      </div>
    </Link>
  );
}

function MetricCard({
  formatter,
  label,
  suffix,
  tone = "ink",
  value,
}: {
  formatter?: (value: number | null) => string;
  label: string;
  suffix?: string;
  tone?: "red" | "amber" | "ink";
  value: number | null;
}) {
  const toneClass = tone === "red" ? "text-[#d92d20]" : tone === "amber" ? "text-[#b45309]" : "text-[#11100e]";
  return (
    <div className="workbench-panel rounded-xl border bg-white px-4 py-3">
      <div className="text-xs font-black text-[#7b756d]">{label}</div>
      <div className={`mt-2 text-2xl font-black ${toneClass}`}>
        {formatter ? formatter(value) : value === null ? "--" : value}
        {!formatter && suffix ? <span className="ml-1 text-sm font-semibold text-[#7b756d]">{suffix}</span> : null}
      </div>
    </div>
  );
}

function SkeletonRows() {
  return (
    <>
      {[0, 1, 2, 3].map((item) => (
        <div className="rounded-lg border border-[#e3ddd3] bg-white p-3" key={item}>
          <div className="h-4 w-2/3 rounded bg-[#eee9df]" />
          <div className="mt-2 h-3 w-1/2 rounded bg-[#eee9df]" />
        </div>
      ))}
    </>
  );
}

function PctValue({ value }: { value: number | null }) {
  return (
    <span className={value !== null && value >= 0 ? "text-[#d92d20]" : "market-green-text"}>
      {formatPct(value)}
    </span>
  );
}

function tierLabel(value: AuctionSnapshotItem["tier"]): string {
  if (value === "strong_high_open") {
    return "强势高开";
  }
  if (value === "volume_leader") {
    return "放量活跃";
  }
  if (value === "risk_overheat") {
    return "高开过热";
  }
  if (value === "weak_low_open") {
    return "低开偏弱";
  }
  if (value === "reversal_watch") {
    return "低开观察";
  }
  return "中性";
}

function tierColor(value: AuctionSnapshotItem["tier"]): string {
  if (value === "risk_overheat") {
    return "orange";
  }
  if (value === "weak_low_open") {
    return "green";
  }
  if (value === "reversal_watch") {
    return "blue";
  }
  if (value === "volume_leader") {
    return "purple";
  }
  if (value === "strong_high_open") {
    return "red";
  }
  return "default";
}

function sessionLabel(value: string | null | undefined): string {
  if (value === "call_auction") {
    return "集合竞价中";
  }
  if (value === "pre_open") {
    return "开盘前撮合";
  }
  if (value === "continuous") {
    return "连续竞价";
  }
  if (value === "closed") {
    return "非交易时段";
  }
  return "等待数据";
}

function sessionColor(value: string | null | undefined): string {
  if (value === "call_auction" || value === "pre_open") {
    return "red";
  }
  if (value === "continuous") {
    return "green";
  }
  return "default";
}

function formatPct(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
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

function buildIndustryStats(items: AuctionSnapshotItem[]): IndustryAuctionStat[] {
  const stats = new Map<string, { count: number; gapTotal: number; gapCount: number; strongCount: number; turnoverCny: number }>();
  for (const item of items) {
    const industry = item.industry || "未标注";
    const current = stats.get(industry) ?? {
      count: 0,
      gapCount: 0,
      gapTotal: 0,
      strongCount: 0,
      turnoverCny: 0,
    };
    current.count += 1;
    current.turnoverCny += item.turnover_cny ?? 0;
    if (item.open_gap_pct !== null) {
      current.gapCount += 1;
      current.gapTotal += item.open_gap_pct;
      if (item.open_gap_pct >= 3) {
        current.strongCount += 1;
      }
    }
    stats.set(industry, current);
  }
  return Array.from(stats.entries())
    .map(([industry, value]) => ({
      avgOpenGapPct: value.gapCount ? value.gapTotal / value.gapCount : null,
      count: value.count,
      industry,
      strongCount: value.strongCount,
      turnoverCny: value.turnoverCny,
    }))
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }
      return right.turnoverCny - left.turnoverCny;
    })
    .slice(0, 8);
}

function buildIndustryConcentration(stats: IndustryAuctionStat[], totalCount: number): { label: string; message: string } {
  const top = stats[0];
  if (!top || totalCount <= 0) {
    return { label: "--", message: "主线集中度暂无数据。" };
  }
  const ratio = (top.count / totalCount) * 100;
  const label = `${top.industry} ${ratio.toFixed(0)}%`;
  if (ratio >= 18) {
    return { label, message: `主线集中度偏高，${top.industry} 是当前竞价首要观察方向。` };
  }
  if (ratio >= 10) {
    return { label, message: `主线集中度中等，${top.industry} 有一定聚集但仍需看开盘延续。` };
  }
  return { label, message: "主线集中度分散，早盘不要急着押单一方向。" };
}

function buildAuctionWatchlistNote(item: AuctionSnapshotItem): string {
  return [
    "来源：竞价雷达",
    `行业：${item.industry || "--"}`,
    `开盘幅度：${formatPct(item.open_gap_pct)}`,
    `当前涨幅：${formatPct(item.current_pct_change)}`,
    `成交额：${formatCny(item.turnover_cny)}`,
    `分层：${tierLabel(item.tier)}`,
    `操作备注：${item.action_note || "--"}`,
  ].join("；");
}
