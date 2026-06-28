from pathlib import Path

from app.models import GsgfAnalysis, KlineBar, StrongStockScreeningItem, StrongStockScreeningResult
from app.services.gsgf_review import GsgfReviewStore


def test_gsgf_review_store_persists_snapshot_and_rechecks_windows(tmp_path: Path) -> None:
    store = GsgfReviewStore(tmp_path)
    result = StrongStockScreeningResult(
        trade_date="2026-06-11",
        strategy="gsgf",
        gsgf_model_version="gsgf-v1",
        sort_version="gsgf-sort-v1",
        items=[
            StrongStockScreeningItem(
                symbol="603890.SH",
                name="春秋电子",
                industry="消费电子",
                status="focus",
                score=90,
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

    snapshot = store.persist_snapshot(result)
    summary = store.recheck_snapshots({"603890.SH": _bars([10, 10.4, 10.7, 10.2, 11.1, 11.4])}, windows=[1, 3, 5])

    assert snapshot.saved_count == 1
    assert snapshot.records[0].signal_type == "放量突破确认"
    assert summary.record_count == 1
    assert summary.items[0].windows[0].window_days == 1
    assert summary.items[0].windows[0].realized_return_pct == 4
    assert summary.items[0].windows[1].max_drawdown_pct == 2
    assert summary.items[0].confirmed is True
    assert summary.buckets[0].signal_type == "放量突破确认"
    assert summary.buckets[0].status == "确认买点"
    assert summary.buckets[0].sample_count == 1
    assert summary.buckets[0].confirmed_count == 1
    assert (tmp_path / "gsgf_review" / "snapshots.jsonl").exists()


def _bars(closes: list[float]) -> list[KlineBar]:
    return [
        KlineBar(
            date=f"2026-06-{index + 11:02d}",
            open=close,
            close=close,
            high=close,
            low=close,
            volume=1_000_000,
        )
        for index, close in enumerate(closes)
    ]
