from app.models import AuctionReviewRecord, AuctionReviewSnapshot, KlineBar
from app.services.auction_review import build_auction_rule_buckets, finalize_auction_records


def test_finalize_auction_records_scores_intraday_day_and_next_day_results() -> None:
    record = _record("2026-07-01", "300001.SZ", ["温和高开", "量能活跃"])
    summary = finalize_auction_records(
        [record],
        symbol_bars={
            "300001.SZ": [
                KlineBar(date="2026-06-30", open=9.8, close=10.0, high=10.2, low=9.7, volume=100),
                KlineBar(date="2026-07-01", open=10.4, close=10.8, high=11.3, low=10.2, volume=300),
                KlineBar(date="2026-07-02", open=11.0, close=11.2, high=11.5, low=10.7, volume=280),
            ]
        },
        symbol_intraday_bars={
            "300001.SZ": [
                KlineBar(date="2026-07-01 09:30", open=10.4, close=10.5, high=10.6, low=10.3, volume=30),
                KlineBar(date="2026-07-01 09:45", open=10.5, close=10.9, high=11.0, low=10.5, volume=50),
                KlineBar(date="2026-07-01 10:00", open=10.9, close=10.7, high=11.1, low=10.6, volume=40),
                KlineBar(date="2026-07-01 10:15", open=10.7, close=10.4, high=10.8, low=10.3, volume=20),
            ]
        },
    )

    reviewed = summary.records[0]
    assert reviewed.review_status == "next_day_done"
    assert reviewed.intraday_result.peak_pct == 11.0
    assert reviewed.intraday_result.close_pct == 7.0
    assert reviewed.day_result.peak_pct == 13.0
    assert reviewed.day_result.close_pct == 8.0
    assert reviewed.next_day_result.open_pct == 1.85
    assert reviewed.next_day_result.peak_pct == 6.48
    assert reviewed.score.total_score is not None
    assert summary.completed_count == 1
    assert summary.buckets[0].sample_count == 1


def test_finalize_auction_records_keeps_day_result_when_minute_data_missing() -> None:
    summary = finalize_auction_records(
        [_record("2026-07-01", "300002.SZ", ["高开过热"])],
        symbol_bars={
            "300002.SZ": [
                KlineBar(date="2026-06-30", open=9.8, close=10.0, high=10.2, low=9.7, volume=100),
                KlineBar(date="2026-07-01", open=10.9, close=9.9, high=11.0, low=9.2, volume=300),
            ]
        },
    )

    reviewed = summary.records[0]
    assert reviewed.review_status == "data_incomplete"
    assert reviewed.intraday_result.status == "data_incomplete"
    assert reviewed.day_result.close_pct == -1.0
    assert reviewed.score.day_score is not None
    assert summary.data_incomplete_count == 1


def test_build_auction_rule_buckets_summarizes_winners_failures_and_suggestions() -> None:
    winner = _record("2026-07-01", "300001.SZ", ["温和高开"])
    winner.score.total_score = 72
    winner.intraday_result.peak_pct = 8
    winner.day_result.close_pct = 6
    winner.day_result.drawdown_pct = -2
    winner.next_day_result.open_pct = 2
    loser = _record("2026-07-02", "300002.SZ", ["温和高开"])
    loser.score.total_score = 25
    loser.intraday_result.peak_pct = 1
    loser.day_result.close_pct = -4
    loser.day_result.drawdown_pct = -8
    loser.next_day_result.open_pct = -3

    buckets = build_auction_rule_buckets([winner, loser])

    bucket = buckets[0]
    assert bucket.rule_tag == "温和高开"
    assert bucket.sample_count == 2
    assert bucket.win_rate == 0.5
    assert bucket.avg_score == 48.5
    assert bucket.failure_count == 1
    assert "增加过滤条件" in bucket.suggestion


def _record(trade_date: str, symbol: str, rule_tags: list[str]) -> AuctionReviewRecord:
    return AuctionReviewRecord(
        trade_date=trade_date,
        symbol=symbol,
        name=symbol,
        selected_at_label="09:25",
        selected_at=f"{trade_date}T09:25:00+08:00",
        auction_snapshot=AuctionReviewSnapshot(
            open_gap_pct=3.8,
            current_pct_change=4.6,
            turnover_cny=360_000_000,
            turnover_rate=6.2,
            auction_score=78,
            rank=1,
            tier="strong_high_open",
        ),
        rule_tags=rule_tags,
    )
