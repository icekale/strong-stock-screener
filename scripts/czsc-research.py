#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps/api"))

from app.config import get_settings  # noqa: E402
from app.services.chanlun.research_dataset import (  # noqa: E402
    ResearchDatasetBuilder,
    FrozenResearchDataset,
    _gc_disabled,
    load_frozen_dataset,
)
from app.services.chanlun.research_history import FreeStockDbResearchSource  # noqa: E402
from app.services.chanlun.research_score_cache import (  # noqa: E402
    ResearchScoreCache,
    ResearchScoreableUniverse,
    ResearchScoreRecord,
    apply_score_cache_gate,
    derive_scoreable_universe,
    pending_score_keys,
    score_cache_coverage,
)
from app.services.chanlun.research_report import (  # noqa: E402
    ValidationReportInput,
    verify_dataset_manifest,
    write_validation_report,
)
from app.services.chanlun.research_validation import (  # noqa: E402
    FrozenValidationDataset,
    PromotionMetrics,
    build_walk_forward_folds,
    evaluate_promotion,
    validate_frozen_dataset,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def main() -> int:
    parser = argparse.ArgumentParser(description="CZSC 历史研究数据与验证工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build-dataset", help="构建冻结 Parquet 数据集")
    build.add_argument("--start", required=True)
    build.add_argument("--end", required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--free-stockdb-base-url", default=None)
    build.add_argument("--free-stockdb-timeout", type=float, default=30.0)
    build.add_argument("--free-stockdb-workers", type=int, default=4)
    build.add_argument("--resume", action="store_true", help="从上次中断的分块进度继续")
    score = subparsers.add_parser("score", help="分批生成并断点续跑 rc8 评分缓存")
    score.add_argument("--dataset", type=Path, required=True)
    score.add_argument("--score-cache", type=Path, required=True)
    score.add_argument("--worker-python", required=True)
    score.add_argument("--batch-size", type=int, default=300)
    score.add_argument("--save-every", type=int, default=25)
    validate = subparsers.add_parser("validate", help="校验冻结数据集")
    validate.add_argument("--dataset", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    validate.add_argument("--round-trip-cost-bps", type=float, default=20)
    validate.add_argument("--worker-python", default=None)
    validate.add_argument("--score-cache", type=Path, default=None)
    args = parser.parse_args()
    if args.command == "build-dataset":
        return _build_dataset(args)
    if args.command == "score":
        return _score(args)
    return _validate(args)


def _build_dataset(args: argparse.Namespace) -> int:
    settings = get_settings()
    source = FreeStockDbResearchSource(
        base_url=args.free_stockdb_base_url or settings.auction_model_free_stockdb_base_url,
        timeout_seconds=args.free_stockdb_timeout,
        max_workers=args.free_stockdb_workers,
    )
    manifest = ResearchDatasetBuilder(source=source, resume=args.resume).build(
        start=args.start,
        end=args.end,
        output=args.output,
    )
    print(json.dumps({"dataset_id": manifest.dataset_id, "root": str(manifest.root)}, ensure_ascii=False))
    return 0


def _score(args: argparse.Namespace) -> int:
    if args.batch_size < 1 or args.save_every < 1:
        raise ValueError("batch size and save interval must be at least 1")
    manifest_path = args.dataset / "manifest.json"
    verify_dataset_manifest(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_id = str(manifest.get("dataset_id", ""))
    cache = ResearchScoreCache(args.score_cache, dataset_id=dataset_id)
    all_keys = [
        (str(sample["symbol"]), str(sample["decision_date"]))
        for sample in manifest.get("samples", [])
    ]
    universe = derive_scoreable_universe(
        samples=all_keys,
        partitions=manifest.get("partitions", []),
    )
    pending = pending_score_keys(
        list(universe.keys),
        completed_keys=cache.completed_keys(),
        limit=args.batch_size,
    )
    if not pending:
        print(json.dumps(_score_progress(cache, universe, dataset_id, 0), ensure_ascii=False))
        return 0

    settings = get_settings()
    worker = _build_worker(args.worker_python, settings)
    if worker is None:
        raise RuntimeError(f"rc8 worker interpreter not found: {args.worker_python}")
    frozen = load_frozen_dataset(args.dataset, selected_samples=set(pending))
    score_candidate = _build_score_candidate(frozen, worker)
    candidate_by_key = {
        (str(candidate["symbol"]), str(candidate["decision_date"])): candidate
        for candidates in frozen.candidates_by_date.values()
        for candidate in candidates
    }
    buffered: list[ResearchScoreRecord] = []
    scored_in_batch = 0
    try:
        for key in pending:
            candidate = candidate_by_key[key]
            score_value, eligible = score_candidate(candidate)
            buffered.append(
                ResearchScoreRecord(
                    symbol=key[0],
                    decision_date=key[1],
                    score=score_value,
                    eligible=eligible,
                )
            )
            scored_in_batch += 1
            if len(buffered) >= args.save_every:
                cache.save_many(buffered)
                buffered.clear()
        if buffered:
            cache.save_many(buffered)
    finally:
        worker.close()

    payload = _score_progress(cache, universe, dataset_id, scored_in_batch)
    payload["score_cache"] = str(args.score_cache)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _score_progress(
    cache: ResearchScoreCache,
    universe: ResearchScoreableUniverse,
    dataset_id: str,
    scored_in_batch: int,
) -> dict[str, object]:
    records = cache.load()
    completed_count = len(universe.keys.intersection(records))
    usable_count = sum(
        record.score is not None
        for key, record in records.items()
        if key in universe.keys
    )
    return {
        "status": "attempts_complete" if completed_count == len(universe.keys) else "partial",
        "dataset_id": dataset_id,
        "scored_in_batch": scored_in_batch,
        "dataset_candidate_count": universe.dataset_candidate_count,
        "scoreable_candidate_count": len(universe.keys),
        "completed_count": completed_count,
        "scored_count": usable_count,
        "scoreable_start": universe.start_date,
        "scoreable_end": universe.end_date,
    }


def _validate(args: argparse.Namespace) -> int:
    manifest_path = args.dataset / "manifest.json"
    verify_dataset_manifest(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    settings = get_settings()
    score_records = None
    coverage = None
    universe = None
    if args.score_cache is not None:
        score_records = ResearchScoreCache(
            args.score_cache,
            dataset_id=str(manifest.get("dataset_id", "")),
        ).load()
        all_keys = [
            (str(sample["symbol"]), str(sample["decision_date"]))
            for sample in manifest.get("samples", [])
        ]
        universe = derive_scoreable_universe(
            samples=all_keys,
            partitions=manifest.get("partitions", []),
        )
        coverage = score_cache_coverage(
            completed_count=len(universe.keys.intersection(score_records)),
            scored_count=sum(
                record.score is not None
                for key, record in score_records.items()
                if key in universe.keys
            ),
            total_count=len(universe.keys),
        )
    worker = None if score_records is not None else _build_worker(args.worker_python, settings)
    frozen = load_frozen_dataset(args.dataset, include_minute=worker is not None)
    if universe is not None:
        frozen = replace(
            frozen,
            candidates_by_date=_filter_candidates_by_keys(
                frozen.candidates_by_date,
                universe.keys,
            ),
        )
    score_candidate = (
        _build_cached_score_candidate(score_records)
        if score_records is not None
        else _build_score_candidate(frozen, worker)
    )
    try:
        with _gc_disabled():
            all_dates = sorted(frozen.candidates_by_date)
            result = validate_frozen_dataset(
                FrozenValidationDataset(
                    candidates_by_date=frozen.candidates_by_date,
                    daily_bars_by_symbol=frozen.daily_bars_by_symbol,
                ),
                decision_dates=all_dates,
                score_candidate=score_candidate,
                round_trip_cost_pct=args.round_trip_cost_bps / 100,
            )
            folds = _fold_payloads(frozen, score_candidate, args.round_trip_cost_bps)
        promotion = _promotion_for_result(result, folds)
        recommendation = promotion.recommendation
        failed_gates = promotion.failed_gates
        if coverage is not None:
            recommendation, failed_gates = apply_score_cache_gate(
                recommendation=recommendation,
                failed_gates=failed_gates,
                coverage=coverage,
            )
        scored_count = sum(sample.get("score") is not None for sample in result.samples)
        metrics = _metrics_payload(
            result,
            promotion,
            args.round_trip_cost_bps,
            worker is not None,
            scored_count=scored_count,
        )
        if coverage is not None:
            metrics.update(
                {
                    "research_status": coverage.status,
                    "score_cache_completed_count": coverage.completed_count,
                    "score_cache_scored_count": coverage.scored_count,
                    "score_cache_total_count": coverage.total_count,
                    "score_cache_coverage_pct": round(coverage.ratio * 100, 6),
                    "dataset_candidate_count": universe.dataset_candidate_count,
                    "scoreable_candidate_count": len(universe.keys),
                    "scoreable_start": universe.start_date,
                    "scoreable_end": universe.end_date,
                    "failed_gates": list(failed_gates),
                }
            )
        artifacts = write_validation_report(
            ValidationReportInput(
                manifest=manifest,
                metrics=metrics,
                folds=folds,
                samples=result.samples,
                recommendation=recommendation,
            ),
            output=args.output,
            generated_at=datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        )
    finally:
        if worker is not None:
            worker.close()
    print(
        json.dumps(
            {
                "status": "validated",
                "dataset_id": frozen.manifest.dataset_id,
                "recommendation": recommendation,
                "failed_gates": failed_gates,
                "report": str(artifacts.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _build_worker(worker_python: str | None, settings: object) -> object | None:
    from app.services.chanlun.rc8_client import Rc8WorkerClient

    if worker_python:
        path = Path(worker_python)
        if not path.is_absolute():
            path = (REPO_ROOT / path).absolute()
    else:
        configured = str(getattr(settings, "chanlun_rc8_python", ""))
        if not configured:
            return None
        path = Path(configured)
        if not path.is_absolute():
            path = (REPO_ROOT / "apps/api" / path).absolute()
    if not path.exists():
        return None
    return Rc8WorkerClient(
        python_path=path,
        worker_path=REPO_ROOT / "apps/api/app/services/chanlun/rc8_worker.py",
        hard_timeout_seconds=float(getattr(settings, "chanlun_rc8_hard_timeout_seconds", 10)),
    )


def _build_score_candidate(
    frozen: FrozenResearchDataset,
    worker: object | None,
) -> Any:
    if worker is None:
        return None
    from app.services.chanlun.research_catalog import map_raw_state
    from app.services.chanlun.research_protocol import build_research_request
    from app.services.chanlun.research_scoring import score_czsc_v2
    from app.services.chanlun.bars import aggregate_closed_intraday_bars
    from app.providers.tickflow import TickFlowIntradayBar

    cache: dict[tuple[str, str], tuple[int | None, bool]] = {}

    def score(candidate: Mapping[str, Any]) -> tuple[int | None, bool]:
        key = (str(candidate["symbol"]), str(candidate["decision_date"]))
        if key in cache:
            return cache[key]
        try:
            decision_date = date.fromisoformat(key[1])
            decision_at = datetime.combine(decision_date, time(15), tzinfo=SHANGHAI)
            daily = [
                bar
                for bar in frozen.daily_bars_by_symbol.get(key[0], ())
                if str(bar.date)[:10] <= key[1]
            ][-260:]
            minute = [
                bar
                for bar in frozen.minute_bars_by_symbol.get(key[0], ())
                if str(bar.date)[:10] <= key[1]
            ]
            raw_minute = [
                TickFlowIntradayBar(
                    timestamp=int(datetime.fromisoformat(bar.date).timestamp() * 1000),
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    amount=bar.amount or 0,
                )
                for bar in minute
            ]
            periods = {
                "1d": daily,
                "5m": aggregate_closed_intraday_bars(raw_minute, period="5m", now=decision_at)[-480:],
                "30m": aggregate_closed_intraday_bars(raw_minute, period="30m", now=decision_at)[-240:],
                "60m": aggregate_closed_intraday_bars(raw_minute, period="60m", now=decision_at)[-240:],
            }
            if any(len(periods[period]) < 3 for period in ("1d", "5m", "30m", "60m")):
                cache[key] = (None, False)
                return cache[key]
            request = build_research_request(
                key[0],
                periods,
                decision_at=decision_at,
                adjustment_mode=frozen.manifest.adjustment_mode,
            )
            response = worker.submit(request, priority=0).result(timeout=12)
            evidence = []
            for raw in response.current_states:
                mapped = map_raw_state(
                    symbol=request.symbol,
                    catalog_id=raw.catalog_id,
                    value_fields=raw.value_fields.model_dump(mode="python"),
                    raw_key=raw.raw_key,
                    raw_value=raw.raw_value,
                    occurred_at=raw.occurred_at,
                    last_closed_bar_at=raw.last_closed_bar_at,
                    input_snapshot_id=request.input_snapshot_id,
                    engine_version=response.engine_version,
                    period=raw.period,
                    higher_period=raw.higher_period,
                    lower_period=raw.lower_period,
                )
                if mapped is not None:
                    evidence.append(mapped)
            scored = score_czsc_v2(
                evidence=evidence,
                freshness={period: "fresh" for period in ("1d", "60m", "30m", "5m")},
            )
            cache[key] = (scored.score, scored.eligible)
        except Exception:
            cache[key] = (None, False)
        return cache[key]

    return score


def _build_cached_score_candidate(
    records: Mapping[tuple[str, str], ResearchScoreRecord],
) -> Any:
    def score(candidate: Mapping[str, Any]) -> tuple[int | None, bool]:
        key = (str(candidate["symbol"]), str(candidate["decision_date"]))
        record = records.get(key)
        if record is None:
            return None, False
        return record.score, record.eligible

    return score


def _filter_candidates_by_keys(
    candidates_by_date: Mapping[str, list[dict[str, Any]]],
    selected_keys: set[tuple[str, str]] | frozenset[tuple[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    filtered: dict[str, list[dict[str, Any]]] = {}
    for decision_date, candidates in candidates_by_date.items():
        selected = [
            candidate
            for candidate in candidates
            if (str(candidate.get("symbol", "")), decision_date) in selected_keys
        ]
        if selected:
            filtered[decision_date] = selected
    return filtered


def _fold_payloads(
    frozen: FrozenResearchDataset,
    score_candidate: Any,
    round_trip_cost_bps: float,
) -> list[dict[str, Any]]:
    folds = build_walk_forward_folds(
        date.fromisoformat(frozen.manifest.start[:10]),
        date.fromisoformat(frozen.manifest.end[:10]),
    )
    dataset = FrozenValidationDataset(
        candidates_by_date=frozen.candidates_by_date,
        daily_bars_by_symbol=frozen.daily_bars_by_symbol,
    )
    payloads: list[dict[str, Any]] = []
    for fold in folds:
        decision_dates = [
            decision_date
            for decision_date in frozen.candidates_by_date
            if fold.test_start.isoformat() <= decision_date <= fold.test_end.isoformat()
        ]
        fold_result = validate_frozen_dataset(
            dataset,
            decision_dates=decision_dates,
            score_candidate=score_candidate,
            round_trip_cost_pct=round_trip_cost_bps / 100,
        )
        top5 = fold_result.portfolios["top5"]
        payloads.append(
            {
                "development_start": fold.development_start.isoformat(),
                "development_end": fold.development_end.isoformat(),
                "validation_start": fold.validation_start.isoformat(),
                "validation_end": fold.validation_end.isoformat(),
                "test_start": fold.test_start.isoformat(),
                "test_end": fold.test_end.isoformat(),
                "sample_count": top5.v2_sample_count,
                "top5_v2_win_rate_pct": top5.v2_win_rate_pct,
                "top5_baseline_net_return_pct": top5.baseline_net_return_pct,
                "top5_v2_net_return_pct": top5.v2_net_return_pct,
                "top5_baseline_max_drawdown_pct": top5.baseline_max_drawdown_pct,
                "top5_v2_max_drawdown_pct": top5.v2_max_drawdown_pct,
                "leakage_passed": fold_result.leakage_passed,
            }
        )
    return payloads


def _promotion_for_result(result: Any, folds: list[dict[str, Any]]) -> object:
    top5 = result.portfolios["top5"]
    top10 = result.portfolios["top10"]
    recent = folds[-1] if folds else None
    recent_decay = 0.0
    if len(folds) > 1:
        prior_win_rate = sum(float(fold["top5_v2_win_rate_pct"]) for fold in folds[:-1]) / (len(folds) - 1)
        recent_decay = float(folds[-1]["top5_v2_win_rate_pct"]) - prior_win_rate
    metrics = PromotionMetrics(
        sample_count=top5.v2_sample_count,
        win_rate_pct=top5.v2_win_rate_pct,
        profit_loss_ratio=top5.v2_profit_loss_ratio,
        baseline_top5_net_return_pct=top5.baseline_net_return_pct,
        v2_top5_net_return_pct=top5.v2_net_return_pct,
        baseline_top10_net_return_pct=top10.baseline_net_return_pct,
        v2_top10_net_return_pct=top10.v2_net_return_pct,
        baseline_top5_max_drawdown_pct=top5.baseline_max_drawdown_pct,
        v2_top5_max_drawdown_pct=top5.v2_max_drawdown_pct,
        baseline_top10_max_drawdown_pct=top10.baseline_max_drawdown_pct,
        v2_top10_max_drawdown_pct=top10.v2_max_drawdown_pct,
        recent_six_month_return_pct=float(recent["top5_v2_net_return_pct"]) if recent else top5.v2_net_return_pct,
        recent_decay_pct=round(recent_decay, 6),
        leakage_passed=result.leakage_passed and all(bool(fold["leakage_passed"]) for fold in folds),
    )
    return evaluate_promotion(metrics)


def _metrics_payload(
    result: Any,
    promotion: object,
    round_trip_cost_bps: float,
    worker_available: bool,
    *,
    scored_count: int,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "round_trip_cost_bps": round_trip_cost_bps,
        "research_status": (
            "worker_scored"
            if worker_available and scored_count
            else "worker_no_usable_score"
            if worker_available
            else "worker_unavailable"
        ),
        "scored_sample_count": scored_count,
        "leakage_passed": result.leakage_passed,
        "failed_gates": list(promotion.failed_gates),
        "sample_count": result.portfolios["top5"].v2_sample_count,
        "win_rate_pct": result.portfolios["top5"].v2_win_rate_pct,
        "profit_loss_ratio": result.portfolios["top5"].v2_profit_loss_ratio,
    }
    for name, portfolio in result.portfolios.items():
        metrics[name] = asdict(portfolio)
    return metrics


if __name__ == "__main__":
    raise SystemExit(main())
