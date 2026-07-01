from datetime import datetime

from app.models import AuctionSnapshotItem, AuctionSnapshotResponse
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
