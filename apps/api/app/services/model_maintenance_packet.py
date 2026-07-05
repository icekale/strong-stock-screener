from __future__ import annotations

from typing import Any

from app.models import (
    AuctionModelTop3Response,
    AuctionTop3TrainingSummary,
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
    auction_top3_run: AuctionModelTop3Response | None = None,
    auction_top3_training_summary: AuctionTop3TrainingSummary | None = None,
    packet_base_url: str | None = None,
) -> ModelMaintenancePacket:
    items = latest_screen_run.items if latest_screen_run else []
    first_gsgf = next((item.gsgf for item in items if item.gsgf is not None), None)
    packet_id = new_model_maintenance_id("packet")
    return ModelMaintenancePacket(
        packet_id=packet_id,
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
        model_sections=_model_sections(
            latest_screen_run,
            auction_top3_run,
            auction_top3_training_summary,
        ),
        packet_url=_packet_url(packet_base_url, packet_id),
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


def _packet_url(packet_base_url: str | None, packet_id: str) -> str | None:
    if not packet_base_url:
        return None
    return f"{packet_base_url.rstrip('/')}/model-maintenance/packets/{packet_id}"


def _model_sections(
    screen_run: StrongStockScreeningResult | None,
    auction_top3_run: AuctionModelTop3Response | None,
    auction_top3_training_summary: AuctionTop3TrainingSummary | None,
) -> dict[str, Any]:
    return {
        "gsgf": _gsgf_section(screen_run),
        "auction_top3": _auction_top3_section(auction_top3_run),
        "auction_top3_training": _auction_top3_training_section(auction_top3_training_summary),
    }


def _gsgf_section(result: StrongStockScreeningResult | None) -> dict[str, Any]:
    if result is None:
        return {
            "available": False,
            "selected_count": 0,
            "risk_item_count": 0,
            "observation_item_count": 0,
            "notes": ["暂无选股运行记录，本次未纳入股是股非模型样本。"],
        }
    return {
        "available": True,
        "trade_date": result.trade_date,
        "model_version": result.gsgf_model_version,
        "sort_version": result.sort_version,
        "selected_count": len(result.items),
        "risk_item_count": len(result.watchlist_risk_items),
        "observation_item_count": len(result.gsgf_observation_items),
        "generated_at": result.generated_at,
    }


def _auction_top3_section(result: AuctionModelTop3Response | None) -> dict[str, Any]:
    if result is None:
        return {
            "enabled": True,
            "available": False,
            "items": [],
            "notes": ["竞价 Top3 无缓存，本次未纳入模型维护。"],
        }
    selected = [item for item in result.items if item.bucket == "selected"]
    watch = [item for item in result.items if item.bucket == "watch"]
    return {
        "enabled": True,
        "available": True,
        "trade_date": result.trade_date,
        "feature_end_date": result.feature_end_date,
        "model_version": result.model_version,
        "feature_version": result.feature_version,
        "guard_rule": result.guard_rule,
        "mode": result.mode,
        "cache_status": result.cache_status,
        "generated_at": result.generated_at,
        "top_count": len(selected),
        "watch_count": len(watch),
        "backtest_summary": result.backtest.model_dump(mode="json") if result.backtest else None,
        "items": [item.model_dump(mode="json") for item in result.items[:10]],
        "source_status": [status.model_dump(mode="json") for status in result.source_status],
        "notes": [],
    }


def _auction_top3_training_section(summary: AuctionTop3TrainingSummary | None) -> dict[str, Any]:
    if summary is None:
        return {
            "enabled": False,
            "signal_sample_count": 0,
            "simulated_trade_sample_count": 0,
            "manual_trade_sample_count": 0,
            "quality_notes": ["暂无竞价 Top3 训练摘要。"],
        }
    return summary.model_dump(mode="json")
