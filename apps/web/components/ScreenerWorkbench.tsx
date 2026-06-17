import type {
  DataSourceStatusResponse,
  ScreenRunFilters,
  SourceStatusValue,
  StrongStockIntradayItem,
  StrongStockIntradaySnapshot,
  StrongStockScreeningItem,
  StrongStockScreeningResponse,
  WatchlistPoolItem,
  WatchlistRiskItem,
} from "../lib/types";
import { useEffect, useMemo, useState } from "react";

type ScreenerWorkbenchProps = {
  tradeDate: string;
  sources: DataSourceStatusResponse | null;
  result: StrongStockScreeningResponse | null;
  intraday: StrongStockIntradaySnapshot | null;
  running: boolean;
  watchlistPoolItems: WatchlistPoolItem[];
  watchlistMessage: string | null;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  error: string | null;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  onTradeDateChange: (value: string) => void;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onAddManyToWatchlist: (items: StrongStockScreeningItem[], group: string, tags: string[]) => void;
  onRun: () => void;
  onRefreshSources: () => void;
};

const sourceTone: Record<SourceStatusValue, string> = {
  success: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  failed: "bg-red-50 text-red-700 ring-red-100",
  disabled: "bg-slate-100 text-slate-600 ring-slate-200",
  missing_key: "bg-amber-50 text-amber-700 ring-amber-100",
};

const statusCopy: Record<StrongStockScreeningItem["status"], { label: string; tone: string }> = {
  focus: { label: "可关注", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  wait_pullback: { label: "等回踩", tone: "bg-sky-50 text-sky-700 ring-sky-100" },
  reduce_risk: { label: "减仓风险", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  data_incomplete: { label: "数据不足", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
};

type CandidateStatusFilter = StrongStockScreeningItem["status"] | "all";

const candidateStatusFilters: Array<{ label: string; value: CandidateStatusFilter }> = [
  { label: "全部", value: "all" },
  { label: statusCopy.focus.label, value: "focus" },
  { label: statusCopy.wait_pullback.label, value: "wait_pullback" },
  { label: statusCopy.reduce_risk.label, value: "reduce_risk" },
  { label: statusCopy.data_incomplete.label, value: "data_incomplete" },
];

const riskCopy: Record<WatchlistRiskItem["risk_action"], { label: string; tone: string }> = {
  hold_watch: { label: "继续观察", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  reduce: { label: "降低关注", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  empty: { label: "空仓纪律触发", tone: "bg-red-50 text-red-700 ring-red-100" },
};

const intradayCopy: Record<StrongStockIntradayItem["action"], { label: string; tone: string }> = {
  watch: { label: "继续观察", tone: "bg-sky-50 text-sky-700 ring-sky-100" },
  low_buy_watch: { label: "低吸观察", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  reduce: { label: "减仓锁利", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  avoid_chase: { label: "避免追高", tone: "bg-red-50 text-red-700 ring-red-100" },
  data_incomplete: { label: "数据不足", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
};

const industryStrengthCopy: Record<
  NonNullable<StrongStockScreeningItem["industry_strength"]>,
  { label: string; tone: string }
> = {
  strong: { label: "强", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  neutral: { label: "中", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
  weak: { label: "弱", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
};

type MarketType = NonNullable<ScreenRunFilters["market_types"]>[number];

const marketTypeOptions: Array<{ label: string; value: MarketType }> = [
  { label: "主板", value: "main" },
  { label: "创业板", value: "gem" },
  { label: "科创板", value: "star" },
  { label: "北交所", value: "bj" },
];

export function ScreenerWorkbench({
  tradeDate,
  sources,
  result,
  intraday,
  running,
  watchlistPoolItems,
  watchlistMessage,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  error,
  onScanLimitChange,
  onScreenFiltersChange,
  onSaveScreenFilters,
  onTradeDateChange,
  onAddToWatchlist,
  onAddManyToWatchlist,
  onRun,
  onRefreshSources,
}: ScreenerWorkbenchProps) {
  const candidates = result?.items ?? [];
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  useEffect(() => {
    if (candidates.length === 0) {
      setSelectedSymbol(null);
      return;
    }
    if (!selectedSymbol || !candidates.some((item) => item.symbol === selectedSymbol)) {
      setSelectedSymbol(candidates[0].symbol);
    }
  }, [result, selectedSymbol, candidates]);

  const selectedItem = candidates.find((item) => item.symbol === selectedSymbol) ?? candidates[0] ?? null;
  const selectedRiskItem =
    result?.watchlist_risk_items.find((item) => item.symbol === selectedItem?.symbol) ?? null;
  const selectedIntradayItem = intraday?.items.find((item) => item.symbol === selectedItem?.symbol) ?? null;
  const focusCount = candidates.filter((item) => item.status === "focus").length;
  const riskEmptyCount = result?.watchlist_risk_items.filter((item) => item.risk_action === "empty").length ?? 0;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-[1680px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        <header className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase text-slate-400">Strong Stock Screener</p>
              <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-950">强势股选股工作台</h1>
            </div>
            <div className="flex flex-col gap-3 sm:min-w-[420px]">
              <div className="grid grid-cols-3 gap-2">
                <Metric label="候选" value={candidates.length} />
                <Metric label="可关注" value={focusCount} />
                <Metric label="空仓风控" value={riskEmptyCount} />
              </div>
              <a
                aria-label="打开自选股管理页"
                className="inline-flex min-h-[38px] items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-bold text-white transition hover:bg-slate-800 active:translate-y-px"
                href="/watchlist"
              >
                管理自选股
              </a>
              <a
                aria-label="打开数据源设置页"
                className="inline-flex min-h-[38px] items-center justify-center rounded-md bg-white px-4 text-sm font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100 active:translate-y-px"
                href="/settings"
              >
                数据源设置
              </a>
            </div>
          </div>
        </header>

        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
          <WorkflowPanel
            error={error}
            onRefreshSources={onRefreshSources}
            onRun={onRun}
            onTradeDateChange={onTradeDateChange}
            result={result}
            running={running}
            scanLimit={scanLimit}
            screenFilters={screenFilters}
            screenFiltersSaved={screenFiltersSaved}
            sources={sources}
            tradeDate={tradeDate}
            onScanLimitChange={onScanLimitChange}
            onScreenFiltersChange={onScreenFiltersChange}
            onSaveScreenFilters={onSaveScreenFilters}
            watchlistPoolItems={watchlistPoolItems}
          />
          <CandidateTable
            generatedAt={result?.generated_at ?? null}
            items={candidates}
            onAddManyToWatchlist={onAddManyToWatchlist}
            onAddToWatchlist={onAddToWatchlist}
            onSelect={setSelectedSymbol}
            running={running}
            selectedSymbol={selectedItem?.symbol ?? null}
            watchlistMessage={watchlistMessage}
            watchlistPoolItems={watchlistPoolItems}
          />
          <CandidateDetailPanel
            intradayItem={selectedIntradayItem}
            item={selectedItem}
            onAddToWatchlist={onAddToWatchlist}
            riskItem={selectedRiskItem}
            watchlistPoolItems={watchlistPoolItems}
          />
        </div>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
      <div className="text-2xl font-black tabular-nums text-slate-950">{value}</div>
      <div className="mt-1 text-xs font-semibold text-slate-500">{label}</div>
    </div>
  );
}

function WorkflowPanel({
  error,
  onRefreshSources,
  onRun,
  onTradeDateChange,
  result,
  running,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  sources,
  tradeDate,
  onScanLimitChange,
  onScreenFiltersChange,
  onSaveScreenFilters,
  watchlistPoolItems,
}: {
  error: string | null;
  onRefreshSources: () => void;
  onRun: () => void;
  onTradeDateChange: (value: string) => void;
  result: StrongStockScreeningResponse | null;
  running: boolean;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  sources: DataSourceStatusResponse | null;
  tradeDate: string;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  return (
    <aside className="space-y-3">
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-black text-slate-950">今日流程</h2>
          {error && <span className="rounded-full bg-red-50 px-2 py-1 text-xs font-bold text-red-700">错误</span>}
        </div>
        <DataSourceStrip onRefreshSources={onRefreshSources} sources={sources} />
        {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm leading-6 text-red-700">{error}</p>}

        <div className="mt-4">
          <ScreenPanel
            onRun={onRun}
            onScanLimitChange={onScanLimitChange}
            onScreenFiltersChange={onScreenFiltersChange}
            onSaveScreenFilters={onSaveScreenFilters}
            onTradeDateChange={onTradeDateChange}
            running={running}
            scanLimit={scanLimit}
            screenFilters={screenFilters}
            screenFiltersSaved={screenFiltersSaved}
            tradeDate={tradeDate}
          />
        </div>
      </section>

      <WatchlistPanel watchlistPoolItems={watchlistPoolItems} />
    </aside>
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
        <button
          className="min-h-[32px] shrink-0 rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100 active:translate-y-px"
          onClick={onRefreshSources}
          type="button"
        >
          刷新
        </button>
      </div>
      {items.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {items.map((item) => (
            <span
              className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${sourceTone[item.status]}`}
              key={item.source}
              title={item.detail}
            >
              {item.source} {item.status}
            </span>
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
  onTradeDateChange,
  running,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  tradeDate,
}: {
  onRun: () => void;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  onTradeDateChange: (value: string) => void;
  running: boolean;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  tradeDate: string;
}) {
  const scanLimitOptions = [40, 160, 300];

  return (
    <section className="border-t border-slate-100 pt-4">
      <h3 className="text-sm font-black text-slate-950">1. 手动筛选</h3>
      <label className="mt-3 block text-xs font-bold text-slate-600" htmlFor="trade-date">
        交易日
      </label>
      <input
        id="trade-date"
        className="mt-2 min-h-[40px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
        inputMode="numeric"
        onChange={(event) => onTradeDateChange(event.target.value)}
        placeholder="YYYY-MM-DD"
        value={tradeDate}
      />
      <div className="mt-3">
        <div className="flex items-center justify-between gap-2">
          <label className="text-xs font-bold text-slate-600" htmlFor="scan-limit">
            扫描候选数
          </label>
          <div className="flex gap-1">
            {scanLimitOptions.map((value) => (
              <button
                className={`h-7 min-w-9 rounded-md px-2 text-[11px] font-bold ring-1 transition ${
                  scanLimit === value
                    ? "bg-slate-950 text-white ring-slate-950"
                    : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-100"
                }`}
                key={value}
                onClick={() => onScanLimitChange(value)}
                type="button"
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        <input
          id="scan-limit"
          className="mt-2 min-h-[40px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
          inputMode="numeric"
          max={300}
          min={1}
          onChange={(event) => onScanLimitChange(normalizeScanLimit(event.target.value))}
          type="number"
          value={scanLimit}
        />
      </div>
      <AdvancedScreenFilters
        filters={screenFilters}
        onChange={onScreenFiltersChange}
        onSave={onSaveScreenFilters}
        saved={screenFiltersSaved}
      />
      <button
        className="mt-3 min-h-[42px] w-full rounded-lg bg-slate-950 px-4 py-2 text-sm font-bold text-white transition hover:bg-slate-800 active:translate-y-px disabled:cursor-not-allowed disabled:bg-slate-300"
        disabled={running || tradeDate.trim().length === 0}
        onClick={onRun}
        type="button"
      >
        {running ? "筛选中..." : "运行筛选"}
      </button>
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
  const activeMarketTypes = new Set(filters.market_types ?? []);

  function update(next: Partial<ScreenRunFilters>) {
    onChange(cleanScreenFilters({ ...filters, ...next }));
  }

  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3" open>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-black text-slate-950">
        <span>高级筛选</span>
        <span className="rounded-full bg-white px-2 py-1 text-[11px] font-bold tabular-nums text-slate-500 ring-1 ring-slate-100">
          已启用 {enabledCount}
        </span>
      </summary>
      <div className="mt-3 grid gap-3">
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

        <label className="block">
          <span className="text-xs font-bold text-slate-600">行业板块（多选）</span>
          <input
            className="mt-2 min-h-[38px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
            onChange={(event) => update({ industries: splitFilterValues(event.target.value) })}
            placeholder="消费电子，半导体"
            value={(filters.industries ?? []).join("，")}
          />
        </label>

        <div>
          <p className="text-xs font-bold text-slate-600">市场类型</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {marketTypeOptions.map((option) => (
              <label
                className="flex min-h-[34px] items-center gap-2 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-bold text-slate-700"
                key={option.value}
              >
                <input
                  checked={activeMarketTypes.has(option.value)}
                  className="size-4 rounded border-slate-300 text-slate-950"
                  onChange={(event) =>
                    update({
                      market_types: toggleMarketType(filters.market_types ?? [], option.value, event.target.checked),
                    })
                  }
                  type="checkbox"
                />
                {option.label}
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-[1fr_auto] gap-2">
          <button
            className={`min-h-[36px] rounded-md px-3 text-xs font-bold text-white transition active:translate-y-px ${
              saved ? "bg-emerald-600 hover:bg-emerald-700" : "bg-blue-600 hover:bg-blue-700"
            }`}
            onClick={onSave}
            type="button"
          >
            {saved ? "已保存" : "保存筛选参数"}
          </button>
          <button
            className="min-h-[36px] rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100 active:translate-y-px"
            onClick={() => onChange({})}
            type="button"
          >
            重置
          </button>
        </div>
        {saved && (
          <p aria-live="polite" className="rounded-md bg-emerald-50 px-2.5 py-2 text-xs font-bold text-emerald-700">
            筛选参数已保存到本机
          </p>
        )}
      </div>
    </details>
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
  onChange: (value: string) => void;
  placeholder: string;
  value: number | null | undefined;
}) {
  return (
    <label className="block">
      <span className="text-xs font-bold text-slate-600">{label}</span>
      <input
        className="mt-2 min-h-[38px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
        inputMode="decimal"
        min={min}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type="number"
        value={formatOptionalNumber(value)}
      />
    </label>
  );
}

function DisabledFilterInput({ label, placeholder }: { label: string; placeholder: string }) {
  return (
    <label className="block">
      <span className="text-xs font-bold text-slate-600">{label}</span>
      <input
        className="mt-2 min-h-[38px] w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-400 outline-none"
        disabled
        placeholder={placeholder}
      />
    </label>
  );
}

function WatchlistPanel({
  watchlistPoolItems,
}: {
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  const groups = groupWatchlistPoolItems(watchlistPoolItems);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-black text-slate-950">结构化自选池</h3>
          <p className="mt-1 text-xs font-medium text-slate-500">完整分组、标签和备注在独立页面管理。</p>
        </div>
        <a
          className="min-h-[32px] shrink-0 whitespace-nowrap rounded-md bg-slate-950 px-3 py-2 text-xs font-bold text-white transition hover:bg-slate-800 active:translate-y-px"
          href="/watchlist"
        >
          管理自选股
        </a>
      </div>
      <div className="mt-3 space-y-3">
        {groups.length > 0 ? (
          groups.map((group) => <WatchlistGroupSection group={group} key={group.name} />)
        ) : (
          <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">暂无自选股，候选表或详情抽屉可加入。</p>
        )}
      </div>
    </section>
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

function CandidateTable({
  generatedAt,
  items,
  onAddManyToWatchlist,
  onAddToWatchlist,
  onSelect,
  running,
  selectedSymbol,
  watchlistMessage,
  watchlistPoolItems,
}: {
  generatedAt: string | null;
  items: StrongStockScreeningItem[];
  onAddManyToWatchlist: (items: StrongStockScreeningItem[], group: string, tags: string[]) => void;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  running: boolean;
  selectedSymbol: string | null;
  watchlistMessage: string | null;
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  const [selectedCandidateSymbols, setSelectedCandidateSymbols] = useState<Set<string>>(() => new Set());
  const [batchGroup, setBatchGroup] = useState("");
  const [batchTagsText, setBatchTagsText] = useState("");
  const [candidateStatusFilter, setCandidateStatusFilter] = useState<CandidateStatusFilter>("all");
  const [strongIndustryOnly, setStrongIndustryOnly] = useState(false);
  const statusCounts = useMemo(() => {
    const counts: Record<CandidateStatusFilter, number> = {
      all: items.length,
      data_incomplete: 0,
      focus: 0,
      reduce_risk: 0,
      wait_pullback: 0,
    };
    for (const item of items) {
      counts[item.status] += 1;
    }
    return counts;
  }, [items]);
  const strongIndustryCount = useMemo(
    () => items.filter((item) => item.industry_strength === "strong").length,
    [items],
  );
  const visibleCandidates = useMemo(
    () =>
      items.filter(
        (item) =>
          (candidateStatusFilter === "all" || item.status === candidateStatusFilter) &&
          (!strongIndustryOnly || item.industry_strength === "strong"),
      ),
    [candidateStatusFilter, items, strongIndustryOnly],
  );
  const selectedCandidateItems = visibleCandidates.filter((item) => selectedCandidateSymbols.has(item.symbol));
  const watchlistSymbols = useMemo(
    () => new Set(watchlistPoolItems.map((item) => item.symbol)),
    [watchlistPoolItems],
  );

  useEffect(() => {
    const validSymbols = new Set(visibleCandidates.map((item) => item.symbol));
    setSelectedCandidateSymbols((current) => {
      const next = new Set(Array.from(current).filter((symbol) => validSymbols.has(symbol)));
      return next.size === current.size ? current : next;
    });
  }, [visibleCandidates]);

  function toggleCandidateSelection(symbol: string, checked: boolean) {
    setSelectedCandidateSymbols((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(symbol);
      } else {
        next.delete(symbol);
      }
      return next;
    });
  }

  function clearBatchSelection() {
    setSelectedCandidateSymbols(new Set());
  }

  function selectAllCandidates() {
    setSelectedCandidateSymbols(new Set(visibleCandidates.map((item) => item.symbol)));
  }

  function addSelectedCandidates() {
    onAddManyToWatchlist(selectedCandidateItems, batchGroup, splitTags(batchTagsText));
    clearBatchSelection();
  }

  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-2 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-400">Candidates</p>
          <h2 className="mt-1 text-xl font-black text-slate-950">候选决策表</h2>
        </div>
        <span className="text-xs font-semibold text-slate-400">
          {generatedAt ? new Date(generatedAt).toLocaleString("zh-CN") : "暂无运行结果"}
        </span>
      </div>
      {watchlistMessage && (
        <div aria-live="polite" className="border-b border-emerald-100 bg-emerald-50 px-5 py-3 text-sm font-bold text-emerald-700">
          {watchlistMessage}
        </div>
      )}
      {items.length > 0 && (
        <>
          <CandidateFilterBar
            candidateStatusFilter={candidateStatusFilter}
            onStatusFilterChange={setCandidateStatusFilter}
            onStrongIndustryOnlyChange={setStrongIndustryOnly}
            statusCounts={statusCounts}
            strongIndustryCount={strongIndustryCount}
            strongIndustryOnly={strongIndustryOnly}
            visibleCount={visibleCandidates.length}
          />
          {visibleCandidates.length > 0 && (
            <BatchActionBar
              batchGroup={batchGroup}
              batchTagsText={batchTagsText}
              onAddSelected={addSelectedCandidates}
              onBatchGroupChange={setBatchGroup}
              onBatchTagsTextChange={setBatchTagsText}
              onClearSelection={clearBatchSelection}
              onSelectAll={selectAllCandidates}
              selectedCount={selectedCandidateItems.length}
              totalCount={visibleCandidates.length}
            />
          )}
        </>
      )}
      <div className="hidden overflow-x-auto lg:block">
        {items.length > 0 ? (
          visibleCandidates.length > 0 ? (
            <table className="w-full min-w-[660px] border-separate border-spacing-0 text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs font-bold text-slate-400">
                  <th className="px-5 py-3">股票</th>
                  <th className="px-3 py-3">决策/得分</th>
                  <th className="px-4 py-3">行业/板块</th>
                  <th className="px-4 py-3">风险</th>
                  <th className="px-5 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibleCandidates.map((item) => (
                  <CandidateTableRow
                    isBatchSelected={selectedCandidateSymbols.has(item.symbol)}
                    isSelected={item.symbol === selectedSymbol}
                    item={item}
                    key={item.symbol}
                    isInWatchlist={watchlistSymbols.has(item.symbol)}
                    onAddToWatchlist={onAddToWatchlist}
                    onSelect={onSelect}
                    onToggleBatchSelect={toggleCandidateSelection}
                  />
                ))}
              </tbody>
            </table>
          ) : (
            <FilteredTableState />
          )
        ) : (
          <EmptyTableState running={running} />
        )}
      </div>
      <div className="border-t border-slate-100 p-3 lg:hidden">
        {items.length > 0 ? (
          visibleCandidates.length > 0 ? (
            <CandidateCardList
              isBatchSelected={(symbol) => selectedCandidateSymbols.has(symbol)}
              items={visibleCandidates}
              isInWatchlist={(symbol) => watchlistSymbols.has(symbol)}
              onAddToWatchlist={onAddToWatchlist}
              onSelect={onSelect}
              onToggleBatchSelect={toggleCandidateSelection}
              selectedSymbol={selectedSymbol}
            />
          ) : (
            <FilteredTableState />
          )
        ) : (
          <EmptyTableState running={running} />
        )}
      </div>
    </section>
  );
}

function CandidateCardList({
  isInWatchlist,
  isBatchSelected,
  items,
  onAddToWatchlist,
  onSelect,
  onToggleBatchSelect,
  selectedSymbol,
}: {
  isInWatchlist: (symbol: string) => boolean;
  isBatchSelected: (symbol: string) => boolean;
  items: StrongStockScreeningItem[];
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  onToggleBatchSelect: (symbol: string, checked: boolean) => void;
  selectedSymbol: string | null;
}) {
  return (
    <div className="space-y-3">
      {items.map((item) => {
        const view = statusCopy[item.status];
        const riskSummary = primaryRiskSummary(item);
        const alreadyAdded = isInWatchlist(item.symbol);
        return (
          <article
            aria-selected={item.symbol === selectedSymbol}
            className={`rounded-lg border p-3 transition ${
              item.symbol === selectedSymbol ? "border-slate-950 bg-slate-50" : "border-slate-200 bg-white"
            }`}
            key={item.symbol}
          >
            <div className="flex items-start gap-3">
              <input
                aria-label={`选择 ${item.name}`}
                checked={isBatchSelected(item.symbol)}
                className="mt-1 size-4 rounded border-slate-300"
                onChange={(event) => onToggleBatchSelect(item.symbol, event.target.checked)}
                type="checkbox"
              />
              <button className="min-w-0 flex-1 text-left" onClick={() => onSelect(item.symbol)} type="button">
                <span className="block truncate text-sm font-black text-slate-950">{item.name}</span>
                <span className="mt-1 block text-xs font-semibold text-slate-400">{item.symbol}</span>
              </button>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${view.tone}`}>
                {view.label}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-2 text-[11px] font-bold text-slate-700">
                得分 {item.score}
              </span>
              <IndustryBadge industry={item.industry} />
              <IndustryStrengthBadge item={item} />
            </div>
            <p className={`mt-3 line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>{riskSummary.text}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <a
                className="inline-flex min-h-[36px] items-center justify-center rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200"
                href={`/stock/${item.symbol}`}
              >
                K线
              </a>
              <button
                className="min-h-[36px] rounded-md bg-slate-950 px-3 text-xs font-bold text-white disabled:cursor-not-allowed disabled:bg-emerald-100 disabled:text-emerald-700"
                disabled={alreadyAdded}
                onClick={() => onAddToWatchlist(item, "自选", [])}
                type="button"
              >
                {alreadyAdded ? "已在自选" : "加入自选"}
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function CandidateFilterBar({
  candidateStatusFilter,
  onStatusFilterChange,
  onStrongIndustryOnlyChange,
  statusCounts,
  strongIndustryCount,
  strongIndustryOnly,
  visibleCount,
}: {
  candidateStatusFilter: CandidateStatusFilter;
  onStatusFilterChange: (value: CandidateStatusFilter) => void;
  onStrongIndustryOnlyChange: (value: boolean) => void;
  statusCounts: Record<CandidateStatusFilter, number>;
  strongIndustryCount: number;
  strongIndustryOnly: boolean;
  visibleCount: number;
}) {
  return (
    <div className="border-b border-slate-100 bg-white px-5 py-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black text-slate-700">候选筛选</span>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-bold tabular-nums text-slate-500">
            显示 {visibleCount}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {candidateStatusFilters.map((filter) => {
            const active = candidateStatusFilter === filter.value;
            return (
              <button
                aria-pressed={active}
                className={`inline-flex h-8 items-center rounded-md px-2.5 text-xs font-bold ring-1 transition active:translate-y-px ${
                  active
                    ? "bg-slate-950 text-white ring-slate-950"
                    : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50 hover:text-slate-950"
                }`}
                key={filter.value}
                onClick={() => onStatusFilterChange(filter.value)}
                type="button"
              >
                {filter.label}
                <span className="ml-1.5 tabular-nums opacity-75">{statusCounts[filter.value]}</span>
              </button>
            );
          })}
          <button
            aria-pressed={strongIndustryOnly}
            className={`inline-flex h-8 items-center rounded-md px-2.5 text-xs font-bold ring-1 transition active:translate-y-px ${
              strongIndustryOnly
                ? "bg-emerald-600 text-white ring-emerald-600"
                : "bg-emerald-50 text-emerald-700 ring-emerald-100 hover:bg-emerald-100"
            }`}
            onClick={() => onStrongIndustryOnlyChange(!strongIndustryOnly)}
            type="button"
          >
            强板块
            <span className="ml-1.5 tabular-nums opacity-80">{strongIndustryCount}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function BatchActionBar({
  batchGroup,
  batchTagsText,
  onAddSelected,
  onBatchGroupChange,
  onBatchTagsTextChange,
  onClearSelection,
  onSelectAll,
  selectedCount,
  totalCount,
}: {
  batchGroup: string;
  batchTagsText: string;
  onAddSelected: () => void;
  onBatchGroupChange: (value: string) => void;
  onBatchTagsTextChange: (value: string) => void;
  onClearSelection: () => void;
  onSelectAll: () => void;
  selectedCount: number;
  totalCount: number;
}) {
  return (
    <div className="grid gap-2 border-b border-slate-100 bg-slate-50 px-5 py-3 lg:grid-cols-[auto_minmax(90px,120px)_minmax(120px,1fr)_auto] lg:items-center">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-600">
        <span className="rounded-full bg-white px-2 py-1 ring-1 ring-slate-100">已选 {selectedCount}</span>
        <button className="text-slate-500 transition hover:text-slate-950" onClick={onSelectAll} type="button">
          全选 {totalCount}
        </button>
        <button
          className="text-slate-500 transition hover:text-slate-950 disabled:cursor-not-allowed disabled:text-slate-300"
          disabled={selectedCount === 0}
          onClick={onClearSelection}
          type="button"
        >
          清空选择
        </button>
      </div>
      <input
        className="min-h-[34px] rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
        onChange={(event) => onBatchGroupChange(event.target.value)}
        placeholder="批量分组"
        value={batchGroup}
      />
      <input
        className="min-h-[34px] rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
        onChange={(event) => onBatchTagsTextChange(event.target.value)}
        placeholder="批量标签，逗号分隔"
        value={batchTagsText}
      />
      <button
        className="min-h-[34px] min-w-[112px] whitespace-nowrap rounded-md bg-slate-950 px-3 text-xs font-bold text-white transition hover:bg-slate-800 active:translate-y-px disabled:cursor-not-allowed disabled:bg-slate-300"
        disabled={selectedCount === 0}
        onClick={onAddSelected}
        type="button"
      >
        批量加入自选
      </button>
    </div>
  );
}

function CandidateTableRow({
  isInWatchlist,
  isBatchSelected,
  isSelected,
  item,
  onAddToWatchlist,
  onSelect,
  onToggleBatchSelect,
}: {
  isInWatchlist: boolean;
  isBatchSelected: boolean;
  isSelected: boolean;
  item: StrongStockScreeningItem;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  onToggleBatchSelect: (symbol: string, checked: boolean) => void;
}) {
  const view = statusCopy[item.status];
  const riskSummary = primaryRiskSummary(item);

  return (
    <tr
      aria-selected={isSelected}
      className={`cursor-pointer transition ${isSelected ? "bg-slate-100" : "bg-white hover:bg-slate-50"}`}
      onClick={() => onSelect(item.symbol)}
    >
      <td className="px-5 py-4 align-top">
        <div className="flex items-start gap-2">
          <input
            aria-label={`选择 ${item.name}`}
            checked={isBatchSelected}
            className="mt-1 size-4 rounded border-slate-300"
            onChange={(event) => onToggleBatchSelect(item.symbol, event.target.checked)}
            onClick={(event) => event.stopPropagation()}
            type="checkbox"
          />
          <div className="min-w-0">
            <a
              className="inline-flex items-baseline gap-2 whitespace-nowrap font-black text-slate-950 transition hover:text-slate-700"
              href={`/stock/${item.symbol}`}
              onClick={(event) => event.stopPropagation()}
            >
              {item.name}
              <span className="text-xs font-semibold text-slate-400">{item.symbol}</span>
            </a>
            <p className="mt-1 line-clamp-1 text-xs text-slate-500">{item.rule_hits[0] ?? "暂无规则说明"}</p>
          </div>
        </div>
      </td>
      <td className="px-3 py-4 align-top">
        <span className={`inline-flex h-7 items-center whitespace-nowrap rounded-full px-2.5 text-xs font-bold ring-1 ${view.tone}`}>
          {view.label}
        </span>
        <p className="mt-2 text-xs font-black tabular-nums text-slate-950">得分 {item.score}</p>
      </td>
      <td className="px-4 py-4 align-top">
        <div className="flex flex-wrap items-center gap-1.5">
          <IndustryBadge industry={item.industry} />
          <IndustryStrengthBadge item={item} />
        </div>
      </td>
      <td className="max-w-[220px] px-4 py-4 align-top">
        <p className={`line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>
          {riskSummary.text}
        </p>
      </td>
      <td className="px-5 py-4 text-right align-top">
        <div className="flex justify-end gap-2">
          <button
            className="min-h-[32px] whitespace-nowrap rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100 active:translate-y-px"
            onClick={(event) => {
              event.stopPropagation();
              onSelect(item.symbol);
            }}
            type="button"
          >
            详情
          </button>
          <button
            className="min-h-[32px] whitespace-nowrap rounded-md bg-slate-950 px-3 text-xs font-bold text-white transition hover:bg-slate-800 active:translate-y-px disabled:cursor-not-allowed disabled:bg-emerald-100 disabled:text-emerald-700"
            disabled={isInWatchlist}
            onClick={(event) => {
              event.stopPropagation();
              onAddToWatchlist(item, "自选", []);
            }}
            type="button"
          >
            {isInWatchlist ? "已在自选" : "加入自选"}
          </button>
        </div>
      </td>
    </tr>
  );
}

function EmptyTableState({ running }: { running: boolean }) {
  return (
    <div className="px-5 py-12 text-center">
      <p className="text-sm font-bold text-slate-700">{running ? "筛选中..." : "未运行筛选"}</p>
      <p className="mt-2 text-sm text-slate-500">{running ? "正在读取候选和板块强度。" : "运行筛选后显示候选。"}</p>
    </div>
  );
}

function FilteredTableState() {
  return (
    <div className="px-5 py-12 text-center">
      <p className="text-sm font-bold text-slate-700">当前筛选暂无候选</p>
      <p className="mt-2 text-sm text-slate-500">切换候选筛选后显示匹配股票。</p>
    </div>
  );
}

function CandidateDetailPanel({
  intradayItem,
  item,
  onAddToWatchlist,
  riskItem,
  watchlistPoolItems,
}: {
  intradayItem: StrongStockIntradayItem | null;
  item: StrongStockScreeningItem | null;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  riskItem: WatchlistRiskItem | null;
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  const [watchlistGroup, setWatchlistGroup] = useState("");
  const [watchlistTagsText, setWatchlistTagsText] = useState("");
  const watchlistSymbols = useMemo(
    () => new Set(watchlistPoolItems.map((poolItem) => poolItem.symbol)),
    [watchlistPoolItems],
  );

  useEffect(() => {
    setWatchlistGroup("");
    setWatchlistTagsText("");
  }, [item?.symbol]);

  if (!item) {
    return (
      <aside className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase text-slate-400">Detail</p>
        <h2 className="mt-1 text-xl font-black text-slate-950">详情抽屉</h2>
        <div className="mt-8 rounded-lg bg-slate-50 p-5 text-sm text-slate-500">选择候选股票后显示结论和证据。</div>
      </aside>
    );
  }

  const view = statusCopy[item.status];
  const riskView = riskItem ? riskCopy[riskItem.risk_action] : null;
  const intradayView = intradayItem ? intradayCopy[intradayItem.action] : null;
  const otherFlags = item.risk_flags.filter((flag) => !flag.includes("严重异动"));
  const alreadyAdded = watchlistSymbols.has(item.symbol);

  return (
    <aside className="rounded-lg border border-slate-200 bg-white shadow-sm xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto">
      <div className="border-b border-slate-100 px-5 py-4">
        <p className="text-xs font-semibold uppercase text-slate-400">Detail</p>
        <h2 className="mt-1 text-xl font-black text-slate-950">详情抽屉</h2>
      </div>
      <div className="space-y-5 p-5">
        <section>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-lg font-black text-slate-950">{item.name}</h3>
              <p className="mt-1 text-xs font-semibold text-slate-400">{item.symbol}</p>
            </div>
            <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${view.tone}`}>
              {view.label}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-2 text-xs font-bold text-slate-700">
              得分 {item.score}
            </span>
            <IndustryBadge industry={item.industry} />
            <IndustryStrengthBadge item={item} />
          </div>
        </section>

        <DetailSection title="关键证据">
          <EvidenceList items={item.rule_hits} fallback="暂无规则说明" />
          {item.industry_notes.length > 0 && <EvidenceList items={item.industry_notes} />}
        </DetailSection>

        <DetailSection title="风险">
          <RiskCheckPanel item={item} riskItem={riskItem} />
          <EvidenceList items={otherFlags} fallback="暂无风险提示" />
          {riskItem && riskView && (
            <div className="mt-3 rounded-lg bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-500">自选股 / 持仓风控</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ring-1 ${riskView.tone}`}>
                  {riskView.label}
                </span>
              </div>
              <EvidenceList items={[...riskItem.risk_flags, ...riskItem.negative_news_flags, ...riskItem.intraday_notes]} />
            </div>
          )}
        </DetailSection>

        <DetailSection title="操作">
          <div className="space-y-2">
            <input
              className="min-h-[38px] w-full rounded-lg border border-slate-200 px-3 text-sm font-semibold text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
              onChange={(event) => setWatchlistGroup(event.target.value)}
              placeholder="分组"
              value={watchlistGroup}
            />
            <input
              className="min-h-[38px] w-full rounded-lg border border-slate-200 px-3 text-sm font-semibold text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
              onChange={(event) => setWatchlistTagsText(event.target.value)}
              placeholder="标签，逗号分隔"
              value={watchlistTagsText}
            />
            <button
              className="min-h-[38px] w-full rounded-lg bg-slate-950 px-4 text-sm font-bold text-white transition hover:bg-slate-800 active:translate-y-px disabled:cursor-not-allowed disabled:bg-emerald-100 disabled:text-emerald-700"
              disabled={alreadyAdded}
              onClick={() => onAddToWatchlist(item, watchlistGroup, splitTags(watchlistTagsText))}
              type="button"
            >
              {alreadyAdded ? "已在自选" : "加入自选"}
            </button>
          </div>
          {intradayItem && intradayView && (
            <div className="mt-3 rounded-lg bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-500">盘中监控</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ring-1 ${intradayView.tone}`}>
                  {intradayView.label}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <ValuePill label="现价" value={formatPrice(intradayItem.last_price)} />
                <ValuePill label="涨跌" value={formatPercent(intradayItem.pct_change)} />
              </div>
              <EvidenceList items={intradayItem.signals} />
              {(intradayItem.group || intradayItem.tags.length > 0) && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {intradayItem.group && (
                    <span className="inline-flex h-6 items-center rounded-full bg-slate-200 px-2 text-[11px] font-bold text-slate-700">
                      分组 {intradayItem.group}
                    </span>
                  )}
                  {intradayItem.tags.map((tag) => (
                    <span
                      className="inline-flex h-6 items-center rounded-full bg-white px-2 text-[11px] font-bold text-slate-600 ring-1 ring-slate-100"
                      key={tag}
                    >
                      标签 {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </DetailSection>

        <details className="rounded-lg border border-slate-100 bg-slate-50 p-3">
          <summary className="cursor-pointer text-xs font-bold text-slate-600">展开全部证据</summary>
          <div className="mt-3 space-y-3">
            <EvidenceBlock title="盘中备注" items={item.intraday_notes} />
            <EvidenceBlock title="数据源" items={item.source_trace} />
            <EvidenceBlock title="风控原文" items={item.risk_flags} />
          </div>
        </details>
      </div>
    </aside>
  );
}

function DetailSection({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="border-t border-slate-100 pt-4">
      <h4 className="text-sm font-black text-slate-950">{title}</h4>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function EvidenceList({ fallback, items }: { fallback?: string; items: string[] }) {
  if (items.length === 0) {
    return fallback ? <p className="text-sm leading-6 text-slate-500">{fallback}</p> : null;
  }
  return (
    <ul className="space-y-1.5">
      {items.map((item, index) => (
        <li className="text-sm leading-6 text-slate-600" key={`${item}-${index}`}>
          {item}
        </li>
      ))}
    </ul>
  );
}

function EvidenceBlock({ items, title }: { items: string[]; title: string }) {
  return (
    <div>
      <p className="text-xs font-bold text-slate-500">{title}</p>
      <EvidenceList fallback="暂无记录" items={items} />
    </div>
  );
}

function RiskCheckPanel({
  item,
  riskItem,
}: {
  item: StrongStockScreeningItem;
  riskItem: WatchlistRiskItem | null;
}) {
  const newsFlags = [...item.negative_news_flags, ...(riskItem?.negative_news_flags ?? [])];
  const severeFlags = [
    ...item.risk_flags.filter((flag) => flag.includes("严重异动")),
    ...(riskItem?.risk_flags.filter((flag) => flag.includes("严重异动")) ?? []),
  ];
  const severeStatus = riskItem?.severe_abnormal_warning === "triggered"
    ? riskItem.severe_abnormal_warning
    : item.severe_abnormal_warning;
  const newsStatus = riskItem?.negative_news_status === "triggered"
    ? riskItem.negative_news_status
    : item.negative_news_status;

  return (
    <div className="mb-3 space-y-2">
      <RiskCheckNotice
        flags={newsFlags}
        status={newsStatus}
        title="负面新闻待核验"
        unknownText="负面新闻未知，新闻源未返回有效结果"
        clearText="近20条东方财富新闻未命中负面关键词"
      />
      <RiskCheckNotice
        flags={severeFlags}
        status={severeStatus}
        title="严重异动"
        unknownText="严重异动状态未知，候选源未返回该字段"
        clearText="候选源显示未触发严重异动"
      />
    </div>
  );
}

function RiskCheckNotice({
  clearText,
  flags,
  status,
  title,
  unknownText,
}: {
  clearText: string;
  flags: string[];
  status: "triggered" | "clear" | "unknown";
  title: string;
  unknownText: string;
}) {
  if (status === "triggered") {
    return (
      <div className="rounded-lg bg-red-50 p-3 ring-1 ring-red-100">
        <p className="text-sm font-black leading-6 text-red-700">{title}</p>
        <EvidenceList items={flags.length > 0 ? flags : [title]} />
      </div>
    );
  }
  if (status === "clear") {
    return <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700">{clearText}</p>;
  }
  return <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs font-bold text-slate-500">{unknownText}</p>;
}

function primaryRiskSummary(item: StrongStockScreeningItem) {
  if (item.negative_news_status === "triggered") {
    return {
      text: item.negative_news_flags[0] ?? "负面新闻待核验",
      tone: "font-black text-red-600",
    };
  }
  if (item.severe_abnormal_warning === "triggered") {
    const severeFlag = item.risk_flags.find((flag) => flag.includes("严重异动"));
    return {
      text: severeFlag ?? "严重异动",
      tone: "font-black text-red-600",
    };
  }
  const firstRisk = item.risk_flags.find((flag) => !flag.includes("严重异动"));
  return {
    text: firstRisk ?? "无明显风险",
    tone: firstRisk ? "text-slate-500" : "text-slate-400",
  };
}

function ValuePill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-white px-2 text-[11px] font-bold text-slate-600 ring-1 ring-slate-100">
      {label} {value}
    </span>
  );
}

function IndustryStrengthBadge({ item }: { item: StrongStockScreeningItem }) {
  if (!item.industry_strength) {
    return null;
  }
  const view = industryStrengthCopy[item.industry_strength];
  const scoreText = item.industry_score > 0 ? ` +${item.industry_score}` : "";
  return (
    <span className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${view.tone}`}>
      板块强度 {view.label}
      {scoreText}
    </span>
  );
}

function IndustryBadge({ industry }: { industry: string | null }) {
  if (!industry) {
    return null;
  }
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-indigo-50 px-2 text-[11px] font-bold text-indigo-700 ring-1 ring-indigo-100">
      行业 {industry}
    </span>
  );
}

function groupWatchlistPoolItems(items: WatchlistPoolItem[]) {
  const groups: Array<{ name: string; items: WatchlistPoolItem[] }> = [];
  const indexByName = new Map<string, number>();
  for (const item of items) {
    const name = item.group?.trim() || "自选";
    let index = indexByName.get(name);
    if (index === undefined) {
      index = groups.length;
      indexByName.set(name, index);
      groups.push({ name, items: [] });
    }
    groups[index].items.push(item);
  }
  return groups;
}

function splitTags(value: string) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，]/)) {
    const tag = chunk.trim();
    if (tag && !seen.has(tag)) {
      seen.add(tag);
      output.push(tag);
    }
  }
  return output;
}

function splitFilterValues(value: string) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，]/)) {
    const item = chunk.trim();
    if (item && !seen.has(item)) {
      seen.add(item);
      output.push(item);
    }
  }
  return output;
}

function normalizeOptionalNumber(value: string, minimum?: number) {
  if (value.trim() === "") {
    return null;
  }
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return minimum === undefined ? parsed : Math.max(minimum, parsed);
}

function formatOptionalNumber(value: number | null | undefined) {
  return value === null || value === undefined ? "" : String(value);
}

function toggleMarketType(current: MarketType[], value: MarketType, checked: boolean) {
  const next = new Set(current);
  if (checked) {
    next.add(value);
  } else {
    next.delete(value);
  }
  return marketTypeOptions.map((option) => option.value).filter((option) => next.has(option));
}

function cleanScreenFilters(filters: ScreenRunFilters): ScreenRunFilters {
  return {
    ...(filters.min_market_cap_billion !== null &&
      filters.min_market_cap_billion !== undefined && { min_market_cap_billion: filters.min_market_cap_billion }),
    ...(filters.max_market_cap_billion !== null &&
      filters.max_market_cap_billion !== undefined && { max_market_cap_billion: filters.max_market_cap_billion }),
    ...(filters.kdj_j_max !== null && filters.kdj_j_max !== undefined && { kdj_j_max: filters.kdj_j_max }),
    ...((filters.industries ?? []).length > 0 && { industries: filters.industries }),
    ...((filters.market_types ?? []).length > 0 && { market_types: filters.market_types }),
  };
}

function activeScreenFilterCount(filters: ScreenRunFilters) {
  let count = 0;
  if (filters.min_market_cap_billion !== null && filters.min_market_cap_billion !== undefined) {
    count += 1;
  }
  if (filters.max_market_cap_billion !== null && filters.max_market_cap_billion !== undefined) {
    count += 1;
  }
  if (filters.kdj_j_max !== null && filters.kdj_j_max !== undefined) {
    count += 1;
  }
  if ((filters.industries ?? []).length > 0) {
    count += 1;
  }
  if ((filters.market_types ?? []).length > 0) {
    count += 1;
  }
  return count;
}

function normalizeScanLimit(value: string) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return 40;
  }
  return Math.max(1, Math.min(300, parsed));
}

function formatPrice(value: number | null) {
  if (value === null) {
    return "--";
  }
  return value.toFixed(2);
}

function formatPercent(value: number | null) {
  if (value === null) {
    return "--";
  }
  return `${value.toFixed(2)}%`;
}
