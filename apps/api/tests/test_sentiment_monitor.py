from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    MarketEmotionMetrics,
    MarketEmotionSample,
    MarketEmotionSnapshotResponse,
    ShortTermSentimentResponse,
)
from app.services.notification_channels import NotificationChannelConfig
from app.services.runtime_settings import SettingsUpdate, load_runtime_settings, save_runtime_settings
from app.services.sentiment_monitor import (
    SentimentMonitor,
    SentimentMonitorConfig,
    detect_sentiment_mutations,
    is_trading_session,
)


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


class FakeHttpClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        return FakeResponse()


def test_sentiment_monitor_config_defaults_to_three_minutes() -> None:
    config = SentimentMonitorConfig()

    assert config.interval_minutes == 3
    assert config.cooldown_minutes == 15
    assert config.enabled is False


def test_trading_session_detection_uses_morning_and_afternoon_windows() -> None:
    tz = ZoneInfo("Asia/Shanghai")

    assert is_trading_session(datetime(2026, 6, 29, 9, 25, tzinfo=tz))
    assert is_trading_session(datetime(2026, 6, 29, 11, 30, tzinfo=tz))
    assert not is_trading_session(datetime(2026, 6, 29, 11, 31, tzinfo=tz))
    assert is_trading_session(datetime(2026, 6, 29, 13, 0, tzinfo=tz))
    assert is_trading_session(datetime(2026, 6, 29, 15, 5, tzinfo=tz))
    assert not is_trading_session(datetime(2026, 6, 29, 15, 6, tzinfo=tz))


def test_detect_sentiment_mutations_flags_score_break_and_seal_rate_changes() -> None:
    config = SentimentMonitorConfig()
    previous = _sample("09:35", score=42, break_board=4, limit_down=1, seal_rate=82)
    current = _sample("09:38", score=25, break_board=13, limit_down=7, seal_rate=60)

    alerts = detect_sentiment_mutations([previous, current], config)

    alert_types = {alert.type for alert in alerts}
    assert "emotion_score_drop" in alert_types
    assert "break_board_jump" in alert_types
    assert "limit_down_jump" in alert_types
    assert "seal_rate_drop" in alert_types
    assert any(alert.severity == "high" for alert in alerts)


def test_sentiment_monitor_run_once_sends_alert_once_during_cooldown() -> None:
    notifications: list[dict[str, str]] = []
    snapshots = [
        _snapshot(score=42, break_board=4, limit_down=1, seal_rate=82),
        _snapshot(score=25, break_board=13, limit_down=7, seal_rate=60),
        _snapshot(score=30, break_board=22, limit_down=12, seal_rate=45),
    ]

    def build_snapshot(trade_date: str, limit: int):
        snapshot = snapshots.pop(0)
        return ShortTermSentimentResponse(trade_date=trade_date), snapshot

    monitor = SentimentMonitor(
        snapshot_builder=build_snapshot,
        config_loader=lambda: SentimentMonitorConfig(cooldown_minutes=15),
        notifier=lambda title, message: notifications.append({"title": title, "message": message}),
        now_fn=lambda: datetime(2026, 6, 29, 9, 40, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    first = monitor.run_once("2026-06-29")
    second = monitor.run_once("2026-06-29")
    third = monitor.run_once("2026-06-29")

    assert first.last_alerts == []
    assert second.last_alerts
    assert third.last_alerts
    assert len(notifications) == 1
    assert notifications[0]["title"] == "短线情绪突变提醒 · 2026-06-29"


def test_runtime_settings_persists_sentiment_monitor_config(tmp_path: Path) -> None:
    path = tmp_path / "runtime_config.json"

    save_runtime_settings(
        path,
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_base_url="https://api.tickflow.org",
            ifind_base_url="https://api-mcp.51ifind.com:8643",
            ifind_service_id="hexin-ifind-ds-stock-mcp",
            provider_timeout_seconds=12,
            sentiment_monitor=SentimentMonitorConfig(enabled=True, interval_minutes=1),
        ),
    )

    loaded = load_runtime_settings(path)

    assert loaded.sentiment_monitor.enabled is True
    assert loaded.sentiment_monitor.interval_minutes == 1


def test_sentiment_monitor_api_run_once_and_status_use_runtime_config(tmp_path: Path) -> None:
    path = tmp_path / "runtime_config.json"
    save_runtime_settings(
        path,
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_base_url="https://api.tickflow.org",
            ifind_base_url="https://api-mcp.51ifind.com:8643",
            ifind_service_id="hexin-ifind-ds-stock-mcp",
            provider_timeout_seconds=12,
            sentiment_monitor=SentimentMonitorConfig(interval_minutes=1),
        ),
    )

    calls: list[dict[str, object]] = []

    def build_snapshot(trade_date: str, limit: int):
        calls.append({"trade_date": trade_date, "limit": limit})
        return ShortTermSentimentResponse(trade_date=trade_date), _snapshot(
            score=50,
            break_board=2,
            limit_down=0,
            seal_rate=90,
        )

    app.state.runtime_config_path = path
    app.state.sentiment_monitor_snapshot_builder = build_snapshot
    try:
        client = TestClient(app)
        run_response = client.post("/api/short-term/sentiment/monitor/run-once?trade_date=2026-06-29")
        status_response = client.get("/api/short-term/sentiment/monitor/status")
    finally:
        delattr(app.state, "runtime_config_path")
        delattr(app.state, "sentiment_monitor_snapshot_builder")
        if hasattr(app.state, "sentiment_monitor"):
            delattr(app.state, "sentiment_monitor")

    assert run_response.status_code == 200
    assert status_response.status_code == 200
    assert run_response.json()["last_trade_date"] == "2026-06-29"
    assert status_response.json()["config"]["interval_minutes"] == 1
    assert calls == [{"trade_date": "2026-06-29", "limit": 80}]


def test_sentiment_monitor_starts_with_app_when_runtime_config_enabled(tmp_path: Path) -> None:
    path = tmp_path / "runtime_config.json"
    save_runtime_settings(
        path,
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_base_url="https://api.tickflow.org",
            ifind_base_url="https://api-mcp.51ifind.com:8643",
            ifind_service_id="hexin-ifind-ds-stock-mcp",
            provider_timeout_seconds=12,
            sentiment_monitor=SentimentMonitorConfig(enabled=True, interval_minutes=3),
        ),
    )

    def build_snapshot(trade_date: str, limit: int):
        return ShortTermSentimentResponse(trade_date=trade_date), _snapshot(
            score=50,
            break_board=2,
            limit_down=0,
            seal_rate=90,
        )

    app.state.runtime_config_path = path
    app.state.sentiment_monitor_snapshot_builder = build_snapshot
    try:
        with TestClient(app) as client:
            response = client.get("/api/short-term/sentiment/monitor/status")
            assert response.status_code == 200
            assert response.json()["running"] is True
    finally:
        if hasattr(app.state, "sentiment_monitor"):
            app.state.sentiment_monitor.stop()
            delattr(app.state, "sentiment_monitor")
        delattr(app.state, "runtime_config_path")
        delattr(app.state, "sentiment_monitor_snapshot_builder")


def test_telegram_notification_posts_bot_api_payload() -> None:
    from app.services.notification_channels import NotificationSettings, send_notification_message

    http_client = FakeHttpClient()
    result = send_notification_message(
        NotificationSettings(
            channels=[
                NotificationChannelConfig(
                    id="telegram",
                    type="telegram",
                    name="Telegram",
                    enabled=True,
                    bot_token="bot-secret",
                    chat_id="chat-123",
                )
            ]
        ),
        title="短线情绪突变提醒",
        message_text="炸板快速增加",
        channel_ids=["telegram"],
        http_client=http_client,
    )

    assert result.results[0].status == "success"
    assert http_client.posts[0]["url"] == "https://api.telegram.org/botbot-secret/sendMessage"
    assert http_client.posts[0]["json"] == {
        "chat_id": "chat-123",
        "text": "短线情绪突变提醒\n\n炸板快速增加",
    }


def _sample(
    minute: str,
    *,
    score: float,
    break_board: int,
    limit_down: int,
    seal_rate: float,
    limit_up: int = 20,
    losing_effect: float = 30,
) -> MarketEmotionSample:
    return MarketEmotionSample(
        trade_date="2026-06-29",
        sampled_at=f"2026-06-29T{minute}:00+08:00",
        emotion_score=score,
        emotion_level="一般",
        limit_up_count=limit_up,
        break_board_count=break_board,
        limit_down_count=limit_down,
        losing_effect_score=losing_effect,
        max_consecutive_boards=3,
        seal_rate_pct=seal_rate,
    )


def _snapshot(
    *,
    score: float,
    break_board: int,
    limit_down: int,
    seal_rate: float,
) -> MarketEmotionSnapshotResponse:
    sample = _sample(
        "09:35",
        score=score,
        break_board=break_board,
        limit_down=limit_down,
        seal_rate=seal_rate,
    )
    return MarketEmotionSnapshotResponse(
        trade_date="2026-06-29",
        metrics=MarketEmotionMetrics(
            emotion_score=score,
            emotion_level="一般",
            limit_up_count=sample.limit_up_count,
            break_board_count=break_board,
            limit_down_count=limit_down,
            losing_effect_score=sample.losing_effect_score,
            max_consecutive_boards=3,
            seal_rate_pct=seal_rate,
        ),
        samples=[sample],
        generated_at=sample.sampled_at,
    )
