from datetime import datetime

from app.models import AuctionReviewRecord, AuctionReviewSnapshot, AuctionSnapshotItem, AuctionSnapshotResponse
from app.services.auction_review_store import AuctionReviewStore
from app.services.auction_snapshot_store import AuctionSnapshotStore, auction_timeline_label


def _snapshot(symbol: str, score: float) -> AuctionSnapshotResponse:
    return AuctionSnapshotResponse(
        trade_date="2026-07-01",
        items=[
            AuctionSnapshotItem(
                symbol=symbol,
                name=f"竞价{symbol}",
                auction_score=score,
                open_gap_pct=3.5,
                current_pct_change=4.2,
            )
        ],
    )


def _snapshot_with_items(trade_date: str) -> AuctionSnapshotResponse:
    return AuctionSnapshotResponse(
        trade_date=trade_date,
        items=[
            AuctionSnapshotItem(
                symbol="300001.SZ",
                name="竞价一号",
                industry="机器人",
                auction_score=78,
                open_gap_pct=3.8,
                current_pct_change=4.6,
                turnover_cny=360_000_000,
                turnover_rate=6.2,
                tier="strong_high_open",
                signals=["竞价温和高开", "竞价量能活跃"],
            ),
            AuctionSnapshotItem(
                symbol="300002.SZ",
                name="竞价二号",
                industry="机器人",
                auction_score=68,
                open_gap_pct=2.1,
                current_pct_change=2.8,
                turnover_cny=120_000_000,
                turnover_rate=2.1,
                tier="neutral",
            ),
        ],
    )


def _auction_review_record(trade_date: str, symbol: str, selected_at_label: str) -> AuctionReviewRecord:
    return AuctionReviewRecord(
        trade_date=trade_date,
        symbol=symbol,
        name=f"竞价{symbol}",
        industry="机器人",
        selected_at_label=selected_at_label,
        selected_at=f"{trade_date}T09:25:00+08:00",
        auction_snapshot=AuctionReviewSnapshot(
            open_gap_pct=3.5,
            current_pct_change=4.2,
            turnover_cny=350_000_000,
            turnover_rate=6.0,
            auction_score=72.5,
            rank=1,
            tier="strong_high_open",
            signals=["竞价温和高开", "量能活跃"],
        ),
        rule_tags=["温和高开", "量能活跃"],
    )


def test_auction_timeline_label_matches_key_observation_points() -> None:
    assert auction_timeline_label(datetime(2026, 7, 1, 9, 19, 35)) is None
    assert auction_timeline_label(datetime(2026, 7, 1, 9, 20, 2)) == "09:20"
    assert auction_timeline_label(datetime(2026, 7, 1, 9, 23, 0)) == "09:23"
    assert auction_timeline_label(datetime(2026, 7, 1, 9, 24, 50)) == "09:24:50"
    assert auction_timeline_label(datetime(2026, 7, 1, 9, 25, 0)) == "09:25"
    assert auction_timeline_label(datetime(2026, 7, 1, 9, 25, 31)) is None


def test_auction_snapshot_store_records_timeline_points() -> None:
    store = AuctionSnapshotStore()

    store.save(_snapshot("300001.SZ", 88), captured_at=datetime(2026, 7, 1, 9, 20, 1))
    store.save(_snapshot("300002.SZ", 92), captured_at=datetime(2026, 7, 1, 9, 24, 50))

    timeline = store.timeline(limit=5)

    assert [point.label for point in timeline.points] == ["09:20", "09:23", "09:24:50", "09:25"]
    captured = [point for point in timeline.points if point.snapshot_status == "captured"]
    assert [point.label for point in captured] == ["09:20", "09:24:50"]
    assert captured[0].items[0].symbol == "300001.SZ"
    assert captured[1].items[0].symbol == "300002.SZ"


def test_auction_snapshot_store_keeps_0925_snapshot_locked_after_open() -> None:
    store = AuctionSnapshotStore()

    store.save(_snapshot("300025.SZ", 92), captured_at=datetime(2026, 7, 1, 9, 25, 0))
    returned = store.save(_snapshot("300930.SZ", 99), captured_at=datetime(2026, 7, 1, 9, 30, 1))
    latest = store.latest(limit=5)

    assert returned.items[0].symbol == "300025.SZ"
    assert latest.items[0].symbol == "300025.SZ"
    assert latest.source_status[-1].source == "竞价雷达缓存"
    assert "09:25" in latest.source_status[-1].detail


def test_auction_snapshot_store_restores_locked_0925_snapshot_after_restart(tmp_path) -> None:
    store = AuctionSnapshotStore(data_dir=tmp_path)
    store.save(_snapshot("300025.SZ", 92), captured_at=datetime(2026, 7, 1, 9, 25, 0))

    reloaded = AuctionSnapshotStore(data_dir=tmp_path)
    latest = reloaded.latest(limit=5)
    returned = reloaded.save(_snapshot("300930.SZ", 99), captured_at=datetime(2026, 7, 1, 9, 30, 1))

    assert latest.items[0].symbol == "300025.SZ"
    assert latest.snapshot_status == "cached"
    assert "09:25" in latest.source_status[-1].detail
    assert returned.items[0].symbol == "300025.SZ"


def test_auction_review_store_persists_and_dedupes_records(tmp_path) -> None:
    store = AuctionReviewStore(tmp_path, retention_days=120)
    record = _auction_review_record("2026-07-01", "300001.SZ", "09:25")

    store.upsert_records([record])
    store.upsert_records([record])

    reloaded = AuctionReviewStore(tmp_path, retention_days=120)
    records = reloaded.load_records("2026-07-01")
    assert len(records) == 1
    assert records[0].symbol == "300001.SZ"
    assert records[0].selected_at_label == "09:25"


def test_auction_snapshot_store_archives_review_records(tmp_path) -> None:
    review_store = AuctionReviewStore(tmp_path)
    store = AuctionSnapshotStore(review_store=review_store)

    store.save(_snapshot_with_items("2026-07-01"), captured_at=datetime(2026, 7, 1, 9, 25, 0))

    records = review_store.load_records("2026-07-01")
    assert [record.symbol for record in records] == ["300001.SZ", "300002.SZ"]
    assert records[0].selected_at_label == "09:25"
    assert records[0].auction_snapshot.rank == 1
    assert "温和高开" in records[0].rule_tags
    assert "量能活跃" in records[0].rule_tags
    assert "行业集中" in records[0].rule_tags
