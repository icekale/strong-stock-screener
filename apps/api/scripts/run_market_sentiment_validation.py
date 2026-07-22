from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.providers.tickflow import TickFlowDailyKlineProvider
from app.services.market_sentiment_percentile_service import (
    BENCHMARK_SYMBOL,
    KLINE_COUNT,
    filter_completed_daily_bars,
)
from app.services.market_sentiment_validation import SentimentValidationReport, validate_sentiment_percentile
from app.services.runtime_settings import effective_runtime_settings


MINIMUM_COMPLETE_BARS = 541


def main() -> None:
    args = _parse_args()
    try:
        report = run_validation(output_dir=args.output_dir, as_of=args.as_of)
    except Exception as exc:
        print(f"Market sentiment validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"JSON: {_output_dir(args.output_dir) / 'sentiment-percentile' / 'validation-v1.json'}")
    print(f"Markdown: {_output_dir(args.output_dir) / 'sentiment-percentile' / 'validation-v1.md'}")
    print(f"Validated samples: {len(report.samples)}")


def run_validation(
    *,
    provider: TickFlowDailyKlineProvider | None = None,
    output_dir: Path | str | None = None,
    as_of: str | None = None,
    now: datetime | None = None,
) -> SentimentValidationReport:
    actual_provider = provider or _provider()
    try:
        bars = actual_provider.get_klines(BENCHMARK_SYMBOL, count=KLINE_COUNT)
        completed = filter_completed_daily_bars(bars, now=now)
        selected = _as_of(completed, as_of)
        if len(selected) < MINIMUM_COMPLETE_BARS:
            raise ValueError(
                f"insufficient complete daily bars: need {MINIMUM_COMPLETE_BARS}, received {len(selected)}"
            )
        report = validate_sentiment_percentile(selected)
        _write_reports(report, _output_dir(output_dir) / "sentiment-percentile")
        return report
    finally:
        close = getattr(actual_provider, "close", None)
        if callable(close):
            close()


def _provider() -> TickFlowDailyKlineProvider:
    settings = get_settings()
    runtime = effective_runtime_settings(settings, settings.data_dir / "runtime_config.json")
    return TickFlowDailyKlineProvider(
        api_key=runtime.tickflow_api_key,
        base_url=runtime.tickflow_base_url,
        timeout_seconds=runtime.provider_timeout_seconds,
    )


def _as_of(bars: list[object], as_of: str | None) -> list[object]:
    if as_of is None:
        return bars
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError("--as-of must use YYYY-MM-DD") from exc
    return [bar for bar in bars if getattr(bar, "date") <= as_of]


def _output_dir(value: Path | str | None) -> Path:
    if value is not None:
        return Path(value)
    return get_settings().data_dir


def _write_reports(report: SentimentValidationReport, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    _atomic_write(
        output_dir / "validation-v1.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    _atomic_write(output_dir / "validation-v1.md", _markdown(report))


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _markdown(report: SentimentValidationReport) -> str:
    lines = [
        "# Market Sentiment Percentile Validation",
        "",
        f"- Model: {report.model_version}",
        f"- Benchmark: {report.benchmark_symbol}",
        f"- Data: {report.data_start} to {report.data_end}",
        f"- Scored samples: {len(report.samples)}",
        "",
        "| Level | Samples | Average duration | Horizon | Label samples | Mean return | Median return | Positive rate | Mean max drawdown |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for bucket in report.buckets:
        for window in bucket.windows:
            lines.append(
                "| {level} | {samples} | {duration} | {horizon} | {label_samples} | {mean_return} | {median_return} | {positive_rate} | {drawdown} |".format(
                    level=bucket.level,
                    samples=bucket.sample_count,
                    duration=_format(bucket.average_duration_days),
                    horizon=window.horizon,
                    label_samples=window.sample_count,
                    mean_return=_format(window.mean_return_pct),
                    median_return=_format(window.median_return_pct),
                    positive_rate=_format(window.positive_rate_pct),
                    drawdown=_format(window.mean_max_drawdown_pct),
                )
            )
    lines.extend(["", "## Conclusion", "", report.conclusion, "", "## Notes", ""])
    lines.extend(f"- {note}" for note in report.notes)
    return "\n".join(lines) + "\n"


def _format(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}%"


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate market sentiment percentile history.")
    parser.add_argument(
        "--output-dir",
        help="Base directory for sentiment-percentile/validation-v1.{json,md}.",
    )
    parser.add_argument(
        "--as-of",
        help="Only use complete bars on or before this YYYY-MM-DD date.",
    )
    return parser.parse_args(arguments)


if __name__ == "__main__":
    main()
