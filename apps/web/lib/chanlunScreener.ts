import type {
  ChanlunPeriod,
  ChanlunScreeningSummary,
  ChanlunSignalType,
  ScreenRunFilters,
} from "./types";


export function chanlunFilterFields(filters: ScreenRunFilters): ScreenRunFilters {
  return {
    ...(filters.chanlun_min_confluence_score !== null &&
      filters.chanlun_min_confluence_score !== undefined && {
        chanlun_min_confluence_score: filters.chanlun_min_confluence_score,
      }),
    ...(filters.chanlun_require_confirmed_buy && { chanlun_require_confirmed_buy: true }),
  };
}


export function activeChanlunFilterCount(filters: ScreenRunFilters): number {
  return Number(
    filters.chanlun_min_confluence_score !== null &&
      filters.chanlun_min_confluence_score !== undefined,
  ) + Number(Boolean(filters.chanlun_require_confirmed_buy));
}


export function chanlunScreeningView(summary: ChanlunScreeningSummary | null | undefined): {
  title: string;
  detail: string;
  insufficient: boolean;
} {
  if (!summary || summary.availability !== "ready") {
    return {
      title: "结构数据不足",
      detail: "进入工作台补充分钟历史",
      insufficient: true,
    };
  }
  const latestSignal = summary.periods
    .filter((item) => item.latest_signal_type && item.latest_signal_at)
    .sort((left, right) => (right.latest_signal_at ?? "").localeCompare(left.latest_signal_at ?? ""))[0];
  const signalDetail = latestSignal?.latest_signal_type
    ? `${periodLabel(latestSignal.period)}${signalLabel(latestSignal.latest_signal_type)}`
    : "暂无确认买卖点";
  return {
    title: `缠论共振 ${summary.confluence_score} · ${summary.bullish_periods}周期向上`,
    detail: summary.freshness === "stale" ? `缓存已过期 · ${signalDetail}` : signalDetail,
    insufficient: false,
  };
}


function periodLabel(period: ChanlunPeriod): string {
  return {
    "1d": "日线",
    "60m": "60分钟",
    "30m": "30分钟",
    "5m": "5分钟",
  }[period];
}


function signalLabel(signal: ChanlunSignalType): string {
  return {
    one_buy: "一买",
    one_sell: "一卖",
    two_buy: "二买",
    two_sell: "二卖",
    three_buy: "三买",
    three_sell: "三卖",
  }[signal];
}
