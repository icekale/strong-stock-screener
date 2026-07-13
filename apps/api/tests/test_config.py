import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_accepts_direct_tickflow_api_key(monkeypatch) -> None:
    monkeypatch.delenv("STRONG_STOCK_TICKFLOW_API_KEY", raising=False)
    monkeypatch.setenv("TICKFLOW_API_KEY", "tk-direct")

    settings = Settings(_env_file=None)

    assert settings.tickflow_api_key == "tk-direct"


def test_settings_prefers_prefixed_tickflow_api_key(monkeypatch) -> None:
    monkeypatch.setenv("STRONG_STOCK_TICKFLOW_API_KEY", "tk-prefixed")
    monkeypatch.setenv("TICKFLOW_API_KEY", "tk-direct")

    settings = Settings(_env_file=None)

    assert settings.tickflow_api_key == "tk-prefixed"


def test_settings_defaults_daily_kline_to_tickflow() -> None:
    settings = Settings(_env_file=None)

    assert settings.kline_provider == "tickflow"


def test_settings_defaults_candidate_provider_to_recent_limit_up_pool() -> None:
    settings = Settings(_env_file=None)

    assert settings.candidate_provider == "recent_limit_up"


def test_settings_defaults_ifind_api_key_to_empty() -> None:
    settings = Settings(_env_file=None)

    assert settings.ifind_api_key == ""


def test_settings_defaults_ifind_base_url_to_mcp_endpoint() -> None:
    settings = Settings(_env_file=None)

    assert settings.ifind_base_url == "https://api-mcp.51ifind.com:8643"


def test_settings_accepts_direct_ifind_api_key(monkeypatch) -> None:
    monkeypatch.delenv("STRONG_STOCK_IFIND_API_KEY", raising=False)
    monkeypatch.setenv("IFIND_API_KEY", "ifind-direct")

    settings = Settings(_env_file=None)

    assert settings.ifind_api_key == "ifind-direct"


def test_settings_prefers_prefixed_ifind_api_key(monkeypatch) -> None:
    monkeypatch.setenv("STRONG_STOCK_IFIND_API_KEY", "ifind-prefixed")
    monkeypatch.setenv("IFIND_API_KEY", "ifind-direct")

    settings = Settings(_env_file=None)

    assert settings.ifind_api_key == "ifind-prefixed"


def test_settings_defaults_storage_retention_limits() -> None:
    settings = Settings(_env_file=None)

    assert settings.screen_run_retention_count == 120
    assert settings.gsgf_review_retention_records == 5000
    assert settings.sentiment_snapshot_retention_days == 30
    assert settings.market_emotion_history_retention_days == 30
    assert settings.market_emotion_samples_per_day == 360
    assert settings.auction_review_retention_days == 120


def test_settings_accepts_chanlun_tdx_enabled(monkeypatch) -> None:
    monkeypatch.setenv("STRONG_STOCK_CHANLUN_TDX_ENABLED", "false")

    settings = Settings(_env_file=None)

    assert settings.chanlun_tdx_enabled is False


def test_settings_rejects_chanlun_tdx_timeout_outside_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chanlun_tdx_timeout_seconds=0.5)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, chanlun_tdx_timeout_seconds=16)
