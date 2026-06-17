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
