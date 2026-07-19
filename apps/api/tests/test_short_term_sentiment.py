from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from time import sleep
from zoneinfo import ZoneInfo

import pytest

from app.main import (
    MARKET_EMOTION_CACHE,
    MARKET_OVERVIEW_CACHE,
    SHORT_TERM_SENTIMENT_CACHE,
    _provider_cache_key,
    _should_persist_market_emotion_sample,
    app,
)
from app.models import (
    MarketEmotionBucket,
    MarketAdvanceDeclineSummary,
    MarketOverviewResponse,
    MarketTurnoverSummary,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.providers.tickflow import TickFlowIntradayBar, TickFlowQuote
from app.services.short_term_sentiment import (
    build_market_emotion_snapshot,
    build_sentiment_summary,
    build_short_term_intraday_sentiment,
    build_short_term_intraday_signal_digest,
    build_short_term_sentiment,
)
from app.services.market_emotion_history import MarketEmotionHistoryStore
from app.services.sentiment_snapshot_store import SentimentSnapshotStore
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_short_term_caches() -> None:
    SHORT_TERM_SENTIMENT_CACHE.clear()
    MARKET_EMOTION_CACHE.clear()
    MARKET_OVERVIEW_CACHE.clear()


class FakeSentimentCandidateProvider:
    source_name = "fake涨停池"

    def __init__(self) -> None:
        self.calls = 0

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        self.calls += 1
        return [
            StrongStockCandidate(
                symbol="603001.SH",
                name="三板科技",
                industry="机器人",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260626", "20日涨停次数: 3"],
                board_note="涨停日期: 20260626,20260625,20260624; 连板数: 3; 炸板次数: 0; 首次封板时间: 09:35:00",
            ),
            StrongStockCandidate(
                symbol="603002.SH",
                name="二板智能",
                industry="机器人",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260626", "20日涨停次数: 2"],
                board_note="涨停日期: 20260626,20260625; 连板数: 2; 炸板次数: 1; 首次封板时间: 10:12:00",
            ),
            StrongStockCandidate(
                symbol="002003.SZ",
                name="首板电力",
                industry="电力",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260626", "20日涨停次数: 1"],
                board_note="涨停日期: 20260626; 连板数: 1; 炸板次数: 0",
            ),
            StrongStockCandidate(
                symbol="002004.SZ",
                name="昨日消费",
                industry="消费",
                limit_up_evidence=["20日内涨停", "最近涨停: 20260625", "20日涨停次数: 1"],
                board_note="涨停日期: 20260625; 连板数: 1; 炸板次数: 2",
            ),
        ]


class FailingSentimentCandidateProvider:
    source_name = "fake失败涨停池"

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        raise StrongStockDataUnavailable("涨停池不可用")


class FakeSentimentQuoteProvider:
    source_name = "fake TickFlow"

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        quote_map = {
            "603001.SH": TickFlowQuote(
                symbol="603001.SH",
                name="三板科技",
                last_price=10.8,
                prev_close=10,
                open_price=10.7,
                high_price=10.9,
                pct_change=8,
                turnover_cny=1_200_000_000,
                volume=10_000_000,
            ),
            "603002.SH": TickFlowQuote(
                symbol="603002.SH",
                name="二板智能",
                last_price=9.5,
                prev_close=10,
                open_price=9.2,
                high_price=9.8,
                pct_change=-5,
                turnover_cny=700_000_000,
                volume=8_000_000,
            ),
            "002003.SZ": TickFlowQuote(
                symbol="002003.SZ",
                name="首板电力",
                last_price=10.2,
                prev_close=10,
                open_price=10,
                high_price=10.3,
                pct_change=2,
                turnover_cny=500_000_000,
                volume=5_000_000,
            ),
            "002004.SZ": TickFlowQuote(
                symbol="002004.SZ",
                name="昨日消费",
                last_price=8.8,
                prev_close=10,
                open_price=9.9,
                high_price=10.2,
                pct_change=-12,
                turnover_cny=300_000_000,
                volume=4_000_000,
            ),
        }
        return [quote_map[symbol] for symbol in symbols if symbol in quote_map]

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        return {
            symbol: [
                TickFlowIntradayBar(timestamp=1, open=9.0, high=9.2, low=8.9, close=9.0, volume=1, amount=1),
                TickFlowIntradayBar(timestamp=2, open=9.0, high=9.5, low=8.8, close=9.4, volume=1, amount=1),
                TickFlowIntradayBar(timestamp=3, open=9.4, high=9.8, low=9.2, close=9.6, volume=1, amount=1),
            ]
            for symbol in symbols
        }


class FailingIntradayBarsQuoteProvider(FakeSentimentQuoteProvider):
    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        raise StrongStockDataUnavailable("TickFlow 分钟线请求失败: HTTP 429")


class FakeEmotionMarketOverviewProvider:
    def __init__(self) -> None:
        self.overview_calls = 0
        self.distribution_calls = 0

    def get_overview(self) -> MarketOverviewResponse:
        self.overview_calls += 1
        return MarketOverviewResponse(
            trade_date="2026-06-26",
            turnover=MarketTurnoverSummary(
                total_cny=3_575_720_000_000,
                previous_total_cny=3_618_100_000_000,
                change_cny=-42_380_000_000,
                change_pct=-1.17,
            ),
            advance_decline=MarketAdvanceDeclineSummary(
                advance_count=802,
                decline_count=4738,
                unchanged_count=51,
                limit_down_count=30,
            ),
            source_status=[
                StrongStockSourceStatus(
                    source="fake市场概览",
                    status="success",
                    detail="模拟 iFinD/TickFlow 实时全A概览",
                )
            ],
        )

    def get_pct_change_distribution(self) -> tuple[list[MarketEmotionBucket], StrongStockSourceStatus]:
        self.distribution_calls += 1
        return (
            [
                MarketEmotionBucket(label=">10%", min_pct=10, max_pct=None, count=1, source="fake分布"),
                MarketEmotionBucket(label="7-10%", min_pct=7, max_pct=10, count=0, source="fake分布"),
                MarketEmotionBucket(label="5-7%", min_pct=5, max_pct=7, count=1, source="fake分布"),
                MarketEmotionBucket(label="3-5%", min_pct=3, max_pct=5, count=0, source="fake分布"),
                MarketEmotionBucket(label="0-3%", min_pct=0, max_pct=3, count=2, source="fake分布"),
                MarketEmotionBucket(label="-3-0%", min_pct=-3, max_pct=0, count=4, source="fake分布"),
                MarketEmotionBucket(label="-5--3%", min_pct=-5, max_pct=-3, count=1, source="fake分布"),
                MarketEmotionBucket(label="-7--5%", min_pct=-7, max_pct=-5, count=0, source="fake分布"),
                MarketEmotionBucket(label="-10--7%", min_pct=-10, max_pct=-7, count=0, source="fake分布"),
                MarketEmotionBucket(label="<-10%", min_pct=None, max_pct=-10, count=1, source="fake分布"),
            ],
            StrongStockSourceStatus(source="fake全市场分布", status="success", detail="返回 10 只股票"),
        )


def test_short_term_sentiment_builds_limit_up_pool_ladder_and_break_pool() -> None:
    result = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )

    assert result.trade_date == "2026-06-26"
    assert result.metrics.limit_up_count == 3
    assert result.metrics.break_board_count == 2
    assert result.metrics.max_consecutive_boards == 3
    assert [item.symbol for item in result.limit_up_pool] == [
        "603001.SH",
        "603002.SH",
        "002003.SZ",
    ]
    assert [item.symbol for item in result.break_board_pool] == ["002004.SZ", "603002.SH"]
    assert result.ladder[0].board_count == 3
    assert result.ladder[0].items[0].name == "三板科技"
    assert result.ladder[1].board_count == 2
    assert result.hot_industries[0].name == "机器人"
    assert result.hot_industries[0].limit_up_count == 2
    assert result.source_status[0].source == "fake涨停池"
    assert result.source_status[0].status == "success"


def test_market_emotion_snapshot_combines_limit_up_pool_and_realtime_market_overview() -> None:
    result = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )

    assert result.trade_date == "2026-06-26"
    assert result.metrics.limit_up_count == 3
    assert result.metrics.break_board_count == 2
    assert result.metrics.limit_down_count == 30
    assert result.metrics.max_consecutive_boards == 3
    assert result.metrics.advance_count == 802
    assert result.metrics.decline_count == 4738
    assert result.metrics.seal_rate_pct == 60.0
    assert 0 <= result.metrics.emotion_score <= 100
    assert result.metrics.emotion_level in {"冰点", "一般", "良好", "火爆"}
    assert result.metrics.turnover_cny == 3_575_720_000_000
    assert result.metrics.turnover_change_pct == -1.17
    assert result.buckets[0].label == ">10%"
    assert result.buckets[0].count == 1
    assert result.buckets[5].count == 4
    assert any(status.source == "fake涨停池" for status in result.source_status)
    assert any(status.source == "fake市场概览" for status in result.source_status)
    assert any(status.source == "fake全市场分布" for status in result.source_status)
    assert any(status.source == "市场情绪模型" for status in result.source_status)
    assert any("分时曲线" in note for note in result.notes)


def test_market_emotion_snapshot_uses_preloaded_market_overview() -> None:
    market_provider = FakeEmotionMarketOverviewProvider()
    overview = market_provider.get_overview()

    result = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        market_provider,
        trade_date="2026-06-26",
        limit=20,
        market_overview=overview,
    )

    assert result.metrics.turnover_cny == overview.turnover.total_cny
    assert market_provider.overview_calls == 1


def test_market_emotion_snapshot_can_skip_expensive_distribution_for_homepage() -> None:
    market_provider = FakeEmotionMarketOverviewProvider()

    result = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        market_provider,
        trade_date="2026-06-26",
        limit=20,
        include_distribution=False,
    )

    assert result.buckets == []
    assert market_provider.distribution_calls == 0


def test_market_emotion_history_store_persists_real_samples(tmp_path: Path) -> None:
    snapshot = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    store = MarketEmotionHistoryStore(tmp_path)

    store.append(snapshot)
    samples = store.load("2026-06-26")

    assert len(samples) == 1
    assert samples[0].trade_date == "2026-06-26"
    assert samples[0].emotion_score == snapshot.metrics.emotion_score
    assert samples[0].emotion_level == snapshot.metrics.emotion_level
    assert samples[0].limit_up_count == 3
    assert samples[0].advance_count == 802


def test_sentiment_snapshot_store_persists_summary_and_full_snapshots(tmp_path: Path) -> None:
    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    store = SentimentSnapshotStore(tmp_path)

    store.save(sentiment=sentiment, market_emotion=emotion)
    loaded_summary = store.load_summary("2026-06-26")
    loaded_sentiment = store.load_sentiment("2026-06-26")
    loaded_emotion = store.load_market_emotion("2026-06-26")

    assert loaded_summary is not None
    assert loaded_summary.trade_date == "2026-06-26"
    assert loaded_summary.snapshot_status == "cached"
    assert loaded_summary.metrics.limit_up_count == 3
    assert loaded_summary.metrics.advance_count == 802
    assert loaded_summary.cached_at == emotion.generated_at
    assert loaded_sentiment is not None
    assert loaded_sentiment.ladder[0].label == "3连板"
    assert loaded_emotion is not None
    assert loaded_emotion.buckets[0].count == 1


def test_sentiment_snapshot_store_deduplicates_legacy_summary_source_status(tmp_path: Path) -> None:
    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    store = SentimentSnapshotStore(tmp_path)
    summary = build_sentiment_summary(sentiment, emotion, snapshot_status="cached")
    duplicate = summary.source_status[0]
    legacy_summary = summary.model_copy(update={"source_status": [duplicate, *summary.source_status]})
    summary_path = store.root_dir / "2026-06-26" / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(legacy_summary.model_dump_json(), encoding="utf-8")

    loaded_summary = store.load_summary("2026-06-26")
    persisted_summary = store.load_summary("2026-06-26")

    assert loaded_summary is not None
    source_keys = [(item.source, item.status, item.detail) for item in loaded_summary.source_status]
    assert len(source_keys) == len(set(source_keys))
    assert persisted_summary is not None
    persisted_keys = [(item.source, item.status, item.detail) for item in persisted_summary.source_status]
    assert len(persisted_keys) == len(set(persisted_keys))


def test_build_sentiment_summary_combines_short_term_and_market_emotion() -> None:
    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )

    summary = build_sentiment_summary(sentiment, emotion, snapshot_status="fresh")

    assert summary.trade_date == "2026-06-26"
    assert summary.snapshot_status == "fresh"
    assert summary.metrics.limit_up_count == 3
    assert summary.metrics.break_board_count == 2
    assert summary.metrics.advance_count == 802
    assert summary.metrics.emotion_level in {"冰点", "一般", "良好", "火爆"}
    assert summary.hot_industries[0].name == "机器人"
    source_keys = [(item.source, item.detail) for item in summary.source_status]
    assert len(source_keys) == len(set(source_keys))


def test_short_term_sentiment_reports_unavailable_candidate_source() -> None:
    try:
        build_short_term_sentiment(FailingSentimentCandidateProvider(), trade_date="2026-06-26")
    except StrongStockDataUnavailable as exc:
        assert "涨停池不可用" in str(exc)
    else:
        raise AssertionError("expected StrongStockDataUnavailable")


def test_short_term_sentiment_api_uses_configured_candidate_provider() -> None:
    app.state.candidate_provider = FakeSentimentCandidateProvider()
    try:
        response = TestClient(app).get("/api/short-term/sentiment?trade_date=2026-06-26&limit=10")
    finally:
        delattr(app.state, "candidate_provider")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["limit_up_count"] == 3
    assert payload["ladder"][0]["label"] == "3连板"
    assert payload["hot_industries"][0]["name"] == "机器人"


def test_market_emotion_snapshot_api_uses_configured_sources(tmp_path: Path) -> None:
    candidate_provider = FakeSentimentCandidateProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = FakeEmotionMarketOverviewProvider()
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get("/api/short-term/market-emotion?trade_date=2026-06-26&limit=20")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["limit_up_count"] == 3
    assert payload["metrics"]["advance_count"] == 802
    assert payload["metrics"]["seal_rate_pct"] == 60.0
    assert payload["buckets"][0]["label"] == ">10%"
    assert payload["buckets"][0]["count"] == 1
    assert payload["samples"] == []


def test_short_term_sentiment_decision_api_returns_trade_permission(tmp_path: Path) -> None:
    app.state.candidate_provider = FakeSentimentCandidateProvider()
    app.state.market_overview_provider = FakeEmotionMarketOverviewProvider()
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get(
            "/api/short-term/sentiment/decision?trade_date=2026-06-26&limit=20&refresh=true"
        )
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-26"
    assert payload["market_state"] in ["冰点", "修复", "主升", "高潮", "分歧", "退潮"]
    assert payload["trade_permission"] in ["空仓等待", "轻仓试错", "强势进攻", "只低吸", "只卖不追"]
    assert isinstance(payload["reasons"], list)


def test_short_term_sentiment_api_reuses_cached_snapshot_for_fast_reload(tmp_path: Path) -> None:
    candidate_provider = FakeSentimentCandidateProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = FakeEmotionMarketOverviewProvider()
    app.state.runs_dir = tmp_path
    try:
        first = TestClient(app).get("/api/short-term/sentiment?trade_date=2026-06-26&limit=20")
        second = TestClient(app).get("/api/short-term/sentiment?trade_date=2026-06-26&limit=20")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert first.status_code == 200
    assert second.status_code == 200
    assert candidate_provider.calls == 1


def test_market_emotion_api_reuses_cached_snapshot_for_fast_reload(tmp_path: Path) -> None:
    candidate_provider = FakeSentimentCandidateProvider()
    market_provider = FakeEmotionMarketOverviewProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = market_provider
    app.state.runs_dir = tmp_path
    try:
        first = TestClient(app).get("/api/short-term/market-emotion?trade_date=2026-06-26&limit=20")
        second = TestClient(app).get("/api/short-term/market-emotion?trade_date=2026-06-26&limit=20")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert first.status_code == 200
    assert second.status_code == 200
    assert candidate_provider.calls == 1
    assert market_provider.overview_calls == 1
    assert market_provider.distribution_calls == 1


def test_market_emotion_api_throttles_samples_to_three_minutes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FrozenDateTime(datetime):
        current = datetime(2026, 6, 26, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz) if tz is not None else cls.current.replace(tzinfo=None)

    monkeypatch.setattr("app.main.datetime", FrozenDateTime)
    candidate_provider = FakeSentimentCandidateProvider()
    market_provider = FakeEmotionMarketOverviewProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = market_provider
    app.state.runs_dir = tmp_path
    try:
        first = TestClient(app).get("/api/short-term/market-emotion?trade_date=2026-06-26&limit=20")
        second = TestClient(app).get("/api/short-term/market-emotion?trade_date=2026-06-26&limit=20")
        FrozenDateTime.current += timedelta(minutes=3)
        third = TestClient(app).get("/api/short-term/market-emotion?trade_date=2026-06-26&limit=20")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert len(second.json()["samples"]) == 1
    assert len(third.json()["samples"]) == 2


def test_market_emotion_sampling_skips_weekends() -> None:
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert not _should_persist_market_emotion_sample("2026-06-28", [], now=now)


def test_market_emotion_sampling_stops_at_market_close() -> None:
    tz = ZoneInfo("Asia/Shanghai")

    assert _should_persist_market_emotion_sample(
        "2026-06-29",
        [],
        now=datetime(2026, 6, 29, 15, 0, tzinfo=tz),
    )
    assert not _should_persist_market_emotion_sample(
        "2026-06-29",
        [],
        now=datetime(2026, 6, 29, 15, 1, tzinfo=tz),
    )


def test_homepage_market_emotion_does_not_overwrite_full_snapshot(tmp_path: Path) -> None:
    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    full_emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    store = SentimentSnapshotStore(tmp_path)
    store.save(sentiment=sentiment, market_emotion=full_emotion)

    app.state.candidate_provider = FakeSentimentCandidateProvider()
    app.state.market_overview_provider = FakeEmotionMarketOverviewProvider()
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get(
            "/api/short-term/market-emotion"
            "?trade_date=2026-06-26&limit=20&include_distribution=false"
        )
        persisted = store.load_market_emotion("2026-06-26")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    assert response.json()["buckets"] == []
    assert persisted is not None
    assert persisted.buckets == full_emotion.buckets


def test_historical_market_emotion_does_not_overwrite_full_snapshot(tmp_path: Path) -> None:
    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    historical_emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    historical_emotion.buckets[0].count = 999
    store = SentimentSnapshotStore(tmp_path)
    store.save(sentiment=sentiment, market_emotion=historical_emotion)

    app.state.candidate_provider = FakeSentimentCandidateProvider()
    app.state.market_overview_provider = FakeEmotionMarketOverviewProvider()
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get(
            "/api/short-term/market-emotion?trade_date=2026-06-26&limit=20"
        )
        persisted = store.load_market_emotion("2026-06-26")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    assert response.json()["buckets"][0]["count"] == 1
    assert persisted is not None
    assert persisted.buckets[0].count == 999


def test_sentiment_snapshot_store_serializes_concurrent_saves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.sentiment_snapshot_store as snapshot_store_module

    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    original_builder = snapshot_store_module.build_sentiment_summary
    counter_lock = Lock()
    active_builders = 0
    max_active_builders = 0

    def tracked_builder(*args, **kwargs):
        nonlocal active_builders, max_active_builders
        with counter_lock:
            active_builders += 1
            max_active_builders = max(max_active_builders, active_builders)
        sleep(0.03)
        try:
            return original_builder(*args, **kwargs)
        finally:
            with counter_lock:
                active_builders -= 1

    monkeypatch.setattr(snapshot_store_module, "build_sentiment_summary", tracked_builder)
    store = SentimentSnapshotStore(tmp_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store.save, sentiment, emotion) for _ in range(2)]
        for future in futures:
            future.result()

    assert max_active_builders == 1


def test_sentiment_summary_api_uses_persisted_snapshot_without_provider_calls(tmp_path: Path) -> None:
    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    SentimentSnapshotStore(tmp_path).save(sentiment=sentiment, market_emotion=emotion)

    candidate_provider = FakeSentimentCandidateProvider()
    market_provider = FakeEmotionMarketOverviewProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = market_provider
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get("/api/short-term/sentiment/summary?trade_date=2026-06-26")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_status"] == "cached"
    assert payload["metrics"]["limit_up_count"] == 3
    assert payload["metrics"]["advance_count"] == 802
    assert candidate_provider.calls == 0
    assert market_provider.overview_calls == 0


def test_sentiment_summary_api_builds_and_persists_snapshot_when_missing(tmp_path: Path) -> None:
    candidate_provider = FakeSentimentCandidateProvider()
    market_provider = FakeEmotionMarketOverviewProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = market_provider
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get("/api/short-term/sentiment/summary?trade_date=2026-06-26&limit=20")
        missing_loaded = SentimentSnapshotStore(tmp_path).load_summary("2026-06-26")
        refresh_response = TestClient(app).get(
            "/api/short-term/sentiment/summary?trade_date=2026-06-26&limit=20&refresh=true"
        )
        loaded = SentimentSnapshotStore(tmp_path).load_summary("2026-06-26")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    assert response.json()["snapshot_status"] == "missing"
    assert missing_loaded is None
    assert refresh_response.status_code == 200
    assert refresh_response.json()["snapshot_status"] == "fresh"
    assert loaded is not None
    assert loaded.snapshot_status == "cached"
    assert candidate_provider.calls == 1
    assert market_provider.overview_calls == 1


def test_sentiment_summary_refresh_rebuilds_existing_snapshot(tmp_path: Path) -> None:
    old_sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    old_emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    old_emotion.metrics.limit_down_count = None
    SentimentSnapshotStore(tmp_path).save(sentiment=old_sentiment, market_emotion=old_emotion)

    candidate_provider = FakeSentimentCandidateProvider()
    market_provider = FakeEmotionMarketOverviewProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = market_provider
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get(
            "/api/short-term/sentiment/summary?trade_date=2026-06-26&limit=20&refresh=true"
        )
        loaded = SentimentSnapshotStore(tmp_path).load_summary("2026-06-26")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_status"] == "fresh"
    assert payload["metrics"]["limit_down_count"] == 30
    assert loaded is not None
    assert loaded.metrics.limit_down_count == 30
    assert candidate_provider.calls == 1
    assert market_provider.overview_calls == 1


def test_sentiment_detail_api_reads_persisted_snapshot_without_provider_calls(tmp_path: Path) -> None:
    sentiment = build_short_term_sentiment(
        FakeSentimentCandidateProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    emotion = build_market_emotion_snapshot(
        FakeSentimentCandidateProvider(),
        FakeEmotionMarketOverviewProvider(),
        trade_date="2026-06-26",
        limit=20,
    )
    SentimentSnapshotStore(tmp_path).save(sentiment=sentiment, market_emotion=emotion)

    candidate_provider = FakeSentimentCandidateProvider()
    market_provider = FakeEmotionMarketOverviewProvider()
    app.state.candidate_provider = candidate_provider
    app.state.market_overview_provider = market_provider
    app.state.runs_dir = tmp_path
    try:
        response = TestClient(app).get("/api/short-term/sentiment/detail?trade_date=2026-06-26")
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "market_overview_provider")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sentiment"]["ladder"][0]["label"] == "3连板"
    assert payload["market_emotion"]["buckets"][0]["count"] == 1
    assert candidate_provider.calls == 0
    assert market_provider.overview_calls == 0


def test_default_provider_cache_key_is_stable_across_instances() -> None:
    first = FakeSentimentCandidateProvider()
    second = FakeSentimentCandidateProvider()

    assert _provider_cache_key(first) == _provider_cache_key(second)


def test_short_term_intraday_sentiment_adds_tickflow_actions_and_pool_tags() -> None:
    result = build_short_term_intraday_sentiment(
        FakeSentimentCandidateProvider(),
        FakeSentimentQuoteProvider(),
        trade_date="2026-06-26",
        limit=20,
    )

    assert result.trade_date == "2026-06-26"
    assert result.metrics.watched_count == 4
    assert result.metrics.alert_count >= 2
    assert result.items[0].symbol == "002004.SZ"
    assert "炸板池" in result.items[0].pool_tags
    assert result.items[0].action in {"low_buy_watch", "avoid_chase"}
    assert result.items[1].symbol == "603001.SH"
    assert "涨停池" in result.items[1].pool_tags
    assert "3连板" in result.items[1].pool_tags
    assert result.source_status[0].source == "TickFlow 实时行情"


def test_short_term_intraday_sentiment_api_uses_quote_provider() -> None:
    app.state.candidate_provider = FakeSentimentCandidateProvider()
    app.state.quote_provider = FakeSentimentQuoteProvider()
    try:
        response = TestClient(app).get(
            "/api/short-term/sentiment/intraday?trade_date=2026-06-26&limit=20"
        )
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "quote_provider")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["watched_count"] == 4
    assert payload["items"][0]["pool_tags"]


def test_short_term_intraday_signal_digest_builds_notification_draft() -> None:
    snapshot = build_short_term_intraday_sentiment(
        FakeSentimentCandidateProvider(),
        FakeSentimentQuoteProvider(),
        trade_date="2026-06-26",
        limit=20,
    )

    digest = build_short_term_intraday_signal_digest(snapshot)

    assert digest.title == "短线情绪提醒 · 2026-06-26"
    assert digest.alert_count == len(digest.alerts)
    assert digest.alert_count >= 2
    assert digest.alerts[0].severity in {"high", "medium"}
    assert digest.alerts[0].symbol
    assert digest.alerts[0].reasons
    assert "减仓确认" in digest.message_text or "低吸观察" in digest.message_text
    assert "仅供复盘与盯盘" in digest.message_text


def test_short_term_intraday_signal_digest_api_returns_alert_message() -> None:
    app.state.candidate_provider = FakeSentimentCandidateProvider()
    app.state.quote_provider = FakeSentimentQuoteProvider()
    try:
        response = TestClient(app).get(
            "/api/short-term/sentiment/intraday/digest?trade_date=2026-06-26&limit=20"
        )
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "quote_provider")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "短线情绪提醒 · 2026-06-26"
    assert payload["alert_count"] >= 2
    assert payload["message_text"]


def test_short_term_intraday_sentiment_degrades_when_minute_bars_rate_limited() -> None:
    result = build_short_term_intraday_sentiment(
        FakeSentimentCandidateProvider(),
        FailingIntradayBarsQuoteProvider(),
        trade_date="2026-06-26",
        limit=20,
    )

    assert result.metrics.watched_count == 4
    assert result.source_status[0].source == "TickFlow 实时行情"
    assert result.source_status[0].status == "success"
    assert result.source_status[1].source == "TickFlow 当日分钟线"
    assert result.source_status[1].status == "failed"
    assert "HTTP 429" in result.source_status[1].detail
    assert all(item.intraday_ma is None for item in result.items)


def test_short_term_intraday_sentiment_api_degrades_when_minute_bars_rate_limited() -> None:
    app.state.candidate_provider = FakeSentimentCandidateProvider()
    app.state.quote_provider = FailingIntradayBarsQuoteProvider()
    try:
        response = TestClient(app).get(
            "/api/short-term/sentiment/intraday?trade_date=2026-06-26&limit=20"
        )
    finally:
        delattr(app.state, "candidate_provider")
        delattr(app.state, "quote_provider")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["watched_count"] == 4
    assert payload["source_status"][1]["status"] == "failed"
    assert "HTTP 429" in payload["source_status"][1]["detail"]
