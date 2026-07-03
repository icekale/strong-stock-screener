"use client";

import { Button, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import type {
  ShortTermIntradaySentimentItem,
  ShortTermIntradaySentimentResponse,
  ShortTermIntradaySignalDigest,
} from "../../lib/types";

export type IntradaySentimentPanelProps = {
  data: ShortTermIntradaySentimentResponse | null;
  digest: ShortTermIntradaySignalDigest | null;
  digestLoading: boolean;
  loading: boolean;
  onCopyDigest: () => void;
  onRefreshDigest: () => void;
  onRefresh: () => void;
  onSendDigest: () => void;
  sendingDigest: boolean;
};

export function IntradaySentimentPanel({
  data,
  digest,
  digestLoading,
  loading,
  onCopyDigest,
  onRefreshDigest,
  onRefresh,
  onSendDigest,
  sendingDigest,
}: IntradaySentimentPanelProps) {
  return (
    <section className="workbench-panel min-w-0 overflow-hidden rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">盘中情绪快照</div>
          <div className="text-xs text-[#7b756d]">
            TickFlow 实时行情 + 1分钟线，先用于手动刷新观察，定时提醒放到任务流版本。
          </div>
        </div>
        <Space wrap>
          {data?.source_status.map((item, index) => (
            <Tag color={item.status === "success" ? "green" : "orange"} key={`${item.source}-${item.detail}-${index}`}>
              {item.source}
            </Tag>
          ))}
          <Button loading={loading} onClick={onRefresh}>
            刷新盘中
          </Button>
          <Button loading={digestLoading} onClick={onRefreshDigest}>
            生成草稿
          </Button>
          <Button disabled={!digest?.message_text} onClick={onCopyDigest}>
            复制草稿
          </Button>
          <Button disabled={!digest?.message_text} loading={sendingDigest} onClick={onSendDigest} type="primary">
            发送草稿
          </Button>
        </Space>
      </div>
      <div className="grid gap-3 border-b border-[#ddd8d0] p-4 md:grid-cols-2 xl:grid-cols-5">
        <SmallMetric label="监控数" value={data?.metrics.watched_count ?? 0} />
        <SmallMetric label="预警数" value={data?.metrics.alert_count ?? 0} />
        <SmallMetric label="减仓确认" value={data?.metrics.reduce_count ?? 0} />
        <SmallMetric label="低吸观察" value={data?.metrics.low_buy_watch_count ?? 0} />
        <SmallMetric label="回避追高" value={data?.metrics.avoid_chase_count ?? 0} />
      </div>
      <div className="grid gap-4 border-b border-[#ddd8d0] p-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-lg border border-[#e3ddd3] bg-white p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-black text-[#11100e]">提醒草稿</div>
              <div className="text-xs text-[#7b756d]">可复制后发送到企业微信、飞书、Telegram 或邮件。</div>
            </div>
            <Tag color={(digest?.alert_count ?? 0) > 0 ? "red" : "default"}>
              {digest?.alert_count ?? 0} 条提醒
            </Tag>
          </div>
          <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-[#1d1b18] p-3 text-xs leading-5 text-[#f8f7f4]">
            {digest?.message_text ?? "点击生成草稿，系统会把盘中动作整理成可发送的中文消息。"}
          </pre>
        </div>
        <div className="rounded-lg border border-[#e3ddd3] bg-white p-3">
          <div className="text-sm font-black text-[#11100e]">规则说明</div>
          <div className="mt-2 space-y-2 text-xs leading-5 text-[#433f38]">
            <div>减仓确认：高位强势、冲高回落或盘中风险信号。</div>
            <div>低吸观察：急跌后等待修复，必须结合趋势位置。</div>
            <div>回避追高：未站稳日内均线或风险信号未解除。</div>
            <div className="text-[#8a4b12]">当前只生成草稿，不自动发送。</div>
          </div>
        </div>
      </div>
      <div className="w-full max-w-full overflow-x-auto">
        <Table
          columns={intradayColumns}
          dataSource={data?.items ?? []}
          loading={loading}
          locale={{ emptyText: "点击刷新盘中，读取 TickFlow 实时行情" }}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          rowKey={(item) => item.symbol}
          scroll={{ x: 900 }}
          size="small"
        />
      </div>
    </section>
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

const intradayColumns: ColumnsType<ShortTermIntradaySentimentItem> = [
  {
    title: "股票",
    dataIndex: "name",
    fixed: "left",
    render: (value: string, item) => (
      <Link className="font-black text-[#11100e] hover:text-[#d92d20]" href={`/stock/${item.symbol}`}>
        {value}
        <span className="ml-2 text-xs font-semibold text-[#7b756d]">{item.symbol}</span>
      </Link>
    ),
  },
  {
    title: "池子",
    dataIndex: "pool_tags",
    render: (value: string[]) => (
      <div className="flex flex-wrap gap-1">
        {value.slice(0, 4).map((tag) => (
          <Tag key={tag}>{tag}</Tag>
        ))}
      </div>
    ),
  },
  {
    title: "动作",
    dataIndex: "action",
    render: (value: ShortTermIntradaySentimentItem["action"]) => (
      <Tag color={actionColor(value)}>{actionLabel(value)}</Tag>
    ),
  },
  {
    title: "涨跌幅",
    dataIndex: "pct_change",
    sorter: (a, b) => (a.pct_change ?? 0) - (b.pct_change ?? 0),
    render: (value: number | null) => (
      <span className={(value ?? 0) >= 0 ? "text-[#d92d20]" : "market-green-text"}>
        {formatPct(value)}
      </span>
    ),
  },
  {
    title: "日内均线",
    dataIndex: "latest_vs_intraday_ma_pct",
    render: (value: number | null) => formatPct(value),
  },
  {
    title: "成交额",
    dataIndex: "turnover_cny",
    render: (value: number | null) => formatCny(value),
  },
  {
    title: "信号",
    dataIndex: "signals",
    render: (value: string[]) => (
      <span className="text-xs text-[#433f38]">{value.slice(0, 3).join(" / ") || "--"}</span>
    ),
  },
];

function actionLabel(value: ShortTermIntradaySentimentItem["action"]): string {
  const labels: Record<ShortTermIntradaySentimentItem["action"], string> = {
    watch: "观察",
    low_buy_watch: "低吸观察",
    reduce: "减仓确认",
    avoid_chase: "回避追高",
    data_incomplete: "数据不足",
  };
  return labels[value];
}

function actionColor(value: ShortTermIntradaySentimentItem["action"]): string {
  const colors: Record<ShortTermIntradaySentimentItem["action"], string> = {
    watch: "blue",
    low_buy_watch: "orange",
    reduce: "red",
    avoid_chase: "volcano",
    data_incomplete: "default",
  };
  return colors[value];
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
