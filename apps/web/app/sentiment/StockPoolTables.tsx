"use client";

import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import type { ShortTermSentimentStockItem } from "../../lib/types";

export type StockPoolTableProps = {
  dataSource: ShortTermSentimentStockItem[];
  loading: boolean;
  title: "涨停池" | "炸板池";
};

export function StockPoolTable({ dataSource, loading, title }: StockPoolTableProps) {
  return (
    <section className="workbench-panel min-w-0 overflow-hidden rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[var(--app-ink)]">{title}</div>
          <div className="text-xs text-[var(--app-muted)]">点击股票名称进入 K 线详情页。</div>
        </div>
        <Tag color={title === "涨停池" ? "red" : "green"}>{dataSource.length} 只</Tag>
      </div>
      <div className="w-full max-w-full overflow-x-auto">
        <Table
          columns={stockColumns}
          dataSource={dataSource}
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          rowKey={(item) => `${title}-${item.symbol}`}
          scroll={{ x: 680 }}
          size="small"
        />
      </div>
    </section>
  );
}

const stockColumns: ColumnsType<ShortTermSentimentStockItem> = [
  {
    title: "股票",
    dataIndex: "name",
    fixed: "left",
    render: (value: string, item) => (
      <Link className="font-black text-[var(--app-ink)] hover:text-[var(--app-primary)]" href={`/stock/${item.symbol}`}>
        {value}
        <span className="ml-2 text-xs font-semibold text-[var(--app-muted)]">{item.symbol}</span>
      </Link>
    ),
  },
  {
    title: "行业",
    dataIndex: "industry",
    render: (value: string | null) => value ?? "--",
  },
  {
    title: "连板",
    dataIndex: "board_count",
    sorter: (a, b) => a.board_count - b.board_count,
    render: (value: number) => <Tag color={value >= 3 ? "red" : value === 2 ? "orange" : "default"}>{value}板</Tag>,
  },
  {
    title: "20日涨停",
    dataIndex: "limit_up_hits_20d",
    sorter: (a, b) => a.limit_up_hits_20d - b.limit_up_hits_20d,
  },
  {
    title: "炸板",
    dataIndex: "break_board_count",
    sorter: (a, b) => a.break_board_count - b.break_board_count,
    render: (value: number) => <span className={value > 0 ? "font-black market-green-text" : ""}>{value}</span>,
  },
  {
    title: "封板时间",
    dataIndex: "first_seal_time",
    render: (value: string | null) => value ?? "--",
  },
];
