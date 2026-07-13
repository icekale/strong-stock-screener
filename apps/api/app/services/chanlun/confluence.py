from __future__ import annotations

from collections.abc import Mapping

from app.models import (
    ChanlunAnalysisResponse,
    ChanlunConfluenceSignal,
    ChanlunPeriod,
    ChanlunSignal,
    ChanlunStroke,
    ChanlunZone,
)


_PERIOD_PAIRS: tuple[tuple[ChanlunPeriod, ChanlunPeriod], ...] = (
    ("1d", "60m"),
    ("60m", "30m"),
    ("30m", "5m"),
)


def derive_confluence_signals(
    analyses: Mapping[ChanlunPeriod, ChanlunAnalysisResponse],
) -> list[ChanlunConfluenceSignal]:
    signals: list[ChanlunConfluenceSignal] = []
    for higher_period, lower_period in _PERIOD_PAIRS:
        higher = analyses[higher_period]
        lower = analyses[lower_period]
        if higher.availability != "ready" or lower.availability != "ready":
            continue

        higher_direction = _direction(higher)
        higher_zone = _latest_confirmed_zone(higher)
        lower_zone = _latest_confirmed_zone(lower)
        lower_stroke = _latest_confirmed_stroke(lower)
        lower_signal = _latest_confirmed_signal(lower)

        if higher_direction == "up":
            if higher_zone and lower_zone and lower_stroke and lower_stroke.direction == "down" and lower_zone.low > higher_zone.high:
                signals.append(
                    _signal(
                        "class_two_buy",
                        higher_period,
                        lower_period,
                        lower_stroke.end_at,
                        lower_stroke.end_price,
                        higher_zone=higher_zone,
                        reason="低周期确认中枢整体位于高周期中枢上沿上方，且末笔回落已确认。",
                    )
                )
            if lower_signal and lower_signal.type == "two_buy":
                signals.append(
                    _signal(
                        "sub_two_buy",
                        higher_period,
                        lower_period,
                        lower_signal.occurred_at,
                        lower_signal.price,
                        source_signal=lower_signal,
                        higher_zone=higher_zone,
                        reason="高周期方向向上，低周期二买已确认。",
                    )
                )
            if lower_signal and lower_signal.type == "three_buy":
                if higher_zone and lower_signal.price > higher_zone.high:
                    signals.append(
                        _signal(
                            "class_three_buy",
                            higher_period,
                            lower_period,
                            lower_signal.occurred_at,
                            lower_signal.price,
                            source_signal=lower_signal,
                            higher_zone=higher_zone,
                            reason="低周期三买位于高周期确认中枢上沿上方。",
                        )
                    )
                signals.append(
                    _signal(
                        "sub_three_buy",
                        higher_period,
                        lower_period,
                        lower_signal.occurred_at,
                        lower_signal.price,
                        source_signal=lower_signal,
                        higher_zone=higher_zone,
                        reason="高周期方向向上，低周期三买已确认。",
                    )
                )

        if higher_direction == "down":
            if higher_zone and lower_zone and lower_stroke and lower_stroke.direction == "up" and lower_zone.high < higher_zone.low:
                signals.append(
                    _signal(
                        "class_two_sell",
                        higher_period,
                        lower_period,
                        lower_stroke.end_at,
                        lower_stroke.end_price,
                        higher_zone=higher_zone,
                        reason="低周期确认中枢整体位于高周期中枢下沿下方，且末笔反弹已确认。",
                    )
                )
            if lower_signal and lower_signal.type == "two_sell":
                signals.append(
                    _signal(
                        "sub_two_sell",
                        higher_period,
                        lower_period,
                        lower_signal.occurred_at,
                        lower_signal.price,
                        source_signal=lower_signal,
                        higher_zone=higher_zone,
                        reason="高周期方向向下，低周期二卖已确认。",
                    )
                )
            if lower_signal and lower_signal.type == "three_sell":
                if higher_zone and lower_signal.price < higher_zone.low:
                    signals.append(
                        _signal(
                            "class_three_sell",
                            higher_period,
                            lower_period,
                            lower_signal.occurred_at,
                            lower_signal.price,
                            source_signal=lower_signal,
                            higher_zone=higher_zone,
                            reason="低周期三卖位于高周期确认中枢下沿下方。",
                        )
                    )
                signals.append(
                    _signal(
                        "sub_three_sell",
                        higher_period,
                        lower_period,
                        lower_signal.occurred_at,
                        lower_signal.price,
                        source_signal=lower_signal,
                        higher_zone=higher_zone,
                        reason="高周期方向向下，低周期三卖已确认。",
                    )
                )

    return sorted(signals, key=lambda signal: (signal.occurred_at, signal.type))


def _direction(analysis: ChanlunAnalysisResponse) -> str:
    structures = analysis.segments or analysis.strokes
    return structures[-1].direction if structures else "unknown"


def _latest_confirmed_zone(analysis: ChanlunAnalysisResponse) -> ChanlunZone | None:
    return next(
        (
            zone
            for zone in reversed(analysis.zones)
            if not zone.virtual and zone.status in {"confirmed", "final"}
        ),
        None,
    )


def _latest_confirmed_stroke(analysis: ChanlunAnalysisResponse) -> ChanlunStroke | None:
    return next(
        (stroke for stroke in reversed(analysis.strokes) if stroke.status in {"confirmed", "final"}),
        None,
    )


def _latest_confirmed_signal(analysis: ChanlunAnalysisResponse) -> ChanlunSignal | None:
    return next(
        (signal for signal in reversed(analysis.signals) if signal.status in {"confirmed", "final"}),
        None,
    )


def _signal(
    signal_type: str,
    higher_period: ChanlunPeriod,
    lower_period: ChanlunPeriod,
    occurred_at: str,
    price: float,
    *,
    source_signal: ChanlunSignal | None = None,
    higher_zone: ChanlunZone | None = None,
    reason: str,
) -> ChanlunConfluenceSignal:
    source_key = source_signal.id if source_signal else occurred_at
    return ChanlunConfluenceSignal(
        id=f"confluence:{signal_type}:{higher_period}:{lower_period}:{source_key}",
        type=signal_type,
        higher_period=higher_period,
        lower_period=lower_period,
        occurred_at=occurred_at,
        price=price,
        source_signal_id=source_signal.id if source_signal else None,
        higher_zone_id=higher_zone.id if higher_zone else None,
        status="confirmed",
        reason=reason,
    )
