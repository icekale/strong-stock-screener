from fastapi.testclient import TestClient

from app.main import MARKET_EMOTION_CACHE, SHORT_TERM_SENTIMENT_CACHE, app
from app.models import SentimentDecisionResponse, SentimentMainSectorSignal
from app.providers.watchlist import WatchlistItem
from app.services.sentiment_watchlist import build_sentiment_watchlist_alerts
from tests.test_short_term_sentiment import FakeEmotionMarketOverviewProvider, FakeSentimentCandidateProvider


def test_watchlist_alerts_prioritize_main_sector_matches() -> None:
    decision = SentimentDecisionResponse(
        trade_date="2026-07-02",
        market_state="修复",
        trade_permission="轻仓试错",
        risk_level="中",
        main_sectors=[
            SentimentMainSectorSignal(name="存储芯片", strength_score=88, symbols=["001309.SZ"]),
        ],
        reasons=["主线板块集中在存储芯片"],
    )
    items = [
        WatchlistItem(symbol="001309.SZ", name="德明利", group="存储芯片", tags=["观察"]),
        WatchlistItem(symbol="600000.SH", name="浦发银行", group="银行", tags=[]),
    ]

    result = build_sentiment_watchlist_alerts(decision, items)

    assert result[0].symbol == "001309.SZ"
    assert result[0].action == "重点盯"
    assert "命中主线板块" in result[0].reasons
    assert result[1].action == "等确认"


def test_watchlist_alerts_mark_risk_avoid_when_market_permission_is_defensive() -> None:
    decision = SentimentDecisionResponse(
        trade_date="2026-07-02",
        market_state="退潮",
        trade_permission="空仓等待",
        risk_level="高",
        main_sectors=[SentimentMainSectorSignal(name="机器人", strength_score=80, symbols=["603001.SH"])],
    )
    items = [WatchlistItem(symbol="603001.SH", name="三板科技", group="机器人", tags=["观察"])]

    result = build_sentiment_watchlist_alerts(decision, items)

    assert result[0].action == "风险回避"
    assert "当前交易许可为空仓等待" in result[0].reasons


def test_sentiment_watchlist_alerts_api_reads_watchlist_pool(tmp_path) -> None:
    SHORT_TERM_SENTIMENT_CACHE.clear()
    MARKET_EMOTION_CACHE.clear()
    app.state.candidate_provider = FakeSentimentCandidateProvider()
    app.state.market_overview_provider = FakeEmotionMarketOverviewProvider()
    app.state.runs_dir = tmp_path
    app.state.watchlist_path = tmp_path / "watchlist.txt"
    app.state.watchlist_path.write_text(
        "[机器人]\n603001.SH 三板科技 #观察\n\n[电力]\n002003.SZ 首板电力 #待确认",
        encoding="utf-8",
    )
    try:
        response = TestClient(app).get(
            "/api/short-term/sentiment/watchlist-alerts?trade_date=2026-06-26&limit=20&refresh=true"
        )
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")
        delattr(app.state, "watchlist_path")
        SHORT_TERM_SENTIMENT_CACHE.clear()
        MARKET_EMOTION_CACHE.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    by_symbol = {item["symbol"]: item for item in payload["items"]}
    assert by_symbol["603001.SH"]["name"] == "三板科技"
    assert by_symbol["603001.SH"]["matched_sector"] == "机器人"
    assert by_symbol["002003.SZ"]["matched_sector"] == "电力"
    assert {item["action"] for item in payload["items"]} == {"风险回避"}
