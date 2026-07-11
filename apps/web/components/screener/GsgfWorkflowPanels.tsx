"use client";

import { Button, Input, InputNumber, Progress, Tag } from "antd";
import { useEffect, useState } from "react";
import type {
  BackgroundJobState,
  GsgfCalibrationBucket,
  GsgfModelHealth,
  GsgfRealCalibrationSummary,
  GsgfReviewSummary,
} from "../../lib/types";
import {
  formatDateTime,
  formatPlainPercent,
  formatReviewPercent,
  formatSignedPercent,
  normalizeKlineCount,
  normalizeScanLimit,
} from "./screenerUtils";

export type GsgfReviewPanelProps = {
  gsgfHealth: GsgfModelHealth | null;
  onRecheck: () => void;
  onSaveSnapshot: () => void;
  reviewRunning: boolean;
  reviewSummary: GsgfReviewSummary | null;
};

export type GsgfCalibrationPanelProps = {
  calibrationJob: BackgroundJobState | null;
  calibrationRunning: boolean;
  calibrationSummary: GsgfRealCalibrationSummary | null;
  defaultTradeDate: string;
  onCancelCalibration: () => void;
  onRunCalibration: (options: {
    tradeDatesText: string;
    windowsText: string;
    scanLimit: number;
    count: number;
  }) => void;
};

export function GsgfReviewPanel({
  gsgfHealth,
  onRecheck,
  onSaveSnapshot,
  reviewRunning,
  reviewSummary,
}: {
  gsgfHealth: GsgfModelHealth | null;
  onRecheck: () => void;
  onSaveSnapshot: () => void;
  reviewRunning: boolean;
  reviewSummary: GsgfReviewSummary | null;
}) {
  const buckets = reviewSummary?.buckets.slice(0, 4) ?? [];

  return (
    <section className="mt-4 rounded-xl border border-[var(--app-border)] bg-[var(--app-raised)] px-4 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-base font-black text-[var(--app-ink)]">信号复盘</h2>
          <p className="mt-1 text-xs font-medium text-[var(--app-muted)]">
            样本 {reviewSummary?.record_count ?? 0} 条 · 窗口 {(reviewSummary?.windows ?? [1, 3, 5, 10]).join("/")} 日
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button loading={reviewRunning} onClick={onSaveSnapshot} size="small">
            保存复盘快照
          </Button>
          <Button loading={reviewRunning} onClick={onRecheck} size="small" type="primary">
            复查信号
          </Button>
        </div>
      </div>
      <ModelHealthBar gsgfHealth={gsgfHealth} />
      {buckets.length > 0 ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {buckets.map((bucket) => (
            <div className="rounded-lg border border-[var(--app-border)] bg-[var(--app-raised)] p-3" key={`${bucket.signal_type}-${bucket.status}`}>
              <p className="truncate text-xs font-black text-[var(--app-ink)]" title={bucket.signal_type}>
                {bucket.signal_type}
              </p>
              <p className="mt-1 text-[11px] font-semibold text-[var(--app-muted)]">
                {bucket.status} · 确认 {bucket.confirmed_count}/{bucket.sample_count}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <ValuePill label="收益" value={formatReviewPercent(bucket.avg_return_pct)} />
                <ValuePill label="回撤" value={formatReviewPercent(bucket.avg_max_drawdown_pct)} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-[var(--app-raised)] px-3 py-2 text-sm text-[var(--app-muted)]">
          暂无复盘样本。先运行筛选，再保存复盘快照。
        </p>
      )}
    </section>
  );
}

export function GsgfCalibrationPanel({
  calibrationJob,
  calibrationRunning,
  calibrationSummary,
  defaultTradeDate,
  onCancelCalibration,
  onRunCalibration,
}: {
  calibrationJob: BackgroundJobState | null;
  calibrationRunning: boolean;
  calibrationSummary: GsgfRealCalibrationSummary | null;
  defaultTradeDate: string;
  onCancelCalibration: () => void;
  onRunCalibration: (options: {
    tradeDatesText: string;
    windowsText: string;
    scanLimit: number;
    count: number;
  }) => void;
}) {
  const [tradeDatesText, setTradeDatesText] = useState(defaultTradeDate);
  const [windowsText, setWindowsText] = useState("1,3,5,10");
  const [scanLimit, setScanLimit] = useState(80);
  const [count, setCount] = useState(260);

  useEffect(() => {
    if (tradeDatesText.trim().length === 0) {
      setTradeDatesText(defaultTradeDate);
    }
  }, [defaultTradeDate, tradeDatesText]);

  return (
    <section className="mt-4 rounded-xl border border-[var(--app-border)] bg-[var(--app-raised)] px-4 py-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-black text-[var(--app-ink)]">真实样本校准</h2>
          <p className="mt-1 text-xs font-medium text-[var(--app-muted)]">
            用 TickFlow 历史日K复盘“确认买点 / 低吸观察 / B区A点 / 放量突破确认”的分桶命中率
          </p>
        </div>
        <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(220px,1fr)_120px_92px_92px_auto] xl:min-w-[760px]">
          <Input
            onChange={(event) => setTradeDatesText(event.target.value)}
            placeholder="样本日，逗号分隔"
            value={tradeDatesText}
          />
          <Input
            onChange={(event) => setWindowsText(event.target.value)}
            placeholder="窗口"
            value={windowsText}
          />
          <InputNumber
            className="w-full"
            max={300}
            min={1}
            onChange={(value) => setScanLimit(normalizeScanLimit(value))}
            value={scanLimit}
          />
          <InputNumber
            className="w-full"
            max={260}
            min={70}
            onChange={(value) => setCount(normalizeKlineCount(value))}
            value={count}
          />
          <Button
            disabled={tradeDatesText.trim().length === 0}
            loading={calibrationRunning}
            onClick={() => onRunCalibration({ tradeDatesText, windowsText, scanLimit, count })}
            type="primary"
          >
            运行校准
          </Button>
        </div>
      </div>

      {calibrationJob && (
        <div className="mt-3 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-black text-[var(--app-ink)]">校准任务</span>
                <Tag className="m-0" color={jobStatusColor(calibrationJob.status)}>
                  {calibrationJob.status}
                </Tag>
                <span className="text-xs font-semibold text-[var(--app-muted)]">
                  {calibrationJob.progress_current}/{calibrationJob.progress_total || 1} · {calibrationJob.message || "等待执行"}
                </span>
              </div>
              {calibrationJob.error && (
                <p className="mt-1 text-xs font-semibold text-[var(--market-rise)]">{calibrationJob.error}</p>
              )}
            </div>
            {(calibrationJob.status === "pending" || calibrationJob.status === "running") && (
              <Button danger onClick={onCancelCalibration} size="small">
                取消任务
              </Button>
            )}
          </div>
          <Progress
            className="mt-2"
            percent={jobProgressPercent(calibrationJob)}
            size="small"
            status={calibrationJob.status === "failed" ? "exception" : calibrationJob.status === "success" ? "success" : "active"}
          />
        </div>
      )}

      {calibrationSummary ? (
        <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <CalibrationBucketTable buckets={calibrationSummary.buckets} title="样本分桶" />
          <CalibrationBucketTable buckets={calibrationSummary.unique_symbol_buckets} title="去重股票分桶" />
          {calibrationSummary.diagnostic_groups.length > 0 && (
            <div className="xl:col-span-2">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-black text-[var(--app-ink)]">诊断分桶</h3>
                <Tag className="m-0">确认信号 / 准备形态 / 结构区间 / 评分段</Tag>
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {calibrationSummary.diagnostic_groups.map((group) => (
                  <CalibrationBucketTable buckets={group.buckets} key={group.name} title={group.name} />
                ))}
              </div>
            </div>
          )}
          <div className="xl:col-span-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-[var(--app-muted)]">
              <Tag className="m-0">样本日 {calibrationSummary.trade_dates.join(" / ")}</Tag>
              <Tag className="m-0">扫描 {calibrationSummary.scanned_count}</Tag>
              <Tag className="m-0">目标样本 {calibrationSummary.target_sample_count}</Tag>
              <Tag className="m-0">跳过 {calibrationSummary.skipped_count}</Tag>
              <Tag className="m-0">窗口 {calibrationSummary.windows.join("/")}</Tag>
              <span>生成 {formatDateTime(calibrationSummary.generated_at)}</span>
            </div>
            {calibrationSummary.samples.length > 0 && (
              <div className="mt-3 overflow-x-auto rounded-lg border border-[var(--app-border)]">
                <table className="min-w-full divide-y divide-[var(--app-border)] text-left text-xs">
                  <thead className="bg-[var(--app-raised)] text-[var(--app-muted)]">
                    <tr>
                      <th className="px-3 py-2 font-black" colSpan={4 + calibrationSummary.windows.length}>
                        信号后T+演化
                      </th>
                    </tr>
                    <tr>
                      <th className="px-3 py-2 font-black">样例</th>
                      <th className="px-3 py-2 font-black">分桶</th>
                      <th className="px-3 py-2 font-black">状态</th>
                      <th className="px-3 py-2 font-black">入场价</th>
                      {calibrationSummary.windows.map((window) => (
                        <th className="px-3 py-2 font-black" key={window}>
                          T+{window}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--app-border)] bg-white">
                    {calibrationSummary.samples.slice(0, 6).map((sample) => (
                      <tr key={`${sample.trade_date}-${sample.symbol}`}>
                        <td className="px-3 py-2 font-bold text-[var(--app-ink)]">
                          {sample.trade_date} · {sample.name} {sample.symbol}
                        </td>
                        <td className="px-3 py-2 text-[var(--app-muted)]">{sample.bucket_names.join(" / ")}</td>
                        <td className="px-3 py-2 text-[var(--app-muted)]">{sample.status}</td>
                        <td className="px-3 py-2 tabular-nums text-[var(--app-muted)]">
                          {sample.entry_close === null ? "--" : sample.entry_close.toFixed(2)}
                        </td>
                        {calibrationSummary.windows.map((window) => {
                          const sampleWindow = sample.windows.find((item) => item.window_days === window);
                          return (
                            <td className="px-3 py-2 tabular-nums" key={window}>
                              <div className="font-black text-[var(--app-ink)]">
                                {formatSignedPercent(sampleWindow?.realized_return_pct)}
                              </div>
                              <div className="text-[11px] text-[var(--app-muted)]">
                                最大回撤 {formatSignedPercent(sampleWindow?.max_drawdown_pct)}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-[var(--app-raised)] px-3 py-2 text-sm text-[var(--app-muted)]">
          暂无真实样本校准结果。建议先跑 3-10 个历史交易日的小样本，再逐步扩大 scan limit。
        </p>
      )}
    </section>
  );
}

function ModelHealthBar({ gsgfHealth }: { gsgfHealth: GsgfModelHealth | null }) {
  if (!gsgfHealth) {
    return (
      <div className="mt-3 rounded-lg bg-[var(--app-raised)] px-3 py-2 text-xs font-semibold text-[var(--app-muted)]">
        模型健康：暂无自动复盘摘要，保存快照并复查后生成。
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-black text-[var(--app-ink)]">模型健康</span>
        <Tag className="m-0" color="success">
          强信号 {gsgfHealth.best_signals.length}
        </Tag>
        <Tag className="m-0" color="warning">
          弱信号 {gsgfHealth.weak_signals.length}
        </Tag>
        <Tag className="m-0" color={gsgfHealth.degraded_signals.length > 0 ? "error" : "default"}>
          退化 {gsgfHealth.degraded_signals.length}
        </Tag>
        <Tag className="m-0">样本不足 {gsgfHealth.insufficient_sample_signals.length}</Tag>
      </div>
      <p className="mt-1 text-xs font-semibold text-[var(--app-muted)]">{gsgfHealth.summary_text}</p>
    </div>
  );
}

function CalibrationBucketTable({
  buckets,
  title,
}: {
  buckets: GsgfCalibrationBucket[];
  title: string;
}) {
  return (
    <div className="min-w-0 max-w-full overflow-hidden rounded-lg border border-[var(--app-border)] bg-[var(--app-raised)] p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-black text-[var(--app-ink)]">{title}</h3>
        <Tag className="m-0">{buckets.length || "待数据"}</Tag>
      </div>
      {buckets.length > 0 ? (
        <div className="max-w-full overflow-x-auto">
          <table className="min-w-[520px] text-left text-xs">
            <thead className="text-[var(--app-muted)]">
              <tr>
                <th className="px-2 py-2 font-black">分桶</th>
                <th className="px-2 py-2 font-black">样本</th>
                <th className="px-2 py-2 font-black">综合分</th>
                <th className="px-2 py-2 font-black">评级</th>
                <th className="px-2 py-2 font-black">hit_rate</th>
                <th className="px-2 py-2 font-black">均收</th>
                <th className="px-2 py-2 font-black">回撤</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--app-border)]">
              {buckets.map((bucket) => {
                const primaryWindow = bucket.windows[0] ?? null;
                return (
                  <tr key={bucket.name}>
                    <td className="px-2 py-2 font-black text-[var(--app-ink)]">{bucket.name}</td>
                    <td className="px-2 py-2 tabular-nums text-[var(--app-muted)]">{bucket.sample_count}</td>
                    <td className="px-2 py-2 font-black tabular-nums text-[var(--app-ink)]">
                      {bucket.composite_score === null ? "--" : bucket.composite_score.toFixed(2)}
                    </td>
                    <td className="px-2 py-2">
                      <Tag className="m-0" color={calibrationRatingColor(bucket.calibration_rating)}>
                        {bucket.calibration_rating}
                      </Tag>
                    </td>
                    <td className="px-2 py-2 font-black tabular-nums text-[var(--app-ink)]">
                      {formatPlainPercent(primaryWindow?.hit_rate)}
                    </td>
                    <td className="px-2 py-2 tabular-nums text-[var(--app-muted)]">
                      {formatSignedPercent(primaryWindow?.avg_return_pct)}
                    </td>
                    <td className="px-2 py-2 tabular-nums text-[var(--app-muted)]">
                      {formatSignedPercent(primaryWindow?.avg_max_drawdown_pct)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-md bg-white px-3 py-2 text-sm text-[var(--app-muted)]">当前样本没有命中目标分桶。</p>
      )}
    </div>
  );
}

function jobProgressPercent(job: BackgroundJobState): number {
  if (job.status === "success") {
    return 100;
  }
  const total = Math.max(job.progress_total, 1);
  return Math.min(99, Math.round((job.progress_current / total) * 100));
}

function jobStatusColor(status: BackgroundJobState["status"]): string {
  if (status === "success") {
    return "success";
  }
  if (status === "failed") {
    return "error";
  }
  if (status === "canceled") {
    return "default";
  }
  return "processing";
}

function calibrationRatingColor(rating: string): string {
  if (rating === "强") {
    return "green";
  }
  if (rating === "中强") {
    return "cyan";
  }
  if (rating === "中性") {
    return "blue";
  }
  if (rating === "弱") {
    return "orange";
  }
  return "default";
}

function ValuePill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-white px-2 text-[11px] font-bold text-slate-600 ring-1 ring-slate-100">
      {label} {value}
    </span>
  );
}
