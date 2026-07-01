from __future__ import annotations

from pathlib import Path

from app.models import (
    GsgfAnalysis,
    MarketEmotionSnapshotResponse,
    ShortTermSentimentResponse,
    StrongStockScreeningItem,
    StrongStockScreeningResult,
)
from app.services.gsgf_review import GsgfReviewStore
from app.services.market_emotion_history import MarketEmotionHistoryStore
from app.services.runs import RunStore
from app.services.sentiment_snapshot_store import SentimentSnapshotStore


def test_run_store_prunes_old_screen_runs_and_keeps_latest_pointer(tmp_path: Path) -> None:
    store = RunStore(tmp_path, retention_count=2)

    store.save(_screen_result("2026-06-10", "000001.SZ"))
    store.save(_screen_result("2026-06-11", "000002.SZ"))
    store.save(_screen_result("2026-06-12", "000003.SZ"))

    history_files = sorted(path.name for path in tmp_path.glob("*.json") if path.name != "latest.json")
    assert len(history_files) == 2
    assert store.load_latest() is not None
    assert store.load_latest().trade_date == "2026-06-12"


def test_gsgf_review_store_prunes_old_records(tmp_path: Path) -> None:
    store = GsgfReviewStore(tmp_path, max_records=2)

    store.persist_snapshot(_screen_result("2026-06-10", "000001.SZ"))
    store.persist_snapshot(_screen_result("2026-06-11", "000002.SZ"))
    store.persist_snapshot(_screen_result("2026-06-12", "000003.SZ"))

    records = store.load_records()
    assert [record.symbol for record in records] == ["000002.SZ", "000003.SZ"]


def test_sentiment_snapshot_store_prunes_old_trade_date_dirs(tmp_path: Path) -> None:
    store = SentimentSnapshotStore(tmp_path, retention_days=2)

    for trade_date in ["2026-06-10", "2026-06-11", "2026-06-12"]:
        store.save(
            sentiment=ShortTermSentimentResponse(trade_date=trade_date),
            market_emotion=MarketEmotionSnapshotResponse(trade_date=trade_date),
        )

    remaining = sorted(path.name for path in (tmp_path / "sentiment_snapshots").iterdir())
    assert remaining == ["2026-06-11", "2026-06-12"]


def test_market_emotion_history_store_prunes_days_and_samples(tmp_path: Path) -> None:
    store = MarketEmotionHistoryStore(tmp_path, retention_days=2, samples_per_day=2)

    for trade_date in ["2026-06-10", "2026-06-11", "2026-06-12"]:
        for index in range(3):
            store.append(
                MarketEmotionSnapshotResponse(
                    trade_date=trade_date,
                    generated_at=f"{trade_date}T09:2{index}:00+08:00",
                )
            )

    remaining_files = sorted(path.name for path in (tmp_path / "market_emotion").glob("*.jsonl"))
    assert remaining_files == ["2026-06-11.jsonl", "2026-06-12.jsonl"]
    assert len(store.load("2026-06-12", limit=10)) == 2


def _screen_result(trade_date: str, symbol: str) -> StrongStockScreeningResult:
    return StrongStockScreeningResult(
        trade_date=trade_date,
        strategy="gsgf",
        gsgf_model_version="gsgf-v2",
        sort_version="gsgf-sort-v1",
        items=[
            StrongStockScreeningItem(
                symbol=symbol,
                name=symbol,
                status="focus",
                score=80,
                gsgf=GsgfAnalysis(
                    total_score=82,
                    final_status="确认买点",
                    action="strong_candidate",
                    zone="a_zone",
                    setup_type="B区A点",
                    confirm_type="放量突破确认",
                ),
            )
        ],
    )
