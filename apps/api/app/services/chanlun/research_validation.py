from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import mean
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class WalkForwardFold:
    development_start: date
    development_end: date
    validation_start: date
    validation_end: date
    test_start: date
    test_end: date
    development_months: int = 24
    validation_months: int = 6
    test_months: int = 6


@dataclass(frozen=True)
class DecisionPoint:
    symbol: str
    decision_date: str


@dataclass(frozen=True)
class DailyOutcomeBar:
    trade_date: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class _OutcomeSeries:
    dates: tuple[str, ...]
    bars: tuple[DailyOutcomeBar, ...]


_EMPTY_OUTCOME_SERIES = _OutcomeSeries((), ())


@dataclass(frozen=True)
class OutcomeSample:
    symbol: str
    entry_at: str
    exit_at: str
    filled: bool
    gross_return_pct: float | None
    net_return_pct: float | None


@dataclass(frozen=True)
class ReturnMetrics:
    sample_count: int
    win_rate_pct: float
    profit_loss_ratio: float | None
    average_return_pct: float | None


@dataclass(frozen=True)
class PromotionMetrics:
    sample_count: int
    win_rate_pct: float
    profit_loss_ratio: float | None
    baseline_top5_net_return_pct: float
    v2_top5_net_return_pct: float
    baseline_top10_net_return_pct: float
    v2_top10_net_return_pct: float
    baseline_top5_max_drawdown_pct: float
    v2_top5_max_drawdown_pct: float
    baseline_top10_max_drawdown_pct: float
    v2_top10_max_drawdown_pct: float
    recent_six_month_return_pct: float
    recent_decay_pct: float
    leakage_passed: bool


@dataclass(frozen=True)
class PromotionDecision:
    recommendation: str
    failed_gates: tuple[str, ...]


@dataclass(frozen=True)
class FrozenValidationDataset:
    candidates_by_date: Mapping[str, Sequence[Mapping[str, Any]]]
    daily_bars_by_symbol: Mapping[str, Sequence[Any]]


@dataclass(frozen=True)
class PortfolioValidationMetrics:
    top_n: int
    baseline_net_return_pct: float
    v2_net_return_pct: float
    baseline_max_drawdown_pct: float
    v2_max_drawdown_pct: float
    baseline_sample_count: int
    v2_sample_count: int
    baseline_win_rate_pct: float
    v2_win_rate_pct: float
    baseline_profit_loss_ratio: float | None
    v2_profit_loss_ratio: float | None
    baseline_equity_curve: tuple[dict[str, float | str], ...]
    v2_equity_curve: tuple[dict[str, float | str], ...]


@dataclass(frozen=True)
class FrozenValidationResult:
    portfolios: dict[str, PortfolioValidationMetrics]
    samples: list[dict[str, Any]]
    leakage_passed: bool


def build_walk_forward_folds(start: date, end: date) -> list[WalkForwardFold]:
    folds: list[WalkForwardFold] = []
    cursor = start
    while True:
        development_end = _add_months(cursor, 24) - timedelta(days=1)
        validation_start = development_end + timedelta(days=1)
        validation_end = _add_months(validation_start, 6) - timedelta(days=1)
        test_start = validation_end + timedelta(days=1)
        test_end = _add_months(test_start, 6) - timedelta(days=1)
        if test_end > end:
            break
        folds.append(
            WalkForwardFold(
                development_start=cursor,
                development_end=development_end,
                validation_start=validation_start,
                validation_end=validation_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        cursor = _add_months(cursor, 6)
    return folds


def build_outcome(
    decision: DecisionPoint,
    future_bars: list[DailyOutcomeBar],
    *,
    round_trip_cost_pct: float = 0.20,
) -> OutcomeSample:
    return _build_outcome_from_series(
        decision,
        _build_outcome_series(future_bars),
        round_trip_cost_pct=round_trip_cost_pct,
    )


def _build_outcome_series(bars: Sequence[DailyOutcomeBar]) -> _OutcomeSeries:
    ordered = tuple(sorted(bars, key=lambda bar: bar.trade_date))
    return _OutcomeSeries(
        dates=tuple(bar.trade_date for bar in ordered),
        bars=ordered,
    )


def _build_outcome_from_series(
    decision: DecisionPoint,
    series: _OutcomeSeries,
    *,
    round_trip_cost_pct: float = 0.20,
) -> OutcomeSample:
    decision_date = _parse_date(decision.decision_date)
    future_index = bisect_right(series.dates, decision_date.isoformat())
    bars = series.bars[future_index : future_index + 3]
    first = bars[0] if bars else None
    last = bars[-1] if bars else None
    entry_at = _timestamp(first.trade_date if first else _add_days(decision_date, 1), time(9, 30))
    exit_at = _timestamp(last.trade_date if last else _add_days(decision_date, 3), time(15, 0))
    if first is None or last is None or first.open <= 0 or _is_untradeable_limit_up(first):
        return OutcomeSample(decision.symbol, entry_at, exit_at, False, None, None)
    gross = (last.close / first.open - 1) * 100
    return OutcomeSample(
        decision.symbol,
        entry_at,
        exit_at,
        True,
        round(gross, 6),
        round(gross - round_trip_cost_pct, 6),
    )


def summarize_returns(returns: list[float]) -> ReturnMetrics:
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    average_win = mean(wins) if wins else None
    average_loss = abs(mean(losses)) if losses else None
    return ReturnMetrics(
        sample_count=len(returns),
        win_rate_pct=round(len(wins) / len(returns) * 100, 6) if returns else 0.0,
        profit_loss_ratio=(round(average_win / average_loss, 6) if average_win and average_loss else None),
        average_return_pct=round(mean(returns), 6) if returns else None,
    )


def validate_frozen_dataset(
    dataset: FrozenValidationDataset,
    *,
    decision_dates: Sequence[str] | None = None,
    score_candidate: Callable[[Mapping[str, Any]], tuple[int | None, bool]] | None = None,
    round_trip_cost_pct: float = 0.20,
    top_ns: Sequence[int] = (3, 5, 10),
) -> FrozenValidationResult:
    """Evaluate fixed candidate snapshots without reading any network source."""
    selected_dates = sorted(decision_dates or dataset.candidates_by_date)
    sample_rows: list[dict[str, Any]] = []
    by_date: dict[str, list[dict[str, Any]]] = {}
    leakage_passed = True
    outcome_series_by_symbol = {
        symbol: _build_outcome_series(_coerce_outcome_bars(bars))
        for symbol, bars in dataset.daily_bars_by_symbol.items()
    }

    for decision_date in selected_dates:
        candidates = sorted(
            dataset.candidates_by_date.get(decision_date, ()),
            key=lambda candidate: int(candidate.get("baseline_rank", 0)),
        )
        ranked: list[dict[str, Any]] = []
        for candidate in candidates:
            symbol = str(candidate.get("symbol", "")).strip().upper()
            baseline_rank = int(candidate.get("baseline_rank", 0))
            score, eligible = score_candidate(candidate) if score_candidate else (None, False)
            outcome = _build_outcome_from_series(
                DecisionPoint(symbol=symbol, decision_date=decision_date),
                outcome_series_by_symbol.get(symbol, _EMPTY_OUTCOME_SERIES),
                round_trip_cost_pct=round_trip_cost_pct,
            )
            if outcome.entry_at <= _timestamp(decision_date, time(15, 0)):
                leakage_passed = False
            ranked.append(
                {
                    "symbol": symbol,
                    "decision_date": decision_date,
                    "baseline_rank": baseline_rank,
                    "score": score,
                    "eligible": bool(eligible and score is not None),
                    "outcome": outcome,
                }
            )
        ranked.sort(
            key=lambda item: (
                0 if item["eligible"] else 1,
                -(item["score"] if item["score"] is not None else -1),
                item["baseline_rank"],
            )
        )
        for index, item in enumerate(ranked, start=1):
            item["v2_rank"] = index
            outcome: OutcomeSample = item["outcome"]
            sample_rows.append(
                {
                    "decision_date": item["decision_date"],
                    "symbol": item["symbol"],
                    "baseline_rank": item["baseline_rank"],
                    "v2_rank": item["v2_rank"],
                    "score": item["score"],
                    "eligible": item["eligible"],
                    "filled": outcome.filled,
                    "gross_return_pct": outcome.gross_return_pct,
                    "net_return_pct": outcome.net_return_pct,
                    "entry_at": outcome.entry_at,
                    "exit_at": outcome.exit_at,
                }
            )
        by_date[decision_date] = ranked

    portfolios = {
        f"top{top_n}": _validate_portfolio(
            top_n,
            [item for decision_date in selected_dates for item in by_date.get(decision_date, ())],
        )
        for top_n in top_ns
    }
    return FrozenValidationResult(
        portfolios=portfolios,
        samples=sample_rows,
        leakage_passed=leakage_passed,
    )


def evaluate_promotion(metrics: PromotionMetrics) -> PromotionDecision:
    failed: list[str] = []
    if metrics.sample_count < 300:
        failed.append("sample_count")
    if metrics.win_rate_pct <= 50:
        failed.append("win_rate_pct")
    if metrics.profit_loss_ratio is None or metrics.profit_loss_ratio < 1.3:
        failed.append("profit_loss_ratio")
    if metrics.v2_top5_net_return_pct <= metrics.baseline_top5_net_return_pct:
        failed.append("top5_excess_return")
    if metrics.v2_top10_net_return_pct <= metrics.baseline_top10_net_return_pct:
        failed.append("top10_excess_return")
    if metrics.v2_top5_max_drawdown_pct < metrics.baseline_top5_max_drawdown_pct:
        failed.append("top5_drawdown")
    if metrics.v2_top10_max_drawdown_pct < metrics.baseline_top10_max_drawdown_pct:
        failed.append("top10_drawdown")
    if metrics.recent_six_month_return_pct <= 0:
        failed.append("recent_return")
    if metrics.recent_decay_pct < -5:
        failed.append("recent_decay")
    if not metrics.leakage_passed:
        failed.append("leakage")
    return PromotionDecision(
        recommendation="suggest_promotion" if not failed else "keep_shadow",
        failed_gates=tuple(failed),
    )


def _validate_portfolio(top_n: int, rows: list[dict[str, Any]]) -> PortfolioValidationMetrics:
    dates = sorted({str(row["decision_date"]) for row in rows})

    baseline_returns: list[float] = []
    v2_returns: list[float] = []
    for date_value in dates:
        day_rows = [row for row in rows if row["decision_date"] == date_value]
        baseline_rows = sorted(day_rows, key=lambda row: row["baseline_rank"])[:top_n]
        v2_rows = sorted(day_rows, key=lambda row: row["v2_rank"])[:top_n]
        baseline_returns.append(_mean_ranked_return(baseline_rows))
        v2_returns.append(_mean_ranked_return(v2_rows))

    baseline_curve = _equity_curve(dates, baseline_returns)
    v2_curve = _equity_curve(dates, v2_returns)
    baseline_filled = [
        float(row["outcome"].net_return_pct)
        for date_value in dates
        for row in sorted(
            [row for row in rows if row["decision_date"] == date_value],
            key=lambda row: row["baseline_rank"],
        )[:top_n]
        if _row_filled(row)
    ]
    v2_filled = [
        float(row["outcome"].net_return_pct)
        for date_value in dates
        for row in sorted(
            [row for row in rows if row["decision_date"] == date_value],
            key=lambda row: row["v2_rank"],
        )[:top_n]
        if _row_filled(row)
    ]
    baseline_summary = summarize_returns(baseline_filled)
    v2_summary = summarize_returns(v2_filled)
    return PortfolioValidationMetrics(
        top_n=top_n,
        baseline_net_return_pct=_cumulative_return(baseline_returns),
        v2_net_return_pct=_cumulative_return(v2_returns),
        baseline_max_drawdown_pct=_max_drawdown(baseline_curve),
        v2_max_drawdown_pct=_max_drawdown(v2_curve),
        baseline_sample_count=baseline_summary.sample_count,
        v2_sample_count=v2_summary.sample_count,
        baseline_win_rate_pct=baseline_summary.win_rate_pct,
        v2_win_rate_pct=v2_summary.win_rate_pct,
        baseline_profit_loss_ratio=baseline_summary.profit_loss_ratio,
        v2_profit_loss_ratio=v2_summary.profit_loss_ratio,
        baseline_equity_curve=tuple(baseline_curve),
        v2_equity_curve=tuple(v2_curve),
    )


def _coerce_outcome_bars(bars: Sequence[Any]) -> list[DailyOutcomeBar]:
    result: list[DailyOutcomeBar] = []
    for bar in bars:
        trade_date = getattr(bar, "trade_date", None) or getattr(bar, "date", None)
        if trade_date is None:
            continue
        result.append(
            DailyOutcomeBar(
                trade_date=str(trade_date)[:10],
                open=float(getattr(bar, "open")),
                high=float(getattr(bar, "high")),
                low=float(getattr(bar, "low")),
                close=float(getattr(bar, "close")),
            )
        )
    return result


def _mean_ranked_return(rows: Sequence[Mapping[str, Any]]) -> float:
    values = [
        float(row["outcome"].net_return_pct)
        for row in rows
        if _row_filled(row)
    ]
    return mean(values) if values else 0.0


def _row_filled(row: Mapping[str, Any]) -> bool:
    outcome = row.get("outcome")
    return bool(outcome is not None and outcome.filled and outcome.net_return_pct is not None)


def _equity_curve(dates: Sequence[str], returns: Sequence[float]) -> list[dict[str, float | str]]:
    equity = 100.0
    curve: list[dict[str, float | str]] = []
    for date_value, return_pct in zip(dates, returns, strict=True):
        equity *= 1 + return_pct / 100
        curve.append({"date": date_value, "equity": round(equity, 8)})
    return curve


def _cumulative_return(returns: Sequence[float]) -> float:
    equity = 1.0
    for return_pct in returns:
        equity *= 1 + return_pct / 100
    return round((equity - 1) * 100, 6)


def _max_drawdown(curve: Sequence[Mapping[str, float | str]]) -> float:
    peak = 0.0
    drawdown = 0.0
    for point in curve:
        equity = float(point["equity"])
        peak = max(peak, equity)
        if peak:
            drawdown = min(drawdown, (equity / peak - 1) * 100)
    return round(drawdown, 6)


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    last_day = next_month - timedelta(days=1)
    return date(year, month, min(value.day, last_day.day))


def _parse_date(value: str | date) -> date:
    text = str(value)
    if len(text) >= 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d").date()
    return date.fromisoformat(text[:10])


def _add_days(value: date, days: int) -> str:
    return (value + timedelta(days=days)).isoformat()


def _timestamp(value: str, at: time) -> str:
    return datetime.combine(_parse_date(value), at, tzinfo=SHANGHAI).isoformat(timespec="seconds")


def _is_untradeable_limit_up(bar: DailyOutcomeBar) -> bool:
    return bar.open == bar.high == bar.low == bar.close
