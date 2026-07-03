"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Checkbox, Empty, Segmented, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import * as echarts from "echarts";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { addWatchlistPoolItem, getSectorWorkbench } from "../../lib/api";
import { buildStockDetailHref } from "../../lib/stockNavigation";
import type {
  SectorWorkbenchMode,
  SectorWorkbenchResponse,
  SectorWorkbenchSeries,
  SectorWorkbenchStock,
  SectorWorkbenchTheme,
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
          scope: "auto",
          selected: selectedThemes,
          stockLimit: 80,
        });
        if (ignore) {
          return;
        }
        setData(response);
        if (response.selected_themes.length > 0 && response.selected_themes.join(",") !== selectedThemes.join(",")) {
          setSelectedThemes(response.selected_themes);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "读取题材工作台失败");
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

  const sourceSummary = useMemo(() => {
    const first = data?.source_status.find((item) => item.status === "success") ?? data?.source_status[0];
    return first ? `${first.source} · ${first.detail}` : "等待数据源";
  }, [data]);

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
        void messageApi.warning("最多同时对比 5 个题材");
        return current;
      }
      return [...current, name];
    });
  }

  async function addToWatchlist(item: SectorWorkbenchStock) {
    setAddingSymbol(item.symbol);
    try {
      await addWatchlistPoolItem({
        group: "题材观察",
        industry: item.industry,
        name: item.name,
        note: "从题材强度工作台加入",
        symbol: item.symbol,
        tags: ["题材", ...item.themes.slice(0, 6)],
      });
      void messageApi.success(`${item.name ?? item.symbol} 已加入自选`);
    } catch (err) {
      void messageApi.error(err instanceof Error ? err.message : "加入自选失败");
    } finally {
      setAddingSymbol(null);
    }
  }

  return (
    <section className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
      {contextHolder}
      <aside className="workbench-panel overflow-hidden rounded-xl border">
        <div className="grid grid-cols-2 border-b border-[#ddd8d0] bg-[#f8f7f4] p-2">
          <Segmented
            block
            className="col-span-2"
            onChange={(value) => setMode(value as SectorWorkbenchMode)}
            options={MODE_OPTIONS}
            value={mode}
          />
        </div>
        <div className="border-b border-[#ddd8d0] px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-sm font-black text-[#11100e]">题材多选</div>
              <div className="text-xs text-[#7b756d]">
                {mode === "strength" ? "按强度、涨停和扩散度排序" : "按资金确认强弱排序"}
              </div>
            </div>
            <Button icon={<ReloadOutlined />} loading={loading} onClick={() => setRefreshKey((value) => value + 1)} size="small">
              刷新
            </Button>
          </div>
        </div>

        {loading && !data ? (
          <div className="p-4">
            <Skeleton active paragraph={{ rows: 10 }} title={false} />
          </div>
        ) : (
          <div className="max-h-[calc(100vh-250px)] overflow-y-auto p-2">
            {(data?.themes ?? []).map((theme) => (
              <ThemeSelectorItem
                checked={selectedSet.has(theme.name)}
                key={theme.name}
                mode={mode}
                onChange={(checked) => toggleTheme(theme.name, checked)}
                theme={theme}
              />
            ))}
            {data && data.themes.length === 0 && <Empty description="暂无题材数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </div>
        )}

        <div className="border-t border-[#ddd8d0] bg-[#fff7ed] px-4 py-3 text-xs leading-5 text-[#8a4b12]">
          {data?.scope === "industry" ? "行业兜底：概念映射不可用，当前按行业聚合。" : "概念/题材优先：行情来自 TickFlow，题材映射来自补充数据源。"}
        </div>
      </aside>

      <section className="min-w-0 space-y-4">
        {error && <Alert showIcon title={error} type="error" />}

        <div className="workbench-panel rounded-xl border">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#ddd8d0] px-4 py-3">
            <div>
              <div className="text-xs font-black text-[#7b756d]">双模式分时</div>
              <Typography.Title className="m-0 text-[#11100e]" level={4}>
                {mode === "strength" ? "板块强度分时" : "主力流入分时"}
              </Typography.Title>
              <div className="mt-1 text-xs text-[#7b756d]">
                {data?.trade_date ?? "--"} · {sourceSummary}
              </div>
            </div>
            <Space wrap>
              <Tag color={data?.scope === "theme" ? "red" : "orange"}>{data?.scope === "theme" ? "概念/题材" : "行业兜底"}</Tag>
              <Tag color={mode === "strength" ? "blue" : "purple"}>{mode === "strength" ? "强度口径" : "资金口径"}</Tag>
              {data?.themes.some((item) => item.flow_status === "estimated") && <Tag color="orange">估算口径</Tag>}
            </Space>
          </div>
          <div className="p-4">
            <SectorIntradayChart mode={mode} series={data?.series ?? []} />
          </div>
        </div>

        <div className="workbench-panel rounded-xl border px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-black text-[#7b756d]">关联子题材</span>
            {(data?.related_tags ?? []).slice(0, 12).map((tag) => (
              <Tag className="m-0" key={tag}>
                {tag}
              </Tag>
            ))}
            {data && data.related_tags.length === 0 && <span className="text-xs text-[#7b756d]">暂无关联题材</span>}
          </div>
        </div>

        <div className="workbench-panel rounded-xl border">
          <div className="flex items-center justify-between border-b border-[#ddd8d0] px-4 py-3">
            <div>
              <div className="text-sm font-black text-[#11100e]">选中题材成分股</div>
              <div className="text-xs text-[#7b756d]">点击股票看 K 线，也可以直接加入题材观察自选组。</div>
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
  const value = mode === "strength" ? `${theme.limit_up_count}涨停` : formatCny(theme.main_flow_cny);
  return (
    <label
      className={`mb-2 flex cursor-pointer gap-2 rounded-lg border p-3 transition ${
        checked ? "border-[#fca5a5] bg-[#fff1f2]" : "border-[#e5e0d8] bg-white hover:bg-[#faf8f5]"
      }`}
    >
      <Checkbox checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-black text-[#11100e]">{theme.name}</span>
          <span className={mode === "strength" ? "shrink-0 text-xs font-black text-[#d92d20]" : "shrink-0 text-xs font-black text-[#7c3aed]"}>
            {value}
          </span>
        </div>
        <div className="mt-1 truncate text-xs text-[#7b756d]">
          强度 {theme.strength_score.toFixed(1)} · 成交 {formatCny(theme.turnover_cny)} · 领涨 {theme.leader ?? "--"}
        </div>
      </div>
    </label>
  );
}

function SectorIntradayChart({ mode, series }: { mode: SectorWorkbenchMode; series: SectorWorkbenchSeries[] }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const hasData = series.some((item) => item.points.length > 0);

  useEffect(() => {
    if (!chartRef.current || !hasData) {
      return;
    }
    const chart = echarts.init(chartRef.current);
    const times = Array.from(new Set(series.flatMap((item) => item.points.map((point) => point.time))));
    chart.setOption({
      color: ["#d92d20", "#f59e0b", "#7c3aed", "#2563eb", "var(--market-green-fill)"],
      grid: { bottom: 36, left: 56, right: 28, top: 24 },
      legend: { top: 0, type: "scroll" },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value: unknown) =>
          mode === "main_flow" && typeof value === "number" ? formatCny(value) : String(value ?? "--"),
      },
      xAxis: { axisTick: { show: false }, data: times, type: "category" },
      yAxis: {
        axisLabel: {
          formatter: (value: number) => (mode === "main_flow" ? formatCompactNumber(value) : String(value)),
        },
        splitLine: { lineStyle: { color: "#eee9df" } },
        type: "value",
      },
      series: series.map((item) => {
        const pointByTime = new Map(item.points.map((point) => [point.time, point.value]));
        return {
          data: times.map((time) => pointByTime.get(time) ?? null),
          name: item.name,
          showSymbol: times.length < 12,
          smooth: true,
          type: "line",
        };
      }),
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [hasData, mode, series]);

  if (!hasData) {
    return <Empty className="py-12" description="暂无分时采样数据，刷新后开始积累曲线" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return <div className="h-[320px] w-full" ref={chartRef} />;
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
      title: "题材",
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
