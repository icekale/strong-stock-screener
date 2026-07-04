from __future__ import annotations

from typing import Any

from app.models import (
    GsgfRealCalibrationSummary,
    GsgfReviewSummary,
    ModelMaintenancePacket,
    StrongStockScreeningResult,
    StrongStockSourceStatus,
)
from app.services.model_maintenance_store import new_model_maintenance_id


def build_model_maintenance_packet(
    *,
    trade_date: str | None,
    latest_screen_run: StrongStockScreeningResult | None,
    review_summary: GsgfReviewSummary | None,
    calibration_summary: GsgfRealCalibrationSummary | None,
    source_status: list[StrongStockSourceStatus],
) -> ModelMaintenancePacket:
    items = latest_screen_run.items if latest_screen_run else []
    first_gsgf = next((item.gsgf for item in items if item.gsgf is not None), None)
    return ModelMaintenancePacket(
        packet_id=new_model_maintenance_id("packet"),
        trade_date=trade_date or (latest_screen_run.trade_date if latest_screen_run else None),
        model_version=first_gsgf.model_version if first_gsgf else None,
        screen_strategy=latest_screen_run.strategy if latest_screen_run else None,
        screen_params=_screen_params(latest_screen_run),
        source_status=source_status,
        latest_screen_run=_screen_run_summary(latest_screen_run),
        review_summary=_review_summary(review_summary),
        calibration_summary=_calibration_summary(calibration_summary),
        false_positive_cases=_false_positive_cases(latest_screen_run),
        data_quality_notes=_data_quality_notes(source_status),
    )


def _screen_params(result: StrongStockScreeningResult | None) -> dict[str, Any]:
    if result is None:
        return {}
    return {
        "strategy": result.strategy,
        "strong_model_version": result.strong_model_version,
        "gsgf_model_version": result.gsgf_model_version,
        "sort_version": result.sort_version,
    }


def _screen_run_summary(result: StrongStockScreeningResult | None) -> dict[str, Any]:
    if result is None:
        return {}
    return {
        "trade_date": result.trade_date,
        "selected_count": len(result.items),
        "risk_item_count": len(result.watchlist_risk_items),
        "observation_item_count": len(result.gsgf_observation_items),
        "sort_version": result.sort_version,
        "strong_model_version": result.strong_model_version,
        "gsgf_model_version": result.gsgf_model_version,
        "generated_at": result.generated_at,
    }


def _review_summary(summary: GsgfReviewSummary | None) -> dict[str, Any]:
    if summary is None:
        return {}
    return {
        "windows": summary.windows,
        "record_count": summary.record_count,
        "generated_at": summary.generated_at,
        "buckets": [bucket.model_dump() for bucket in summary.buckets[:20]],
    }


def _calibration_summary(summary: GsgfRealCalibrationSummary | None) -> dict[str, Any]:
    if summary is None:
        return {}
    return {
        "trade_dates": summary.trade_dates,
        "windows": summary.windows,
        "scanned_count": summary.scanned_count,
        "target_sample_count": summary.target_sample_count,
        "skipped_count": summary.skipped_count,
        "generated_at": summary.generated_at,
        "buckets": [bucket.model_dump() for bucket in summary.buckets[:20]],
        "diagnostic_groups": [group.model_dump() for group in summary.diagnostic_groups[:20]],
        "unique_symbol_buckets": [bucket.model_dump() for bucket in summary.unique_symbol_buckets[:20]],
    }


def _false_positive_cases(result: StrongStockScreeningResult | None) -> list[dict[str, Any]]:
    if result is None:
        return []
    output: list[dict[str, Any]] = []
    for item in result.items[:20]:
        if item.risk_flags or item.negative_news_flags:
            output.append(
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "score": item.score,
                    "risk_flags": item.risk_flags[:5],
                    "negative_news_flags": item.negative_news_flags[:5],
                    "gsgf_status": item.gsgf.final_status if item.gsgf else None,
                }
            )
    return output


def _data_quality_notes(source_status: list[StrongStockSourceStatus]) -> list[str]:
    notes: list[str] = []
    for status in source_status:
        if status.status != "success":
            notes.append(f"{status.source}: {status.status} · {status.detail}")
    return notes
