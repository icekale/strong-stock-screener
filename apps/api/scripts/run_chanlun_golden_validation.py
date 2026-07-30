from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.models import ChanlunFractal, ChanlunPeriod, ChanlunStroke, ChanlunZone, KlineBar  # noqa: E402
from app.services.chanlun.adapter import ChanlunAdapter  # noqa: E402


GOLDEN_RULE_VERSION = "cl-v2-visual"
GOLDEN_FIXTURE_DIR = API_ROOT / "tests" / "fixtures" / "chanlun" / "golden"
SUPPORTED_PERIODS: set[str] = {"1d", "60m", "30m", "5m"}
PRICE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class GoldenFixture:
    path: Path
    schema_version: int
    symbol: str
    period: ChanlunPeriod
    lookback: int
    source: str
    adjustment_mode: str
    czsc_version: str
    rule_version: str
    bars: list[KlineBar]
    fractals: list[ChanlunFractal]
    strokes: list[ChanlunStroke]
    zones: list[ChanlunZone]
    confirmed_at: dict[str, str]
    reviewed_by: str
    reviewed_at: str
    review_status: Literal["approved"]
    review_notes: str


@dataclass(frozen=True)
class GoldenFixtureResult:
    fixture_name: str
    symbol: str
    period: ChanlunPeriod
    bar_count: int
    coverage_status: Literal["pass", "fail"]
    fractal_matches: int
    stroke_matches: int
    zone_matches: int
    fractal_count: int
    stroke_count: int
    zone_count: int
    fractal_coordinate_mismatches: int
    stroke_coordinate_mismatches: int
    zone_coordinate_mismatches: int
    early_confirmations: int
    confirmed_coordinate_drifts: int
    rule_version: str
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def load_golden_fixture(path: Path) -> GoldenFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    required_fields = {
        "schema_version",
        "symbol",
        "period",
        "lookback",
        "source",
        "adjustment_mode",
        "czsc_version",
        "rule_version",
        "bars",
        "fractals",
        "strokes",
        "zones",
        "confirmed_at",
        "reviewed_by",
        "reviewed_at",
        "review_status",
        "review_notes",
    }
    missing = sorted(required_fields - raw.keys())
    if missing:
        raise ValueError(f"missing fixture fields: {', '.join(missing)}")
    if raw["review_status"] != "approved":
        raise ValueError("review_status must be approved")
    if raw["period"] not in SUPPORTED_PERIODS:
        raise ValueError(f"unsupported period: {raw['period']}")
    if raw["rule_version"] != GOLDEN_RULE_VERSION:
        raise ValueError(f"rule_version must be {GOLDEN_RULE_VERSION}")
    for key in ("fractals", "strokes", "zones"):
        if not isinstance(raw[key], list):
            raise ValueError(f"{key} must be a list")
    if not isinstance(raw["confirmed_at"], dict):
        raise ValueError("confirmed_at must be an object")

    bars = [KlineBar.model_validate(item) for item in raw["bars"]]
    _validate_bars(bars)
    fractals = [ChanlunFractal.model_validate(item) for item in raw["fractals"]]
    strokes = [ChanlunStroke.model_validate(item) for item in raw["strokes"]]
    zones = [ChanlunZone.model_validate(item) for item in raw["zones"]]
    confirmed_at = {str(key): str(value) for key, value in raw["confirmed_at"].items()}
    _validate_confirmed_at(confirmed_at, fractals, strokes, zones)

    return GoldenFixture(
        path=path,
        schema_version=int(raw["schema_version"]),
        symbol=str(raw["symbol"]),
        period=raw["period"],
        lookback=int(raw["lookback"]),
        source=str(raw["source"]),
        adjustment_mode=str(raw["adjustment_mode"]),
        czsc_version=str(raw["czsc_version"]),
        rule_version=str(raw["rule_version"]),
        bars=bars,
        fractals=fractals,
        strokes=strokes,
        zones=zones,
        confirmed_at=confirmed_at,
        reviewed_by=str(raw["reviewed_by"]),
        reviewed_at=str(raw["reviewed_at"]),
        review_status="approved",
        review_notes=str(raw["review_notes"]),
    )


def validate_golden_fixture(path: Path) -> GoldenFixtureResult:
    fixture = load_golden_fixture(path)
    failures: list[str] = []
    analysis = ChanlunAdapter().analyze(
        fixture.symbol,
        period=fixture.period,
        bars=fixture.bars,
        include_observing=False,
    )
    if analysis.availability != "ready":
        failures.append(f"adapter availability is {analysis.availability}")
    if analysis.rule_version != fixture.rule_version:
        failures.append(f"rule version drift: {analysis.rule_version}")

    fractal_result = _compare_fractals(fixture.fractals, analysis.fractals)
    stroke_result = _compare_strokes(fixture.strokes, analysis.strokes)
    zone_result = _compare_zones(fixture.zones, analysis.zones)
    failures.extend(fractal_result.failures)
    failures.extend(stroke_result.failures)
    failures.extend(zone_result.failures)

    early_confirmations, confirmed_coordinate_drifts, replay_failures = _validate_truncation_stability(
        fixture
    )
    failures.extend(replay_failures)

    return GoldenFixtureResult(
        fixture_name=path.name,
        symbol=fixture.symbol,
        period=fixture.period,
        bar_count=len(fixture.bars),
        coverage_status="pass" if not failures else "fail",
        fractal_matches=fractal_result.matches,
        stroke_matches=stroke_result.matches,
        zone_matches=zone_result.matches,
        fractal_count=len(fixture.fractals),
        stroke_count=len(fixture.strokes),
        zone_count=len(fixture.zones),
        fractal_coordinate_mismatches=fractal_result.coordinate_mismatches,
        stroke_coordinate_mismatches=stroke_result.coordinate_mismatches,
        zone_coordinate_mismatches=zone_result.coordinate_mismatches,
        early_confirmations=early_confirmations,
        confirmed_coordinate_drifts=confirmed_coordinate_drifts,
        rule_version=fixture.rule_version,
        failures=tuple(failures),
    )


def write_report(results: list[GoldenFixtureResult], output: Path) -> None:
    lines = [
        "# Chanlun Golden Validation",
        "",
        f"Rule version: `{GOLDEN_RULE_VERSION}`",
        "",
        "| Fixture | Symbol | Period | Bars | Status | Fractals | Strokes | Zones | Early | Drifts | Rule |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    result.fixture_name,
                    result.symbol,
                    result.period,
                    str(result.bar_count),
                    result.coverage_status,
                    f"{result.fractal_matches}/{result.fractal_count}",
                    f"{result.stroke_matches}/{result.stroke_count}",
                    f"{result.zone_matches}/{result.zone_count}",
                    str(result.early_confirmations),
                    str(result.confirmed_coordinate_drifts),
                    result.rule_version,
                ]
            )
            + " |"
        )
    failing = [result for result in results if not result.passed]
    if failing:
        lines.extend(["", "## Failures", ""])
        for result in failing:
            lines.append(f"### {result.fixture_name}")
            lines.extend(f"- {failure}" for failure in result.failures)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate frozen Chanlun golden fixtures.")
    parser.add_argument("--fixture-dir", type=Path, default=GOLDEN_FIXTURE_DIR)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    paths = sorted(args.fixture_dir.glob("*.json"))
    results = [validate_golden_fixture(path) for path in paths]
    write_report(results, args.output)
    return 0 if results and all(result.passed for result in results) else 1


@dataclass(frozen=True)
class _ComparisonResult:
    matches: int
    coordinate_mismatches: int
    failures: tuple[str, ...]


def _validate_bars(bars: list[KlineBar]) -> None:
    if not bars:
        raise ValueError("bars must not be empty")
    previous: str | None = None
    for bar in bars:
        if previous is not None and bar.date <= previous:
            raise ValueError("bars must be in strictly increasing time order")
        if (
            bar.low > min(bar.open, bar.close)
            or bar.high < max(bar.open, bar.close)
            or bar.volume < 0
            or (bar.amount is not None and bar.amount < 0)
        ):
            raise ValueError("malformed bars")
        previous = bar.date


def _validate_confirmed_at(
    confirmed_at: dict[str, str],
    fractals: list[ChanlunFractal],
    strokes: list[ChanlunStroke],
    zones: list[ChanlunZone],
) -> None:
    expected_ids = {item.id for item in [*fractals, *strokes, *zones]}
    missing = sorted(expected_ids - confirmed_at.keys())
    if missing:
        raise ValueError(f"confirmed_at missing ids: {', '.join(missing)}")


def _compare_fractals(
    expected: list[ChanlunFractal], actual: list[ChanlunFractal]
) -> _ComparisonResult:
    actual_by_id = {item.id: item for item in actual}
    failures: list[str] = []
    mismatches = 0
    matches = 0
    for want in expected:
        got = actual_by_id.get(want.id)
        if got is None:
            failures.append(f"missing fractal {want.id}")
            continue
        fields_match = (
            got.occurred_at == want.occurred_at
            and _same_price(got.price, want.price)
            and got.mark == want.mark
            and got.status == want.status
        )
        if fields_match:
            matches += 1
        else:
            mismatches += 1
            failures.append(f"fractal coordinate mismatch {want.id}")
    extra = sorted(set(actual_by_id) - {item.id for item in expected})
    failures.extend(f"unexpected fractal {item_id}" for item_id in extra)
    return _ComparisonResult(matches, mismatches, tuple(failures))


def _compare_strokes(expected: list[ChanlunStroke], actual: list[ChanlunStroke]) -> _ComparisonResult:
    actual_by_id = {item.id: item for item in actual}
    failures: list[str] = []
    mismatches = 0
    matches = 0
    for want in expected:
        got = actual_by_id.get(want.id)
        if got is None:
            failures.append(f"missing stroke {want.id}")
            continue
        fields_match = (
            got.start_at == want.start_at
            and got.end_at == want.end_at
            and _same_price(got.start_price, want.start_price)
            and _same_price(got.end_price, want.end_price)
            and got.direction == want.direction
            and got.status == want.status
        )
        if fields_match:
            matches += 1
        else:
            mismatches += 1
            failures.append(f"stroke coordinate mismatch {want.id}")
    extra = sorted(set(actual_by_id) - {item.id for item in expected})
    failures.extend(f"unexpected stroke {item_id}" for item_id in extra)
    return _ComparisonResult(matches, mismatches, tuple(failures))


def _compare_zones(expected: list[ChanlunZone], actual: list[ChanlunZone]) -> _ComparisonResult:
    actual_by_id = {item.id: item for item in actual}
    failures: list[str] = []
    mismatches = 0
    matches = 0
    for want in expected:
        got = actual_by_id.get(want.id)
        if got is None:
            failures.append(f"missing zone {want.id}")
            continue
        fields_match = (
            got.start_at == want.start_at
            and got.end_at == want.end_at
            and _same_price(got.high, want.high)
            and _same_price(got.low, want.low)
            and got.virtual == want.virtual
            and got.status == want.status
        )
        if fields_match:
            matches += 1
        else:
            mismatches += 1
            failures.append(f"zone coordinate mismatch {want.id}")
    extra = sorted(set(actual_by_id) - {item.id for item in expected})
    failures.extend(f"unexpected zone {item_id}" for item_id in extra)
    return _ComparisonResult(matches, mismatches, tuple(failures))


def _validate_truncation_stability(fixture: GoldenFixture) -> tuple[int, int, list[str]]:
    failures: list[str] = []
    early_confirmations = 0
    coordinate_drifts = 0
    expected_by_id: dict[str, Any] = {
        item.id: item for item in [*fixture.fractals, *fixture.strokes, *fixture.zones]
    }
    confirmed_at = fixture.confirmed_at
    for size in range(3, len(fixture.bars) + 1):
        last_at = fixture.bars[size - 1].date
        analysis = ChanlunAdapter().analyze(
            fixture.symbol,
            period=fixture.period,
            bars=fixture.bars[:size],
            include_observing=False,
        )
        current_by_id: dict[str, Any] = {
            item.id: item for item in [*analysis.fractals, *analysis.strokes, *analysis.zones]
        }
        for item_id, want in expected_by_id.items():
            got = current_by_id.get(item_id)
            item_confirmed_at = confirmed_at[item_id]
            if got is not None and last_at < item_confirmed_at:
                early_confirmations += 1
                failures.append(f"early confirmation {item_id} at prefix {last_at}")
            if got is not None and last_at >= item_confirmed_at and not _same_structure(want, got):
                coordinate_drifts += 1
                failures.append(f"confirmed coordinate drift {item_id} at prefix {last_at}")
    return early_confirmations, coordinate_drifts, failures


def _same_structure(want: Any, got: Any) -> bool:
    if isinstance(want, ChanlunFractal) and isinstance(got, ChanlunFractal):
        return (
            got.occurred_at == want.occurred_at
            and _same_price(got.price, want.price)
            and got.mark == want.mark
            and got.status == want.status
        )
    if isinstance(want, ChanlunStroke) and isinstance(got, ChanlunStroke):
        return (
            got.start_at == want.start_at
            and got.end_at == want.end_at
            and _same_price(got.start_price, want.start_price)
            and _same_price(got.end_price, want.end_price)
            and got.direction == want.direction
            and got.status == want.status
        )
    if isinstance(want, ChanlunZone) and isinstance(got, ChanlunZone):
        return (
            got.start_at == want.start_at
            and got.end_at == want.end_at
            and _same_price(got.high, want.high)
            and _same_price(got.low, want.low)
            and got.virtual == want.virtual
            and got.status == want.status
        )
    return False


def _same_price(left: float, right: float) -> bool:
    return abs(left - right) <= PRICE_TOLERANCE


if __name__ == "__main__":
    sys.exit(main())
