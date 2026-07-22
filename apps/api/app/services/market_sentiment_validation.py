from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, median
from typing import Literal

from pydantic import BaseModel

from app.models import KlineBar, SentimentPercentileLevel
from app.services.market_sentiment_percentile import MODEL_VERSION, calculate_sentiment_percentile


BENCHMARK_SYMBOL = "000985.SH"
HORIZONS: tuple[Literal[5, 10, 20], ...] = (5, 10, 20)
LEVELS: tuple[SentimentPercentileLevel, ...] = ("冰点", "偏冷", "中性", "偏热", "过热")


class SentimentValidationWindow(BaseModel):
    horizon: Literal[5, 10, 20]
    sample_count: int
    mean_return_pct: float | None
    median_return_pct: float | None
    positive_rate_pct: float | None
    mean_max_drawdown_pct: float | None
    future_data_end: str


class SentimentValidationBucket(BaseModel):
    level: SentimentPercentileLevel
    sample_count: int
    average_duration_days: float | None
    windows: list[SentimentValidationWindow]


class SentimentValidationReport(BaseModel):
    model_version: str
    benchmark_symbol: str
    data_start: str
    data_end: str
    horizons: list[Literal[5, 10, 20]]
    samples: list[dict[str, object]]
    buckets: list[SentimentValidationBucket]
    conclusion: str
    notes: list[str]
    generated_at: str


def validate_sentiment_percentile(bars: list[KlineBar]) -> SentimentValidationReport:
    normalized = _normalize_bars(bars)
    points = calculate_sentiment_percentile(normalized)
    index_by_date = {bar.date: index for index, bar in enumerate(normalized)}
    samples = [_sample(point.trade_date, point.score, point.level, index_by_date, normalized) for point in points]
    notes = _notes(samples)

    return SentimentValidationReport(
        model_version=MODEL_VERSION,
        benchmark_symbol=BENCHMARK_SYMBOL,
        data_start=normalized[0].date if normalized else "",
        data_end=normalized[-1].date if normalized else "",
        horizons=list(HORIZONS),
        samples=samples,
        buckets=_buckets(samples, normalized[-1].date if normalized else ""),
        conclusion=_conclusion(samples),
        notes=notes,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _normalize_bars(bars: list[KlineBar]) -> list[KlineBar]:
    by_date = {bar.date: bar for bar in bars}
    return [by_date[date] for date in sorted(by_date)]


def _sample(
    trade_date: str,
    score: float,
    level: SentimentPercentileLevel,
    index_by_date: dict[str, int],
    bars: list[KlineBar],
) -> dict[str, object]:
    index = index_by_date[trade_date]
    entry_close = bars[index].close
    forward_returns: dict[str, float] = {}
    max_drawdowns: dict[str, float] = {}
    for horizon in HORIZONS:
        if index + horizon >= len(bars):
            continue
        future_bars = bars[index + 1 : index + horizon + 1]
        forward_returns[str(horizon)] = (bars[index + horizon].close / entry_close - 1) * 100
        max_drawdowns[str(horizon)] = (min(bar.close for bar in future_bars) / entry_close - 1) * 100
    return {
        "trade_date": trade_date,
        "score": score,
        "level": level,
        "forward_returns": forward_returns,
        "max_drawdowns": max_drawdowns,
    }


def _buckets(samples: list[dict[str, object]], future_data_end: str) -> list[SentimentValidationBucket]:
    durations = _durations(samples)
    buckets: list[SentimentValidationBucket] = []
    for level in LEVELS:
        level_samples = [sample for sample in samples if sample["level"] == level]
        windows = [_window(level_samples, horizon, future_data_end) for horizon in HORIZONS]
        level_durations = durations[level]
        buckets.append(
            SentimentValidationBucket(
                level=level,
                sample_count=len(level_samples),
                average_duration_days=mean(level_durations) if level_durations else None,
                windows=windows,
            )
        )
    return buckets


def _durations(samples: list[dict[str, object]]) -> dict[SentimentPercentileLevel, list[int]]:
    durations: dict[SentimentPercentileLevel, list[int]] = {level: [] for level in LEVELS}
    previous: SentimentPercentileLevel | None = None
    duration = 0
    for sample in samples:
        level = sample["level"]
        if not isinstance(level, str):
            continue
        if level == previous:
            duration += 1
            continue
        if previous is not None:
            durations[previous].append(duration)
        previous = level  # type: ignore[assignment]
        duration = 1
    if previous is not None:
        durations[previous].append(duration)
    return durations


def _window(
    samples: list[dict[str, object]],
    horizon: Literal[5, 10, 20],
    future_data_end: str,
) -> SentimentValidationWindow:
    returns: list[float] = []
    drawdowns: list[float] = []
    for sample in samples:
        forward_returns = sample["forward_returns"]
        max_drawdowns = sample["max_drawdowns"]
        if not isinstance(forward_returns, dict) or not isinstance(max_drawdowns, dict):
            continue
        value = forward_returns.get(str(horizon))
        drawdown = max_drawdowns.get(str(horizon))
        if isinstance(value, (int, float)) and isinstance(drawdown, (int, float)):
            returns.append(float(value))
            drawdowns.append(float(drawdown))
    if not returns:
        return SentimentValidationWindow(
            horizon=horizon,
            sample_count=0,
            mean_return_pct=None,
            median_return_pct=None,
            positive_rate_pct=None,
            mean_max_drawdown_pct=None,
            future_data_end=future_data_end,
        )
    return SentimentValidationWindow(
        horizon=horizon,
        sample_count=len(returns),
        mean_return_pct=mean(returns),
        median_return_pct=median(returns),
        positive_rate_pct=sum(value > 0 for value in returns) / len(returns) * 100,
        mean_max_drawdown_pct=mean(drawdowns),
        future_data_end=future_data_end,
    )


def _notes(samples: list[dict[str, object]]) -> list[str]:
    if not samples:
        return ["Insufficient history: no sentiment percentile scores were produced."]
    notes: list[str] = []
    for level in LEVELS:
        level_samples = [sample for sample in samples if sample["level"] == level]
        if not level_samples:
            notes.append(f"Insufficient samples for level {level}.")
            continue
        for horizon in HORIZONS:
            if not any(str(horizon) in sample["forward_returns"] for sample in level_samples):
                notes.append(f"Insufficient samples for level {level} at {horizon}-day horizon.")
    return notes


def _conclusion(samples: list[dict[str, object]]) -> str:
    if not samples:
        return "No scored history is available for walk-forward validation."
    return "Walk-forward metrics are descriptive and do not alter historical sentiment scores."
