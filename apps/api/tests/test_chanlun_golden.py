from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import pytest

from scripts.run_chanlun_golden_validation import (
    GOLDEN_FIXTURE_DIR,
    GOLDEN_RULE_VERSION,
    load_golden_fixture,
    validate_golden_fixture,
)


GOLDEN_300308_DAILY = GOLDEN_FIXTURE_DIR / "300308_SZ_1d.json"


def write_fixture(tmp_path: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "schema_version": 1,
        "symbol": "600000.SH",
        "period": "1d",
        "lookback": 3,
        "source": "unit-test",
        "adjustment_mode": "none",
        "czsc_version": "0.10.12",
        "rule_version": GOLDEN_RULE_VERSION,
        "bars": [
            {
                "date": "2026-01-01T00:00:00+08:00",
                "open": 10.0,
                "close": 10.2,
                "high": 10.4,
                "low": 9.8,
                "volume": 100.0,
                "amount": 1000.0,
            },
            {
                "date": "2026-01-02T00:00:00+08:00",
                "open": 10.2,
                "close": 10.8,
                "high": 11.0,
                "low": 10.1,
                "volume": 101.0,
                "amount": 1001.0,
            },
            {
                "date": "2026-01-03T00:00:00+08:00",
                "open": 10.8,
                "close": 10.4,
                "high": 10.9,
                "low": 10.2,
                "volume": 102.0,
                "amount": 1002.0,
            },
        ],
        "fractals": [],
        "strokes": [],
        "zones": [],
        "confirmed_at": {},
        "reviewed_by": "manual-reviewer",
        "reviewed_at": "2026-07-30T16:00:00+08:00",
        "review_status": "approved",
        "review_notes": "unit fixture",
    }
    payload.update(overrides)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_golden_fixture_rejects_an_unapproved_label_file(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, review_status="pending")

    with pytest.raises(ValueError, match="review_status"):
        load_golden_fixture(path)


def test_golden_fixture_rejects_missing_expected_structure_arrays(tmp_path: Path) -> None:
    path = write_fixture(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["strokes"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="strokes"):
        load_golden_fixture(path)


def test_golden_fixture_rejects_malformed_bars(tmp_path: Path) -> None:
    path = write_fixture(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bars"][1]["date"] = payload["bars"][0]["date"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="strictly increasing"):
        load_golden_fixture(path)


def test_golden_fixture_rejects_unsupported_period(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, period="15m")

    with pytest.raises(ValueError, match="period"):
        load_golden_fixture(path)


def test_golden_result_requires_exact_stroke_coordinates() -> None:
    result = validate_golden_fixture(GOLDEN_300308_DAILY)

    assert result.passed is True
    assert result.stroke_coordinate_mismatches == 0
    assert result.zone_coordinate_mismatches == 0
    assert result.early_confirmations == 0
    assert result.confirmed_coordinate_drifts == 0


def test_all_golden_fixtures_pass_exact_matching_and_truncation_stability() -> None:
    fixture_paths = sorted(GOLDEN_FIXTURE_DIR.glob("*.json"))

    assert [path.name for path in fixture_paths] == [
        "300308_SZ_1d.json",
        "300308_SZ_60m.json",
        "600000_SH_1d.json",
        "600000_SH_60m.json",
        "inclusion_synthetic.json",
    ]
    for path in fixture_paths:
        result = validate_golden_fixture(path)
        assert result.passed is True, result.failures
        assert result.coverage_status == "pass"
        assert result.rule_version == GOLDEN_RULE_VERSION
        assert result.fractal_coordinate_mismatches == 0
        assert result.stroke_coordinate_mismatches == 0
        assert result.zone_coordinate_mismatches == 0
        assert result.early_confirmations == 0
        assert result.confirmed_coordinate_drifts == 0


def test_real_symbol_golden_fixtures_freeze_downloaded_bars_without_future_dates() -> None:
    expected_sources = {
        "300308_SZ_1d.json": "baidu-kline-provider",
        "600000_SH_1d.json": "baidu-kline-provider",
        "300308_SZ_60m.json": "sina-kline-provider",
        "600000_SH_60m.json": "sina-kline-provider",
    }

    for fixture_name, source_prefix in expected_sources.items():
        fixture = load_golden_fixture(GOLDEN_FIXTURE_DIR / fixture_name)

        assert fixture.source.startswith(source_prefix)
        assert len(fixture.bars) == 220
        assert max(_parse_bar_date(bar.date) for bar in fixture.bars) <= datetime.fromisoformat(
            "2026-07-30T23:59:59+08:00"
        )
        assert not _has_regular_placeholder_price_sequence(fixture.bars)


def test_golden_validator_cli_writes_deterministic_report(tmp_path: Path) -> None:
    output = tmp_path / "golden.md"
    command = [
        sys.executable,
        "scripts/run_chanlun_golden_validation.py",
        "--fixture-dir",
        str(GOLDEN_FIXTURE_DIR),
        "--output",
        str(output),
    ]

    first = subprocess.run(command, check=False, text=True, capture_output=True)
    first_report = output.read_text(encoding="utf-8")
    second = subprocess.run(command, check=False, text=True, capture_output=True)
    second_report = output.read_text(encoding="utf-8")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first_report == second_report
    assert "cl-v2-visual" in first_report
    assert "generated_at" not in first_report


def _parse_bar_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.fromisoformat("2026-01-01T00:00:00+08:00").tzinfo)
    return parsed


def _has_regular_placeholder_price_sequence(bars: list[object]) -> bool:
    closes = [round(float(getattr(bar, "close")), 6) for bar in bars[:44]]
    return set(closes).issubset(
        {
            10.0,
            11.333333,
            11.5,
            12.0,
            12.666667,
            13.0,
            13.333333,
            14.0,
            14.666667,
            15.0,
            15.333333,
            16.0,
            16.666667,
            17.333333,
            18.0,
            18.333333,
            18.5,
            19.0,
            19.333333,
            20.0,
            20.333333,
            20.5,
            20.666667,
            21.0,
            21.333333,
            21.5,
            22.0,
        }
    )
