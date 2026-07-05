from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    AuctionModelPredictionItem,
    AuctionModelTop3Response,
    AuctionTop3ManualTradeSample,
    AuctionTop3SignalSample,
    AuctionTop3SimulatedPerformancePoint,
    AuctionTop3SimulatedTradeSample,
    KlineBar,
    ModelMaintenancePacket,
    StrongStockSourceStatus,
)
from app.services.runtime_settings import (
    AuctionTop3TrainingSettings,
    SettingsUpdate,
    load_runtime_settings,
    save_runtime_settings,
)


def test_auction_top3_training_models_and_packet_section_defaults() -> None:
    signal = AuctionTop3SignalSample(
        sample_id="sig-1",
        trade_date="2026-07-06",
        symbol="300001.SZ",
        name="模型一号",
        rank=1,
        score=0.91,
        model_version="fake-model",
        feature_version="fake-features",
        guard_rule="10:00收益<0则退出，否则持有到T+1收盘",
    )
    trade = AuctionTop3SimulatedTradeSample(
        sample_id="sim-1",
        signal_sample_id="sig-1",
        portfolio_id="default",
        trade_date="2026-07-06",
        symbol="300001.SZ",
        entry_policy="open_0930",
        exit_policy="next_open_exit",
        position_pct=0.33,
        entry_price=10.0,
        exit_price=10.5,
        return_pct=5.0,
        profit_amount=1650.0,
    )
    point = AuctionTop3SimulatedPerformancePoint(
        portfolio_id="default",
        trade_date="2026-07-06",
        entry_policy="open_0930",
        exit_policy="next_open_exit",
        trade_count=1,
        win_count=1,
        loss_count=0,
        daily_return_pct=1.65,
        cumulative_return_pct=1.65,
        equity=101650.0,
        max_drawdown_pct=0,
    )
    manual = AuctionTop3ManualTradeSample(
        sample_id="manual-1",
        signal_sample_id="sig-1",
        trade_date="2026-07-06",
        symbol="300001.SZ",
        bought=True,
        enabled_for_training=False,
    )
    packet = ModelMaintenancePacket(
        packet_id="packet-1",
        model_sections={
            "auction_top3_training": {
                "enabled": True,
                "signal_sample_count": 1,
                "simulated_trade_sample_count": 1,
                "manual_trade_sample_count": 1,
                "simulated_profit_summary": {"latest_equity": 101650.0},
            }
        },
        packet_url="http://localhost:3110/model-maintenance/packets/packet-1",
    )

    assert signal.symbol == "300001.SZ"
    assert trade.label == "win"
    assert point.equity == 101650.0
    assert manual.enabled_for_training is False
    assert packet.model_sections["auction_top3_training"]["signal_sample_count"] == 1
    assert packet.packet_url.endswith("/model-maintenance/packets/packet-1")


def test_runtime_settings_persist_auction_top3_training_options(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    save_runtime_settings(
        path,
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_base_url="https://api.tickflow.test",
            provider_timeout_seconds=3,
            auction_top3_training=AuctionTop3TrainingSettings(
                record_signal_samples=True,
                generate_simulated_trade_samples=True,
                include_manual_trade_samples_in_training=True,
                training_window_days=45,
                simulated_initial_capital=200000,
                simulated_position_pct=0.25,
            ),
        ),
    )

    loaded = load_runtime_settings(path)

    assert loaded.auction_top3_training.record_signal_samples is True
    assert loaded.auction_top3_training.generate_simulated_trade_samples is True
    assert loaded.auction_top3_training.include_manual_trade_samples_in_training is True
    assert loaded.auction_top3_training.training_window_days == 45
    assert loaded.auction_top3_training.simulated_initial_capital == 200000
    assert loaded.auction_top3_training.simulated_position_pct == 0.25


def test_training_store_upserts_signal_samples_by_trade_date_symbol_rank(tmp_path: Path) -> None:
    from app.services.auction_top3_training import AuctionTop3TrainingStore, build_signal_samples_from_top3

    store = AuctionTop3TrainingStore(tmp_path)
    response = _top3_response()

    first = store.upsert_signal_samples(build_signal_samples_from_top3(response))
    second = store.upsert_signal_samples(build_signal_samples_from_top3(response))
    loaded = store.load_signal_samples("2026-07-06")

    assert len(first) == 2
    assert len(second) == 2
    assert len(loaded) == 2
    assert loaded[0].sample_id == "sig-20260706-300001SZ-1"
    assert loaded[0].feature_snapshot["prob_3pct"] == 0.91
    assert loaded[0].source_status[0].source == "fake-source"


def test_generate_simulated_trade_samples_and_performance_dedupes(tmp_path: Path) -> None:
    from app.services.auction_top3_training import (
        AuctionTop3TrainingStore,
        build_signal_samples_from_top3,
        generate_simulated_trade_samples,
        summarize_simulated_performance,
    )

    store = AuctionTop3TrainingStore(tmp_path)
    signals = store.upsert_signal_samples(build_signal_samples_from_top3(_top3_response()))
    bars_by_symbol = {
        "300001.SZ": [
            KlineBar(date="2026-07-06", open=10, high=10.8, low=9.8, close=10.5, volume=100),
            KlineBar(date="2026-07-07", open=10.7, high=11, low=10.4, close=10.8, volume=120),
        ],
        "300002.SZ": [
            KlineBar(date="2026-07-06", open=20, high=20.2, low=19.2, close=19.4, volume=100),
            KlineBar(date="2026-07-07", open=19.0, high=19.4, low=18.8, close=19.1, volume=90),
        ],
    }

    trades = generate_simulated_trade_samples(
        signals,
        bars_by_symbol,
        initial_capital=100000,
        position_pct=0.5,
        entry_policy="open_0930",
        exit_policy="next_open_exit",
    )
    store.upsert_simulated_trades(trades)
    store.upsert_simulated_trades(trades)
    performance = summarize_simulated_performance(
        store.load_simulated_trades(),
        initial_capital=100000,
        portfolio_id="default",
    )
    store.save_performance_points(performance.points)

    assert len(store.load_simulated_trades()) == 2
    assert performance.summary["complete_sample_count"] == 2
    assert performance.summary["latest_equity"] == 101000.0
    assert performance.summary["cumulative_return_pct"] == 1.0
    assert performance.summary["win_rate"] == 0.5
    assert performance.points[0].trade_date == "2026-07-06"


def test_manual_trade_samples_count_only_when_enabled_for_training(tmp_path: Path) -> None:
    from app.services.auction_top3_training import AuctionTop3TrainingStore

    store = AuctionTop3TrainingStore(tmp_path)
    store.upsert_manual_trade(
        AuctionTop3ManualTradeSample(
            sample_id="manual-1",
            signal_sample_id="sig-1",
            trade_date="2026-07-06",
            symbol="300001.SZ",
            bought=True,
            enabled_for_training=False,
        )
    )
    store.upsert_manual_trade(
        AuctionTop3ManualTradeSample(
            sample_id="manual-2",
            signal_sample_id="sig-2",
            trade_date="2026-07-06",
            symbol="300002.SZ",
            bought=True,
            enabled_for_training=True,
        )
    )

    summary = store.training_summary(training_window_days=60, include_manual_training=True)

    assert summary.manual_trade_sample_count == 1


def _top3_response() -> AuctionModelTop3Response:
    return AuctionModelTop3Response(
        trade_date="2026-07-06",
        feature_end_date="2026-07-03",
        model_version="fake-model",
        feature_version="fake-features",
        guard_rule="fake-guard",
        items=[
            AuctionModelPredictionItem(
                symbol="300001.SZ",
                name="模型一号",
                rank=1,
                prob_3pct=0.91,
                bucket="selected",
                guard_rule="fake-guard",
                trend_reasons=["强趋势"],
            ),
            AuctionModelPredictionItem(
                symbol="300002.SZ",
                name="模型二号",
                rank=2,
                prob_3pct=0.82,
                bucket="selected",
                guard_rule="fake-guard",
                risk_flags=["高开过热"],
            ),
        ],
        source_status=[StrongStockSourceStatus(source="fake-source", status="success", detail="ok")],
    )


def test_training_performance_api_returns_summary(tmp_path: Path) -> None:
    from app.services.auction_top3_training import (
        AuctionTop3TrainingStore,
        build_signal_samples_from_top3,
        generate_simulated_trade_samples,
    )

    app.state.runs_dir = tmp_path
    store = AuctionTop3TrainingStore(tmp_path)
    signals = store.upsert_signal_samples(build_signal_samples_from_top3(_top3_response()))
    trades = generate_simulated_trade_samples(
        signals[:1],
        {
            "300001.SZ": [
                KlineBar(date="2026-07-06", open=10, high=11, low=9.8, close=10.4, volume=1),
                KlineBar(date="2026-07-07", open=10.5, high=10.8, low=10.2, close=10.6, volume=1),
            ]
        },
        initial_capital=100000,
        position_pct=0.33,
    )
    store.upsert_simulated_trades(trades)
    client = TestClient(app)
    try:
        response = client.get("/api/model-maintenance/auction-top3/training/performance")
    finally:
        delattr(app.state, "runs_dir")

    assert response.status_code == 200
    assert response.json()["summary"]["complete_sample_count"] == 1
