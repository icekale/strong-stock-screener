"use client";

import { Button, Input, InputNumber, Tag } from "antd";
import { useEffect, useState } from "react";
import type { GsgfCalibrationBucket, GsgfRealCalibrationSummary, GsgfReviewSummary } from "../../lib/types";
import {
  formatDateTime,
  formatPlainPercent,
  formatReviewPercent,
  formatSignedPercent,
  normalizeKlineCount,
  normalizeScanLimit,
} from "./screenerUtils";

export type GsgfReviewPanelProps = {
  onRecheck: () => void;
  onSaveSnapshot: () => void;
  reviewRunning: boolean;
  reviewSummary: GsgfReviewSummary | null;
};

export type GsgfCalibrationPanelProps = {
  calibrationRunning: boolean;
  calibrationSummary: GsgfRealCalibrationSummary | null;
  defaultTradeDate: string;
  onRunCalibration: (options: {
    tradeDatesText: string;
    windowsText: string;
    scanLimit: number;
    count: number;
  }) => void;
};

export function GsgfReviewPanel({
  onRecheck,
  onSaveSnapshot,
  reviewRunning,
  reviewSummary,
}: {
  onRecheck: () => void;
  onSaveSnapshot: () => void;
  reviewRunning: boolean;
  reviewSummary: GsgfReviewSummary | null;
}) {
  const buckets = reviewSummary?.buckets.slice(0, 4) ?? [];

  return (
    <section className="mt-4 rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] px-4 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-base font-black text-[#11100e]">信号复盘</h2>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
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
      {buckets.length > 0 ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {buckets.map((bucket) => (
            <div className="rounded-lg border border-[#ddd8d0] bg-[#f5f3f0] p-3" key={`${bucket.signal_type}-${bucket.status}`}>
              <p className="truncate text-xs font-black text-[#11100e]" title={bucket.signal_type}>
                {bucket.signal_type}
              </p>
              <p className="mt-1 text-[11px] font-semibold text-[#7b756d]">
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
        <p className="mt-3 rounded-lg bg-[#f5f3f0] px-3 py-2 text-sm text-[#7b756d]">
          暂无复盘样本。先运行筛选，再保存复盘快照。
        </p>
      )}
    </section>
  );
}

export function GsgfCalibrationPanel({
  calibrationRunning,
  calibrationSummary,
  defaultTradeDate,
  onRunCalibration,
}: {
  calibrationRunning: boolean;
  calibrationSummary: GsgfRealCalibrationSummary | null;
  defaultTradeDate: string;
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
    <section className="mt-4 rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] px-4 py-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-black text-[#11100e]">真实样本校准</h2>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
            用 TickFlow 历史日K复盘“确认买点 / 低吸观察 / B区A点 / 放量突破确认”的分桶命中率
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-[minmax(220px,1fr)_120px_92px_92px_auto] xl:min-w-[760px]">
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

      {calibrationSummary ? (
        <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <CalibrationBucketTable buckets={calibrationSummary.buckets} title="样本分桶" />
          <CalibrationBucketTable buckets={calibrationSummary.unique_symbol_buckets} title="去重股票分桶" />
          <div className="xl:col-span-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-[#7b756d]">
              <Tag className="m-0">样本日 {calibrationSummary.trade_dates.join(" / ")}</Tag>
              <Tag className="m-0">扫描 {calibrationSummary.scanned_count}</Tag>
              <Tag className="m-0">目标样本 {calibrationSummary.target_sample_count}</Tag>
              <Tag className="m-0">跳过 {calibrationSummary.skipped_count}</Tag>
              <Tag className="m-0">窗口 {calibrationSummary.windows.join("/")}</Tag>
              <span>生成 {formatDateTime(calibrationSummary.generated_at)}</span>
            </div>
            {calibrationSummary.samples.length > 0 && (
              <div className="mt-3 overflow-x-auto rounded-lg border border-[#ddd8d0]">
                <table className="min-w-full divide-y divide-[#ddd8d0] text-left text-xs">
                  <thead className="bg-[#f5f3f0] text-[#7b756d]">
                    <tr>
                      <th className="px-3 py-2 font-black">样例</th>
                      <th className="px-3 py-2 font-black">分桶</th>
                      <th className="px-3 py-2 font-black">状态</th>
                      <th className="px-3 py-2 font-black">首窗收益</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e5e0d8] bg-white">
                    {calibrationSummary.samples.slice(0, 6).map((sample) => (
                      <tr key={`${sample.trade_date}-${sample.symbol}`}>
                        <td className="px-3 py-2 font-bold text-[#11100e]">
                          {sample.trade_date} · {sample.name} {sample.symbol}
                        </td>
                        <td className="px-3 py-2 text-[#7b756d]">{sample.bucket_names.join(" / ")}</td>
                        <td className="px-3 py-2 text-[#7b756d]">{sample.status}</td>
                        <td className="px-3 py-2 font-black tabular-nums text-[#11100e]">
                          {formatSignedPercent(sample.windows[0]?.realized_return_pct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-[#f5f3f0] px-3 py-2 text-sm text-[#7b756d]">
          暂无真实样本校准结果。建议先跑 3-10 个历史交易日的小样本，再逐步扩大 scan limit。
        </p>
      )}
    </section>
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
    <div className="min-w-0 rounded-lg border border-[#ddd8d0] bg-[#f5f3f0] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-black text-[#11100e]">{title}</h3>
        <Tag className="m-0">{buckets.length || "待数据"}</Tag>
      </div>
      {buckets.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-[#7b756d]">
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
            <tbody className="divide-y divide-[#ddd8d0]">
              {buckets.map((bucket) => {
                const primaryWindow = bucket.windows[0] ?? null;
                return (
                  <tr key={bucket.name}>
                    <td className="px-2 py-2 font-black text-[#11100e]">{bucket.name}</td>
                    <td className="px-2 py-2 tabular-nums text-[#7b756d]">{bucket.sample_count}</td>
                    <td className="px-2 py-2 font-black tabular-nums text-[#11100e]">
                      {bucket.composite_score === null ? "--" : bucket.composite_score.toFixed(2)}
                    </td>
                    <td className="px-2 py-2">
                      <Tag className="m-0" color={calibrationRatingColor(bucket.calibration_rating)}>
                        {bucket.calibration_rating}
                      </Tag>
                    </td>
                    <td className="px-2 py-2 font-black tabular-nums text-[#11100e]">
                      {formatPlainPercent(primaryWindow?.hit_rate)}
                    </td>
                    <td className="px-2 py-2 tabular-nums text-[#7b756d]">
                      {formatSignedPercent(primaryWindow?.avg_return_pct)}
                    </td>
                    <td className="px-2 py-2 tabular-nums text-[#7b756d]">
                      {formatSignedPercent(primaryWindow?.avg_max_drawdown_pct)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-md bg-white px-3 py-2 text-sm text-[#7b756d]">当前样本没有命中目标分桶。</p>
      )}
    </div>
  );
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
