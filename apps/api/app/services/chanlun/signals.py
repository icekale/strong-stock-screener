from __future__ import annotations

from app.models import (
    ChanlunDivergence,
    ChanlunSignal,
    ChanlunStroke,
    ChanlunZone,
    KlineBar,
)


def derive_confirmed_events(
    bars: list[KlineBar],
    strokes: list[ChanlunStroke],
    zones: list[ChanlunZone],
    *,
    rule_version: str = "cl-v1",
) -> tuple[list[ChanlunDivergence], list[ChanlunSignal]]:
    """Compare completed same-direction strokes using only bars available at each endpoint."""
    if len(bars) < 2:
        return [], []

    index_by_date = {bar.date: index for index, bar in enumerate(bars)}
    histogram = _macd_histogram([bar.close for bar in bars])
    completed = sorted(
        (
            stroke
            for stroke in strokes
            if stroke.status in {"confirmed", "final"}
            and stroke.start_at in index_by_date
            and stroke.end_at in index_by_date
        ),
        key=lambda stroke: index_by_date[stroke.end_at],
    )
    confirmed_zones = [
        zone
        for zone in zones
        if not zone.virtual
        and zone.status in {"confirmed", "final"}
        and zone.start_at in index_by_date
        and zone.end_at in index_by_date
    ]
    divergences: list[ChanlunDivergence] = []
    signals: list[ChanlunSignal] = []

    for current_index, current in enumerate(completed):
        reference = next(
            (
                candidate
                for candidate in reversed(completed[:current_index])
                if candidate.direction == current.direction
            ),
            None,
        )
        if reference is None:
            continue

        reference_strength = _stroke_strength(reference, index_by_date, histogram)
        current_strength = _stroke_strength(current, index_by_date, histogram)
        if reference_strength is None or current_strength is None or current_strength >= reference_strength:
            continue
        if not _extends_price(current, reference):
            continue

        zone_count = sum(
            1
            for zone in confirmed_zones
            if index_by_date[reference.start_at] <= index_by_date[zone.end_at] <= index_by_date[current.end_at]
        )
        if zone_count == 0:
            continue

        divergence_type = "consolidation" if zone_count == 1 else ("bottom" if current.direction == "down" else "top")
        coefficient = current_strength / reference_strength
        divergence = ChanlunDivergence(
            id=f"divergence:{divergence_type}:{reference.id}:{current.id}",
            type=divergence_type,
            occurred_at=current.end_at,
            reference_occurred_at=reference.end_at,
            direction=current.direction,
            reference_stroke_id=reference.id,
            current_stroke_id=current.id,
            reference_price=reference.end_price,
            current_price=current.end_price,
            reference_macd_strength=reference_strength,
            current_macd_strength=current_strength,
            coefficient=coefficient,
            zone_count=zone_count,
            status="confirmed",
            rule_version=rule_version,
        )
        divergences.append(divergence)
        signal_type = "one_buy" if current.direction == "down" else "one_sell"
        signals.append(
            ChanlunSignal(
                id=f"signal:{signal_type}:{current.id}",
                type=signal_type,
                occurred_at=current.end_at,
                price=current.end_price,
                divergence_id=divergence.id,
                stroke_id=current.id,
                status="confirmed",
                rule_version=rule_version,
            )
        )

    signals.extend(
        _derive_second_and_third_signals(
            bars,
            completed,
            index_by_date,
            rule_version=rule_version,
        )
    )
    signals.sort(key=lambda signal: (index_by_date[signal.occurred_at], signal.type))
    return divergences, signals


def _macd_histogram(closes: list[float]) -> list[float]:
    fast = closes[0]
    slow = closes[0]
    signal = 0.0
    histogram: list[float] = []
    for close in closes:
        fast += (close - fast) * 2 / 13
        slow += (close - slow) * 2 / 27
        difference = fast - slow
        signal += (difference - signal) * 2 / 10
        histogram.append((difference - signal) * 2)
    return histogram


def _stroke_strength(
    stroke: ChanlunStroke,
    index_by_date: dict[str, int],
    histogram: list[float],
) -> float | None:
    start = index_by_date[stroke.start_at]
    end = index_by_date[stroke.end_at]
    if end <= start:
        return None
    values = histogram[start : end + 1]
    return sum(abs(value) for value in values) / len(values)


def _extends_price(current: ChanlunStroke, reference: ChanlunStroke) -> bool:
    if current.direction == "down":
        return current.end_price < reference.end_price
    if current.direction == "up":
        return current.end_price > reference.end_price
    return False


def _derive_second_and_third_signals(
    bars: list[KlineBar],
    strokes: list[ChanlunStroke],
    index_by_date: dict[str, int],
    *,
    rule_version: str,
) -> list[ChanlunSignal]:
    sma21 = _simple_moving_average([bar.close for bar in bars], 21)
    sma34 = _simple_moving_average([bar.close for bar in bars], 34)
    signals: list[ChanlunSignal] = []

    for end_index in range(4, len(strokes)):
        first, _second, third, _fourth, fifth = strokes[end_index - 4 : end_index + 1]
        if not _alternating((first, _second, third, _fourth, fifth)):
            continue

        signals.extend(
            _second_point_signal(
                first,
                third,
                fifth,
                index_by_date,
                sma21,
                rule_version=rule_version,
            )
        )
        signals.extend(
            _third_point_signal(
                first,
                third,
                fifth,
                index_by_date,
                sma34,
                rule_version=rule_version,
            )
        )

    return signals


def _second_point_signal(
    first: ChanlunStroke,
    third: ChanlunStroke,
    fifth: ChanlunStroke,
    index_by_date: dict[str, int],
    averages: list[float],
    *,
    rule_version: str,
) -> list[ChanlunSignal]:
    first_end_average = averages[index_by_date[first.end_at]]
    third_end_average = averages[index_by_date[third.end_at]]
    fifth_start_average = averages[index_by_date[fifth.start_at]]
    fifth_end_average = averages[index_by_date[fifth.end_at]]

    if (
        fifth.direction == "down"
        and _stroke_low(first) < first_end_average
        and _stroke_low(third) < third_end_average
        and fifth_start_average < fifth_end_average
    ):
        return [_signal("two_buy", fifth, rule_version=rule_version)]
    if (
        fifth.direction == "up"
        and _stroke_high(first) > first_end_average
        and _stroke_high(third) > third_end_average
        and fifth_start_average > fifth_end_average
    ):
        return [_signal("two_sell", fifth, rule_version=rule_version)]
    return []


def _third_point_signal(
    first: ChanlunStroke,
    third: ChanlunStroke,
    fifth: ChanlunStroke,
    index_by_date: dict[str, int],
    averages: list[float],
    *,
    rule_version: str,
) -> list[ChanlunSignal]:
    zone_low = max(_stroke_low(first), _stroke_low(third))
    zone_high = min(_stroke_high(first), _stroke_high(third))
    if zone_low > zone_high:
        return []

    first_end_average = averages[index_by_date[first.end_at]]
    third_end_average = averages[index_by_date[third.end_at]]
    fifth_end_average = averages[index_by_date[fifth.end_at]]
    if (
        fifth.direction == "down"
        and _stroke_low(fifth) > zone_high
        and fifth_end_average > third_end_average > first_end_average
    ):
        return [_signal("three_buy", fifth, rule_version=rule_version)]
    if (
        fifth.direction == "up"
        and _stroke_high(fifth) < zone_low
        and fifth_end_average < third_end_average < first_end_average
    ):
        return [_signal("three_sell", fifth, rule_version=rule_version)]
    return []


def _simple_moving_average(closes: list[float], period: int) -> list[float]:
    averages: list[float] = []
    running_total = 0.0
    for index, close in enumerate(closes):
        running_total += close
        if index >= period:
            running_total -= closes[index - period]
        window_size = min(index + 1, period)
        averages.append(running_total / window_size)
    return averages


def _signal(signal_type: str, stroke: ChanlunStroke, *, rule_version: str) -> ChanlunSignal:
    return ChanlunSignal(
        id=f"signal:{signal_type}:{stroke.id}",
        type=signal_type,
        occurred_at=stroke.end_at,
        price=stroke.end_price,
        stroke_id=stroke.id,
        status="confirmed",
        rule_version=rule_version,
    )


def _stroke_low(stroke: ChanlunStroke) -> float:
    return min(stroke.start_price, stroke.end_price)


def _stroke_high(stroke: ChanlunStroke) -> float:
    return max(stroke.start_price, stroke.end_price)


def _alternating(strokes: tuple[ChanlunStroke, ChanlunStroke, ChanlunStroke, ChanlunStroke, ChanlunStroke]) -> bool:
    return all(current.direction != previous.direction for previous, current in zip(strokes, strokes[1:]))
