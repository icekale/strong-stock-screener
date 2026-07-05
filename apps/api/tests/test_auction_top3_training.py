from pathlib import Path

from app.models import (
    AuctionTop3ManualTradeSample,
    AuctionTop3SignalSample,
    AuctionTop3SimulatedPerformancePoint,
    AuctionTop3SimulatedTradeSample,
    ModelMaintenancePacket,
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
