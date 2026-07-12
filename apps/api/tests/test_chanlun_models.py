from app.config import Settings
from app.models import ChanlunAnalysisResponse


def test_chanlun_analysis_response_has_project_owned_layers() -> None:
    response = ChanlunAnalysisResponse(
        symbol="600000.SH",
        period="5m",
        availability="ready",
        source_status=[],
    )

    assert response.rule_version == "cl-v1"
    assert response.strokes == []
    assert response.zones == []
    assert not hasattr(response, "order")


def test_chanlun_settings_have_bounded_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.chanlun_history_days == 60
    assert settings.chanlun_minute_retention_days == 180
    assert settings.chanlun_cache_seconds == 30
    assert settings.chanlun_backfill_max_bars == 4800
