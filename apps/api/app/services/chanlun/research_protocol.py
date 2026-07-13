from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, time
from types import MappingProxyType
from typing import Literal, Mapping, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_serializer,
    field_validator,
    model_validator,
)

from app.models import CZSC_CATALOG_VERSION, ChanlunPeriod, KlineBar


CZSC_RC8_PROTOCOL_VERSION = "czsc-rc8-jsonl-v1"
CZSC_RC8_ENGINE_VERSION = "1.0.0rc8"
APPROVED_PERIODS: tuple[ChanlunPeriod, ...] = ("1d", "60m", "30m", "5m")
_APPROVED_PERIOD_SET = frozenset(APPROVED_PERIODS)
_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_BAR_FIELD_SET = frozenset(
    {
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "ma5",
        "ma10",
        "ma20",
        "ma60",
    }
)


class CzscRc8Bar(KlineBar):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @model_validator(mode="before")
    @classmethod
    def _require_exact_fields(cls, value: object) -> object:
        if isinstance(value, KlineBar):
            value = value.model_dump(mode="python")
        if not isinstance(value, Mapping) or set(value) != _BAR_FIELD_SET:
            raise ValueError("bar must contain the exact KlineBar field set")
        return value


class CzscRc8ValueFields(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    v1: str
    v2: str
    v3: str
    score: StrictInt = Field(ge=0, le=100)


class CzscRc8RawSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_id: str
    period: ChanlunPeriod | None = None
    higher_period: ChanlunPeriod | None = None
    lower_period: ChanlunPeriod | None = None
    occurred_at: str
    last_closed_bar_at: str
    raw_key: str
    raw_value: str
    value_fields: CzscRc8ValueFields

    @field_validator("occurred_at", "last_closed_bar_at")
    @classmethod
    def _normalize_timestamps(cls, value: str) -> str:
        return _canonical_timestamp(value, field_name="signal timestamp")

    @model_validator(mode="after")
    def _validate_scope(self) -> CzscRc8RawSignal:
        is_single = (
            self.period is not None
            and self.higher_period is None
            and self.lower_period is None
        )
        is_pair = (
            self.period is None
            and self.higher_period is not None
            and self.lower_period is not None
        )
        if not (is_single or is_pair):
            raise ValueError("signal requires exactly one period or one period pair")
        return self


class CzscRc8PeriodDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bar_count: int = Field(ge=0)
    fractal_count: int = Field(ge=0)
    stroke_count: int = Field(ge=0)
    last_stroke_direction: Literal["向上", "向下", "unknown"]


class CzscRc8Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["czsc-rc8-jsonl-v1"] = CZSC_RC8_PROTOCOL_VERSION
    request_id: str
    symbol: str
    catalog_version: Literal["czsc-v2-catalog-1"] = CZSC_CATALOG_VERSION
    adjustment_mode: str
    decision_at: str
    last_closed_by_period: Mapping[ChanlunPeriod, str]
    input_snapshot_id: str
    periods: Mapping[ChanlunPeriod, tuple[CzscRc8Bar, ...]]

    @field_validator("request_id", "adjustment_mode", "input_snapshot_id")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be empty")
        return normalized

    @field_validator("decision_at")
    @classmethod
    def _normalize_decision_at(cls, value: str) -> str:
        return _canonical_timestamp(value, field_name="decision_at")

    @field_validator("last_closed_by_period", "periods", mode="before")
    @classmethod
    def _require_exact_period_keys(cls, value: object) -> object:
        if not isinstance(value, Mapping) or set(value) != _APPROVED_PERIOD_SET:
            raise ValueError("period map must contain exactly 1d, 60m, 30m, and 5m")
        return value

    @field_validator("last_closed_by_period")
    @classmethod
    def _normalize_boundaries(
        cls,
        value: Mapping[ChanlunPeriod, str],
    ) -> Mapping[ChanlunPeriod, str]:
        return MappingProxyType(
            {
                period: _canonical_bar_timestamp(period, value[period])
                for period in APPROVED_PERIODS
            }
        )

    @field_validator("periods")
    @classmethod
    def _normalize_periods(
        cls,
        value: Mapping[ChanlunPeriod, tuple[CzscRc8Bar, ...]],
    ) -> Mapping[ChanlunPeriod, tuple[CzscRc8Bar, ...]]:
        return MappingProxyType(
            {
                period: tuple(
                    bar.model_copy(
                        update={"date": _canonical_bar_timestamp(period, bar.date)}
                    )
                    for bar in value[period]
                )
                for period in APPROVED_PERIODS
            }
        )

    @field_serializer("last_closed_by_period")
    def _serialize_boundaries(
        self,
        value: Mapping[ChanlunPeriod, str],
    ) -> dict[ChanlunPeriod, str]:
        return {period: value[period] for period in APPROVED_PERIODS}

    @field_serializer("periods")
    def _serialize_periods(
        self,
        value: Mapping[ChanlunPeriod, tuple[CzscRc8Bar, ...]],
    ) -> dict[ChanlunPeriod, list[dict[str, object]]]:
        return {
            period: [bar.model_dump(mode="json") for bar in value[period]]
            for period in APPROVED_PERIODS
        }

    @model_validator(mode="after")
    def _validate_closed_periods(self) -> CzscRc8Request:
        if set(self.periods) != _APPROVED_PERIOD_SET:
            raise ValueError("periods must contain exactly 1d, 60m, 30m, and 5m")
        if set(self.last_closed_by_period) != _APPROVED_PERIOD_SET:
            raise ValueError(
                "last_closed_by_period must contain exactly 1d, 60m, 30m, and 5m"
            )

        decision_at = _parse_timestamp(self.decision_at, field_name="decision_at")
        for period in APPROVED_PERIODS:
            bars = self.periods[period]
            if not bars:
                raise ValueError(f"period {period} requires at least one closed bar")

            boundary = _parse_timestamp(
                self.last_closed_by_period[period],
                field_name=f"last_closed_by_period[{period}]",
            )
            previous: datetime | None = None
            for bar in bars:
                _validate_bar_values(period, bar)
                closed_at = _bar_timestamp(period, bar.date)
                if previous is not None and closed_at <= previous:
                    raise ValueError(f"{period} bar timestamps must be strictly increasing")
                if closed_at > boundary:
                    raise ValueError(
                        f"{period} bar is later than last_closed_by_period[{period}]"
                    )
                if closed_at > decision_at:
                    raise ValueError(f"{period} bar is later than decision_at")
                previous = closed_at

            if previous != boundary:
                raise ValueError(
                    f"{period} last bar must equal last_closed_by_period[{period}]"
                )
            if boundary > decision_at:
                raise ValueError(f"last_closed_by_period[{period}] exceeds decision_at")
        return self


class CzscRc8Response(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["czsc-rc8-jsonl-v1"] = CZSC_RC8_PROTOCOL_VERSION
    catalog_version: Literal["czsc-v2-catalog-1"] = CZSC_CATALOG_VERSION
    engine_version: Literal["1.0.0rc8"] = CZSC_RC8_ENGINE_VERSION
    request_id: str
    input_snapshot_id: str
    status: Literal["ready", "error"]
    current_states: list[CzscRc8RawSignal] = Field(default_factory=list)
    events: list[CzscRc8RawSignal] = Field(default_factory=list)
    diagnostics: dict[ChanlunPeriod, CzscRc8PeriodDiagnostic] = Field(default_factory=dict)
    error: str | None = None

    @field_validator("error")
    @classmethod
    def _validate_sanitized_error(cls, value: str | None) -> str | None:
        if value is not None and ("\n" in value or "\r" in value or "Traceback" in value):
            raise ValueError("error must be sanitized")
        return value

    @model_validator(mode="after")
    def _validate_status(self) -> CzscRc8Response:
        if self.status == "ready":
            if self.error is not None:
                raise ValueError("ready response cannot contain an error")
            if set(self.diagnostics) != _APPROVED_PERIOD_SET:
                raise ValueError("ready response diagnostics must contain all four periods")
        elif not self.error:
            raise ValueError("error response requires a sanitized error")
        return self


def build_research_request(
    symbol: str,
    periods: Mapping[ChanlunPeriod, list[KlineBar]],
    *,
    request_id: str | None = None,
    adjustment_mode: str = "unknown",
    decision_at: str | datetime | None = None,
    last_closed_by_period: Mapping[ChanlunPeriod, str] | None = None,
    catalog_version: str = CZSC_CATALOG_VERSION,
) -> CzscRc8Request:
    copied_periods = {
        period: [
            CzscRc8Bar.model_validate(
                bar.model_dump(mode="python") if isinstance(bar, KlineBar) else bar
            )
            for bar in bars
        ]
        for period, bars in periods.items()
    }
    if set(copied_periods) != _APPROVED_PERIOD_SET:
        raise ValueError("periods must contain exactly 1d, 60m, 30m, and 5m")

    if last_closed_by_period is None:
        boundaries = {
            period: _canonical_bar_timestamp(period, copied_periods[period][-1].date)
            for period in APPROVED_PERIODS
            if copied_periods[period]
        }
    else:
        boundaries = dict(last_closed_by_period)

    if decision_at is None:
        if set(boundaries) != _APPROVED_PERIOD_SET:
            raise ValueError("cannot derive decision_at without all period boundaries")
        latest = max(
            _parse_timestamp(value, field_name=f"last_closed_by_period[{period}]")
            for period, value in boundaries.items()
        )
        decision_value = latest.astimezone(_SHANGHAI).isoformat(timespec="seconds")
    elif isinstance(decision_at, datetime):
        decision_value = _canonical_datetime(decision_at, field_name="decision_at")
    else:
        decision_value = decision_at

    request = CzscRc8Request.model_validate(
        {
            "schema_version": CZSC_RC8_PROTOCOL_VERSION,
            "request_id": request_id or uuid4().hex,
            "symbol": symbol,
            "catalog_version": catalog_version,
            "adjustment_mode": adjustment_mode,
            "decision_at": decision_value,
            "last_closed_by_period": boundaries,
            "input_snapshot_id": "sha256:pending",
            "periods": copied_periods,
        }
    )
    canonical_input = request.model_dump(
        mode="json",
        exclude={"request_id", "input_snapshot_id"},
    )
    canonical_json = json.dumps(
        canonical_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    snapshot_id = f"sha256:{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()}"
    return request.model_copy(update={"input_snapshot_id": snapshot_id})


def _validate_bar_values(period: ChanlunPeriod, bar: KlineBar) -> None:
    values = (bar.open, bar.close, bar.high, bar.low, bar.volume)
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{period} OHLCV values must be finite")
    if bar.amount is not None and not math.isfinite(bar.amount):
        raise ValueError(f"{period} amount must be finite")
    if bar.volume < 0:
        raise ValueError(f"{period} volume cannot be negative")
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        raise ValueError(f"{period} price relations are invalid")


def _canonical_bar_timestamp(period: ChanlunPeriod, value: str) -> str:
    parsed = _bar_timestamp(period, value)
    return parsed.astimezone(_SHANGHAI).isoformat(timespec="seconds")


def _bar_timestamp(period: ChanlunPeriod, value: str) -> datetime:
    if _DATE_ONLY.fullmatch(value):
        if period != "1d":
            raise ValueError(f"{period} bars require an actual closed timestamp")
        return datetime.combine(date.fromisoformat(value), time(15), tzinfo=_SHANGHAI)
    return _parse_timestamp(value, field_name=f"{period} bar timestamp")


def _canonical_timestamp(value: str, *, field_name: str) -> str:
    parsed = _parse_timestamp(value, field_name=field_name)
    return parsed.astimezone(_SHANGHAI).isoformat(timespec="seconds")


def _canonical_datetime(value: datetime, *, field_name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=_SHANGHAI)
    try:
        return value.astimezone(_SHANGHAI).isoformat(timespec="seconds")
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid timestamp") from exc


def _parse_timestamp(value: str, *, field_name: str) -> datetime:
    if not isinstance(value, str) or _DATE_ONLY.fullmatch(value):
        raise ValueError(f"{field_name} must include a time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    return cast(datetime, parsed.replace(tzinfo=_SHANGHAI) if parsed.tzinfo is None else parsed)
