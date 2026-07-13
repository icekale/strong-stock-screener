import copy
from datetime import datetime, timezone
from typing import Callable

import pytest
from pydantic import ValidationError

from app.models import KlineBar
from app.services.chanlun import research_protocol
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


def _add_period(request: CzscRc8Request) -> None:
    request.periods["15m"] = ()


def _replace_period_bars(request: CzscRc8Request) -> None:
    request.periods["5m"] = request.periods["5m"]


def _append_bar(request: CzscRc8Request) -> None:
    request.periods["5m"].append(request.periods["5m"][-1])


def _replace_bar(request: CzscRc8Request) -> None:
    request.periods["5m"][0] = request.periods["5m"][1]


def _mutate_bar(request: CzscRc8Request) -> None:
    request.periods["5m"][0].close = 99.0


def _mutate_boundary(request: CzscRc8Request) -> None:
    request.last_closed_by_period["5m"] = "2020-01-01T00:00:00+08:00"


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


@pytest.mark.parametrize(
    ("salt_name", "changed_value"),
    [
        ("CZSC_RC8_ENGINE_VERSION", "1.0.0rc8-simulated"),
        ("CZSC_SCORE_RULE_VERSION", "czsc-score-v2-rule-simulated"),
    ],
)
def test_request_hash_includes_runtime_version_salts_without_changing_wire_fields(
    monkeypatch: pytest.MonkeyPatch,
    salt_name: str,
    changed_value: str,
) -> None:
    baseline = research_protocol.build_research_request(
        "600000.SH",
        _period_bars(),
        request_id="version-salt",
    )
    wire_fields = set(baseline.model_dump(mode="json"))

    monkeypatch.setattr(research_protocol, salt_name, changed_value, raising=False)
    changed = research_protocol.build_research_request(
        "600000.SH",
        _period_bars(),
        request_id="version-salt",
    )

    assert changed.input_snapshot_id != baseline.input_snapshot_id
    assert set(changed.model_dump(mode="json")) == wire_fields
    assert "engine_version" not in wire_fields
    assert "rule_version" not in wire_fields


@pytest.mark.parametrize(
    ("mutate", "error_type"),
    [
        (_add_period, TypeError),
        (_replace_period_bars, TypeError),
        (_append_bar, AttributeError),
        (_replace_bar, TypeError),
        (_mutate_bar, ValidationError),
        (_mutate_boundary, TypeError),
    ],
    ids=[
        "add-period",
        "replace-period-bars",
        "append-bar",
        "replace-bar",
        "mutate-bar",
        "mutate-boundary",
    ],
)
def test_request_graph_is_deeply_immutable_after_hashing(
    mutate: Callable[[CzscRc8Request], None],
    error_type: type[Exception],
) -> None:
    request = build_research_request(
        "600000.SH",
        _period_bars(),
        request_id="immutable",
    )
    serialized = request.model_dump_json().encode("utf-8")
    snapshot_id = request.input_snapshot_id

    with pytest.raises(error_type):
        mutate(request)

    assert request.model_dump_json().encode("utf-8") == serialized
    assert request.input_snapshot_id == snapshot_id


def test_equivalent_minute_instants_have_identical_hash_and_worker_dates() -> None:
    shanghai_bars = _period_bars()
    utc_bars = _period_bars()
    for period, bars in utc_bars.items():
        if period == "1d":
            continue
        for bar in bars:
            bar.date = (
                datetime.fromisoformat(bar.date)
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

    shanghai = build_research_request(
        "600000.SH",
        shanghai_bars,
        request_id="canonical",
    )
    utc = build_research_request(
        "600000.SH",
        utc_bars,
        request_id="canonical",
    )

    assert shanghai.input_snapshot_id == utc.input_snapshot_id
    assert shanghai.model_dump_json() == utc.model_dump_json()
    assert shanghai.periods["5m"][-1].date == "2026-07-10T11:00:00+08:00"
    assert utc.periods["5m"][-1].date == "2026-07-10T11:00:00+08:00"
    assert shanghai.periods["1d"][-1].date == "2026-07-10T15:00:00+08:00"


@pytest.mark.parametrize("periods", [{"15m": []}, {"1d": []}])
def test_request_requires_exactly_the_approved_periods(
    periods: dict[str, list[object]],
) -> None:
    payload = _request_payload()
    payload["periods"] = periods

    with pytest.raises(ValidationError, match="period"):
        CzscRc8Request.model_validate(payload)


@pytest.mark.parametrize("field", ["periods", "last_closed_by_period"])
def test_request_rejects_required_period_keys_plus_unknown_extra(field: str) -> None:
    payload = _request_payload()
    if field == "periods":
        payload[field]["15m"] = copy.deepcopy(payload[field]["5m"])
    else:
        payload[field]["15m"] = payload[field]["5m"]

    with pytest.raises(ValidationError):
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


def test_request_rejects_unknown_bar_fields() -> None:
    payload = _request_payload()
    payload["periods"]["5m"][0]["unexpected"] = True

    with pytest.raises(ValidationError):
        CzscRc8Request.model_validate(payload)


def test_request_requires_the_exact_bar_field_set() -> None:
    payload = _request_payload()
    del payload["periods"]["5m"][0]["ma60"]

    with pytest.raises(ValidationError):
        CzscRc8Request.model_validate(payload)


def test_request_rejects_coercible_numeric_strings_in_bars() -> None:
    payload = _request_payload()
    payload["periods"]["5m"][0]["open"] = "10.0"

    with pytest.raises(ValidationError):
        CzscRc8Request.model_validate(payload)


def test_daily_source_date_is_available_at_shanghai_close() -> None:
    request = build_research_request(
        "600000.SH",
        _period_bars(),
        decision_at="2026-07-10T15:00:00+08:00",
    )

    assert request.last_closed_by_period["1d"] == "2026-07-10T15:00:00+08:00"
    assert request.last_closed_by_period["5m"] == "2026-07-10T11:00:00+08:00"
    assert request.periods["1d"][-1].date == "2026-07-10T15:00:00+08:00"

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


@pytest.mark.parametrize(
    ("period", "higher_period", "lower_period"),
    [
        ("5m", "1d", None),
        (None, "1d", None),
    ],
    ids=["mixed-single-and-pair", "partial-pair"],
)
def test_response_rejects_mixed_or_partial_signal_scope(
    period: str | None,
    higher_period: str | None,
    lower_period: str | None,
) -> None:
    payload = _response_payload()
    payload["current_states"][0].update(
        period=period,
        higher_period=higher_period,
        lower_period=lower_period,
    )

    with pytest.raises(ValidationError, match="exactly one period or one period pair"):
        CzscRc8Response.model_validate(payload)


def test_ready_response_requires_all_diagnostics_and_sanitized_error_text() -> None:
    missing_period = _response_payload()
    del missing_period["diagnostics"]["5m"]
    with pytest.raises(ValidationError, match="diagnostics"):
        CzscRc8Response.model_validate(missing_period)

    unsafe_error = _response_payload()
    unsafe_error.update(status="error", diagnostics={}, error="Traceback:\nsecret")
    with pytest.raises(ValidationError, match="sanitized"):
        CzscRc8Response.model_validate(unsafe_error)
