import type { SystemCacheItem, SystemStatusResponse } from "./types";

export function cacheFreshnessLabel(item: SystemCacheItem): string {
  const seconds = item.oldest_expires_in_seconds;
  if (seconds === null) {
    return item.size > 0 ? "缓存状态未知" : "暂无缓存";
  }
  if (seconds >= 0) {
    return `${Math.round(seconds)}秒后过期`;
  }
  return `已过期${Math.abs(Math.round(seconds))}秒`;
}

export function systemStatusTone(status: SystemStatusResponse): "success" | "warning" {
  if (status.status === "ok" && status.confidence === "fresh") {
    return "success";
  }
  return "warning";
}
