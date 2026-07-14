from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import mean
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
    decision_date = _parse_date(decision.decision_date)
    bars = sorted(
        (bar for bar in future_bars if _parse_date(bar.trade_date) > decision_date),
        key=lambda bar: bar.trade_date,
    )[:3]
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
