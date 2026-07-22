from __future__ import annotations

from math import isfinite

from app.models import (
    KlineBar,
    SentimentPercentileFactor,
    SentimentPercentileFactors,
    SentimentPercentileLevel,
    SentimentPercentilePoint,
)


MODEL_VERSION = "market-sentiment-percentile-v1"
WINDOW = 500
WEIGHTS = {
    "volume": 0.2,
    "index_move_5d": 0.2,
    "price_position": 0.2,
    "amplitude_5d": 0.2,
    "volume_trend": 0.2,
}


def midrank_percentile(values: list[float], current: float) -> float:
    if len(values) != WINDOW:
        raise ValueError(f"percentile window must contain {WINDOW} values")
    less = sum(value < current for value in values)
    equal = sum(value == current for value in values)
    return round((less + 0.5 * equal) / WINDOW * 100, 1)


def sentiment_percentile_level(score: float) -> SentimentPercentileLevel:
    if score < 20:
        return "冰点"
    if score < 40:
        return "偏冷"
    if score < 60:
        return "中性"
    if score < 80:
        return "偏热"
    return "过热"


def directional_amplitude(
    previous_close: float,
    high: float,
    low: float,
    close: float,
) -> float:
    direction = (close > previous_close) - (close < previous_close)
    return direction * (high - low) / previous_close


def calculate_sentiment_percentile(bars: list[KlineBar]) -> list[SentimentPercentilePoint]:
    normalized = _normalize_bars(bars)
    amounts = [float(bar.amount) for bar in normalized]
    returns: list[float | None] = [None] * len(normalized)
    amplitudes: list[float | None] = [None] * len(normalized)
    volume_trends: list[float | None] = [None] * len(normalized)

    for index, bar in enumerate(normalized):
        if index >= 5:
            previous_close = normalized[index - 5].close
            returns[index] = bar.close / previous_close - 1
            amplitudes[index] = directional_amplitude(
                previous_close,
                max(item.high for item in normalized[index - 4 : index + 1]),
                min(item.low for item in normalized[index - 4 : index + 1]),
                bar.close,
            )
        if index >= 19:
            mean_5 = sum(amounts[index - 4 : index + 1]) / 5
            mean_20 = sum(amounts[index - 19 : index + 1]) / 20
            volume_trends[index] = mean_5 / mean_20 - 1

    points: list[SentimentPercentilePoint] = []
    for index in range(518, len(normalized)):
        window_start = index - WINDOW + 1
        price_low = min(bar.low for bar in normalized[window_start : index + 1])
        price_high = max(bar.high for bar in normalized[window_start : index + 1])
        price_range = price_high - price_low
        if price_range == 0:
            continue

        current_return = returns[index]
        current_amplitude = amplitudes[index]
        current_volume_trend = volume_trends[index]
        if current_return is None or current_amplitude is None or current_volume_trend is None:
            continue
        return_values = returns[window_start : index + 1]
        amplitude_values = amplitudes[window_start : index + 1]
        trend_values = volume_trends[window_start : index + 1]
        if any(value is None for value in (*return_values, *amplitude_values, *trend_values)):
            continue

        price_position = (normalized[index].close - price_low) / price_range * 100
        factors = SentimentPercentileFactors(
            volume=SentimentPercentileFactor(
                score=midrank_percentile(amounts[window_start : index + 1], amounts[index]),
                raw_value=amounts[index],
                raw_unit="CNY",
            ),
            index_move_5d=SentimentPercentileFactor(
                score=midrank_percentile(
                    [value for value in return_values if value is not None], current_return
                ),
                raw_value=current_return * 100,
                raw_unit="%",
            ),
            price_position=SentimentPercentileFactor(
                score=round(max(0, min(100, price_position)), 1),
                raw_value=price_position,
                raw_unit="%",
            ),
            amplitude_5d=SentimentPercentileFactor(
                score=midrank_percentile(
                    [value for value in amplitude_values if value is not None], current_amplitude
                ),
                raw_value=current_amplitude * 100,
                raw_unit="%",
            ),
            volume_trend=SentimentPercentileFactor(
                score=midrank_percentile(
                    [value for value in trend_values if value is not None], current_volume_trend
                ),
                raw_value=current_volume_trend * 100,
                raw_unit="%",
            ),
        )
        score = round(
            sum(
                (
                    factors.volume.score,
                    factors.index_move_5d.score,
                    factors.price_position.score,
                    factors.amplitude_5d.score,
                    factors.volume_trend.score,
                )
            )
            / 5,
            1,
        )
        points.append(
            SentimentPercentilePoint(
                trade_date=normalized[index].date,
                score=score,
                level=sentiment_percentile_level(score),
                factors=factors,
            )
        )
    return points[-WINDOW:]


def _normalize_bars(bars: list[KlineBar]) -> list[KlineBar]:
    by_date: dict[str, KlineBar] = {}
    for bar in bars:
        validate_sentiment_bar(bar)
        by_date[bar.date] = bar
    return [by_date[key] for key in sorted(by_date)]


def validate_sentiment_bar(bar: KlineBar) -> None:
    values = (bar.open, bar.high, bar.low, bar.close, bar.amount)
    if (
        bar.amount is None
        or not all(isfinite(float(value)) for value in values if value is not None)
        or min(bar.open, bar.high, bar.low, bar.close, bar.amount) <= 0
        or bar.high < bar.low
        or bar.high < max(bar.open, bar.close)
        or bar.low > min(bar.open, bar.close)
    ):
        raise ValueError(f"invalid market bar: {bar.date}")
