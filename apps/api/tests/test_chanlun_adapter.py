from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.models import KlineBar
from app.services.chanlun import adapter
from app.services.chanlun.adapter import ChanlunAdapter


def fixture_bars() -> list[KlineBar]:
    values: list[float] = []
    for start, end in [
        (20, 10),
        (10, 20),
        (20, 12),
        (12, 21),
        (21, 13),
        (13, 22),
        (22, 14),
        (14, 20),
    ]:
        leg = [start + (end - start) * index / 6 for index in range(7)]
        values.extend(leg if not values else leg[1:])

    start_at = datetime.fromisoformat("2026-01-01T00:00:00+08:00")
    return [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=price,
            close=price,
            high=price + 0.4,
            low=price - 0.4,
            volume=100,
            amount=1_000,
        )
        for index, price in enumerate(values)
    ]


def fixture_bars_with_retracing_tail() -> list[KlineBar]:
    bars = fixture_bars()
    for price in (18, 19):
        occurred_at = datetime.fromisoformat(bars[-1].date) + timedelta(days=1)
        bars.append(
            KlineBar(
                date=occurred_at.isoformat(timespec="seconds"),
                open=price,
                close=price,
                high=price + 0.4,
                low=price - 0.4,
                volume=100,
                amount=1_000,
            )
        )
    return bars


def fixture_bottom_divergence_bars(*, include_future_tail: bool = False) -> list[KlineBar]:
    prices = (
        [20.0] * 30
        + [20.0, 17.5, 15.0, 12.5, 10.0]
        + [10.0 + 5.0 * step / 15 for step in range(1, 16)]
        + [15.0 - 6.0 * step / 15 for step in range(1, 16)]
        + [9.0]
    )
    if include_future_tail:
        prices += [18.0, 6.0, 19.0, 5.0]
    start_at = datetime.fromisoformat("2026-03-01T00:00:00+08:00")
    return [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=price,
            close=price,
            high=price + 0.2,
            low=price - 0.2,
            volume=100,
            amount=1_000,
        )
        for index, price in enumerate(prices)
    ]


def native_fractal(index: int, price: float, mark: str) -> SimpleNamespace:
    source_bar = SimpleNamespace(id=index)
    return SimpleNamespace(elements=[source_bar, source_bar, source_bar], fx=price, mark=mark)


def native_stroke(
    start: SimpleNamespace,
    end: SimpleNamespace,
    direction: str,
) -> SimpleNamespace:
    return SimpleNamespace(direction=direction, fx_a=start, fx_b=end)


def bottom_divergence_native() -> SimpleNamespace:
    first_top = native_fractal(30, 20.0, "top")
    first_bottom = native_fractal(34, 10.0, "bottom")
    rebound_top = native_fractal(49, 15.0, "top")
    second_bottom = native_fractal(64, 9.0, "bottom")
    return SimpleNamespace(
        finished_bis=[
            native_stroke(first_top, first_bottom, "down"),
            native_stroke(first_bottom, rebound_top, "up"),
            native_stroke(rebound_top, second_bottom, "down"),
        ],
        fx_list=[],
        ubi=None,
    )


def fixture_top_divergence_bars() -> list[KlineBar]:
    prices = (
        [10.0] * 30
        + [10.0, 12.5, 15.0, 17.5, 20.0]
        + [20.0 - 5.0 * step / 15 for step in range(1, 16)]
        + [15.0 + 6.0 * step / 15 for step in range(1, 16)]
        + [21.0]
    )
    start_at = datetime.fromisoformat("2026-04-01T00:00:00+08:00")
    return [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=price,
            close=price,
            high=price + 0.2,
            low=price - 0.2,
            volume=100,
            amount=1_000,
        )
        for index, price in enumerate(prices)
    ]


def top_divergence_native() -> SimpleNamespace:
    first_bottom = native_fractal(30, 10.0, "bottom")
    first_top = native_fractal(34, 20.0, "top")
    retrace_bottom = native_fractal(49, 15.0, "bottom")
    second_top = native_fractal(64, 21.0, "top")
    return SimpleNamespace(
        finished_bis=[
            native_stroke(first_bottom, first_top, "up"),
            native_stroke(first_top, retrace_bottom, "down"),
            native_stroke(retrace_bottom, second_top, "up"),
        ],
        fx_list=[],
        ubi=None,
    )


def fixture_double_zone_bottom_divergence_bars() -> list[KlineBar]:
    prices = (
        [20.0] * 30
        + [20.0, 17.5, 15.0, 12.5, 10.0]
        + [10.0 + 5.0 * step / 15 for step in range(1, 16)]
        + [15.0 - 6.0 * step / 15 for step in range(1, 16)]
        + [9.0 + 4.0 * step / 15 for step in range(1, 16)]
        + [13.0 - 5.0 * step / 20 for step in range(1, 21)]
        + [8.0]
    )
    start_at = datetime.fromisoformat("2026-05-01T00:00:00+08:00")
    return [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=price,
            close=price,
            high=price + 0.2,
            low=price - 0.2,
            volume=100,
            amount=1_000,
        )
        for index, price in enumerate(prices)
    ]


def double_zone_bottom_divergence_native() -> SimpleNamespace:
    first_top = native_fractal(30, 20.0, "top")
    first_bottom = native_fractal(34, 10.0, "bottom")
    second_top = native_fractal(49, 15.0, "top")
    second_bottom = native_fractal(64, 9.0, "bottom")
    third_top = native_fractal(79, 13.0, "top")
    third_bottom = native_fractal(99, 8.0, "bottom")
    first = native_stroke(first_top, first_bottom, "down")
    second = native_stroke(first_bottom, second_top, "up")
    third = native_stroke(second_top, second_bottom, "down")
    fourth = native_stroke(second_bottom, third_top, "up")
    fifth = native_stroke(third_top, third_bottom, "down")
    return SimpleNamespace(
        finished_bis=[first, second, third, fourth, fifth],
        fx_list=[],
        ubi=None,
        zs_list=[SimpleNamespace(bis=[first, second, third]), SimpleNamespace(bis=[third, fourth, fifth])],
    )


def fixture_second_buy_bars(*, mirror: bool = False) -> list[KlineBar]:
    prices = (
        [10.0] * 40
        + [10.0 - 2.0 * step / 4 for step in range(5)]
        + [8.0 + 2.0 * step / 15 for step in range(1, 16)]
        + [10.0 - step / 15 for step in range(1, 16)]
        + [9.0 + 3.0 * step / 15 for step in range(1, 16)]
        + [12.0 - step / 5 for step in range(1, 6)]
        + [11.0]
    )
    if mirror:
        prices = [20.0 - price for price in prices]
    start_at = datetime.fromisoformat("2026-06-01T00:00:00+08:00")
    return [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=price,
            close=price,
            high=price + 0.2,
            low=price - 0.2,
            volume=100,
            amount=1_000,
        )
        for index, price in enumerate(prices)
    ]


def fixture_third_buy_bars(*, mirror: bool = False) -> list[KlineBar]:
    prices = (
        [10.0] * 40
        + [10.0 - 2.0 * step / 4 for step in range(5)]
        + [8.0 + 4.0 * step / 15 for step in range(1, 16)]
        + [12.0 - 2.0 * step / 15 for step in range(1, 16)]
        + [10.0 + 3.0 * step / 15 for step in range(1, 16)]
        + [13.0 - 2.0 * step / 5 for step in range(1, 6)]
        + [11.0]
    )
    if mirror:
        prices = [20.0 - price for price in prices]
    start_at = datetime.fromisoformat("2026-07-01T00:00:00+08:00")
    return [
        KlineBar(
            date=(start_at + timedelta(days=index)).isoformat(timespec="seconds"),
            open=price,
            close=price,
            high=price + 0.2,
            low=price - 0.2,
            volume=100,
            amount=1_000,
        )
        for index, price in enumerate(prices)
    ]


def five_stroke_native(*, mirror: bool = False, third: bool = False) -> SimpleNamespace:
    prices = (10.0, 8.0, 12.0, 10.0, 13.0, 11.0) if third else (10.0, 8.0, 10.0, 9.0, 12.0, 11.0)
    marks = ("top", "bottom", "top", "bottom", "top", "bottom")
    directions = ("down", "up", "down", "up", "down")
    if mirror:
        prices = tuple(20.0 - price for price in prices)
        marks = ("bottom", "top", "bottom", "top", "bottom", "top")
        directions = ("up", "down", "up", "down", "up")
    fractals = [native_fractal(index, price, mark) for index, price, mark in zip((40, 44, 59, 74, 89, 94), prices, marks)]
    strokes = [native_stroke(start, end, direction) for start, end, direction in zip(fractals, fractals[1:], directions)]
    return SimpleNamespace(finished_bis=strokes, fx_list=[], ubi=None)


def test_adapter_maps_czsc_fractals_strokes_and_confirmed_zone() -> None:
    analysis = ChanlunAdapter().analyze("600000.SH", period="1d", bars=fixture_bars())

    assert analysis.availability == "ready"
    # Verified against czsc==0.10.12: fx_list starts at the first completed top fractal.
    assert [item.mark for item in analysis.fractals] == [
        "top",
        "bottom",
        "top",
        "bottom",
        "top",
        "bottom",
    ]
    assert [item.direction for item in analysis.strokes] == [
        "up",
        "down",
        "up",
        "down",
        "up",
        "down",
    ]
    confirmed_zones = [zone for zone in analysis.zones if not zone.virtual]
    virtual_zones = [zone for zone in analysis.zones if zone.virtual]
    assert len(confirmed_zones) == 1
    assert confirmed_zones[0].high == 20.4
    assert confirmed_zones[0].low == 13.6
    assert confirmed_zones[0].status in {"confirmed", "final"}
    assert len(virtual_zones) == 1
    assert virtual_zones[0].status == "provisional"
    assert (virtual_zones[0].high, virtual_zones[0].low) != (
        confirmed_zones[0].high,
        confirmed_zones[0].low,
    )
    assert len(analysis.segments) == 2
    assert len({item.id for item in analysis.fractals}) == len(analysis.fractals)
    assert len({item.id for item in analysis.strokes}) == len(analysis.strokes)


def test_adapter_emits_confirmed_consolidation_bottom_divergence_without_future_leakage() -> None:
    adapter_instance = ChanlunAdapter()
    truncated_bars = fixture_bottom_divergence_bars()
    full_bars = fixture_bottom_divergence_bars(include_future_tail=True)

    truncated = adapter_instance._map_native(
        "600000.SH",
        "1d",
        truncated_bars,
        bottom_divergence_native(),
        include_observing=False,
    )
    full = adapter_instance._map_native(
        "600000.SH",
        "1d",
        full_bars,
        bottom_divergence_native(),
        include_observing=False,
    )

    assert len(truncated.divergences) == 1
    assert truncated.divergences[0].type == "consolidation"
    assert truncated.divergences[0].status == "confirmed"
    assert truncated.divergences[0].direction == "down"
    assert truncated.divergences[0].current_price == 9.0
    assert truncated.divergences[0].reference_price == 10.0
    assert 0 < truncated.divergences[0].coefficient < 1
    assert [(item.type, item.price, item.status) for item in truncated.signals] == [
        ("one_buy", 9.0, "confirmed")
    ]
    assert [item.model_dump() for item in full.divergences] == [item.model_dump() for item in truncated.divergences]
    assert [item.model_dump() for item in full.signals] == [item.model_dump() for item in truncated.signals]


def test_adapter_emits_confirmed_consolidation_top_divergence_and_one_sell() -> None:
    analysis = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        fixture_top_divergence_bars(),
        top_divergence_native(),
        include_observing=False,
    )

    assert len(analysis.divergences) == 1
    assert analysis.divergences[0].type == "consolidation"
    assert analysis.divergences[0].direction == "up"
    assert analysis.divergences[0].current_price == 21.0
    assert analysis.divergences[0].reference_price == 20.0
    assert 0 < analysis.divergences[0].coefficient < 1
    assert [(item.type, item.price, item.status) for item in analysis.signals] == [
        ("one_sell", 21.0, "confirmed")
    ]


def test_adapter_classifies_a_second_confirmed_zone_as_bottom_divergence() -> None:
    analysis = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        fixture_double_zone_bottom_divergence_bars(),
        double_zone_bottom_divergence_native(),
        include_observing=False,
    )

    assert [item.type for item in analysis.divergences] == ["consolidation", "bottom"]
    assert [item.zone_count for item in analysis.divergences] == [1, 2]
    assert [(item.type, item.price) for item in analysis.signals] == [
        ("one_buy", 9.0),
        ("one_buy", 8.0),
    ]


def test_adapter_emits_confirmed_second_buy_and_sell_from_five_stroke_ma_rules() -> None:
    buy = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        fixture_second_buy_bars(),
        five_stroke_native(),
        include_observing=False,
    )
    sell = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        fixture_second_buy_bars(mirror=True),
        five_stroke_native(mirror=True),
        include_observing=False,
    )

    buy_second = [item for item in buy.signals if item.type == "two_buy"]
    sell_second = [item for item in sell.signals if item.type == "two_sell"]
    assert [(item.price, item.divergence_id, item.status) for item in buy_second] == [
        (11.0, None, "confirmed")
    ]
    assert [(item.price, item.divergence_id, item.status) for item in sell_second] == [
        (9.0, None, "confirmed")
    ]


def test_adapter_emits_confirmed_third_buy_and_sell_after_zone_exit_without_reentry() -> None:
    buy = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        fixture_third_buy_bars(),
        five_stroke_native(third=True),
        include_observing=False,
    )
    sell = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        fixture_third_buy_bars(mirror=True),
        five_stroke_native(mirror=True, third=True),
        include_observing=False,
    )

    assert [(item.price, item.divergence_id, item.status) for item in buy.signals if item.type == "three_buy"] == [
        (11.0, None, "confirmed")
    ]
    assert [(item.price, item.divergence_id, item.status) for item in sell.signals if item.type == "three_sell"] == [
        (9.0, None, "confirmed")
    ]


def test_adapter_second_and_third_points_are_unchanged_by_future_bars() -> None:
    truncated_bars = fixture_third_buy_bars()
    full_bars = list(truncated_bars)
    future_at = datetime.fromisoformat(full_bars[-1].date)
    for price in (18.0, 6.0, 19.0):
        future_at += timedelta(days=1)
        full_bars.append(
            KlineBar(
                date=future_at.isoformat(timespec="seconds"),
                open=price,
                close=price,
                high=price + 0.2,
                low=price - 0.2,
                volume=100,
                amount=1_000,
            )
        )

    truncated = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        truncated_bars,
        five_stroke_native(third=True),
        include_observing=False,
    )
    full = ChanlunAdapter()._map_native(
        "600000.SH",
        "1d",
        full_bars,
        five_stroke_native(third=True),
        include_observing=False,
    )

    secondary_types = {"two_buy", "two_sell", "three_buy", "three_sell"}
    assert [item.model_dump() for item in full.signals if item.type in secondary_types] == [
        item.model_dump() for item in truncated.signals if item.type in secondary_types
    ]


def test_adapter_does_not_confirm_the_observing_tail() -> None:
    analysis = ChanlunAdapter().analyze(
        "600000.SH", period="5m", bars=fixture_bars(), include_observing=True
    )

    assert any(item.end_at == analysis.bars[-1].date for item in analysis.strokes)
    assert all(
        item.status != "confirmed" for item in analysis.strokes if item.end_at == analysis.bars[-1].date
    )


def test_adapter_maps_observing_stroke_to_ubi_extreme_before_retracing_tail() -> None:
    bars = fixture_bars_with_retracing_tail()

    analysis = ChanlunAdapter().analyze(
        "600000.SH", period="5m", bars=bars, include_observing=True
    )

    observing = [stroke for stroke in analysis.strokes if stroke.status == "observing"]
    assert len(observing) == 1
    assert observing[0].direction == "down"
    assert observing[0].end_at == bars[-2].date
    assert observing[0].end_price == 17.6


def test_adapter_keeps_provisional_zone_when_bounds_match_confirmed_fallback_zone() -> None:
    bars = fixture_bars()

    def fractal(index: int, price: float) -> SimpleNamespace:
        return SimpleNamespace(id=index, dt=datetime.fromisoformat(bars[index].date), fx=price, mark="top")

    native = SimpleNamespace(
        finished_bis=[
            SimpleNamespace(fx_a=fractal(0, 10), fx_b=fractal(1, 20), direction="up"),
            SimpleNamespace(fx_a=fractal(2, 20), fx_b=fractal(3, 10), direction="down"),
            SimpleNamespace(fx_a=fractal(4, 10), fx_b=fractal(5, 20), direction="up"),
        ],
        fx_list=[],
        zs_list=None,
        ubi=None,
    )

    analysis = ChanlunAdapter()._map_native(
        "600000.SH", "1d", bars, native, include_observing=False
    )

    assert [(zone.virtual, zone.status, zone.high, zone.low) for zone in analysis.zones] == [
        (False, "confirmed", 20.0, 10.0),
        (True, "provisional", 20.0, 10.0),
    ]


def test_adapter_returns_unavailable_when_native_runtime_cannot_import(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.chanlun.adapter._load_czsc",
        lambda: (_ for _ in ()).throw(ImportError("missing")),
    )

    analysis = ChanlunAdapter().analyze("600000.SH", period="1d", bars=fixture_bars())

    assert analysis.availability == "unavailable"
    assert analysis.source_status[0].source == "czsc"
    assert analysis.source_status[0].status == "failed"


def test_adapter_returns_insufficient_bars_for_invalid_values() -> None:
    bars = fixture_bars()
    bars[-1].high = float("nan")

    analysis = ChanlunAdapter().analyze("600000.SH", period="1d", bars=bars)

    assert analysis.availability == "insufficient_bars"
    assert analysis.source_status[0].source == "czsc"
    assert analysis.source_status[0].status == "failed"
    assert "invalid" in analysis.source_status[0].detail


def test_adapter_returns_unavailable_for_native_mapping_failure(monkeypatch) -> None:
    monkeypatch.setattr(adapter, "_to_raw_bars", lambda *_args: [object()])
    monkeypatch.setattr(
        adapter,
        "_load_czsc",
        lambda: (object, object, lambda _raw_bars: SimpleNamespace(finished_bis=[object()])),
    )

    analysis = ChanlunAdapter().analyze("600000.SH", period="1d", bars=fixture_bars())

    assert analysis.availability == "unavailable"
    assert analysis.source_status[0].source == "czsc"
    assert analysis.source_status[0].status == "failed"
    assert "native" in analysis.source_status[0].detail
