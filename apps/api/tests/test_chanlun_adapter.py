from __future__ import annotations

from datetime import datetime, timedelta

from app.models import KlineBar
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
