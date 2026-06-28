from __future__ import annotations

from collections import defaultdict
from statistics import mean, median

from app.gsgf_rules import analyze_gsgf
from app.models import (
    GsgfBacktestBucket,
    GsgfBacktestSummary,
    GsgfBacktestWindowStat,
    GsgfFinalStatus,
    KlineBar,
    StrongStockSourceStatus,
)

DEFAULT_BACKTEST_WINDOWS = [1, 3, 5, 10]
GSGF_STATUS_ORDER: list[GsgfFinalStatus] = ["确认买点", "候选", "低吸观察", "观察", "减仓", "回避"]


def summarize_gsgf_backtest(
    symbol_bars: dict[str, list[KlineBar]],
    *,
    windows: list[int] | None = None,
    min_history: int = 60,
) -> GsgfBacktestSummary:
    clean_windows = _clean_windows(windows)
    max_window = max(clean_windows)
    samples_by_status: dict[GsgfFinalStatus, list[_BacktestSample]] = defaultdict(list)
    skipped = 0

    for symbol, bars in symbol_bars.items():
        sorted_bars = sorted(bars, key=lambda bar: bar.date)
        if len(sorted_bars) < min_history + max_window:
            skipped += 1
            continue
        last_signal_index = len(sorted_bars) - max_window - 1
        for index in range(min_history - 1, last_signal_index + 1):
            prefix = sorted_bars[: index + 1]
            analysis = analyze_gsgf(prefix)
            current = sorted_bars[index]
            samples_by_status[analysis.final_status].append(
                _BacktestSample(
                    symbol=symbol,
                    score=analysis.total_score,
                    entry_close=current.close,
                    future_bars=sorted_bars[index + 1 : index + max_window + 1],
                )
            )

    buckets = [
        _bucket(status, samples_by_status[status], clean_windows)
        for status in GSGF_STATUS_ORDER
        if samples_by_status.get(status)
    ]
    sample_count = sum(bucket.sample_count for bucket in buckets)
    return GsgfBacktestSummary(
        windows=clean_windows,
        sample_count=sample_count,
        buckets=buckets,
        source_status=[
            StrongStockSourceStatus(
                source="股是股非回测",
                status="success",
                detail=f"输入 {len(symbol_bars)} 只，跳过 {skipped} 只，有效样本 {sample_count}",
            )
        ],
    )


class _BacktestSample:
    def __init__(
        self,
        *,
        symbol: str,
        score: int,
        entry_close: float,
        future_bars: list[KlineBar],
    ) -> None:
        self.symbol = symbol
        self.score = score
        self.entry_close = entry_close
        self.future_bars = future_bars


def _bucket(status: GsgfFinalStatus, samples: list[_BacktestSample], windows: list[int]) -> GsgfBacktestBucket:
    return GsgfBacktestBucket(
        status=status,
        sample_count=len(samples),
        avg_score=_round_or_none([sample.score for sample in samples]),
        windows=[_window_stat(samples, window) for window in windows],
    )


def _window_stat(samples: list[_BacktestSample], window: int) -> GsgfBacktestWindowStat:
    returns: list[float] = []
    drawdowns: list[float] = []
    for sample in samples:
        if len(sample.future_bars) < window or sample.entry_close <= 0:
            continue
        exit_close = sample.future_bars[window - 1].close
        returns.append((exit_close / sample.entry_close - 1) * 100)
        lowest_low = min(bar.low for bar in sample.future_bars[:window])
        drawdowns.append((lowest_low / sample.entry_close - 1) * 100)

    return GsgfBacktestWindowStat(
        window_days=window,
        sample_count=len(returns),
        win_rate=round(sum(1 for value in returns if value > 0) / len(returns) * 100, 2) if returns else None,
        avg_return_pct=_round_or_none(returns),
        median_return_pct=round(median(returns), 2) if returns else None,
        avg_max_drawdown_pct=_round_or_none(drawdowns),
    )


def _clean_windows(windows: list[int] | None) -> list[int]:
    values = windows or DEFAULT_BACKTEST_WINDOWS
    output: list[int] = []
    seen: set[int] = set()
    for value in values:
        normalized = max(1, min(int(value), 60))
        if normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output or DEFAULT_BACKTEST_WINDOWS


def _round_or_none(values: list[float] | list[int]) -> float | None:
    if not values:
        return None
    return round(mean(values), 2)
