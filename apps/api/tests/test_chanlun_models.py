from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import ChanlunAnalysisResponse, ChanlunBackfillRequest


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


def test_chanlun_analysis_response_serializes_contract_defaults() -> None:
    response = ChanlunAnalysisResponse(
        symbol="600000.SH",
        period="5m",
        availability="ready",
    )

    payload = response.model_dump(mode="json")

    assert payload["adjustment_mode"] == "raw_unadjusted"
    assert payload["rule_version"] == "cl-v1"


def test_chanlun_backfill_rejects_invalid_period() -> None:
    with pytest.raises(ValidationError):
        ChanlunAnalysisResponse(
            symbol="600000.SH",
            period="15m",
            availability="ready",
        )


def test_chanlun_backfill_request_history_days_is_optional_in_backend_and_typescript() -> None:
    request = ChanlunBackfillRequest()
    types_source = (Path(__file__).parents[2] / "web" / "lib" / "types.ts").read_text(
        encoding="utf-8"
    )

    assert request.history_days == 60
    assert "export type ChanlunBackfillRequest = {\n  history_days?: number;\n};" in types_source


def test_chanlun_settings_have_bounded_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.chanlun_history_days == 60
    assert settings.chanlun_minute_retention_days == 180
    assert settings.chanlun_cache_seconds == 30
    assert settings.chanlun_backfill_max_bars == 4800


@pytest.mark.parametrize(
    ("setting", "minimum", "maximum"),
    [
        ("chanlun_history_days", 5, 240),
        ("chanlun_minute_retention_days", 30, 730),
        ("chanlun_cache_seconds", 5, 600),
        ("chanlun_backfill_max_bars", 240, 24000),
    ],
)
def test_chanlun_settings_reject_values_outside_bounds(
    setting: str, minimum: int, maximum: int
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{setting: minimum - 1})

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{setting: maximum + 1})
