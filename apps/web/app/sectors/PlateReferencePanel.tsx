"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Skeleton, Tag } from "antd";
import { useEffect, useMemo, useState } from "react";
import { getPlateRotationReference } from "../../lib/api";
import type { PlateRotationReferenceResponse, PlateRotationThemeItem } from "../../lib/types";

export function PlateReferencePanel({ title }: { title: string }) {
  const [data, setData] = useState<PlateRotationReferenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await getPlateRotationReference(10, "kaipan", 20);
        if (!ignore) {
          setData(response);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "读取短线题材参考榜失败");
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
  }, [refreshKey]);

  const sourceStatus = data?.source_status[0] ?? null;
  const sourceText = useMemo(() => {
    if (!sourceStatus) {
      return "等待参考源";
    }
    return `${sourceStatus.source} · ${sourceStatus.detail}`;
  }, [sourceStatus]);

  return (
    <section className="workbench-panel overflow-hidden rounded-xl border">
      <div className="workbench-panel-divider flex flex-col gap-3 border-b px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="m-0 text-base font-black text-[#11100e]">{title}</h2>
            <Tag className="m-0" color="orange">
              开盘啦口径
            </Tag>
          </div>
          <div className="mt-1 text-xs text-[#7b756d]">
            {sourceText}。用于校准题材分类和热度排序，当前工作台主图仍使用本系统行业指数口径。
          </div>
        </div>
        <Button
          icon={<ReloadOutlined />}
          loading={loading}
          onClick={() => setRefreshKey((value) => value + 1)}
          size="small"
        >
          刷新参考榜
        </Button>
      </div>

      {error ? (
        <div className="p-4">
          <Alert showIcon title={error} type="warning" />
        </div>
      ) : loading && !data ? (
        <div className="grid gap-2 p-4 md:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 10 }).map((_, index) => (
            <div className="rounded-lg border border-[#ece7df] bg-white px-3 py-3" key={index}>
              <Skeleton active paragraph={{ rows: 1, width: "70%" }} title={false} />
            </div>
          ))}
        </div>
      ) : data && data.themes.length > 0 ? (
        <div className="grid gap-2 p-4 md:grid-cols-2 xl:grid-cols-5">
          {data.themes.map((theme) => (
            <PlateReferenceItem item={theme} key={theme.code} />
          ))}
        </div>
      ) : (
        <Empty className="py-8" description="暂无短线题材参考数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </section>
  );
}

function PlateReferenceItem({ item }: { item: PlateRotationThemeItem }) {
  const isPositive = item.color !== "green";

  return (
    <div className="rounded-lg border border-[#ece7df] bg-white px-3 py-2.5 shadow-none">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[11px] font-black text-[#7b756d]">#{item.rank} · {item.code}</div>
          <div className="mt-0.5 truncate text-sm font-black text-[#11100e]">{item.name}</div>
        </div>
        <div className={`shrink-0 text-right text-sm font-black ${isPositive ? "text-[#d92d20]" : "market-green-text"}`}>
          {formatPlateReferenceValue(item)}
        </div>
      </div>
    </div>
  );
}

function formatPlateReferenceValue(item: PlateRotationThemeItem): string {
  if (item.value_type === "pct") {
    return `${item.score > 0 ? "+" : ""}${item.score.toFixed(2)}%`;
  }
  return Math.round(item.score).toLocaleString("zh-CN");
}
