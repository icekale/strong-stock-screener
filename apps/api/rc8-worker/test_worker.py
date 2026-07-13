import ast
import copy
import importlib.metadata
import importlib.util
import json
import math
import random
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from czsc import CZSC, Direction, Freq, RawBar, Signal, ZS


WORKER_PATH = Path(__file__).parents[1] / "app/services/chanlun/rc8_worker.py"
CATALOG_PATH = WORKER_PATH.with_name("research_catalog.json")
SPEC = importlib.util.spec_from_file_location("standalone_rc8_worker", WORKER_PATH)
assert SPEC is not None and SPEC.loader is not None
WORKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKER)
SHANGHAI = ZoneInfo("Asia/Shanghai")
PERIODS = ("1d", "60m", "30m", "5m")


def _zig_zag_bars(period: str, count: int = 96) -> list[dict[str, object]]:
    step = {"60m": timedelta(hours=1), "30m": timedelta(minutes=30), "5m": timedelta(minutes=5)}
    start = datetime(2026, 1, 1, 9, 30, tzinfo=SHANGHAI)
    bars = []
    for index in range(count):
        offset = index % 12 if (index // 12) % 2 == 0 else 11 - (index % 12)
        price = 10 + offset * 0.2
        if period == "1d":
            date = (start.date() + timedelta(days=index)).isoformat()
        else:
            date = (start + step[period] * index).isoformat()
        bars.append(
            {
                "date": date,
                "open": price - 0.02,
                "close": price + 0.02,
                "high": price + 0.1,
                "low": price - 0.1,
                "volume": 1_000 + index,
                "amount": (1_000 + index) * price,
                "ma5": None,
                "ma10": None,
                "ma20": None,
                "ma60": None,
            }
        )
    return bars


def _available_at(period: str, date: str) -> str:
    if period == "1d":
        return f"{date}T15:00:00+08:00"
    return date


def make_request() -> dict[str, object]:
    periods = {period: _zig_zag_bars(period) for period in PERIODS}
    boundaries = {
        period: _available_at(period, bars[-1]["date"]) for period, bars in periods.items()
    }
    return {
        "schema_version": "czsc-rc8-jsonl-v1",
        "request_id": "worker-request-1",
        "symbol": "600000.SH",
        "catalog_version": "czsc-v2-catalog-1",
        "adjustment_mode": "qfq",
        "decision_at": max(
            datetime.fromisoformat(value).astimezone(timezone.utc) for value in boundaries.values()
        )
        .astimezone(SHANGHAI)
        .isoformat(),
        "last_closed_by_period": boundaries,
        "input_snapshot_id": f"sha256:{'a' * 64}",
        "periods": periods,
    }


def _request_ending_at(
    request: dict[str, object],
    occurred_at: str,
) -> dict[str, object]:
    cutoff = datetime.fromisoformat(occurred_at).astimezone(SHANGHAI)
    prefix = copy.deepcopy(request)
    for period in PERIODS:
        bars = [
            bar
            for bar in prefix["periods"][period]
            if datetime.fromisoformat(_available_at(period, bar["date"])).astimezone(SHANGHAI)
            <= cutoff
        ]
        if not bars:
            raise AssertionError(f"fixture has no {period} bars at {occurred_at}")
        prefix["periods"][period] = bars
        prefix["last_closed_by_period"][period] = _available_at(period, bars[-1]["date"])
    prefix["decision_at"] = cutoff.isoformat(timespec="seconds")
    prefix["request_id"] = f"prefix-{occurred_at}"
    return prefix


def _event_identity(event: dict[str, object]) -> tuple[object, ...]:
    return (
        event["catalog_id"],
        event["period"],
        event["higher_period"],
        event["lower_period"],
        event["occurred_at"],
        event["raw_key"],
        event["raw_value"],
    )


def _event_clock_period(event: dict[str, object]) -> object:
    return event["period"] or event["lower_period"]


def _scope(state: dict[str, object]) -> tuple[object, object, object, object]:
    return (
        state["catalog_id"],
        state["period"],
        state["higher_period"],
        state["lower_period"],
    )


def _raw_wave(prices: list[float], freq: Freq) -> list[RawBar]:
    start = datetime(2026, 1, 1, 9, 30)
    return [
        RawBar(
            "fixture",
            start + timedelta(minutes=index * 5),
            freq,
            price,
            price,
            price + 0.08,
            price - 0.08,
            1_000,
            1_000 * price,
            index,
        )
        for index, price in enumerate(prices)
    ]


def _triangle_prices(base: float, count: int = 120) -> list[float]:
    return [
        base + (index % 10 if (index // 10) % 2 == 0 else 9 - index % 10) * 0.2
        for index in range(count)
    ]


def _sine_prices(base: float, count: int = 120) -> list[float]:
    return [base + math.sin(index * math.pi / 6) for index in range(count)]


def _random_walk_prices(seed: int, count: int = 180) -> list[float]:
    randomizer = random.Random(seed)
    price = 10.0
    prices = []
    for _ in range(count):
        price += randomizer.choice((-0.3, -0.2, 0.2, 0.3))
        prices.append(price)
    return prices


def _reference_zone_value(big: CZSC | None, small: CZSC | None) -> str:
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


def _wire_bars(
    prices: list[float],
    *,
    start: datetime,
    step: timedelta,
) -> list[dict[str, object]]:
    return [
        {
            "date": (start + step * index).isoformat(),
            "open": price,
            "close": price,
            "high": price + 0.08,
            "low": price - 0.08,
            "volume": 1_000,
            "amount": 1_000 * price,
            "ma5": None,
            "ma10": None,
            "ma20": None,
            "ma60": None,
        }
        for index, price in enumerate(prices)
    ]


def _zone_item() -> dict[str, object]:
    return {
        "catalog_id": "zone.resonance",
        "period": None,
        "higher_period": "60m",
        "lower_period": "30m",
        "raw_key": "60分钟_30分钟_中枢共振V221221",
    }


def _reference_reduce(
    *,
    item: dict[str, object],
    values: list[str],
    times: list[str],
    last_closed_at: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    signals = [Signal(key=item["raw_key"], value=f"{value}_任意_任意_0") for value in values]
    previous = None
    run_started_at = times[0]
    events = []

    def payload(signal: Signal, occurred_at: str) -> dict[str, object]:
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

    for signal, occurred_at in zip(signals, times, strict=True):
        if previous is None or signal.value != previous.value:
            run_started_at = occurred_at
        if signal.v1 != "其他" and (previous is None or previous.v1 == "其他"):
            events.append(payload(signal, occurred_at))
        previous = signal
    return payload(signals[-1], run_started_at), events


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.response = WORKER.handle_request(make_request())

    def test_worker_is_loaded_without_main_api_dependencies(self) -> None:
        tree = ast.parse(WORKER_PATH.read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", maxsplit=1)[0])

        self.assertNotIn("app", roots)
        self.assertNotIn("pydantic", roots)
        self.assertLessEqual(roots, sys.stdlib_module_names | {"__future__", "czsc"})
        self.assertEqual(importlib.metadata.version("czsc"), "1.0.0rc8")
        self.assertEqual(WORKER.CATALOG_PATH, CATALOG_PATH)

    def test_worker_returns_versioned_states_events_and_diagnostics(self) -> None:
        response = self.response

        self.assertEqual(response["schema_version"], "czsc-rc8-jsonl-v1")
        self.assertEqual(response["engine_version"], "1.0.0rc8")
        self.assertEqual(response["catalog_version"], "czsc-v2-catalog-1")
        self.assertEqual(response["request_id"], "worker-request-1")
        self.assertEqual(response["input_snapshot_id"], f"sha256:{'a' * 64}")
        self.assertEqual(response["status"], "ready")
        self.assertIsNone(response["error"])
        self.assertEqual(set(response["diagnostics"]), set(PERIODS))
        self.assertEqual(len(response["current_states"]), 16)
        self.assertTrue(response["events"])

        for item in [*response["current_states"], *response["events"]]:
            self.assertTrue(item["raw_key"])
            self.assertTrue(item["raw_value"])
            self.assertEqual(set(item["value_fields"]), {"v1", "v2", "v3", "score"})
            self.assertIs(type(item["value_fields"]["score"]), int)

        for diagnostic in response["diagnostics"].values():
            self.assertEqual(
                set(diagnostic),
                {"bar_count", "fractal_count", "stroke_count", "last_stroke_direction"},
            )

    def test_worker_output_order_is_deterministic(self) -> None:
        expected_scopes = [
            ("trend.bi-status", "1d", None, None),
            ("trend.bi-status", "60m", None, None),
            ("trend.bi-status", "30m", None, None),
            ("trend.bi-base", "1d", None, None),
            ("trend.bi-base", "60m", None, None),
            ("trend.bi-base", "30m", None, None),
            ("buy2.overlap", "5m", None, None),
            ("buy2.ma-confirm", "5m", None, None),
            ("buy3.structure", "5m", None, None),
            ("buy3.ma-confirm", "5m", None, None),
            ("zone.resonance", None, "1d", "60m"),
            ("zone.resonance", None, "60m", "30m"),
            ("risk.macd-divergence", "1d", None, None),
            ("risk.macd-divergence", "60m", None, None),
            ("risk.macd-divergence", "30m", None, None),
            ("risk.macd-divergence", "5m", None, None),
        ]
        event_keys = [
            (item["occurred_at"], *_scope(item), item["raw_value"])
            for item in self.response["events"]
        ]

        self.assertEqual(
            [_scope(item) for item in self.response["current_states"]], expected_scopes
        )
        self.assertEqual(
            event_keys, sorted(event_keys, key=lambda item: tuple(str(x) for x in item))
        )
        self.assertEqual(
            json.dumps(self.response, ensure_ascii=False, sort_keys=True),
            json.dumps(WORKER.handle_request(make_request()), ensure_ascii=False, sort_keys=True),
        )

    def test_full_timeline_matches_prefix_first_visibility(self) -> None:
        request = make_request()
        full = WORKER.handle_request(request)
        approved_catalog_ids = {item["catalog_id"] for item in WORKER._APPROVED_CATALOG}
        events = [event for event in full["events"] if event["catalog_id"] in approved_catalog_ids]

        self.assertTrue(events, "deterministic fixture must emit a whitelisted event")
        self.assertEqual(events, full["events"])
        prefixes = {}
        for event in events:
            occurred_at = event["occurred_at"]
            prefix = _request_ending_at(request, occurred_at)
            observed = WORKER.handle_request(prefix)
            prefixes[occurred_at] = (prefix, observed)
            self.assertIn(
                _event_identity(event),
                {_event_identity(item) for item in observed["events"]},
            )

        removable_events = []
        for occurred_at, (prefix, observed) in prefixes.items():
            for period in PERIODS:
                final_close = prefix["last_closed_by_period"][period]
                if final_close != occurred_at or len(prefix["periods"][period]) < 2:
                    continue
                at_final_close = [
                    event
                    for event in observed["events"]
                    if event["occurred_at"] == final_close and _event_clock_period(event) == period
                ]
                if not at_final_close:
                    continue

                without_final_bar = copy.deepcopy(prefix)
                without_final_bar["periods"][period].pop()
                previous_bar = without_final_bar["periods"][period][-1]
                without_final_bar["last_closed_by_period"][period] = _available_at(
                    period, previous_bar["date"]
                )
                without_final_bar["request_id"] = f"without-final-{period}-{occurred_at}"
                without_final = WORKER.handle_request(without_final_bar)
                without_final_identities = {
                    _event_identity(item) for item in without_final["events"]
                }
                for event in at_final_close:
                    removable_events.append(event)
                    self.assertNotIn(_event_identity(event), without_final_identities)

        self.assertTrue(
            removable_events,
            "fixture must emit an event at a removable final close",
        )

    def test_worker_rejects_catalog_protocol_or_request_configuration(self) -> None:
        for field, value in [
            ("catalog_version", "unknown"),
            ("schema_version", "unknown"),
            ("signals_config", []),
            ("function_name", "arbitrary_signal"),
        ]:
            with self.subTest(field=field):
                payload = make_request()
                payload[field] = value
                with self.assertRaises(ValueError):
                    WORKER.handle_request(payload)

    def test_worker_rejects_unknown_bar_fields(self) -> None:
        payload = make_request()
        payload["periods"]["5m"][0]["unexpected"] = True

        with self.assertRaises(ValueError):
            WORKER.handle_request(payload)

    def test_worker_requires_the_exact_bar_field_set(self) -> None:
        payload = make_request()
        del payload["periods"]["5m"][0]["ma60"]

        with self.assertRaises(ValueError):
            WORKER.handle_request(payload)

    def test_worker_rejects_numeric_strings_in_bars(self) -> None:
        payload = make_request()
        payload["periods"]["5m"][0]["open"] = "10.0"

        with self.assertRaises(ValueError):
            WORKER.handle_request(payload)

    def test_reduce_signals_emits_only_inactive_to_active_transitions(self) -> None:
        item = {
            "catalog_id": "test.transition",
            "period": "5m",
            "higher_period": None,
            "lower_period": None,
            "raw_key": "5分钟_D1_测试V000001",
        }
        values = ["其他", "看多", "看多", "其他", "看多"]
        times = [f"2026-01-01T10:{index:02d}:00+08:00" for index in range(5)]
        signals = [Signal(key=item["raw_key"], value=f"{value}_任意_任意_0") for value in values]

        current, events = WORKER._reduce_signals(
            item=item,
            signals=signals,
            times=times,
            last_closed_at=times[-1],
        )

        self.assertEqual(len(events), 2)
        self.assertEqual([event["occurred_at"] for event in events], [times[1], times[4]])
        self.assertEqual(current["occurred_at"], times[4])
        self.assertEqual(current["raw_value"], "看多_任意_任意_0")

    def test_zone_adapter_matches_independent_registered_algorithm_fixture(self) -> None:
        # rc8 cannot publicly prime a trader from two independently closed period arrays.
        cases = [
            ("bullish", _triangle_prices(10), _sine_prices(15), "看多"),
            ("bearish", _sine_prices(10), _triangle_prices(5), "看空"),
            ("insufficient", _triangle_prices(10, 10), _sine_prices(15), "其他"),
            ("no-overlap", _random_walk_prices(2), _sine_prices(15), "其他"),
        ]
        for name, big_prices, small_prices, expected in cases:
            with self.subTest(name=name):
                big = CZSC(_raw_wave(big_prices, Freq.F60))
                small = CZSC(_raw_wave(small_prices, Freq.F30))

                if name == "insufficient":
                    self.assertLess(len(big.bi_list), 5)
                if name == "no-overlap":
                    big_zone = ZS(big.bi_list[-3:])
                    self.assertLessEqual(big_zone.zg, big_zone.zd)
                self.assertEqual(_reference_zone_value(big, small), expected)
                self.assertEqual(WORKER._zone_resonance_value(big, small), expected)

    def test_run_zone_pair_matches_reference_at_synchronized_checkpoints(self) -> None:
        start = datetime(2026, 1, 1, 9, 30, tzinfo=SHANGHAI)
        higher = _wire_bars(
            _triangle_prices(10),
            start=start,
            step=timedelta(hours=1),
        )
        lower = _wire_bars(
            _sine_prices(15, 240),
            start=start,
            step=timedelta(minutes=30),
        )
        raw_bars = {
            "60m": WORKER._to_raw_bars("fixture", "60m", higher),
            "30m": WORKER._to_raw_bars("fixture", "30m", lower),
        }
        item = _zone_item()
        request = {
            "periods": {"60m": higher, "30m": lower},
            "last_closed_by_period": {"30m": lower[-1]["date"]},
        }
        higher_times = [datetime.fromisoformat(bar["date"]) for bar in higher]
        lower_times = [datetime.fromisoformat(bar["date"]) for bar in lower]
        visible_counts = [
            sum(higher_time <= checkpoint for higher_time in higher_times)
            for checkpoint in lower_times
        ]
        reference_values = []
        for lower_index, visible_count in enumerate(visible_counts):
            big = CZSC(raw_bars["60m"][:visible_count]) if visible_count else None
            small = CZSC(raw_bars["30m"][: lower_index + 1])
            reference_values.append(_reference_zone_value(big, small))

        actual_values = []
        production_adapter = WORKER._zone_resonance_value

        def record_value(big: CZSC | None, small: CZSC | None) -> str:
            value = production_adapter(big, small)
            actual_values.append(value)
            return value

        with mock.patch.object(WORKER, "_zone_resonance_value", side_effect=record_value):
            current, events = WORKER._run_zone_pair(
                item=item,
                request=request,
                raw_bars=raw_bars,
            )

        times = [timestamp.isoformat(timespec="seconds") for timestamp in lower_times]
        expected_current, expected_events = _reference_reduce(
            item=item,
            values=reference_values,
            times=times,
            last_closed_at=lower[-1]["date"],
        )

        self.assertEqual(visible_counts[:4], [1, 1, 2, 2])
        self.assertEqual(visible_counts[-1], len(higher))
        self.assertIn("看多", reference_values)
        self.assertEqual(actual_values, reference_values)
        self.assertEqual(current, expected_current)
        self.assertEqual(events, expected_events)

    def test_main_emits_one_compact_sanitized_error_per_malformed_line(self) -> None:
        process = subprocess.run(
            [sys.executable, str(WORKER_PATH)],
            input='not-json\n{"schema_version":"bad"}\n',
            capture_output=True,
            text=True,
            check=True,
        )
        lines = process.stdout.splitlines()

        self.assertEqual(len(lines), 2)
        self.assertNotIn("Traceback", process.stdout)
        for line in lines:
            payload = json.loads(line)
            self.assertEqual(payload["status"], "error")
            self.assertTrue(payload["error"])
            self.assertNotIn("\n", payload["error"])
            self.assertEqual(
                line,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )


if __name__ == "__main__":
    unittest.main()
