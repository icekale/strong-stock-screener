from datetime import datetime

from app.models import MarketRankingItem, MarketRankingsResponse
from app.services.auction import build_auction_snapshot


def test_auction_snapshot_separates_open_gap_from_current_pct_change() -> None:
    rankings = MarketRankingsResponse(
        trade_date="2026-07-01",
        pct_change_rank=[
            MarketRankingItem(
                symbol="002001.SZ",
                name="高开一号",
                industry="电池",
                last_price=11.2,
                open_price=10.8,
                prev_close=10.0,
                pct_change=12.0,
                current_pct_change=12.0,
                turnover_rate=8.0,
                turnover_cny=500_000_000,
                quote_time="1782869583000",
            )
        ],
    )

    snapshot = build_auction_snapshot(rankings, limit=1, now=datetime(2026, 7, 1, 9, 26))

    assert snapshot.items[0].current_pct_change == 12.0
    assert snapshot.items[0].industry == "电池"
    assert snapshot.items[0].open_gap_pct == 8.0
    assert snapshot.items[0].tier == "risk_overheat"
    assert "高开需防冲高回落" in snapshot.items[0].risk_flags


def test_auction_snapshot_classifies_reversal_watch_and_weak_low_open() -> None:
    rankings = MarketRankingsResponse(
        trade_date="2026-07-01",
        pct_change_rank=[
            MarketRankingItem(
                symbol="002002.SZ",
                name="低开转强",
                last_price=10.4,
                open_price=9.6,
                prev_close=10.0,
                pct_change=4.0,
                current_pct_change=4.0,
                turnover_rate=6.0,
                turnover_cny=350_000_000,
            ),
            MarketRankingItem(
                symbol="002003.SZ",
                name="低开偏弱",
                last_price=9.4,
                open_price=9.6,
                prev_close=10.0,
                pct_change=-6.0,
                current_pct_change=-6.0,
                turnover_rate=1.0,
                turnover_cny=50_000_000,
            ),
        ],
    )

    snapshot = build_auction_snapshot(rankings, limit=2, now=datetime(2026, 7, 1, 9, 31))
    items_by_symbol = {item.symbol: item for item in snapshot.items}

    assert items_by_symbol["002002.SZ"].open_gap_pct == -4.0
    assert items_by_symbol["002002.SZ"].tier == "reversal_watch"
    assert "低开转强观察" in items_by_symbol["002002.SZ"].signals
    assert items_by_symbol["002003.SZ"].tier == "weak_low_open"
    assert "竞价低开偏弱" in items_by_symbol["002003.SZ"].risk_flags
