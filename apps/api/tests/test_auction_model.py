from pathlib import Path
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app, shutdown_auction_sampler, startup_auction_sampler
from app.models import (
    AuctionModelBacktestSummary,
    AuctionModelPredictionItem,
    AuctionModelTop3Response,
    AuctionSnapshotItem,
    AuctionSnapshotResponse,
)
from app.services.auction_model import (
    GUARD_RULE,
    AuctionModelResultStore,
    prediction_items_from_scored_rows,
)
from app.services.auction_snapshot_store import AuctionSnapshotStore
from app.services.auction_top3_live_confirmation import AuctionTop3LiveConfirmationStore


def test_prediction_items_marks_top3_selected_with_guard_rule() -> None:
    items = prediction_items_from_scored_rows(
        [
            {
                "symbol": "300001.SZ",
                "name": "模型一号",
                "prob_3pct": 0.91,
                "prev_close_price": 11,
                "feature_end_date": "2026-07-03",
                "data_quality": ["no_auction_snapshot", "uses_previous_daily_bar"],
            },
            {
                "symbol": "300002.SZ",
                "name": "模型二号",
                "prob_3pct": 0.82,
                "prev_close_price": 9,
                "feature_end_date": "2026-07-03",
                "data_quality": ["no_auction_snapshot", "uses_previous_daily_bar"],
            },
            {
                "symbol": "300003.SZ",
                "name": "模型三号",
                "prob_3pct": 0.73,
                "prev_close_price": 8,
                "feature_end_date": "2026-07-03",
                "data_quality": ["no_auction_snapshot", "uses_previous_daily_bar"],
            },
            {
                "symbol": "300004.SZ",
                "name": "模型四号",
                "prob_3pct": 0.95,
                "risk_flags": ["ST股票"],
                "feature_end_date": "2026-07-03",
            },
        ],
        top_n=3,
        max_items=4,
    )

    assert [item.symbol for item in items[:3]] == ["300004.SZ", "300001.SZ", "300002.SZ"]
    assert items[0].bucket == "avoid"
    assert items[0].guard_rule is None
    assert items[1].bucket == "selected"
    assert items[1].guard_rule == GUARD_RULE
    assert items[1].data_quality == ["no_auction_snapshot", "uses_previous_daily_bar"]
    assert items[3].bucket == "selected"


def test_prediction_items_downgrades_low_liquidity_candidates() -> None:
    items = prediction_items_from_scored_rows(
        [
            {
                "symbol": "300010.SZ",
                "name": "低市值高分",
                "prob_3pct": 0.96,
                "market_cap_float": 1_500_000_000,
                "avg_amount_3d": 180_000_000,
                "feature_end_date": "2026-07-03",
            },
            {
                "symbol": "300011.SZ",
                "name": "低成交高分",
                "prob_3pct": 0.95,
                "market_cap_float": 8_000_000_000,
                "avg_amount_3d": 80_000_000,
                "feature_end_date": "2026-07-03",
            },
            {
                "symbol": "300012.SZ",
                "name": "合格一号",
                "prob_3pct": 0.90,
                "market_cap_float": 3_000_000_000,
                "avg_amount_3d": 120_000_000,
                "feature_end_date": "2026-07-03",
            },
            {
                "symbol": "300013.SZ",
                "name": "合格二号",
                "prob_3pct": 0.80,
                "market_cap_float": 5_000_000_000,
                "avg_amount_3d": 150_000_000,
                "feature_end_date": "2026-07-03",
            },
            {
                "symbol": "300014.SZ",
                "name": "合格三号",
                "prob_3pct": 0.70,
                "market_cap_float": 6_000_000_000,
                "avg_amount_3d": 160_000_000,
                "feature_end_date": "2026-07-03",
            },
        ],
        top_n=3,
        max_items=5,
    )

    assert items[0].bucket == "avoid"
    assert items[0].market_cap_float == 1_500_000_000
    assert items[0].avg_amount_3d == 180_000_000
    assert "流通市值低于20亿" in items[0].risk_flags
    assert items[1].bucket == "avoid"
    assert "近3日日均成交额低于1亿" in items[1].risk_flags
    assert [item.symbol for item in items if item.bucket == "selected"] == [
        "300012.SZ",
        "300013.SZ",
        "300014.SZ",
    ]


def test_auction_model_api_uses_injected_service(tmp_path: Path) -> None:
    app.state.auction_model_service = FakeAuctionModelService()
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3?trade_date=2026-07-06")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-07-06"
    assert payload["feature_end_date"] == "2026-07-03"
    assert payload["items"][0]["symbol"] == "300001.SZ"
    assert payload["backtest"]["win_rate"] == 0.531073
    assert payload["cache_status"] == "generated"


def test_auction_model_api_uses_cached_result_until_refresh(tmp_path: Path) -> None:
    service = CountingFakeAuctionModelService()
    app.state.auction_model_service = service
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    client = TestClient(app)
    try:
        first = client.get("/api/auction/model/top3?trade_date=2026-07-06")
        second = client.get("/api/auction/model/top3?trade_date=2026-07-06")
        refreshed = client.get("/api/auction/model/top3?trade_date=2026-07-06&refresh=true")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")

    assert first.status_code == 200
    assert second.status_code == 200
    assert refreshed.status_code == 200
    assert first.json()["run_id"] == "fake-run-1"
    assert first.json()["cache_status"] == "generated"
    assert second.json()["run_id"] == "fake-run-1"
    assert second.json()["cache_status"] == "cached"
    assert refreshed.json()["run_id"] == "fake-run-2"
    assert refreshed.json()["cache_status"] == "generated"
    assert service.call_count == 2


def test_auction_model_api_cache_only_does_not_generate_when_missing(tmp_path: Path) -> None:
    service = CountingFakeAuctionModelService()
    app.state.auction_model_service = service
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3?trade_date=2026-07-06&cache_only=true")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")

    assert response.status_code == 404
    assert response.json()["detail"] == "暂无缓存的竞价模型Top3结果"
    assert service.call_count == 0


def test_auction_model_live_confirmation_uses_cached_top3_without_generating(tmp_path: Path) -> None:
    service = CountingFakeAuctionModelService()
    result_store = AuctionModelResultStore(tmp_path)
    result_store.save_top3(
        FakeAuctionModelService().predict_top3("2026-07-06").model_copy(update={"run_id": "fake-run"})
    )
    snapshot_store = AuctionSnapshotStore(data_dir=tmp_path)
    snapshot_store.save(
        AuctionSnapshotResponse(
            trade_date="2026-07-06",
            items=[
                AuctionSnapshotItem(
                    symbol="300001.SZ",
                    name="模型一号",
                    open_gap_pct=4.2,
                    current_pct_change=5.1,
                    turnover_cny=180_000_000,
                    turnover_rate=4.5,
                    quote_time="2026-07-06T09:25:00+08:00",
                )
            ],
        )
    )
    app.state.auction_model_service = service
    app.state.auction_model_result_store = result_store
    app.state.auction_snapshot_store = snapshot_store
    app.state.auction_top3_live_confirmation_store = AuctionTop3LiveConfirmationStore(tmp_path)
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3/live-confirmation?trade_date=2026-07-06")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")
        delattr(app.state, "auction_snapshot_store")
        delattr(app.state, "auction_top3_live_confirmation_store")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-07-06"
    assert payload["model_run_id"] == "fake-run"
    assert payload["cache_status"] == "cached"
    assert payload["items"][0]["symbol"] == "300001.SZ"
    assert payload["items"][0]["confirmation"] == "buyable"
    assert payload["items"][0]["realtime"]["current_pct_change"] == 5.1
    assert service.call_count == 0


def test_auction_model_live_confirmation_returns_404_without_top3_cache(tmp_path: Path) -> None:
    service = CountingFakeAuctionModelService()
    app.state.auction_model_service = service
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    app.state.auction_top3_live_confirmation_store = AuctionTop3LiveConfirmationStore(tmp_path)
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3/live-confirmation?trade_date=2026-07-06")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")
        delattr(app.state, "auction_top3_live_confirmation_store")

    assert response.status_code == 404
    assert response.json()["detail"] == "暂无缓存的竞价模型Top3结果"
    assert service.call_count == 0


def test_auction_model_api_records_top3_signal_samples(tmp_path: Path) -> None:
    app.state.auction_model_service = FakeAuctionModelService()
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    app.state.runs_dir = tmp_path
    client = TestClient(app)
    try:
        response = client.get("/api/auction/model/top3?trade_date=2026-07-06&refresh=true")
        summary = client.get("/api/model-maintenance/auction-top3/training/summary")
    finally:
        delattr(app.state, "auction_model_service")
        delattr(app.state, "auction_model_result_store")
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["signal_sample_count"] == 1
    assert payload["date_range"] == ["2026-07-06", "2026-07-06"]


def test_startup_auction_sampler_auto_generates_top3_after_lock_time(tmp_path: Path) -> None:
    service = CountingFakeAuctionModelService()
    previous_disabled_exists = hasattr(app.state, "auction_sampler_disabled")
    previous_disabled = getattr(app.state, "auction_sampler_disabled", None)
    previous_sampler = getattr(app.state, "auction_sampler", None)
    previous_service_exists = hasattr(app.state, "auction_model_service")
    previous_service = getattr(app.state, "auction_model_service", None)
    previous_result_store_exists = hasattr(app.state, "auction_model_result_store")
    previous_result_store = getattr(app.state, "auction_model_result_store", None)
    app.state.auction_sampler_disabled = False
    app.state.auction_model_service = service
    app.state.auction_model_result_store = AuctionModelResultStore(tmp_path)
    app.state.auction_sampler_clock = lambda: datetime(2026, 7, 6, 9, 26, 0)
    if previous_sampler is not None:
        previous_sampler.stop()
    if hasattr(app.state, "auction_sampler"):
        delattr(app.state, "auction_sampler")

    try:
        startup_auction_sampler()
        sampler = app.state.auction_sampler
        sampler.stop()
        sampler.sample_once()
        result = app.state.auction_model_result_store.load_top3("2026-07-06")
    finally:
        shutdown_auction_sampler()
        for attr in (
            "auction_model_service",
            "auction_model_result_store",
            "auction_sampler_clock",
            "auction_sampler",
        ):
            if hasattr(app.state, attr):
                delattr(app.state, attr)
        if previous_sampler is not None:
            app.state.auction_sampler = previous_sampler
        if previous_service_exists:
            app.state.auction_model_service = previous_service
        if previous_result_store_exists:
            app.state.auction_model_result_store = previous_result_store
        if previous_disabled_exists:
            app.state.auction_sampler_disabled = previous_disabled
        elif hasattr(app.state, "auction_sampler_disabled"):
            delattr(app.state, "auction_sampler_disabled")

    assert result is not None
    assert result.trade_date == "2026-07-06"
    assert service.call_count == 1


class FakeAuctionModelService:
    def predict_top3(self, trade_date: str) -> AuctionModelTop3Response:
        return AuctionModelTop3Response(
            trade_date=trade_date,
            feature_end_date="2026-07-03",
            model_version="fake-model",
            feature_version="fake-features",
            guard_rule=GUARD_RULE,
            mode="research_live_signal",
            backtest=AuctionModelBacktestSummary(
                period=["2026-01-01", "2026-07-03"],
                sample_count=354,
                win_rate=0.531073,
                avg_win=0.072604,
                avg_loss=0.050045,
                payoff_ratio=1.450764,
                profit_factor=1.683603,
                expectancy=0.015656,
                average_return=0.015656,
                breakeven_win_rate=0.408036,
                capital_return_pct=30.6823,
            ),
            items=[
                AuctionModelPredictionItem(
                    symbol="300001.SZ",
                    name="模型一号",
                    rank=1,
                    prob_3pct=0.91,
                    bucket="selected",
                    guard_rule=GUARD_RULE,
                    feature_end_date="2026-07-03",
                )
            ],
        )


class CountingFakeAuctionModelService:
    def __init__(self) -> None:
        self.call_count = 0

    def predict_top3(self, trade_date: str) -> AuctionModelTop3Response:
        self.call_count += 1
        result = FakeAuctionModelService().predict_top3(trade_date)
        return result.model_copy(update={"run_id": f"fake-run-{self.call_count}"})
