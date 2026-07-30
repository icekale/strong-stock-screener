from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import ChanlunAnalysisResponse, ChanlunBackfillRequest, ChanlunSignal, ChanlunWorkspaceResponse


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


def test_coverage_contract_has_unknown_safe_default() -> None:
    response = ChanlunAnalysisResponse(symbol="600000.SH", period="5m", availability="unavailable")

    assert response.coverage.status == "unverified"
    assert response.coverage.backfill_required is True


def test_chanlun_analysis_response_serializes_empty_confirmed_event_layers() -> None:
    response = ChanlunAnalysisResponse(
        symbol="600000.SH",
        period="5m",
        availability="ready",
    )

    payload = response.model_dump(mode="json")

    assert payload["divergences"] == []
    assert payload["signals"] == []


def test_chanlun_workspace_serializes_empty_multiperiod_confluence_layer() -> None:
    response = ChanlunWorkspaceResponse(
        symbol="600000.SH",
        analysis=ChanlunAnalysisResponse(
            symbol="600000.SH",
            period="1d",
            availability="ready",
        ),
    )

    assert response.model_dump(mode="json")["confluence_signals"] == []


@pytest.mark.parametrize("signal_type", ["two_buy", "two_sell", "three_buy", "three_sell"])
def test_chanlun_signal_contract_supports_confirmed_second_and_third_points(
    signal_type: str,
) -> None:
    signal = ChanlunSignal(
        id=f"signal:{signal_type}",
        type=signal_type,
        occurred_at="2026-07-10T10:00:00+08:00",
        price=10.0,
        divergence_id=None,
        stroke_id="stroke:test",
        status="confirmed",
    )

    assert signal.type == signal_type
    assert signal.divergence_id is None


def test_chanlun_backfill_rejects_invalid_period() -> None:
    with pytest.raises(ValidationError):
        ChanlunAnalysisResponse(
            symbol="600000.SH",
            period="15m",
            availability="ready",
        )


def test_chanlun_backfill_contract_defaults_to_all_minute_periods_and_220_bars() -> None:
    request = ChanlunBackfillRequest()
    types_source = (Path(__file__).parents[2] / "web-vue" / "src" / "service" / "types.ts").read_text(
        encoding="utf-8"
    )

    assert request.periods == ["5m", "30m", "60m"]
    assert request.lookback == 220
    assert request.history_days is None
    assert "  periods?: (\"5m\" | \"30m\" | \"60m\")[];" in types_source
    assert "  lookback?: number;" in types_source
    assert "  history_days?: number;" in types_source


def test_chanlun_backfill_request_rejects_duplicate_periods() -> None:
    with pytest.raises(ValidationError):
        ChanlunBackfillRequest(periods=["5m", "5m"])


def test_chanlun_settings_have_bounded_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.chanlun_history_days == 60
    assert settings.chanlun_minute_retention_days == 180
    assert settings.chanlun_cache_seconds == 30
    assert settings.chanlun_backfill_max_bars == 16000


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
