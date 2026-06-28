from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.providers.recent_limit_up_candidates import RecentLimitUpCandidateProvider
from app.providers.tickflow import TickFlowDailyKlineProvider
from app.services.gsgf_real_calibration import summarize_gsgf_real_calibration
from app.services.runtime_settings import effective_runtime_settings


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    runtime = effective_runtime_settings(settings, settings.data_dir / "runtime_config.json")
    candidate_provider = RecentLimitUpCandidateProvider.from_akshare()
    kline_provider = TickFlowDailyKlineProvider(
        api_key=runtime.tickflow_api_key,
        base_url=runtime.tickflow_base_url,
        timeout_seconds=runtime.provider_timeout_seconds,
    )
    try:
        summary = summarize_gsgf_real_calibration(
            candidate_provider=candidate_provider,
            kline_provider=kline_provider,
            trade_dates=args.trade_dates,
            windows=args.windows,
            scan_limit=args.scan_limit,
            kline_count=args.kline_count,
            progress=None if args.quiet else print,
        )
    finally:
        kline_provider.close()

    payload = summary.model_dump(mode="json")
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path = output.with_suffix(".md")
        markdown_path.write_text(_markdown(summary.model_dump(mode="json")), encoding="utf-8")
        print(f"JSON: {output}")
        print(f"Markdown: {markdown_path}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real TickFlow GSGF calibration samples.")
    parser.add_argument(
        "--trade-date",
        dest="trade_dates",
        action="append",
        required=True,
        help="Sample trade date, e.g. 2026-06-12. Repeat for multiple dates.",
    )
    parser.add_argument(
        "--window",
        dest="windows",
        action="append",
        type=int,
        default=[],
        help="Forward review window in sessions. Defaults to 1/3/5/10.",
    )
    parser.add_argument("--scan-limit", type=int, default=80, help="Candidates per sample date.")
    parser.add_argument("--kline-count", type=int, default=260, help="Daily bars requested per symbol.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    args = parser.parse_args()
    if not args.windows:
        args.windows = [1, 3, 5, 10]
    return args


def _markdown(payload: dict[str, object]) -> str:
    lines = [
        "# GSGF Real TickFlow Calibration",
        "",
        f"- 样本日: {', '.join(payload.get('trade_dates', []))}",
        f"- 扫描候选: {payload.get('scanned_count')}",
        f"- 目标样本: {payload.get('target_sample_count')}",
        f"- 跳过样本: {payload.get('skipped_count')}",
        "",
        "| 信号桶 | 样本数 | 窗口 | 命中率 | 平均收益 | 平均最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_bucket_rows(payload.get("buckets", [])))
    lines.extend(
        [
            "",
            "## 唯一股票口径",
            "",
            "| 信号桶 | 样本数 | 窗口 | 命中率 | 平均收益 | 平均最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_bucket_rows(payload.get("unique_symbol_buckets", [])))
    lines.extend(["", "## 样例", ""])
    for bucket in payload.get("buckets", []):
        if not isinstance(bucket, dict):
            continue
        examples = bucket.get("examples", [])
        if not isinstance(examples, list) or not examples:
            continue
        lines.append(f"### {bucket.get('name', '')}")
        for example in examples:
            if not isinstance(example, dict):
                continue
            lines.append(
                "- {date} {symbol} {name} status={status} score={score} setup={setup} confirm={confirm} entry={entry}".format(
                    date=example.get("trade_date", ""),
                    symbol=example.get("symbol", ""),
                    name=example.get("name", ""),
                    status=example.get("status", ""),
                    score=example.get("score", ""),
                    setup=example.get("setup_type") or "-",
                    confirm=example.get("confirm_type") or "-",
                    entry=example.get("entry_close") or "-",
                )
            )
        lines.append("")
    return "\n".join(lines)


def _bucket_rows(buckets: object) -> list[str]:
    lines: list[str] = []
    if not isinstance(buckets, list):
        return lines
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        for stat in bucket.get("windows", []):
            if not isinstance(stat, dict):
                continue
            lines.append(
                "| {name} | {samples} | {window} | {hit_rate} | {ret} | {drawdown} |".format(
                    name=bucket.get("name", ""),
                    samples=bucket.get("sample_count", 0),
                    window=stat.get("window_days", ""),
                    hit_rate=_fmt_pct(stat.get("hit_rate")),
                    ret=_fmt_pct(stat.get("avg_return_pct")),
                    drawdown=_fmt_pct(stat.get("avg_max_drawdown_pct")),
                )
            )
    return lines


def _fmt_pct(value: object) -> str:
    if value is None:
        return "-"
    return f"{value}%"


if __name__ == "__main__":
    main()
