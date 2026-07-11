"use client";

import { Alert, Button, Card, Checkbox, Collapse, Empty, Form, Input, InputNumber, Segmented, Space, Tag } from "antd";
import type {
  DataSourceStatusResponse,
  ScreenRunFilters,
  ScreenRunJobState,
  ScreenStrategy,
  WatchlistPoolItem,
} from "../../lib/types";
import { marketTypeOptions, strategyOptions } from "./types";
import {
  activeScreenFilterCount,
  cleanScreenFilters,
  groupWatchlistPoolItems,
  marketCapFilterLabel,
  marketTypeLabel,
  normalizeOptionalNumber,
  normalizeScanLimit,
  sourceTagColor,
  splitFilterValues,
  strategyName,
} from "./screenerUtils";

export function FilterLogicRail({
  filters,
  onRefreshSources,
  onRun,
  onSaveScreenFilters,
  onScanLimitChange,
  onScreenFiltersChange,
  onStrategyChange,
  onTradeDateChange,
  running,
  scanLimit,
  screenJob,
  screenFiltersSaved,
  sources,
  strategy,
  tradeDate,
  visibleCount,
}: {
  filters: ScreenRunFilters;
  onRefreshSources: () => void;
  onRun: () => void;
  onSaveScreenFilters: () => void;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onStrategyChange: (value: ScreenStrategy) => void;
  onTradeDateChange: (value: string) => void;
  running: boolean;
  scanLimit: number;
  screenJob: ScreenRunJobState | null;
  screenFiltersSaved: boolean;
  sources: DataSourceStatusResponse | null;
  strategy: ScreenStrategy;
  tradeDate: string;
  visibleCount: number;
}) {
  return (
    <section className="mt-4 rounded-xl border border-[var(--app-border)] bg-[var(--app-raised)] px-4 py-3">
      <div className="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="mr-2 border-r border-[var(--app-border)] pr-4 text-xs font-black uppercase text-[var(--app-ink)]">FILTER LOGIC</span>
          <FilterChip active label="20日内涨停" />
          <FilterChip active label={strategyName(strategy)} />
          <FilterChip active label={`扫描 ${scanLimit}`} />
          <FilterChip active={Boolean(filters.kdj_j_max)} label={filters.kdj_j_max ? `KDJ-J < ${filters.kdj_j_max}` : "KDJ-J 不限"} />
          <FilterChip active={Boolean(filters.min_market_cap_billion || filters.max_market_cap_billion)} label={marketCapFilterLabel(filters)} />
          {(filters.market_types ?? []).map((market) => <FilterChip active key={market} label={marketTypeLabel(market)} />)}
          {(filters.industries ?? []).map((industry) => <FilterChip active key={industry} label={industry} />)}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-[var(--app-muted)]">Matched: <b className="text-[var(--app-ink)]">{visibleCount}</b> stocks</span>
          <Button onClick={onRefreshSources} size="small">刷新源</Button>
          <Button loading={running} onClick={onRun} size="small" type="primary">运行筛选</Button>
          <Button onClick={() => onScreenFiltersChange({})} size="small">Reset</Button>
        </div>
      </div>

      {screenJob && (
        <div className="mt-3 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="font-black text-[var(--app-ink)]">筛选任务</span>
            <span className="font-bold text-[var(--app-muted)]">{screenJob.message || jobStatusLabel(screenJob.status)}</span>
            <span className="font-mono text-[var(--app-muted)]">
              {Math.min(screenJob.progress_current, screenJob.progress_total)}/{Math.max(1, screenJob.progress_total)}
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--app-border)]">
            <div
              className="h-full rounded-full bg-[var(--app-ink)] transition-all"
              style={{ width: `${screenJobProgressPercent(screenJob)}%` }}
            />
          </div>
        </div>
      )}

      <details className="mt-3 border-t border-[var(--app-border)] pt-3">
        <summary className="cursor-pointer text-xs font-bold text-[var(--app-muted)]">编辑筛选参数</summary>
        <div className="mt-3 grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <label className="text-xs font-bold text-[var(--app-muted)]">
              交易日
              <Input className="mt-1" onChange={(event) => onTradeDateChange(event.target.value)} value={tradeDate} />
            </label>
            <label className="text-xs font-bold text-[var(--app-muted)]">
              策略模型
              <Segmented
                className="mt-1 w-full"
                onChange={(value) => onStrategyChange(value as ScreenStrategy)}
                options={strategyOptions}
                value={strategy}
              />
            </label>
            <label className="text-xs font-bold text-[var(--app-muted)]">
              扫描候选数
              <InputNumber className="mt-1 w-full" max={300} min={1} onChange={(value) => onScanLimitChange(normalizeScanLimit(value))} value={scanLimit} />
            </label>
            <DataSourceStrip onRefreshSources={onRefreshSources} sources={sources} />
          </div>
          <AdvancedScreenFilters
            filters={filters}
            onChange={onScreenFiltersChange}
            onSave={onSaveScreenFilters}
            saved={screenFiltersSaved}
          />
        </div>
      </details>
    </section>
  );
}

function screenJobProgressPercent(job: ScreenRunJobState): number {
  const total = Math.max(1, job.progress_total);
  if (job.status === "success") {
    return 100;
  }
  return Math.max(5, Math.min(100, Math.round((job.progress_current / total) * 100)));
}

function jobStatusLabel(status: ScreenRunJobState["status"]): string {
  if (status === "pending") {
    return "等待执行";
  }
  if (status === "running") {
    return "运行中";
  }
  if (status === "success") {
    return "已完成";
  }
  if (status === "canceled") {
    return "已取消";
  }
  return "失败";
}

function FilterChip({ active, label }: { active: boolean; label: string }) {
  return (
    <span className={`inline-flex h-8 items-center rounded-md border px-3 text-xs font-bold ${
      active ? "border-[var(--app-ink)] bg-[var(--app-ink)] text-white" : "border-[var(--app-border)] bg-[var(--app-raised)] text-[var(--app-muted)]"
    }`}>
      {active ? "✓ " : ""}{label}
    </span>
  );
}

function DataSourceStrip({
  onRefreshSources,
  sources,
}: {
  onRefreshSources: () => void;
  sources: DataSourceStatusResponse | null;
}) {
  const items = sources?.items ?? [];
  const failed = items.filter((item) => item.status === "failed" || item.status === "missing_key");
  const summary = sources ? `${items.filter((item) => item.status === "success").length}/${items.length} 可用` : "读取中";

  return (
    <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-bold text-slate-600">数据源：{summary}</p>
          <p className="mt-1 truncate text-xs text-slate-500">TickFlow 仅用于独立选股程序。</p>
        </div>
        <Button className="shrink-0" onClick={onRefreshSources} size="small">
          刷新
        </Button>
      </div>
      {items.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {items.map((item) => (
            <Tag color={sourceTagColor(item.status)} key={item.source} title={item.detail}>
              {item.source} {item.status}
            </Tag>
          ))}
        </div>
      )}
      {failed.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-slate-200 pt-2">
          {failed.map((item) => (
            <p className="text-xs leading-5 text-red-700" key={item.source}>
              {item.source}：{item.detail}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function ScreenPanel({
  onRun,
  onScanLimitChange,
  onScreenFiltersChange,
  onSaveScreenFilters,
  onStrategyChange,
  onTradeDateChange,
  running,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  strategy,
  tradeDate,
}: {
  onRun: () => void;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  onStrategyChange: (value: ScreenStrategy) => void;
  onTradeDateChange: (value: string) => void;
  running: boolean;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  strategy: ScreenStrategy;
  tradeDate: string;
}) {
  const scanLimitOptions = [40, 160, 300];

  return (
    <section className="border-t border-slate-100 pt-4">
      <h3 className="text-sm font-black text-slate-950">1. 手动筛选</h3>
      <Form className="mt-3" layout="vertical">
        <Form.Item label="交易日">
          <Input
            id="trade-date"
            inputMode="numeric"
            onChange={(event) => onTradeDateChange(event.target.value)}
            placeholder="YYYY-MM-DD"
            value={tradeDate}
          />
        </Form.Item>
        <Form.Item label="策略模型">
          <Segmented
            block
            onChange={(value) => onStrategyChange(value as ScreenStrategy)}
            options={strategyOptions}
            value={strategy}
            vertical
          />
        </Form.Item>
        <Form.Item label="扫描候选数">
          <Space className="w-full" orientation="vertical" size={8}>
            <Segmented
              block
              onChange={(value) => onScanLimitChange(Number(value))}
              options={scanLimitOptions.map((value) => ({ label: String(value), value }))}
              value={scanLimit}
            />
            <InputNumber
              className="w-full"
              id="scan-limit"
              max={300}
              min={1}
              onChange={(value) => onScanLimitChange(normalizeScanLimit(value))}
              value={scanLimit}
            />
          </Space>
        </Form.Item>
      </Form>
      <AdvancedScreenFilters
        filters={screenFilters}
        onChange={onScreenFiltersChange}
        onSave={onSaveScreenFilters}
        saved={screenFiltersSaved}
      />
      <Button
        block
        disabled={running || tradeDate.trim().length === 0}
        loading={running}
        onClick={onRun}
        type="primary"
      >
        {running ? "筛选中..." : "运行筛选"}
      </Button>
    </section>
  );
}

function AdvancedScreenFilters({
  filters,
  onChange,
  onSave,
  saved,
}: {
  filters: ScreenRunFilters;
  onChange: (value: ScreenRunFilters) => void;
  onSave: () => void;
  saved: boolean;
}) {
  const enabledCount = activeScreenFilterCount(filters);

  function update(next: Partial<ScreenRunFilters>) {
    onChange(cleanScreenFilters({ ...filters, ...next }));
  }

  return (
    <Collapse
      className="mt-3 bg-slate-50"
      defaultActiveKey={["advanced"]}
      items={[
        {
          key: "advanced",
          label: (
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-black text-slate-950">高级筛选</span>
              <Tag variant="filled">已启用 {enabledCount}</Tag>
            </div>
          ),
          children: (
            <Space className="w-full" orientation="vertical" size={12}>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <FilterNumberInput
                  label="最小市值（亿元）"
                  min={0}
                  onChange={(value) => update({ min_market_cap_billion: normalizeOptionalNumber(value, 0) })}
                  placeholder="不限请留空"
                  value={filters.min_market_cap_billion}
                />
                <FilterNumberInput
                  label="最大市值（亿元）"
                  min={0}
                  onChange={(value) => update({ max_market_cap_billion: normalizeOptionalNumber(value, 0) })}
                  placeholder="不限请留空"
                  value={filters.max_market_cap_billion}
                />
                <FilterNumberInput
                  label="KDJ-J值（小于）"
                  onChange={(value) => update({ kdj_j_max: normalizeOptionalNumber(value) })}
                  placeholder="不限请留空"
                  value={filters.kdj_j_max}
                />
              </div>

              <DisabledFilterInput label="概念板块（多选）" placeholder="待接入概念成分数据" />
              <DisabledFilterInput label="概念叠加（多选）" placeholder="待接入概念叠加数据" />

              <Form.Item className="mb-0" label="行业板块（多选）">
                <Input
                  onChange={(event) => update({ industries: splitFilterValues(event.target.value) })}
                  placeholder="消费电子，半导体"
                  value={(filters.industries ?? []).join("，")}
                />
              </Form.Item>

              <Form.Item className="mb-0" label="市场类型">
                <Checkbox.Group
                  className="grid grid-cols-2 gap-2"
                  onChange={(values) =>
                    update({
                      market_types: marketTypeOptions
                        .map((option) => option.value)
                        .filter((option) => values.includes(option)),
                    })
                  }
                  options={marketTypeOptions}
                  value={filters.market_types ?? []}
                />
              </Form.Item>

              <div className="grid grid-cols-[1fr_auto] gap-2">
                <Button block onClick={onSave} type={saved ? "primary" : "default"}>
                  {saved ? "已保存" : "保存筛选参数"}
                </Button>
                <Button onClick={() => onChange({})}>重置</Button>
              </div>
              {saved && (
                <Alert
                  aria-live="polite"
                  showIcon
                  title="筛选参数已保存到本机"
                  type="success"
                />
              )}
            </Space>
          ),
        },
      ]}
    />
  );
}

function FilterNumberInput({
  label,
  min,
  onChange,
  placeholder,
  value,
}: {
  label: string;
  min?: number;
  onChange: (value: number | string | null) => void;
  placeholder: string;
  value: number | null | undefined;
}) {
  return (
    <Form.Item className="mb-0" label={label}>
      <InputNumber
        className="w-full"
        min={min}
        onChange={onChange}
        placeholder={placeholder}
        value={value ?? null}
      />
    </Form.Item>
  );
}

function DisabledFilterInput({ label, placeholder }: { label: string; placeholder: string }) {
  return (
    <Form.Item className="mb-0" label={label}>
      <Input disabled placeholder={placeholder} />
    </Form.Item>
  );
}

function WatchlistPanel({
  watchlistPoolItems,
}: {
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  const groups = groupWatchlistPoolItems(watchlistPoolItems);

  return (
    <Card className="workbench-card" size="small">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-black text-slate-950">结构化自选池</h3>
          <p className="mt-1 text-xs font-medium text-slate-500">完整分组、标签和备注在独立页面管理。</p>
        </div>
        <Button aria-label="打开自选股管理页" className="shrink-0" href="/watchlist" size="small" type="primary">
          管理自选股
        </Button>
      </div>
      <div className="mt-3 space-y-3">
        {groups.length > 0 ? (
          groups.map((group) => <WatchlistGroupSection group={group} key={group.name} />)
        ) : (
          <Empty description="暂无自选股，候选表或 K 线详情页可加入。" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </div>
    </Card>
  );
}

function WatchlistGroupSection({
  group,
}: {
  group: {
    name: string;
    items: WatchlistPoolItem[];
  };
}) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-xs font-black text-slate-800">分组 {group.name}</h4>
        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-bold text-slate-500 ring-1 ring-slate-100">
          {group.items.length}
        </span>
      </div>
      <div className="mt-2 space-y-2">
        {group.items.map((item) => (
          <div className="rounded-md bg-white p-2 ring-1 ring-slate-100" key={item.symbol}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-xs font-black text-slate-950">{item.name ?? item.symbol}</p>
                <p className="mt-0.5 text-[11px] font-semibold text-slate-400">{item.symbol}</p>
              </div>
              {item.industry && (
                <span className="max-w-[120px] truncate rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-bold text-indigo-700 ring-1 ring-indigo-100">
                  {item.industry}
                </span>
              )}
            </div>
            {item.tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {item.tags.map((tag) => (
                  <span
                    className="inline-flex h-5 items-center rounded-full bg-slate-100 px-1.5 text-[11px] font-bold text-slate-600"
                    key={tag}
                  >
                    标签 {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
