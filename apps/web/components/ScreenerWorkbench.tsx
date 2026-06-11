import type {
  DataSourceStatusResponse,
  SourceStatusValue,
  StrongStockScreeningItem,
  StrongStockScreeningResponse,
  WatchlistRiskItem,
} from "../lib/types";

type ScreenerWorkbenchProps = {
  tradeDate: string;
  sources: DataSourceStatusResponse | null;
  result: StrongStockScreeningResponse | null;
  running: boolean;
  error: string | null;
  onTradeDateChange: (value: string) => void;
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

const riskCopy: Record<WatchlistRiskItem["risk_action"], { label: string; tone: string }> = {
  hold_watch: { label: "继续观察", tone: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  reduce: { label: "降低关注", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  empty: { label: "空仓纪律触发", tone: "bg-red-50 text-red-700 ring-red-100" },
};

export function ScreenerWorkbench({
  tradeDate,
  sources,
  result,
  running,
  error,
  onTradeDateChange,
  onRun,
  onRefreshSources,
}: ScreenerWorkbenchProps) {
  const focusCount = result?.items.filter((item) => item.status === "focus").length ?? 0;
  const riskEmptyCount = result?.watchlist_risk_items.filter((item) => item.risk_action === "empty").length ?? 0;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl space-y-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Strong Stock Screener</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">强势股选股工作台</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                只筛选近 20 日有涨停证据的股票；空仓纪律只用于自选股或持仓风控。
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:min-w-[420px]">
              <Metric label="候选" value={result?.items.length ?? 0} />
              <Metric label="可关注" value={focusCount} />
              <Metric label="空仓风控" value={riskEmptyCount} />
            </div>
          </div>
        </header>

        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="space-y-5">
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-black text-slate-950">手动筛选</h2>
              <label className="mt-4 block text-sm font-semibold text-slate-700" htmlFor="trade-date">
                交易日
              </label>
              <input
                id="trade-date"
                className="mt-2 min-h-[44px] w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-950"
                inputMode="numeric"
                onChange={(event) => onTradeDateChange(event.target.value)}
                placeholder="YYYY-MM-DD"
                value={tradeDate}
              />
              <button
                className="mt-4 min-h-[46px] w-full rounded-lg bg-slate-950 px-4 py-3 text-sm font-bold text-white transition hover:bg-slate-800 active:translate-y-px disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={running || tradeDate.trim().length === 0}
                onClick={onRun}
                type="button"
              >
                {running ? "筛选中..." : "运行筛选"}
              </button>
              {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm leading-6 text-red-700">{error}</p>}
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-black text-slate-950">数据源状态</h2>
                <button
                  className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600 transition hover:bg-slate-200"
                  onClick={onRefreshSources}
                  type="button"
                >
                  刷新
                </button>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                TickFlow 只在本独立选股程序中用于报价和强度确认，不影响日报数据源。
              </p>
              <div className="mt-3 space-y-2">
                {(sources?.items ?? []).map((item) => (
                  <article key={item.source} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-black text-slate-950">{item.source}</h3>
                      <span className={`rounded-full px-2 py-1 text-xs font-bold ring-1 ${sourceTone[item.status]}`}>
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-500">{item.detail}</p>
                  </article>
                ))}
                {!sources && <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">读取数据源状态中。</p>}
              </div>
            </section>
          </aside>

          <section className="space-y-5">
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Candidates</p>
                  <h2 className="mt-1 text-xl font-black text-slate-950">强势候选</h2>
                </div>
                <span className="text-xs font-semibold text-slate-400">
                  {result ? new Date(result.generated_at).toLocaleString("zh-CN") : "暂无运行结果"}
                </span>
              </div>
              <div className="mt-4 overflow-hidden rounded-lg border border-slate-100">
                {result && result.items.length > 0 ? (
                  <div className="divide-y divide-slate-100">
                    {result.items.map((item) => <CandidateRow key={item.symbol} item={item} />)}
                  </div>
                ) : (
                  <p className="bg-slate-50 p-5 text-sm text-slate-500">运行筛选后显示候选。</p>
                )}
              </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-xl font-black text-slate-950">自选股 / 持仓风控</h2>
              <div className="mt-4 space-y-2">
                {result && result.watchlist_risk_items.length > 0 ? (
                  result.watchlist_risk_items.map((item) => <RiskRow key={item.symbol} item={item} />)
                ) : (
                  <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">暂无空仓纪律触发项。</p>
                )}
              </div>
            </section>
          </section>
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

function CandidateRow({ item }: { item: StrongStockScreeningItem }) {
  const view = statusCopy[item.status];
  return (
    <article className="grid gap-3 bg-white p-4 text-sm md:grid-cols-[minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <div className="font-black text-slate-950">
          {item.name}
          <span className="ml-2 text-xs font-semibold text-slate-400">{item.symbol}</span>
        </div>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          {[...item.rule_hits, ...item.risk_flags].slice(0, 4).join("；") || "暂无规则说明"}
        </p>
        <p className="mt-1 text-xs font-semibold text-slate-400">{item.intraday_notes.join("；")}</p>
      </div>
      <div className="flex items-center gap-2 md:justify-end">
        <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">得分 {item.score}</span>
        <span className={`rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${view.tone}`}>{view.label}</span>
      </div>
    </article>
  );
}

function RiskRow({ item }: { item: WatchlistRiskItem }) {
  const view = riskCopy[item.risk_action];
  return (
    <article className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-black text-slate-950">
            {item.name}
            <span className="ml-2 text-xs font-semibold text-slate-400">{item.symbol}</span>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {[...item.risk_flags, ...item.intraday_notes].join("；") || "暂无风控说明"}
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${view.tone}`}>
          {view.label}
        </span>
      </div>
    </article>
  );
}
