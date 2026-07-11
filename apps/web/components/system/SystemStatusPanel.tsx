"use client";

import { Alert, Button, Card, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { cacheFreshnessLabel, cacheStatusTone, systemStatusTone } from "../../lib/systemStatus";
import type { SystemCacheItem, SystemStatusResponse } from "../../lib/types";

type Props = {
  loading: boolean;
  status: SystemStatusResponse | null;
  error: string | null;
  onRefresh: () => void;
};

const columns: ColumnsType<SystemCacheItem> = [
  { title: "缓存", dataIndex: "name", key: "name" },
  { title: "分组", dataIndex: "group", key: "group" },
  {
    title: "状态",
    key: "freshness",
    render: (_, item) => {
      const tone = cacheStatusTone(item);
      return (
        <Tag
          className={tone === "fresh" ? "market-green-badge" : ""}
          color={tone === "error" ? "red" : tone === "stale" ? "orange" : undefined}
        >
          {cacheFreshnessLabel(item)}
        </Tag>
      );
    },
  },
  { title: "命中", dataIndex: "hits", key: "hits", align: "right" },
  { title: "Miss", dataIndex: "misses", key: "misses", align: "right" },
  { title: "错误", dataIndex: "last_error", key: "last_error", render: (value) => value || "--" },
];

export function SystemStatusPanel({ loading, status, error, onRefresh }: Props) {
  const tone = status ? systemStatusTone(status) : "warning";
  const statusLabel = status?.status === "ok" && status.confidence === "fresh" ? "运行正常" : "需要关注";

  return (
    <Card
      className="app-panel"
      title="系统运行状态"
      extra={
        <Button loading={loading} onClick={onRefresh} size="small">
          刷新状态
        </Button>
      }
    >
      {error && <Alert className="mb-3" showIcon type="error" message={error} />}
      {status ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Tag
              className={tone === "success" ? "market-green-badge" : ""}
              color={tone === "success" ? undefined : "orange"}
            >
              {statusLabel}
            </Tag>
            <Typography.Text className="app-muted text-xs">生成时间：{status.generated_at}</Typography.Text>
          </div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {status.jobs.map((job) => (
              <div className="app-inset px-3 py-2" key={job.name}>
                <div className="app-ink text-sm font-bold">{job.name}</div>
                <div className="app-muted mt-1 text-xs">{job.detail}</div>
                <Tag
                  className={job.running ? "market-green-badge mt-2" : "mt-2"}
                  color={job.running ? undefined : job.enabled ? "orange" : "default"}
                >
                  {job.running ? "运行中" : job.enabled ? "等待窗口" : "未启用"}
                </Tag>
              </div>
            ))}
          </div>
          <Table
            columns={columns}
            dataSource={status.cache.items}
            loading={loading}
            pagination={false}
            rowKey="name"
            scroll={{ x: true }}
            size="small"
          />
        </div>
      ) : (
        <Typography.Text className="app-muted">暂无系统状态，请点击刷新。</Typography.Text>
      )}
    </Card>
  );
}
