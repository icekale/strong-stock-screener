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
