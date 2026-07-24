from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from pathlib import Path
import statistics
import sys

import pytest

from app.models import KlineBar
from app.services.market_sentiment_validation import validate_sentiment_percentile
from tests.market_sentiment_fixtures import make_test_bar, make_test_bars


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_market_sentiment_validation as validation_cli


class FakeProvider:
    source_name = "fixture TickFlow"

    def __init__(self, bars: list[KlineBar], error: Exception | None = None) -> None:
        self.bars = bars
        self.error = error
        self.calls: list[tuple[str, int]] = []
        self.closed = False

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.calls.append((symbol, count))
        if self.error is not None:
            raise self.error
        return self.bars[-count:]

    def close(self) -> None:
        self.closed = True


def _sample(report: object, trade_date: str) -> dict[str, object]:
    samples = getattr(report, "samples")
    return next(sample for sample in samples if sample["trade_date"] == trade_date)


def test_validation_reports_fixed_level_buckets_and_forward_metrics() -> None:
    bars = make_test_bars(1020)

    report = validate_sentiment_percentile(bars)

    assert report.model_version == "market-sentiment-percentile-v2"
    assert report.horizons == [5, 10, 20]
    assert sum(bucket.sample_count for bucket in report.buckets) == len(report.samples)
    assert report.buckets[0].windows[0].future_data_end <= report.data_end
    assert [bucket.level for bucket in report.buckets] == ["冰点", "偏冷", "中性", "偏热", "过热"]

    sample = report.samples[0]
    bar_index = next(index for index, bar in enumerate(bars) if bar.date == sample["trade_date"])
    expected_return = (bars[bar_index + 5].close / bars[bar_index].close - 1) * 100
    expected_drawdown = (
        min(bar.close for bar in bars[bar_index + 1 : bar_index + 6]) / bars[bar_index].close - 1
    ) * 100
    assert sample["forward_returns"]["5"] == pytest.approx(expected_return)
    assert sample["max_drawdowns"]["5"] == pytest.approx(expected_drawdown)

    bucket = next(bucket for bucket in report.buckets if bucket.sample_count)
    returns = [
        sample["forward_returns"]["5"]
        for sample in report.samples
        if sample["level"] == bucket.level and "5" in sample["forward_returns"]
    ]
    drawdowns = [
        sample["max_drawdowns"]["5"]
        for sample in report.samples
        if sample["level"] == bucket.level and "5" in sample["max_drawdowns"]
    ]
    window = next(window for window in bucket.windows if window.horizon == 5)
    assert window.sample_count == len(returns)
    assert window.mean_return_pct == pytest.approx(statistics.mean(returns))
    assert window.median_return_pct == pytest.approx(statistics.median(returns))
    assert window.positive_rate_pct == pytest.approx(sum(value > 0 for value in returns) / len(returns) * 100)
    assert window.mean_max_drawdown_pct == pytest.approx(statistics.mean(drawdowns))


def test_scores_are_invariant_to_future_mutation_while_forward_label_changes() -> None:
    bars = make_test_bars(1020)
    target_index = 700
    target_date = bars[target_index].date
    baseline = validate_sentiment_percentile(bars)
    future = make_test_bar(target_index + 5, close=500, amount=9_000_000_000)
    mutated = [*bars]
    mutated[target_index + 5] = future

    changed = validate_sentiment_percentile(mutated)

    baseline_sample = _sample(baseline, target_date)
    changed_sample = _sample(changed, target_date)
    assert changed_sample["score"] == baseline_sample["score"]
    assert changed_sample["forward_returns"]["5"] != baseline_sample["forward_returns"]["5"]


def test_level_duration_uses_contiguous_scored_days() -> None:
    report = validate_sentiment_percentile(make_test_bars(1020))
    runs: dict[str, list[int]] = {level: [] for level in ("冰点", "偏冷", "中性", "偏热", "过热")}
    previous_level: str | None = None
    duration = 0
    for sample in report.samples:
        level = sample["level"]
        if level == previous_level:
            duration += 1
            continue
        if previous_level is not None:
            runs[previous_level].append(duration)
        previous_level = level
        duration = 1
    if previous_level is not None:
        runs[previous_level].append(duration)

    for bucket in report.buckets:
        expected = statistics.mean(runs[bucket.level]) if runs[bucket.level] else None
        assert bucket.average_duration_days == expected


def test_insufficient_samples_produce_empty_metrics_and_explicit_notes() -> None:
    report = validate_sentiment_percentile(make_test_bars(518))

    assert report.samples == []
    assert all(bucket.sample_count == 0 for bucket in report.buckets)
    assert all(window.sample_count == 0 for bucket in report.buckets for window in bucket.windows)
    assert all(window.mean_return_pct is None for bucket in report.buckets for window in bucket.windows)
    assert any("insufficient" in note.lower() for note in report.notes)


def test_cli_filters_incomplete_and_as_of_bars_then_writes_atomic_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = make_test_bars(1020)
    bars[-1] = bars[-1].model_copy(update={"date": "2026-07-22"})
    bars[-2] = bars[-2].model_copy(update={"date": "2026-07-21"})
    provider = FakeProvider(bars)
    replacements: list[Path] = []
    original_replace = Path.replace

    def record_replace(path: Path, target: Path) -> Path:
        replacements.append(path)
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", record_replace)
    report = validation_cli.run_validation(
        provider=provider,
        output_dir=tmp_path,
        as_of="2026-07-21",
        now=datetime.fromisoformat("2026-07-22T15:09:00+08:00"),
    )

    output_dir = tmp_path / "sentiment-percentile"
    assert provider.calls == [("000985.SH", 1020)]
    assert provider.closed
    assert report.data_end == "2026-07-21"
    assert (output_dir / "validation-v1.json").is_file()
    assert (output_dir / "validation-v1.md").is_file()
    assert {path.name for path in replacements} == {"validation-v1.json.tmp", "validation-v1.md.tmp"}
    assert not list(output_dir.glob("*.tmp"))


def test_cli_parser_supports_output_dir_and_as_of() -> None:
    args = validation_cli._parse_args(["--output-dir", "/tmp/out", "--as-of", "2026-07-21"])

    assert args.output_dir == "/tmp/out"
    assert args.as_of == "2026-07-21"


@pytest.mark.parametrize("error", [RuntimeError("offline"), None])
def test_cli_exits_nonzero_for_provider_failure_or_insufficient_bars(
    error: Exception | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeProvider(make_test_bars(519), error=error)
    monkeypatch.setattr(
        validation_cli,
        "_parse_args",
        lambda: Namespace(output_dir=None, as_of=None),
    )
    monkeypatch.setattr(validation_cli, "_provider", lambda: provider)

    with pytest.raises(SystemExit) as exc_info:
        validation_cli.main()

    assert exc_info.value.code == 1
    assert provider.closed
