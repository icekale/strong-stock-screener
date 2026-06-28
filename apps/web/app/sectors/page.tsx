"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Progress, Skeleton, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { getSectorRadar } from "../../lib/api";
import type { SectorRadarItem, SectorRadarResponse } from "../../lib/types";

type FlowMode = "inflow" | "outflow";

export default function SectorsPage() {
  const [data, setData] = useState<SectorRadarResponse | null>(null);
  const [mode, setMode] = useState<FlowMode>("inflow");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setData(await getSectorRadar(20));
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取板块资金流失败");
    } finally {
      setLoading(false);
    }
  }

  const activeItems = mode === "inflow" ? data?.inflow ?? [] : data?.outflow ?? [];
  const flowPrefix = data?.capital_flow_status === "direct" ? "资金净额" : "估算净额";
  const sourceSummary = useMemo(() => {
    if (!data) {
      return "等待数据源返回";
    }
    const success = data.source_status.filter((item) => item.status === "success").map((item) => item.source);
    return success.length > 0 ? success.join(" / ") : "暂无可用数据源";
  }, [data]);

  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Typography.Title className="m-0 text-[#11100e]" level={3}>
            板块资金流
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            按全市场板块热度、成交额和涨跌额追踪盘中资金方向。
          </Typography.Text>
        </div>
        <Space wrap>
          <Tag color={data?.capital_flow_status === "direct" ? "green" : "orange"}>
            资金流口径：{data?.flow_source ?? "读取中"}
          </Tag>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void refresh()} type="primary">
            刷新数据
          </Button>
        </Space>
      </div>

      {error && <Alert className="mb-4" message={error} showIcon type="error" />}

      <section className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="workbench-panel overflow-hidden">
          <div className="workbench-panel-divider flex items-center justify-between px-4 py-3">
            <div>
              <div className="text-sm font-black text-[#11100e]">资金流排行</div>
              <div className="text-xs text-[#7b756d]">显示 20 个板块</div>
            </div>
            <div className="rounded-lg bg-[#f5f3f0] p-1">
              <button
                className={`rounded-md px-3 py-1 text-xs font-black ${mode === "inflow" ? "bg-white text-[#c9302c] shadow-sm" : "text-[#7b756d]"}`}
                onClick={() => setMode("inflow")}
                type="button"
              >
                净流入
              </button>
              <button
                className={`rounded-md px-3 py-1 text-xs font-black ${mode === "outflow" ? "bg-white text-[#0f7a3b] shadow-sm" : "text-[#7b756d]"}`}
                onClick={() => setMode("outflow")}
                type="button"
              >
                净流出
              </button>
            </div>
          </div>
          {loading && !data ? (
            <div className="p-4">
              <Skeleton active paragraph={{ rows: 9 }} title={false} />
            </div>
          ) : (
            <div className="max-h-[calc(100vh-190px)] overflow-y-auto">
              {activeItems.map((item, index) => (
                <button
                  className="flex w-full items-center justify-between border-b border-[#ece7df] px-4 py-3 text-left transition hover:bg-[#faf8f5]"
                  key={`${mode}-${item.name}`}
                  type="button"
                >
                  <div className="min-w-0">
                    <div className="truncate text-base font-black text-[#11100e]">{item.name}</div>
                    <div className="mt-1 text-xs text-[#7b756d]">
                      #{index + 1} · {item.leader ?? "暂无领涨股"} · {formatChange(item.change_pct)}
                    </div>
                  </div>
                  <div className={mode === "inflow" ? "text-right font-black text-[#d92d20]" : "text-right font-black text-[#0f7a3b]"}>
                    {formatCny(item.net_flow_cny)}
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="border-t border-[#ece7df] bg-[#fff7ed] px-4 py-3 text-xs leading-5 text-[#8a4b12]">
            风险提示：资金流数据存在滞后与口径差异，仅用于盘中观察，不构成投资建议。
          </div>
        </aside>

        <section className="workbench-panel min-w-0">
          <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div>
              <div className="text-xs font-black text-[#7b756d]">实时资金流明细</div>
              <Typography.Title className="m-0 text-[#11100e]" level={4}>
                板块资金流排行
              </Typography.Title>
              <div className="text-xs text-[#7b756d]">
                {data?.trade_date ?? "--"} · 数据源：{sourceSummary}
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs font-black text-[#7b756d]">净流入合计</div>
              <div className="text-2xl font-black text-[#d92d20]">{formatCny(sumFlow(data?.inflow ?? []))}</div>
            </div>
          </div>

          <div className="grid gap-4 p-4 xl:grid-cols-2">
            <FlowChartCard items={data?.inflow ?? []} title={`板块资金流 · ${flowPrefix}流入`} tone="red" />
            <FlowChartCard items={data?.outflow ?? []} title={`板块资金流 · ${flowPrefix}流出`} tone="green" />
          </div>

          <div className="border-t border-[#ece7df] p-4">
            <Table
              columns={columns}
              dataSource={[...(data?.inflow ?? []), ...(data?.outflow ?? [])]}
              loading={loading}
              pagination={{ pageSize: 12, showSizeChanger: false }}
              rowKey={(item) => item.name}
              size="small"
            />
          </div>
        </section>
      </section>
    </main>
  );
}

function FlowChartCard({ items, title, tone }: { items: SectorRadarItem[]; title: string; tone: "red" | "green" }) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.net_flow_cny ?? 0)), 1);
  return (
    <div className="rounded-xl border border-[#e3ddd3] bg-white">
      <div className="border-b border-[#ece7df] px-4 py-3">
        <div className="text-sm font-black text-[#11100e]">{title}</div>
        <div className="text-xs text-[#7b756d]">按净额排序，显示前 20 个板块</div>
      </div>
      <div className="space-y-3 p-4">
        {items.slice(0, 20).map((item) => (
          <div className="grid grid-cols-[88px_minmax(0,1fr)_72px] items-center gap-3" key={item.name}>
            <div className="truncate text-xs font-semibold text-[#433f38]">{item.name}</div>
            <Progress
              percent={Math.max(2, Math.round((Math.abs(item.net_flow_cny ?? 0) / maxValue) * 100))}
              railColor="#f0ebe4"
              showInfo={false}
              size={["100%", 10]}
              strokeColor={tone === "red" ? "#ef4444" : "#16a34a"}
            />
            <div className={tone === "red" ? "text-xs font-black text-[#d92d20]" : "text-xs font-black text-[#0f7a3b]"}>
              {formatCny(item.net_flow_cny)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const columns: ColumnsType<SectorRadarItem> = [
  {
    title: "板块",
    dataIndex: "name",
    fixed: "left",
    render: (value: string, item) => (
      <div>
        <div className="font-black text-[#11100e]">{value}</div>
        <div className="text-xs text-[#7b756d]">领涨：{item.leader ?? "--"}</div>
      </div>
    ),
  },
  {
    title: "净额",
    dataIndex: "net_flow_cny",
    sorter: (a, b) => (a.net_flow_cny ?? 0) - (b.net_flow_cny ?? 0),
    render: (value: number | null) => (
      <span className={(value ?? 0) >= 0 ? "font-black text-[#d92d20]" : "font-black text-[#0f7a3b]"}>
        {formatCny(value)}
      </span>
    ),
  },
  {
    title: "涨跌幅",
    dataIndex: "change_pct",
    render: (value: number | null) => formatChange(value),
  },
  {
    title: "成交额",
    dataIndex: "turnover_cny",
    render: (value: number | null) => formatCny(value),
  },
  {
    title: "涨跌家数",
    render: (_, item) => `${item.advance_count ?? "--"} / ${item.decline_count ?? "--"}`,
  },
  {
    title: "强度",
    dataIndex: "strength_score",
    sorter: (a, b) => a.strength_score - b.strength_score,
    render: (value: number) => value.toFixed(1),
  },
];

function sumFlow(items: SectorRadarItem[]): number {
  return items.reduce((sum, item) => sum + (item.net_flow_cny ?? 0), 0);
}

function formatChange(value: number | null): string {
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
