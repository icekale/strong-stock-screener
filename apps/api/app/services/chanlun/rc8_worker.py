from __future__ import annotations

import json
import math
import re
import sys
from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import czsc
from czsc import CZSC, Direction, Freq, RawBar, Signal, ZS, generate_czsc_signals


PROTOCOL_VERSION = "czsc-rc8-jsonl-v1"
CATALOG_VERSION = "czsc-v2-catalog-1"
ENGINE_VERSION = "1.0.0rc8"
CATALOG_PATH = Path(__file__).with_name("research_catalog.json")
PERIODS = ("1d", "60m", "30m", "5m")
_PERIOD_SET = frozenset(PERIODS)
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")
_BAR_KEYS = frozenset(
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
_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "request_id",
        "symbol",
        "catalog_version",
        "adjustment_mode",
        "decision_at",
        "last_closed_by_period",
        "input_snapshot_id",
        "periods",
    }
)
_FREQUENCIES = {
    "1d": Freq.D,
    "60m": Freq.F60,
    "30m": Freq.F30,
    "5m": Freq.F5,
}
_FREQUENCY_LABELS = {
    "1d": "日线",
    "60m": "60分钟",
    "30m": "30分钟",
    "5m": "5分钟",
}
_APPROVED_CATALOG = (
    {
        "catalog_id": "trend.bi-status",
        "name": "cxt_bi_status_V230101",
        "periods": ("1d", "60m", "30m"),
        "pairs": None,
        "params": {},
        "key_template": "{freq}_D1_表里关系V230101",
        "role": "primary",
    },
    {
        "catalog_id": "trend.bi-base",
        "name": "cxt_bi_base_V230228",
        "periods": ("1d", "60m", "30m"),
        "pairs": None,
        "params": {"bi_init_length": 9},
        "key_template": "{freq}_D0BL9_V230228",
        "role": "primary",
    },
    {
        "catalog_id": "buy2.overlap",
        "name": "cxt_second_bs_V240524",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1, "w": 9, "t": 2},
        "key_template": "{freq}_D1W9T2_第二买卖点V240524",
        "role": "primary",
    },
    {
        "catalog_id": "buy2.ma-confirm",
        "name": "cxt_second_bs_V230320",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1, "ma_type": "SMA", "timeperiod": 21},
        "key_template": "{freq}_D1#SMA#21_BS2辅助V230320",
        "role": "confirmation",
    },
    {
        "catalog_id": "buy3.structure",
        "name": "cxt_third_buy_V230228",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1},
        "key_template": "{freq}_D1_三买辅助V230228",
        "role": "primary",
    },
    {
        "catalog_id": "buy3.ma-confirm",
        "name": "cxt_third_bs_V230319",
        "periods": ("5m",),
        "pairs": None,
        "params": {"di": 1, "ma_type": "SMA", "timeperiod": 34},
        "key_template": "{freq}_D1#SMA#34_BS3辅助V230319",
        "role": "confirmation",
    },
    {
        "catalog_id": "zone.resonance",
        "name": "cxt_zhong_shu_gong_zhen_V221221",
        "periods": None,
        "pairs": (("1d", "60m"), ("60m", "30m")),
        "params": {},
        "key_template": "{freq1}_{freq2}_中枢共振V221221",
        "role": "primary",
    },
    {
        "catalog_id": "risk.macd-divergence",
        "name": "tas_macd_bc_V240307",
        "periods": ("1d", "60m", "30m", "5m"),
        "pairs": None,
        "params": {"di": 1, "n": 20},
        "key_template": "{freq}_D1N20柱子背驰_BS辅助V240307",
        "role": "risk",
    },
)


def handle_request(payload: dict[str, Any]) -> dict[str, Any]:
    request = _validate_request(payload)
    catalog = _load_catalog()
    raw_bars = {
        period: _to_raw_bars(request["symbol"], period, request["periods"][period])
        for period in PERIODS
    }
    expanded = _expand_catalog(catalog)
    generated_rows = _generate_single_period_rows(expanded, raw_bars)
    current_states: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for item in expanded:
        if item["period"] is not None:
            period = item["period"]
            rows = generated_rows[period]
            times = [
                _bar_available_at(period, bar["date"])
                for bar in request["periods"][period]
            ]
            current, transitions = _reduce_generated_rows(
                item=item,
                rows=rows,
                bar_times=times,
                last_closed_at=request["last_closed_by_period"][period],
            )
        else:
            current, transitions = _run_zone_pair(
                item=item,
                request=request,
                raw_bars=raw_bars,
            )
        current_states.append(current)
        events.extend(transitions)

    events.sort(key=_event_sort_key)
    diagnostics = {}
    for period in PERIODS:
        analyzer = CZSC(raw_bars[period])
        diagnostics[period] = {
            "bar_count": len(raw_bars[period]),
            "fractal_count": len(analyzer.fx_list),
            "stroke_count": len(analyzer.bi_list),
            "last_stroke_direction": (
                str(analyzer.bi_list[-1].direction) if analyzer.bi_list else "unknown"
            ),
        }

    return {
        "schema_version": PROTOCOL_VERSION,
        "catalog_version": CATALOG_VERSION,
        "engine_version": ENGINE_VERSION,
        "request_id": request["request_id"],
        "input_snapshot_id": request["input_snapshot_id"],
        "status": "ready",
        "current_states": current_states,
        "events": events,
        "diagnostics": diagnostics,
        "error": None,
    }


def _validate_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request must be a JSON object")
    if set(payload) != _REQUEST_KEYS:
        raise ValueError("request fields do not match the versioned protocol")
    if payload["schema_version"] != PROTOCOL_VERSION:
        raise ValueError("unsupported protocol version")
    if payload["catalog_version"] != CATALOG_VERSION:
        raise ValueError("unsupported catalog version")
    if czsc.__version__ != ENGINE_VERSION:
        raise ValueError("unsupported engine version")

    for field in ("request_id", "symbol", "adjustment_mode", "input_snapshot_id"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    periods = payload["periods"]
    boundaries = payload["last_closed_by_period"]
    if not isinstance(periods, dict) or set(periods) != _PERIOD_SET:
        raise ValueError("periods must contain exactly 1d, 60m, 30m, and 5m")
    if not isinstance(boundaries, dict) or set(boundaries) != _PERIOD_SET:
        raise ValueError("last_closed_by_period must contain all four periods")

    decision_at = _parse_timestamp(payload["decision_at"], "decision_at")
    normalized_boundaries = {}
    normalized_periods = {}
    for period in PERIODS:
        bars = periods[period]
        if not isinstance(bars, list) or not bars:
            raise ValueError(f"period {period} requires at least one closed bar")
        boundary = _bar_available_at(period, boundaries[period])
        normalized_boundaries[period] = boundary.isoformat(timespec="seconds")
        previous: datetime | None = None
        copied_bars = []
        for bar in bars:
            _validate_bar(period, bar)
            closed_at = _bar_available_at(period, bar["date"])
            if previous is not None and closed_at <= previous:
                raise ValueError(f"{period} bar timestamps must be strictly increasing")
            if closed_at > boundary:
                raise ValueError(f"{period} bar exceeds its declared close boundary")
            if closed_at > decision_at:
                raise ValueError(f"{period} bar exceeds decision_at")
            previous = closed_at
            copied_bars.append(dict(bar))
        if previous != boundary:
            raise ValueError(f"{period} last bar does not match its close boundary")
        normalized_periods[period] = copied_bars

    return {
        **payload,
        "request_id": payload["request_id"].strip(),
        "symbol": payload["symbol"].strip().upper(),
        "decision_at": decision_at.isoformat(timespec="seconds"),
        "last_closed_by_period": normalized_boundaries,
        "periods": normalized_periods,
    }


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[dict[str, Any], ...]:
    try:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("fixed research catalog is unavailable") from exc
    if not isinstance(payload, dict) or set(payload) != {"catalog_version", "entries"}:
        raise ValueError("fixed research catalog has an invalid root")
    if payload["catalog_version"] != CATALOG_VERSION:
        raise ValueError("fixed research catalog version mismatch")
    entries = payload["entries"]
    if not isinstance(entries, list) or len(entries) != len(_APPROVED_CATALOG):
        raise ValueError("fixed research catalog entries mismatch")

    normalized = []
    for actual, expected in zip(entries, _APPROVED_CATALOG, strict=True):
        if not isinstance(actual, dict):
            raise ValueError("fixed research catalog entry must be an object")
        expected_keys = {
            "catalog_id",
            "name",
            "params",
            "key_template",
            "role",
            "periods" if expected["periods"] is not None else "pairs",
        }
        if set(actual) != expected_keys:
            raise ValueError("fixed research catalog entry fields mismatch")
        scopes = actual.get("periods") if expected["periods"] is not None else actual.get("pairs")
        normalized_scopes = (
            tuple(scopes)
            if expected["periods"] is not None
            else tuple(tuple(pair) for pair in scopes)
        )
        comparable = {
            **actual,
            "periods": normalized_scopes if expected["periods"] is not None else None,
            "pairs": normalized_scopes if expected["pairs"] is not None else None,
        }
        if comparable != expected:
            raise ValueError("fixed research catalog entry is not approved")
        normalized.append(comparable)
    return tuple(normalized)


def _expand_catalog(catalog: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    expanded = []
    for entry in catalog:
        if entry["periods"] is not None:
            for period in entry["periods"]:
                expanded.append(
                    {
                        **entry,
                        "period": period,
                        "higher_period": None,
                        "lower_period": None,
                        "raw_key": entry["key_template"].format(
                            freq=_FREQUENCY_LABELS[period]
                        ),
                    }
                )
        else:
            for higher_period, lower_period in entry["pairs"]:
                expanded.append(
                    {
                        **entry,
                        "period": None,
                        "higher_period": higher_period,
                        "lower_period": lower_period,
                        "raw_key": entry["key_template"].format(
                            freq1=_FREQUENCY_LABELS[higher_period],
                            freq2=_FREQUENCY_LABELS[lower_period],
                        ),
                    }
                )
    return expanded


def _generate_single_period_rows(
    expanded: list[dict[str, Any]],
    raw_bars: dict[str, list[RawBar]],
) -> dict[str, list[dict[str, Any]]]:
    rows_by_period = {}
    for period in PERIODS:
        configs = [
            {
                "name": item["name"],
                "freq": _FREQUENCY_LABELS[period],
                **item["params"],
            }
            for item in expanded
            if item["period"] == period
        ]
        start_at = raw_bars[period][0].dt.date().isoformat()
        rows = generate_czsc_signals(
            raw_bars[period],
            signals_config=configs,
            df=False,
            sdt=start_at,
            init_n=0,
        )
        if not isinstance(rows, list) or len(rows) != len(raw_bars[period]):
            raise ValueError(f"rc8 returned incomplete {period} signal rows")
        rows_by_period[period] = rows
    return rows_by_period


def _reduce_generated_rows(
    *,
    item: dict[str, Any],
    rows: list[dict[str, Any]],
    bar_times: list[datetime],
    last_closed_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signals: list[Signal] = []
    times: list[str] = []
    for row in rows:
        if item["raw_key"] not in row:
            raise ValueError(f"rc8 did not return catalog signal {item['catalog_id']}")
        try:
            bar_index = int(row["id"])
            occurred_at = bar_times[bar_index]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError("rc8 returned an invalid signal row id") from exc
        signals.append(Signal(key=item["raw_key"], value=str(row[item["raw_key"]])))
        times.append(occurred_at.isoformat(timespec="seconds"))
    return _reduce_signals(
        item=item,
        signals=signals,
        times=times,
        last_closed_at=last_closed_at,
    )


def _reduce_signals(
    *,
    item: dict[str, Any],
    signals: list[Signal],
    times: list[str],
    last_closed_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not signals or len(signals) != len(times):
        raise ValueError("signal reduction requires aligned rows")
    transitions = []
    previous: Signal | None = None
    run_started_at = times[0]
    for signal, occurred_at in zip(signals, times, strict=True):
        if previous is None or signal.value != previous.value:
            run_started_at = occurred_at
        if signal.v1 != "其他" and (previous is None or previous.v1 == "其他"):
            transitions.append(
                _signal_payload(
                    item=item,
                    signal=signal,
                    occurred_at=occurred_at,
                    last_closed_at=last_closed_at,
                )
            )
        previous = signal
    return (
        _signal_payload(
            item=item,
            signal=signals[-1],
            occurred_at=run_started_at,
            last_closed_at=last_closed_at,
        ),
        transitions,
    )


def _run_zone_pair(
    *,
    item: dict[str, Any],
    request: dict[str, Any],
    raw_bars: dict[str, list[RawBar]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    higher_period = item["higher_period"]
    lower_period = item["lower_period"]
    higher_bars = raw_bars[higher_period]
    lower_bars = raw_bars[lower_period]
    higher_times = [
        _bar_available_at(higher_period, bar["date"])
        for bar in request["periods"][higher_period]
    ]
    lower_times = [
        _bar_available_at(lower_period, bar["date"])
        for bar in request["periods"][lower_period]
    ]
    higher_czsc: CZSC | None = None
    lower_czsc: CZSC | None = None
    higher_index = 0
    signals = []
    times = []

    for lower_index, checkpoint in enumerate(lower_times):
        if lower_czsc is None:
            lower_czsc = CZSC([lower_bars[lower_index]])
        else:
            lower_czsc.update(lower_bars[lower_index])
        while higher_index < len(higher_bars) and higher_times[higher_index] <= checkpoint:
            if higher_czsc is None:
                higher_czsc = CZSC([higher_bars[higher_index]])
            else:
                higher_czsc.update(higher_bars[higher_index])
            higher_index += 1
        value = _zone_resonance_value(higher_czsc, lower_czsc)
        signals.append(
            Signal(
                key=item["raw_key"],
                value=f"{value}_任意_任意_0",
            )
        )
        times.append(checkpoint.isoformat(timespec="seconds"))

    return _reduce_signals(
        item=item,
        signals=signals,
        times=times,
        last_closed_at=request["last_closed_by_period"][lower_period],
    )


def _zone_resonance_value(big: CZSC | None, small: CZSC | None) -> str:
    if big is None or small is None or len(big.bi_list) < 5 or len(small.bi_list) < 5:
        return "其他"
    big_zone = ZS(big.bi_list[-3:])
    small_zone = ZS(small.bi_list[-3:])
    if not (big_zone.zg > big_zone.zd and small_zone.zg > small_zone.zd):
        return "其他"
    if small_zone.dd > big_zone.zz and small.bi_list[-1].direction == Direction.Down:
        return "看多"
    if small_zone.gg < big_zone.zz and small.bi_list[-1].direction == Direction.Up:
        return "看空"
    return "其他"


def _signal_payload(
    *,
    item: dict[str, Any],
    signal: Signal,
    occurred_at: str,
    last_closed_at: str,
) -> dict[str, Any]:
    return {
        "catalog_id": item["catalog_id"],
        "period": item["period"],
        "higher_period": item["higher_period"],
        "lower_period": item["lower_period"],
        "occurred_at": occurred_at,
        "last_closed_bar_at": last_closed_at,
        "raw_key": signal.key,
        "raw_value": signal.value,
        "value_fields": {
            "v1": signal.v1,
            "v2": signal.v2,
            "v3": signal.v3,
            "score": int(signal.score),
        },
    }


def _event_sort_key(item: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(value)
        for value in (
            item["occurred_at"],
            item["catalog_id"],
            item["period"],
            item["higher_period"],
            item["lower_period"],
            item["raw_value"],
        )
    )


def _to_raw_bars(symbol: str, period: str, bars: list[dict[str, Any]]) -> list[RawBar]:
    converted = []
    for index, bar in enumerate(bars):
        amount = bar.get("amount")
        if amount is None:
            amount = float(bar["volume"]) * float(bar["close"])
        converted.append(
            RawBar(
                symbol,
                _bar_available_at(period, bar["date"]).replace(tzinfo=None),
                _FREQUENCIES[period],
                float(bar["open"]),
                float(bar["close"]),
                float(bar["high"]),
                float(bar["low"]),
                float(bar["volume"]),
                float(amount),
                index,
            )
        )
    return converted


def _validate_bar(period: str, bar: Any) -> None:
    if not isinstance(bar, dict):
        raise ValueError(f"{period} bar must be an object")
    if set(bar) != _BAR_KEYS:
        raise ValueError(f"{period} bar must contain the exact protocol field set")
    if not isinstance(bar["date"], str):
        raise ValueError(f"{period} bar date must be a string")
    values = []
    for field in ("open", "close", "high", "low", "volume"):
        value = bar[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{period} bar {field} must be numeric")
        values.append(float(value))
    open_price, close_price, high, low, volume = values
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{period} OHLCV values must be finite")
    for field in ("amount", "ma5", "ma10", "ma20", "ma60"):
        value = bar[field]
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"{period} bar {field} must be a finite number or null")
    if volume < 0:
        raise ValueError(f"{period} volume cannot be negative")
    if high < max(open_price, close_price) or low > min(open_price, close_price):
        raise ValueError(f"{period} price relations are invalid")


def _bar_available_at(period: str, value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{period} timestamp must be a string")
    if _DATE_ONLY.fullmatch(value):
        if period != "1d":
            raise ValueError(f"{period} requires an actual closed timestamp")
        return datetime.combine(date.fromisoformat(value), time(15), tzinfo=_SHANGHAI)
    return _parse_timestamp(value, f"{period} timestamp")


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or _DATE_ONLY.fullmatch(value):
        raise ValueError(f"{field} must include a time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=_SHANGHAI)
    return parsed.astimezone(_SHANGHAI)


def error_response(request_id: str, exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": PROTOCOL_VERSION,
        "catalog_version": CATALOG_VERSION,
        "engine_version": ENGINE_VERSION,
        "request_id": request_id,
        "input_snapshot_id": "unknown",
        "status": "error",
        "current_states": [],
        "events": [],
        "diagnostics": {},
        "error": _sanitize_error(exc),
    }


def _sanitize_error(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "invalid JSON request"
    if not isinstance(exc, ValueError):
        return "worker request failed"
    message = " ".join(str(exc).split())
    return (message or "invalid worker request")[:240]


def main() -> None:
    for line in sys.stdin:
        request_id = "unknown"
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                request_id = str(payload.get("request_id", "unknown"))
            response = handle_request(payload)
        except Exception as exc:
            response = error_response(request_id, exc)
        sys.stdout.write(
            json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        sys.stdout.flush()


if __name__ == "__main__":
    main()
