"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Checkbox, Empty, Segmented, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import * as echarts from "echarts";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { addWatchlistPoolItem, getSectorWorkbench, getSectorWorkbenchStatus } from "../../lib/api";
import { buildStockDetailHref } from "../../lib/stockNavigation";
import type {
  SectorWorkbenchMode,
  SectorWorkbenchResponse,
  SectorWorkbenchSeries,
  SectorWorkbenchStatusResponse,
  SectorWorkbenchStock,
  SectorWorkbenchTheme,
  StrongStockSourceStatus,
} from "../../lib/types";

const MODE_OPTIONS: Array<{ label: string; value: SectorWorkbenchMode }> = [
  { label: "板块强度", value: "strength" },
  { label: "主力流入", value: "main_flow" },
];

export function SectorThemeWorkbench() {
  const [messageApi, contextHolder] = message.useMessage();
  const [mode, setMode] = useState<SectorWorkbenchMode>("strength");
  const [selectedThemes, setSelectedThemes] = useState<string[]>([]);
  const [data, setData] = useState<SectorWorkbenchResponse | null>(null);
  const [status, setStatus] = useState<SectorWorkbenchStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [addingSymbol, setAddingSymbol] = useState<string | null>(null);
  const selectedKey = selectedThemes.join(",");

  useEffect(() => {
    let ignore = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await getSectorWorkbench({
          limit: 30,
          mode,
          scope: "industry",
          selected: selectedThemes,
          stockLimit: 80,
        });
        if (ignore) {
          return;
        }
        setData(response);
        void loadWorkbenchStatus(response.trade_date);
        if (response.selected_themes.length > 0 && response.selected_themes.join(",") !== selectedThemes.join(",")) {
          setSelectedThemes(response.selected_themes);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "读取行业工作台失败");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      ignore = true;
    };
  }, [mode, refreshKey, selectedKey]);

  async function loadWorkbenchStatus(tradeDate?: string | null) {
    setStatusLoading(true);
    try {
      setStatus(await getSectorWorkbenchStatus(tradeDate));
    } catch {
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }

  const sourceSummary = useMemo(() => {
    const first = data?.source_status.find((item) => item.status === "success") ?? data?.source_status[0];
    return first ? `${first.source} · ${first.detail}` : "等待数据源";
  }, [data]);
  const intradayStatus = useMemo(
    () => data?.source_status.find((item) => item.source.includes("分钟线")) ?? null,
    [data],
  );

  const selectedSet = useMemo(() => new Set(selectedThemes), [selectedThemes]);

  function toggleTheme(name: string, checked: boolean) {
    setSelectedThemes((current) => {
      if (!checked) {
        return current.filter((item) => item !== name);
      }
      if (current.includes(name)) {
        return current;
      }
      if (current.length >= 5) {
        void messageApi.warning("最多同时对比 5 个行业");
        return current;
      }
      return [...current, name];
    });
  }

  async function addToWatchlist(item: SectorWorkbenchStock) {
    setAddingSymbol(item.symbol);
    try {
      await addWatchlistPoolItem({
        group: "行业观察",
        industry: item.industry,
        name: item.name,
        note: "从行业强度工作台加入",
        symbol: item.symbol,
        tags: ["行业", ...item.themes.slice(0, 6)],
      });
      void messageApi.success(`${item.name ?? item.symbol} 已加入自选`);
    } catch (err) {
      void messageApi.error(err instanceof Error ? err.message : "加入自选失败");
    } finally {
      setAddingSymbol(null);
    }
  }

  return (
    <section className="grid gap-3 xl:grid-cols-[340px_minmax(0,1fr)]">
      {contextHolder}
      <aside className="workbench-panel overflow-hidden rounded-xl border">
        <div className="border-b border-[#ddd8d0] bg-[#f8f7f4] px-3 py-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-black text-[#7b756d]">工作模式</div>
            <Button icon={<ReloadOutlined />} loading={loading} onClick={() => setRefreshKey((value) => value + 1)} size="small">
              刷新
            </Button>
          </div>
          <Segmented
            block
            onChange={(value) => setMode(value as SectorWorkbenchMode)}
            options={MODE_OPTIONS}
            value={mode}
          />
        </div>
        <div className="border-b border-[#ddd8d0] px-3 py-2.5">
          <div className="flex items-end justify-between gap-2">
            <div className="text-sm font-black text-[#11100e]">行业多选</div>
            <div className="text-[11px] font-bold text-[#7b756d]">{selectedThemes.length}/5</div>
          </div>
          <div className="mt-0.5 text-xs text-[#7b756d]">
            {mode === "strength" ? "按强度、涨幅和扩散度排序" : "按资金确认强弱排序"}
          </div>
        </div>

        {loading && !data ? (
          <div className="p-4">
            <Skeleton active paragraph={{ rows: 10 }} title={false} />
          </div>
        ) : (
          <div className="max-h-[calc(100vh-238px)] overflow-y-auto">
            {(data?.themes ?? []).map((theme) => (
              <ThemeSelectorItem
                checked={selectedSet.has(theme.name)}
                key={theme.name}
                mode={mode}
                onChange={(checked) => toggleTheme(theme.name, checked)}
                theme={theme}
              />
            ))}
            {data && data.themes.length === 0 && <Empty description="暂无行业数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </div>
        )}

        <div className="border-t border-[#ddd8d0] bg-[#fff7ed] px-3 py-3 text-xs leading-5 text-[#8a4b12]">
          行业指数：当前按全A行业聚合；稳定同花顺概念指数接入后再开放概念模式。
        </div>
      </aside>

      <section className="min-w-0 space-y-3">
        {error && <Alert showIcon title={error} type="error" />}

        <div className="workbench-panel overflow-hidden rounded-xl border">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#ddd8d0] px-4 py-3">
            <div>
              <div className="text-xs font-black text-[#7b756d]">双模式分时 · {mode === "strength" ? "热度曲线" : "资金流向"}</div>
              <Typography.Title className="m-0 text-[#11100e]" level={4}>
                {mode === "strength" ? "板块强度分时" : "主力流入分时"}
              </Typography.Title>
              <div className="mt-1 text-xs text-[#7b756d]">
                {data?.trade_date ?? "--"} · {sourceSummary}
              </div>
            </div>
            <Space wrap>
              <Tag color={data?.scope === "theme" ? "red" : "orange"}>{data?.scope === "theme" ? "概念/题材" : "行业指数"}</Tag>
              <Tag color={mode === "strength" ? "blue" : "purple"}>{mode === "strength" ? "强度口径" : "资金口径"}</Tag>
              {data?.themes.some((item) => item.flow_status === "estimated") && <Tag color="orange">估算口径</Tag>}
            </Space>
          </div>
          <SectorSamplingStatus sourceStatus={data?.source_status ?? []} status={status} statusLoading={statusLoading} />
          <div className="bg-white px-3 py-3">
            <SectorIntradayChart mode={mode} series={data?.series ?? []} sourceStatus={intradayStatus} />
          </div>
          <div className="border-t border-[#ece7df] bg-[#faf8f5] px-4 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-black text-[#7b756d]">相关板块</span>
              {(data?.related_tags ?? []).slice(0, 12).map((tag) => (
                <Tag className="m-0" key={tag}>
                  {tag}
                </Tag>
              ))}
              {data && data.related_tags.length === 0 && <span className="text-xs text-[#7b756d]">暂无相关板块</span>}
            </div>
          </div>
        </div>

        <div className="workbench-panel rounded-xl border">
          <div className="flex items-center justify-between border-b border-[#ddd8d0] px-4 py-3">
            <div>
              <div className="text-sm font-black text-[#11100e]">选中行业成分股</div>
              <div className="text-xs text-[#7b756d]">点击股票看 K 线，也可以直接加入行业观察自选组。</div>
            </div>
            <div className="text-xs font-black text-[#7b756d]">{data?.stocks.length ?? 0} 只</div>
          </div>
          <div className="p-4">
            <Table
              columns={stockColumns({ addingSymbol, addToWatchlist })}
              dataSource={data?.stocks ?? []}
              loading={loading}
              pagination={{ pageSize: 12, showSizeChanger: false }}
              rowKey={(item) => item.symbol}
              scroll={{ x: 980 }}
              size="small"
            />
          </div>
        </div>
      </section>
    </section>
  );
}

function SectorSamplingStatus({
  sourceStatus,
  status,
  statusLoading,
}: {
  sourceStatus: StrongStockSourceStatus[];
  status: SectorWorkbenchStatusResponse | null;
  statusLoading: boolean;
}) {
  const cacheCount = status?.cache.sample_count ?? 0;
  const latestSample = formatDateTime(status?.cache.latest_sampled_at ?? null);
  const hasFailedSource = [...sourceStatus, ...(status?.source_status ?? [])].some((item) =>
    ["failed", "missing_key"].includes(item.status),
  );
  const hasStaleSource = [...sourceStatus, ...(status?.source_status ?? [])].some((item) => item.status === "stale");
  const trustLabel = hasFailedSource
    ? "可信度：降级"
    : cacheCount > 0
      ? "可信度：缓存可追溯"
      : hasStaleSource
        ? "可信度：等待采样"
        : "可信度：正常";
  return (
    <div className="border-b border-[#ece7df] bg-[#faf8f5] px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-black text-[#7b756d]">采样状态</span>
        <Tag className="m-0" color={status?.sample_window_open ? "blue" : "default"}>
          {status?.sample_window_open ? "交易时段" : "非采样窗口"}
        </Tag>
        <Tag className="m-0" color={status?.sampler_running ? "green" : status?.sampler_enabled ? "orange" : "default"}>
          {status?.sampler_running ? "后台采样运行中" : status?.sampler_enabled ? "采样器待启动" : "采样器禁用"}
        </Tag>
        <Tag className="m-0" color={cacheCount > 0 ? "green" : "orange"}>
          缓存点 {statusLoading ? "..." : cacheCount}
        </Tag>
        <Tag className="m-0" color={hasFailedSource ? "red" : hasStaleSource ? "orange" : "green"}>
          {trustLabel}
        </Tag>
        <span className="text-[#7b756d]">最近采样 {latestSample ?? "--"}</span>
      </div>
    </div>
  );
}

function ThemeSelectorItem({
  checked,
  mode,
  onChange,
  theme,
}: {
  checked: boolean;
  mode: SectorWorkbenchMode;
  onChange: (checked: boolean) => void;
  theme: SectorWorkbenchTheme;
}) {
  const value =
    mode === "strength"
      ? theme.scope === "theme"
        ? `${theme.limit_up_count}涨停`
        : `${theme.member_count}成分`
      : formatCny(theme.main_flow_cny);
  return (
    <label
      className={`flex cursor-pointer items-center gap-2 border-b px-3 py-2.5 transition ${
        checked ? "border-[#f2b8b5] bg-[#fff1f2]" : "border-[#ece7df] bg-[#f8f7f4] hover:bg-white"
      }`}
    >
      <Checkbox checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className={`truncate text-sm font-black ${checked ? "text-[#d92d20]" : "text-[#11100e]"}`}>
            {theme.name}
            <span className="ml-1 text-xs font-bold text-[#7b756d]">({formatScore(theme.strength_score)})</span>
          </span>
          <span className={mode === "strength" ? "shrink-0 text-xs font-black text-[#d92d20]" : "shrink-0 text-xs font-black text-[#7c3aed]"}>
            {value}
          </span>
        </div>
        <div className="mt-0.5 flex items-center justify-between gap-2 text-xs text-[#7b756d]">
          <span className="truncate">领涨 {theme.leader ?? "--"}</span>
          <span className="shrink-0">成交 {formatCny(theme.turnover_cny)}</span>
        </div>
      </div>
    </label>
  );
}

function SectorIntradayChart({
  mode,
  series,
  sourceStatus,
}: {
  mode: SectorWorkbenchMode;
  series: SectorWorkbenchSeries[];
  sourceStatus: StrongStockSourceStatus | null;
}) {
  const chartRef = useRef<HTMLDivElement>(null);
  const hasData = series.some((item) => item.points.length > 0);
  const sampleCount = Math.max(0, ...series.map((item) => item.points.length));
  const isIntradayUnavailable = Boolean(sourceStatus && sourceStatus.status !== "success");

  useEffect(() => {
    if (!chartRef.current || !hasData) {
      return;
    }
    const chart = echarts.init(chartRef.current);
    const times = buildTradingTimeAxis();
    chart.setOption({
      backgroundColor: "#fffdf8",
      animationDuration: 180,
      color: ["#ef4444", "#ff7a00", "#d946ef", "#78b65b", "#4169d8", "#14b8a6", "#a855f7", "#64748b"],
      grid: { bottom: 58, containLabel: true, left: 18, right: 30, top: 22 },
      legend: {
        icon: "circle",
        itemGap: 18,
        itemHeight: 9,
        itemWidth: 9,
        left: "center",
        bottom: 10,
        type: "scroll",
      },
      tooltip: {
        backgroundColor: "rgba(17, 16, 14, 0.92)",
        borderWidth: 0,
        textStyle: { color: "#fff" },
        axisPointer: {
          label: {
            backgroundColor: "#2b2925",
            color: "#fff",
          },
          lineStyle: {
            color: "#8f8a82",
            type: "dashed",
            width: 1,
          },
          type: "cross",
        },
        confine: true,
        trigger: "axis",
        valueFormatter: (value: unknown) =>
          mode === "main_flow" && typeof value === "number" ? formatCny(value) : formatHeatValue(value),
      },
      xAxis: {
        axisLabel: {
          color: "#7b756d",
          hideOverlap: true,
          interval: (_index: number, value: string) => isKeyTradingTime(value),
        },
        axisLine: { lineStyle: { color: "#cfc7ba" } },
        axisTick: { show: false },
        boundaryGap: false,
        data: times,
        type: "category",
      },
      yAxis: {
        axisLabel: {
          color: "#6f6a62",
          formatter: (value: number) => (mode === "main_flow" ? formatCompactNumber(value) : formatHeatAxis(value)),
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#ebe6dd", type: "solid" } },
        splitNumber: 6,
        type: "value",
      },
      series: series.map((item, index) => {
        const pointByTime = new Map(item.points.map((point) => [point.time, point.value]));
        return {
          data: times.map((time) => pointByTime.get(time) ?? null),
          emphasis: { focus: "series" },
          connectNulls: true,
          lineStyle: { width: index === 0 ? 1.9 : 1.45 },
          markLine:
            index === 0
              ? {
                  data: [{ name: "零轴", yAxis: 0 }],
                  label: {
                    color: "#8a4b12",
                    formatter: "{b}",
                    position: "end",
                    show: true,
                  },
                  lineStyle: { color: "#8f8a82", type: "solid", width: 1 },
                  silent: true,
                  symbol: "none",
                }
              : undefined,
          name: item.name,
          showSymbol: false,
          smooth: 0.12,
          symbol: "circle",
          symbolSize: 5,
          type: "line",
        };
      }),
    });
    const resizeObserver = new ResizeObserver(() => chart.resize());
    resizeObserver.observe(chartRef.current);
    return () => {
      resizeObserver.disconnect();
      chart.dispose();
    };
  }, [hasData, mode, series]);

  if (!hasData) {
    return <Empty className="py-16" description="暂无分时采样数据，刷新后开始积累曲线" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return (
    <div>
      {isIntradayUnavailable && (
        <div className="mb-3 rounded-lg border border-[#fed7aa] bg-[#fff7ed] px-3 py-2 text-xs leading-5 text-[#8a4b12]">
          <div className="font-black">TickFlow 分钟线暂不可用</div>
          <div>
            当前曲线使用快照采样兜底，可能暂时呈横线；分钟线恢复后会切回完整盘中曲线。{sourceStatus?.detail ? ` ${sourceStatus.detail}` : ""}
          </div>
        </div>
      )}
      {sampleCount < 4 && (
        <div className="mb-3 rounded-lg border border-[#bfdbfe] bg-[#eff6ff] px-3 py-2 text-xs leading-5 text-[#1d4ed8]">
          <div className="font-black">等待盘中采样积累</div>
          <div>当前采样点偏少，曲线会随刷新和后台采样逐步变得更连续。</div>
        </div>
      )}
      <div className="h-[520px] w-full" ref={chartRef} />
    </div>
  );
}

function isKeyTradingTime(value: string): boolean {
  return ["09:15", "09:25", "09:30", "10:00", "10:30", "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", "15:00"].includes(value);
}

function buildTradingTimeAxis(): string[] {
  return [...buildMinuteRange("09:15", "09:25"), ...buildMinuteRange("09:30", "11:30"), ...buildMinuteRange("13:00", "15:00")];
}

function buildMinuteRange(start: string, end: string): string[] {
  const output: string[] = [];
  const startMinute = tradingMinuteValue(start);
  const endMinute = tradingMinuteValue(end);
  for (let minute = startMinute; minute <= endMinute; minute += 1) {
    const hour = Math.floor(minute / 60);
    const rest = minute % 60;
    output.push(`${String(hour).padStart(2, "0")}:${String(rest).padStart(2, "0")}`);
  }
  return output;
}

function tradingMinuteValue(value: string): number {
  const [hour, minute] = value.split(":").map((part) => Number.parseInt(part, 10));
  return hour * 60 + minute;
}

function formatDateTime(value: string | null): string | null {
  if (!value) {
    return null;
  }
  return value.replace("T", " ").slice(0, 16);
}

function stockColumns({
  addingSymbol,
  addToWatchlist,
}: {
  addingSymbol: string | null;
  addToWatchlist: (item: SectorWorkbenchStock) => Promise<void>;
}): ColumnsType<SectorWorkbenchStock> {
  return [
    {
      title: "名称 / 代码",
      fixed: "left",
      width: 170,
      render: (_, item) => (
        <div className="min-w-0">
          <Link
            className="font-black text-[#11100e] hover:text-[#d92d20]"
            href={buildStockDetailHref(item.symbol, {
              from: "sectors",
              industry: item.industry,
              name: item.name,
            })}
          >
            {item.name ?? item.symbol}
          </Link>
          <div className="text-xs text-[#7b756d]">{item.symbol}</div>
        </div>
      ),
    },
    { title: "行业", dataIndex: "industry", width: 110, render: (value: string | null) => value ?? "--" },
    {
      title: "板块",
      dataIndex: "themes",
      width: 170,
      render: (themes: string[]) => (
        <div className="flex max-w-[170px] flex-wrap gap-1">
          {themes.slice(0, 2).map((theme) => (
            <Tag className="m-0" key={theme}>
              {theme}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: "涨幅",
      dataIndex: "pct_change",
      sorter: (a, b) => (a.pct_change ?? 0) - (b.pct_change ?? 0),
      width: 86,
      render: (value: number | null) => <span className={(value ?? 0) >= 0 ? "font-black text-[#d92d20]" : "font-black market-green-text"}>{formatPct(value)}</span>,
    },
    {
      title: "成交额",
      dataIndex: "turnover_cny",
      sorter: (a, b) => (a.turnover_cny ?? 0) - (b.turnover_cny ?? 0),
      width: 100,
      render: (value: number | null) => formatCny(value),
    },
    { title: "换手", dataIndex: "turnover_rate", width: 82, render: (value: number | null) => formatPct(value) },
    { title: "连板", dataIndex: "board_count", width: 72, render: (value: number) => (value > 0 ? `${value}板` : "--") },
    { title: "竞价", dataIndex: "auction_pct_change", width: 82, render: (value: number | null) => formatPct(value) },
    { title: "封单", dataIndex: "seal_amount_cny", width: 96, render: (value: number | null) => formatCny(value) },
    {
      title: "操作",
      fixed: "right",
      width: 140,
      render: (_, item) => (
        <Space size={4}>
          <Link
            href={buildStockDetailHref(item.symbol, {
              from: "sectors",
              industry: item.industry,
              name: item.name,
            })}
          >
            看K线
          </Link>
          <Button loading={addingSymbol === item.symbol} onClick={() => void addToWatchlist(item)} size="small" type="link">
            加入自选
          </Button>
        </Space>
      ),
    },
  ];
}

function formatPct(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatScore(value: number): string {
  return value >= 100 ? value.toFixed(0) : value.toFixed(1);
}

function formatHeatValue(value: unknown): string {
  if (typeof value !== "number") {
    return String(value ?? "--");
  }
  return formatHeatAxis(value);
}

function formatCny(value: number | null): string {
  if (value === null) {
    return "--";
  }
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 100_000_000) {
    return `${sign}${(abs / 100_000_000).toFixed(1)}亿`;
  }
  if (abs >= 10_000) {
    return `${sign}${(abs / 10_000).toFixed(0)}万`;
  }
  return `${sign}${abs.toFixed(0)}`;
}

function formatCompactNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(1)}亿`;
  }
  if (abs >= 10_000) {
    return `${(value / 10_000).toFixed(0)}万`;
  }
  return value.toFixed(0);
}

function formatHeatAxis(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 10_000) {
    return `${sign}${Math.round(abs).toLocaleString("zh-CN")}`;
  }
  return `${sign}${abs.toFixed(abs >= 100 ? 0 : 1)}`;
}
