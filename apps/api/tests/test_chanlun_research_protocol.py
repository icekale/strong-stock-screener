import copy

import pytest
from pydantic import ValidationError

from app.models import KlineBar
from app.services.chanlun.research_protocol import (
    CZSC_CATALOG_VERSION,
    CZSC_RC8_PROTOCOL_VERSION,
    CzscRc8Request,
    CzscRc8Response,
    build_research_request,
)


PERIODS = ("1d", "60m", "30m", "5m")


def _bar(date: str, *, close: float = 10.1) -> KlineBar:
    return KlineBar(
        date=date,
        open=10.0,
        close=close,
        high=max(10.3, close + 0.1),
        low=9.8,
        volume=1_000,
        amount=10_000,
    )


def _period_bars(*, close: float = 10.1) -> dict[str, list[KlineBar]]:
    return {
        "1d": [_bar("2026-07-09"), _bar("2026-07-10")],
        "60m": [
            _bar("2026-07-10T10:30:00+08:00"),
            _bar("2026-07-10T11:30:00+08:00"),
        ],
        "30m": [
            _bar("2026-07-10T10:30:00+08:00"),
            _bar("2026-07-10T11:00:00+08:00"),
        ],
        "5m": [
            _bar("2026-07-10T10:55:00+08:00"),
            _bar("2026-07-10T11:00:00+08:00", close=close),
        ],
    }


def _request_payload() -> dict[str, object]:
    return build_research_request(
        "600000.SH",
        _period_bars(),
        request_id="request-1",
        adjustment_mode="qfq",
        decision_at="2026-07-10T15:00:00+08:00",
    ).model_dump(mode="json")


def _raw_state() -> dict[str, object]:
    return {
        "catalog_id": "buy3.structure",
        "period": "5m",
        "higher_period": None,
        "lower_period": None,
        "occurred_at": "2026-07-10T11:00:00+08:00",
        "last_closed_bar_at": "2026-07-10T11:00:00+08:00",
        "raw_key": "5分钟_D1_三买辅助V230228",
        "raw_value": "三买_6笔_任意_0",
        "value_fields": {"v1": "三买", "v2": "6笔", "v3": "任意", "score": 0},
    }


def _response_payload() -> dict[str, object]:
    diagnostic = {
        "bar_count": 2,
        "fractal_count": 0,
        "stroke_count": 0,
        "last_stroke_direction": "unknown",
    }
    return {
        "schema_version": CZSC_RC8_PROTOCOL_VERSION,
        "catalog_version": CZSC_CATALOG_VERSION,
        "engine_version": "1.0.0rc8",
        "request_id": "request-1",
        "input_snapshot_id": "sha256:abc",
        "status": "ready",
        "current_states": [_raw_state()],
        "events": [],
        "diagnostics": {period: diagnostic for period in PERIODS},
        "error": None,
    }


def test_request_hash_is_order_stable_and_changes_with_any_bar_change() -> None:
    bars = _period_bars(close=10.1)
    reordered = dict(reversed(list(_period_bars(close=10.1).items())))

    first = build_research_request("600000.SH", bars, request_id="first")
    second = build_research_request("600000.SH", reordered, request_id="second")
    changed = build_research_request("600000.SH", _period_bars(close=10.2))

    assert first.input_snapshot_id == second.input_snapshot_id
    assert first.input_snapshot_id.startswith("sha256:")
    assert len(first.input_snapshot_id) == len("sha256:") + 64
    assert first.input_snapshot_id != changed.input_snapshot_id
    assert list(first.periods) == list(PERIODS)


@pytest.mark.parametrize("periods", [{"15m": []}, {"1d": []}])
def test_request_requires_exactly_the_approved_periods(
    periods: dict[str, list[object]],
) -> None:
    payload = _request_payload()
    payload["periods"] = periods

    with pytest.raises(ValidationError, match="period"):
        CzscRc8Request.model_validate(payload)


def test_request_rejects_duplicate_or_out_of_order_bar_timestamps() -> None:
    duplicate = _request_payload()
    duplicate["periods"]["5m"][1]["date"] = duplicate["periods"]["5m"][0]["date"]
    out_of_order = _request_payload()
    out_of_order["periods"]["5m"] = list(reversed(out_of_order["periods"]["5m"]))

    with pytest.raises(ValidationError, match="strictly increasing"):
        CzscRc8Request.model_validate(duplicate)
    with pytest.raises(ValidationError, match="strictly increasing"):
        CzscRc8Request.model_validate(out_of_order)


@pytest.mark.parametrize(
    ("field", "value"),
    [("volume", float("nan")), ("high", 9.9), ("volume", -1.0)],
)
def test_request_rejects_non_finite_or_invalid_ohlcv(field: str, value: float) -> None:
    payload = _request_payload()
    payload["periods"]["5m"][-1][field] = value

    with pytest.raises(ValidationError, match="OHLCV|price|volume"):
        CzscRc8Request.model_validate(payload)


def test_daily_source_date_is_available_at_shanghai_close() -> None:
    request = build_research_request(
        "600000.SH",
        _period_bars(),
        decision_at="2026-07-10T15:00:00+08:00",
    )

    assert request.last_closed_by_period["1d"] == "2026-07-10T15:00:00+08:00"
    assert request.last_closed_by_period["5m"] == "2026-07-10T11:00:00+08:00"

    with pytest.raises(ValidationError, match="decision_at"):
        build_research_request(
            "600000.SH",
            _period_bars(),
            decision_at="2026-07-10T14:59:59+08:00",
        )


def test_request_rejects_a_bar_later_than_its_declared_close_boundary() -> None:
    payload = _request_payload()
    payload["last_closed_by_period"]["5m"] = "2026-07-10T10:55:00+08:00"

    with pytest.raises(ValidationError, match="last_closed_by_period"):
        CzscRc8Request.model_validate(payload)

    with pytest.raises(ValidationError):
        CzscRc8Request.model_validate(payload).model_dump_json()


def test_response_requires_exact_structured_signal_fields_and_integer_score() -> None:
    response = CzscRc8Response.model_validate(_response_payload())

    assert response.schema_version == CZSC_RC8_PROTOCOL_VERSION
    assert response.current_states[0].value_fields.score == 0

    missing = copy.deepcopy(_response_payload())
    del missing["current_states"][0]["raw_value"]
    with pytest.raises(ValidationError):
        CzscRc8Response.model_validate(missing)

    extra = copy.deepcopy(_response_payload())
    extra["current_states"][0]["value_fields"]["extra"] = "bad"
    with pytest.raises(ValidationError):
        CzscRc8Response.model_validate(extra)

    coerced = copy.deepcopy(_response_payload())
    coerced["current_states"][0]["value_fields"]["score"] = "0"
    with pytest.raises(ValidationError):
        CzscRc8Response.model_validate(coerced)


def test_ready_response_requires_all_diagnostics_and_sanitized_error_text() -> None:
    missing_period = _response_payload()
    del missing_period["diagnostics"]["5m"]
    with pytest.raises(ValidationError, match="diagnostics"):
        CzscRc8Response.model_validate(missing_period)

    unsafe_error = _response_payload()
    unsafe_error.update(status="error", diagnostics={}, error="Traceback:\nsecret")
    with pytest.raises(ValidationError, match="sanitized"):
        CzscRc8Response.model_validate(unsafe_error)
