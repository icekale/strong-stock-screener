import ast
import importlib.metadata
import importlib.util
import json
import math
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from czsc import CZSC, Direction, Freq, RawBar, ZS


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
        period: _available_at(period, bars[-1]["date"])
        for period, bars in periods.items()
    }
    return {
        "schema_version": "czsc-rc8-jsonl-v1",
        "request_id": "worker-request-1",
        "symbol": "600000.SH",
        "catalog_version": "czsc-v2-catalog-1",
        "adjustment_mode": "qfq",
        "decision_at": max(
            datetime.fromisoformat(value).astimezone(timezone.utc)
            for value in boundaries.values()
        ).astimezone(SHANGHAI).isoformat(),
        "last_closed_by_period": boundaries,
        "input_snapshot_id": f"sha256:{'a' * 64}",
        "periods": periods,
    }


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

        self.assertEqual([_scope(item) for item in self.response["current_states"]], expected_scopes)
        self.assertEqual(event_keys, sorted(event_keys, key=lambda item: tuple(str(x) for x in item)))
        self.assertEqual(
            json.dumps(self.response, ensure_ascii=False, sort_keys=True),
            json.dumps(WORKER.handle_request(make_request()), ensure_ascii=False, sort_keys=True),
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

    def test_zone_adapter_exact_fixture_without_public_independent_priming(self) -> None:
        # rc8 cannot publicly prime a trader from two independently closed period arrays.
        big_prices = [
            10 + (index % 10 if (index // 10) % 2 == 0 else 9 - index % 10) * 0.2
            for index in range(120)
        ]
        small_prices = [15 + math.sin(index * math.pi / 6) for index in range(120)]
        big = CZSC(_raw_wave(big_prices, Freq.F60))
        small = CZSC(_raw_wave(small_prices, Freq.F30))
        big_zone = ZS(big.bi_list[-3:])
        small_zone = ZS(small.bi_list[-3:])

        self.assertGreaterEqual(len(big.bi_list), 5)
        self.assertGreaterEqual(len(small.bi_list), 5)
        self.assertGreater(big_zone.zg, big_zone.zd)
        self.assertGreater(small_zone.zg, small_zone.zd)
        self.assertGreater(small_zone.dd, big_zone.zz)
        self.assertEqual(small.bi_list[-1].direction, Direction.Down)
        self.assertEqual(WORKER._zone_resonance_value(big, small), "看多")

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
