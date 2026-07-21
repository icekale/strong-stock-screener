from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.models import (
    EtfActivityAlert,
    EtfThreeFactorHistoryPoint,
    EtfThreeFactorResponse,
    EtfThreeFactorSummary,
)
from app.services.etf_three_factor_store import EtfThreeFactorStore


def _snapshot() -> EtfThreeFactorResponse:
    return EtfThreeFactorResponse(
        generated_at="2026-07-22T10:00:00+08:00",
        trade_date="2026-07-22",
        as_of="2026-07-22T10:00:00+08:00",
        signal_stage="intraday",
        model_version="three-factor-v1",
        summary=EtfThreeFactorSummary(signal_score=72, level="high", valid_count=1),
    )


def _point(trade_date: str, symbol: str = "510300.SH", score: float = 72) -> EtfThreeFactorHistoryPoint:
    return EtfThreeFactorHistoryPoint(
        trade_date=trade_date,
        symbol=symbol,
        signal_score=score,
        level="high",
    )


def _alert(
    alert_id: str,
    alert_type: str = "single_high",
    *,
    symbol: str | None = "510300.SH",
    level: str = "high",
    score: float = 72,
    triggered_at: str = "2026-07-22T10:00:00+08:00",
    read: bool = False,
) -> EtfActivityAlert:
    return EtfActivityAlert(
        alert_id=alert_id,
        trade_date="2026-07-22",
        alert_type=alert_type,
        level=level,
        symbol=symbol,
        title="ETF alert",
        message="ETF activity changed",
        signal_score=score,
        triggered_at=triggered_at,
        last_triggered_at=triggered_at,
        read=read,
    )


def test_snapshot_round_trip_uses_capital_signals_and_atomic_replace(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)

    store.save_snapshot(_snapshot())

    assert store.load_snapshot() == _snapshot()
    assert store.snapshot_path == tmp_path / "capital-signals" / "etf-three-factor-snapshot.json"
    assert not list(store.root_dir.glob("*.tmp"))


def test_missing_or_corrupt_snapshot_returns_none(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)
    assert store.load_snapshot() is None

    store.root_dir.mkdir(parents=True)
    store.snapshot_path.write_text("not json", encoding="utf-8")
    assert store.load_snapshot() is None


def test_history_round_trip_retains_60_distinct_trade_dates_and_limits_days(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)
    points = [_point(f"2026-05-{day:02d}") for day in range(1, 32)]
    points.extend(_point(f"2026-06-{day:02d}") for day in range(1, 30))
    points.extend([_point("2026-07-01"), _point("2026-07-02")])

    store.upsert_history(points)

    loaded = store.load_history("510300.SH", 3)
    retained = store.load_history("510300.SH", 100)
    assert [point.trade_date for point in loaded] == ["2026-06-29", "2026-07-01", "2026-07-02"]
    assert len(retained) == 60
    assert retained[0].trade_date == "2026-05-03"


def test_history_replaces_same_symbol_and_trade_date_and_ignores_corrupt_file(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)
    store.upsert_history([_point("2026-07-22", score=70), _point("2026-07-22", score=80)])
    assert store.load_history("510300.SH", 1)[0].signal_score == 80

    store.history_path.write_text("{}", encoding="utf-8")
    assert store.load_history("510300.SH", 1) == []


def test_store_deduplicates_same_level_but_keeps_upgrade(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)
    first = _alert("a1", score=72)
    duplicate = _alert("a2", score=75, triggered_at="2026-07-22T10:10:00+08:00")
    upgrade = _alert(
        "a3", "single_upgrade", score=84, triggered_at="2026-07-22T10:11:00+08:00"
    )

    assert store.upsert_alert(first) is True
    assert store.upsert_alert(duplicate) is False
    assert store.upsert_alert(upgrade) is True
    assert [row.alert_id for row in store.load_alerts()] == ["a3", "a1"]


def test_alert_cooldown_expires_and_market_key_is_type_and_level(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)
    assert store.upsert_alert(_alert("a1")) is True
    assert store.upsert_alert(_alert("a2", triggered_at="2026-07-22T10:30:01+08:00")) is True
    assert store.upsert_alert(_alert("m1", "market_high", symbol=None)) is True
    assert store.upsert_alert(_alert("m2", "market_high", symbol=None, triggered_at="2026-07-22T10:10:00+08:00")) is False


def test_alerts_retain_last_30_days_and_preserve_read_state(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)
    old = _alert("old")
    old = old.model_copy(update={"trade_date": (date(2026, 7, 22) - timedelta(days=31)).isoformat()})
    current = _alert("current", read=True)
    store.upsert_alert(old)
    store.upsert_alert(current)

    assert [alert.alert_id for alert in store.load_alerts()] == ["current"]
    assert store.load_alerts(unread_only=True) == []

    store.mark_read("current")
    assert store.load_alerts()[0].read is True
    store.mark_all_read()
    assert store.load_alerts()[0].read is True


def test_missing_or_corrupt_alerts_return_empty_response(tmp_path: Path) -> None:
    store = EtfThreeFactorStore(tmp_path)
    assert store.load_alerts() == []

    store.root_dir.mkdir(parents=True)
    store.alerts_path.write_text("[]", encoding="utf-8")
    assert store.load_alerts() == []
