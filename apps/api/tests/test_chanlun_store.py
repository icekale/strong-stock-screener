from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.providers.tickflow import TickFlowIntradayBar
from app.services.chanlun.store import ChanlunMinuteBarStore


SHANGHAI = ZoneInfo("Asia/Shanghai")


def minute_bar(
    value: str,
    *,
    close: float = 10.0,
    prev_close: float | None = 9.8,
) -> TickFlowIntradayBar:
    timestamp = datetime.fromisoformat(value).replace(tzinfo=SHANGHAI)
    return TickFlowIntradayBar(
        timestamp=int(timestamp.timestamp() * 1000),
        open=close - 0.1,
        high=close + 0.2,
        low=close - 0.3,
        close=close,
        volume=100.0,
        amount=1_000.0,
        prev_close=prev_close,
    )


def store_at(tmp_path: Path) -> ChanlunMinuteBarStore:
    return ChanlunMinuteBarStore(tmp_path / "chanlun" / "minute.sqlite3")


def test_store_updates_an_open_bar(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    original = minute_bar("2026-07-10 09:30", close=10.0)
    update = minute_bar("2026-07-10 09:30", close=10.2)

    store.upsert("600000.SH", [original], source="TickFlow", closed=False)
    store.upsert("600000.SH", [update], source="TickFlow", closed=False)

    bars = store.read("600000.SH")
    assert len(bars) == 1
    assert bars[0].close == 10.2
    assert bars[0].closed is False


def test_store_closed_write_freezes_snapshot_against_later_open_update(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    store.upsert(
        "600000.SH",
        [minute_bar("2026-07-10 09:30", close=10.0)],
        source="TickFlow",
        closed=False,
    )
    store.upsert(
        "600000.SH",
        [minute_bar("2026-07-10 09:30", close=10.2)],
        source="TickFlow",
        closed=True,
    )
    store.upsert(
        "600000.SH",
        [minute_bar("2026-07-10 09:30", close=10.8)],
        source="TickFlow",
        closed=False,
    )

    bars = store.read("600000.SH", start_at="2026-07-10T09:30:00+08:00")
    assert bars[0].close == 10.2
    assert bars[0].closed is True


def test_store_reads_bars_in_timestamp_order(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    store.upsert(
        "600000.SH",
        [
            minute_bar("2026-07-10 09:32", close=10.2),
            minute_bar("2026-07-10 09:30", close=10.0),
            minute_bar("2026-07-10 09:31", close=10.1),
        ],
        source="TickFlow",
        closed=True,
    )

    assert [bar.timestamp for bar in store.read("600000.SH")] == [
        "2026-07-10T09:30:00+08:00",
        "2026-07-10T09:31:00+08:00",
        "2026-07-10T09:32:00+08:00",
    ]


def test_store_records_source_and_capture_metadata(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    captured_at = datetime(2026, 7, 10, 9, 31, 15, tzinfo=SHANGHAI)
    store.upsert(
        "600000.SH",
        [minute_bar("2026-07-10 09:30", close=10.0)],
        source="TickFlow",
        closed=False,
        captured_at=captured_at,
    )

    stored = store.read("600000.SH")[0]
    assert stored.source == "TickFlow"
    assert stored.captured_at == "2026-07-10T09:31:15+08:00"
    assert stored.prev_close == 9.8


def test_store_idempotently_inserts_each_adjustment_mode_key(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    bar = minute_bar("2026-07-10 09:30", close=10.0)

    store.upsert("600000.SH", [bar], source="TickFlow", closed=True)
    store.upsert("600000.SH", [bar], source="TickFlow", closed=True)
    store.upsert(
        "600000.SH",
        [bar],
        source="TickFlow",
        closed=True,
        adjustment_mode="forward_adjusted",
    )

    assert len(store.read("600000.SH")) == 1
    adjusted = store.read("600000.SH", adjustment_mode="forward_adjusted")
    assert len(adjusted) == 1
    assert adjusted[0].adjustment_mode == "forward_adjusted"


def test_store_prunes_trade_dates_older_than_keep_days(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    expired = date.today() - timedelta(days=31)
    retained = date.today() - timedelta(days=30)
    store.upsert(
        "600000.SH",
        [minute_bar(f"{expired.isoformat()} 09:30")],
        source="TickFlow",
        closed=True,
    )
    store.upsert(
        "600000.SH",
        [minute_bar(f"{retained.isoformat()} 09:30")],
        source="TickFlow",
        closed=True,
    )

    store.prune(keep_days=30)

    assert [bar.trade_date for bar in store.read("600000.SH")] == [retained.isoformat()]
