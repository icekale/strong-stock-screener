from app.models import AuctionModelPredictionItem, AuctionSnapshotItem
from app.services.auction_top3_live_confirmation import confirm_auction_top3_item


def model_item(**updates):
    data = {
        "symbol": "300001.SZ",
        "name": "模型一号",
        "prob_3pct": 0.91,
        "bucket": "selected",
        "rank": 1,
        "risk_flags": [],
    }
    data.update(updates)
    return AuctionModelPredictionItem(**data)


def snapshot_item(**updates):
    data = {
        "symbol": "300001.SZ",
        "name": "模型一号",
        "open_gap_pct": 4.5,
        "current_pct_change": 5.2,
        "turnover_cny": 160_000_000,
        "turnover_rate": 3.5,
        "quote_time": "2026-07-06T09:25:00+08:00",
    }
    data.update(updates)
    return AuctionSnapshotItem(**data)


def test_live_confirmation_marks_selected_candidate_buyable() -> None:
    result = confirm_auction_top3_item(model_item(), snapshot_item())

    assert result.confirmation == "buyable"
    assert "模型入选Top3" in result.reasons
    assert "实时量能通过" in result.reasons


def test_live_confirmation_rejects_model_liquidity_risk() -> None:
    result = confirm_auction_top3_item(
        model_item(risk_flags=["近3日日均成交额低于1亿"]),
        snapshot_item(),
    )

    assert result.confirmation == "reject"
    assert "模型流动性风险" in result.risk_flags


def test_live_confirmation_rejects_overheated_gap_without_resonance() -> None:
    result = confirm_auction_top3_item(
        model_item(),
        snapshot_item(open_gap_pct=8.1, theme_resonance=False),
    )

    assert result.confirmation == "reject"
    assert "高开过热" in result.risk_flags


def test_live_confirmation_watches_when_realtime_missing() -> None:
    result = confirm_auction_top3_item(model_item(), None)

    assert result.confirmation == "watch"
    assert "realtime_missing" in result.data_quality
