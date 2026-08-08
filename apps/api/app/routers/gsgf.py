"""gsgf 域路由（自 app.main 拆分）。"""

# ruff: noqa: F401,F403,F405  # 通配导入与复制的 import 存在冗余，聚焦可读性
from __future__ import annotations

from __future__ import annotations

from app.services.common import dedupe_symbols as _dedupe_symbols

import logging

from contextlib import asynccontextmanager

from datetime import date, datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request

from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    AuctionBackfillResponse,
    AuctionTimelineResponse,
    AuctionTop3ManualTradeSample,
    CapitalSummaryResponse,
    ChanlunAnalysisResponse,
    ChanlunAlertListResponse,
    ChanlunAlertRefreshResponse,
    ChanlunBacktestResponse,
    ChanlunPaperAccount,
    ChanlunPaperOrder,
    ChanlunReplayResponse,
    ChanlunBackfillRequest,
    ChanlunPeriod,
    ChanlunWorkspaceResponse,
    CzscResearchSnapshot,
    EtfRadarHistoryResponse,
    EtfRadarHoldersResponse,
    EtfRadarMethodologyResponse,
    EtfRadarOverviewResponse,
    EtfPriceHistoryResponse,
    EtfExcessFlowResponse,
    EtfActivityAlertResponse,
    EtfThreeFactorHistoryResponse,
    EtfThreeFactorResponse,
    GsgfBacktestSummary,
    GsgfRealCalibrationSummary,
    GsgfReviewSnapshotResponse,
    GsgfReviewSummary,
    GsgfTradePlan,
    HeatmapMarketKey,
    HeatmapPeriodKey,
    HeatmapSizeMode,
    HeatmapTrendFilter,
    KlineBar,
    ModelMaintenancePacket,
    ModelMaintenanceReport,
    ModelMaintenanceSuggestion,
    SectorWorkbenchMode,
    SectorWorkbenchCacheSummary,
    SectorWorkbenchScopeRequest,
    SectorWorkbenchResponse,
    SectorWorkbenchStatusResponse,
    SectorReplicaMode,
    SectorReplicaRadarResponse,
    SectorReplicaStocksResponse,
    SentimentDetailResponse,
    SentimentPercentileAnalysisResponse,
    SentimentPercentileResponse,
    ShortTermIntradaySentimentResponse,
    ShortTermIntradaySignalDigest,
    StockKlinePeriod,
    StockQuoteResponse,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
    SystemCacheClearResponse,
    SystemCacheSummary,
    SystemStatusResponse,
    ScreenRunRequest,
    IntradaySnapshotRequest,
    GsgfBacktestRequest,
    NotificationSendRequest,
    WatchlistPoolRequest,
    WatchlistPoolItemRequest,
    GsgfCalibrationRequest,
    GsgfTradePlanRequest,
    GsgfReviewRecheckRequest,
    ChanlunPaperOrderDraftRequest,
)

from app.providers.watchlist import (
    WatchlistItem,
    parse_watchlist_text,
    upsert_watchlist_item,
)

from app.services.intraday import IntradayMonitor

from app.services.capital_signal_sampler import CapitalSignalSampler

from app.services.etf_three_factor_sampler import EtfThreeFactorSampler

from app.services.etf_price_history import EtfPriceHistoryUnavailable

from app.services.huijin_etf_activity import CORE_ETFS

from app.services.chanlun.symbols import normalize_chanlun_symbol

from app.services.gsgf_backtest import summarize_gsgf_backtest

from app.services.gsgf_real_calibration import summarize_gsgf_real_calibration

from app.services.gsgf_trade_plan import build_gsgf_trade_plan

from app.services.ai_model_analysis import analyze_model_maintenance_packet

from app.services.auction_model import (
    AuctionModelDataError,
)

from app.services.auction_top3_live_confirmation import (
    build_auction_top3_live_confirmation,
)

from app.services.auction_top3_training import (
    generate_simulated_trade_samples,
    summarize_simulated_performance,
)

from app.services.auction_review import (
    build_auction_review_records,
    finalize_auction_records,
)

from app.services.auction_sampler import AuctionSnapshotSampler

from app.services.sector_workbench_sampler import (
    SectorWorkbenchSampler,
    is_sector_workbench_sample_window,
)

from app.services.market_sentiment_analysis import (
    pending_analysis_is_stale,
    sentiment_analysis_record_matches,
)

from app.services.runtime_settings import (
    SettingsUpdate,
    load_runtime_settings,
    public_settings_payload,
    save_runtime_settings,
)

from app.services.notification_channels import (
    DefaultSmtpClient,
    NotificationSendResult,
    NotificationSettings,
    send_notification_message,
)

from app.services.sector_workbench import (
    build_sector_workbench_from_radar,
    build_sector_workbench_response,
)

from app.services.sector_radar_replica import (
    build_sector_radar_replica_response,
    build_sector_replica_stock_rows,
    missing_replica_series_names,
    replica_theme_names_for_codes,
)

from app.services.sentiment_monitor import (
    SentimentMonitorConfig,
)

from app.services.sentiment_decision import build_sentiment_decision

from app.services.sentiment_watchlist import build_sentiment_watchlist_alerts

from app.services.short_term_sentiment import (
    build_missing_sentiment_summary,
    build_market_emotion_snapshot,
    build_sentiment_summary,
    build_short_term_intraday_sentiment,
    build_short_term_intraday_signal_digest,
)


from app.compat import *
from fastapi import APIRouter

router = APIRouter()

@router.post("/api/gsgf/backtest")
def create_gsgf_backtest(request: GsgfBacktestRequest) -> dict[str, object]:
    kline_provider = _kline_provider()
    bars_by_symbol: dict[str, list[KlineBar]] = {}
    failures = 0
    for symbol in _dedupe_symbols(request.symbols):
        try:
            bars_by_symbol[symbol] = kline_provider.get_klines(symbol, count=request.count)
        except Exception:
            failures += 1
    if not bars_by_symbol:
        raise HTTPException(status_code=503, detail="回测K线获取失败")
    result: GsgfBacktestSummary = summarize_gsgf_backtest(
        bars_by_symbol,
        windows=request.windows,
        min_history=request.min_history,
    )
    if failures:
        result.source_status.append(
            StrongStockSourceStatus(
                source=getattr(kline_provider, "source_name", "K线源"),
                status="failed",
                detail=f"{failures} 只股票K线获取失败",
            )
        )
    return result.model_dump(mode="json")


@router.post("/api/gsgf/calibration")
def create_gsgf_calibration(request: GsgfCalibrationRequest) -> dict[str, object]:
    try:
        result: GsgfRealCalibrationSummary = summarize_gsgf_real_calibration(
            candidate_provider=_candidate_provider(),
            kline_provider=_kline_provider(),
            trade_dates=request.trade_dates,
            windows=request.windows,
            scan_limit=request.scan_limit,
            kline_count=request.count,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result.scanned_count == 0:
        raise HTTPException(status_code=503, detail="校准候选池为空")
    return result.model_dump(mode="json")


@router.post("/api/gsgf/calibration/jobs")
def create_gsgf_calibration_job(request: GsgfCalibrationRequest) -> dict[str, object]:
    job = _background_job_store().create_calibration_job(
        lambda progress, should_cancel: summarize_gsgf_real_calibration(
            candidate_provider=_candidate_provider(),
            kline_provider=_kline_provider(),
            trade_dates=request.trade_dates,
            windows=request.windows,
            scan_limit=request.scan_limit,
            kline_count=request.count,
            progress=progress,
            should_cancel=should_cancel,
        )
    )
    return job.model_dump(mode="json")


@router.get("/api/gsgf/calibration/jobs/{job_id}")
def get_gsgf_calibration_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="calibration job not found") from exc
    return job.model_dump(mode="json")


@router.post("/api/gsgf/calibration/jobs/{job_id}/cancel")
def cancel_gsgf_calibration_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="calibration job not found") from exc
    return job.model_dump(mode="json")


@router.get("/api/gsgf/calibration/latest")
def get_latest_gsgf_calibration() -> dict[str, object]:
    result = _background_job_store().load_latest_calibration()
    if result is None:
        raise HTTPException(status_code=404, detail="no gsgf calibration result")
    return result.model_dump(mode="json")


@router.post("/api/gsgf/trade-plan")
def create_gsgf_trade_plan(request: GsgfTradePlanRequest) -> dict[str, object]:
    plan: GsgfTradePlan = build_gsgf_trade_plan(request.analysis)
    return plan.model_dump(mode="json")


@router.post("/api/gsgf/review/snapshots/latest")
def create_gsgf_review_snapshot_from_latest() -> dict[str, object]:
    result = _run_store().load_latest()
    if result is None:
        raise HTTPException(status_code=404, detail="no screen run")
    snapshot: GsgfReviewSnapshotResponse = _gsgf_review_store().persist_snapshot(
        result, dedupe=True
    )
    return snapshot.model_dump(mode="json")


@router.post("/api/gsgf/review/recheck")
def recheck_gsgf_review(request: GsgfReviewRecheckRequest) -> dict[str, object]:
    store = _gsgf_review_store()
    records = store.load_records()
    kline_provider = _kline_provider()
    bars_by_symbol: dict[str, list[KlineBar]] = {}
    for symbol in _dedupe_symbols([record.symbol for record in records]):
        try:
            bars_by_symbol[symbol] = kline_provider.get_klines(symbol, count=request.count)
        except Exception:
            bars_by_symbol[symbol] = []
    summary: GsgfReviewSummary = store.recheck_snapshots(bars_by_symbol, windows=request.windows)
    store.save_latest_summary(summary)
    return summary.model_dump(mode="json")


@router.get("/api/gsgf/review/latest")
def get_latest_gsgf_review() -> dict[str, object]:
    summary = _gsgf_review_store().load_latest_summary()
    if summary is None:
        raise HTTPException(status_code=404, detail="no gsgf review summary")
    return summary.model_dump(mode="json")


@router.get("/api/gsgf/health")
def get_gsgf_model_health() -> dict[str, object]:
    health = _gsgf_model_health()
    return health.model_dump(mode="json")


@router.post("/api/model-maintenance/packets/generate", response_model=ModelMaintenancePacket)
def generate_model_maintenance_packet(request: Request) -> ModelMaintenancePacket:
    return _build_and_save_model_maintenance_packet(packet_base_url=_request_base_url(request))


@router.get("/api/model-maintenance/packets/latest", response_model=ModelMaintenancePacket | None)
def get_latest_model_maintenance_packet() -> ModelMaintenancePacket | None:
    return _model_maintenance_store().load_latest_packet()


@router.get("/api/model-maintenance/packets/{packet_id}", response_model=ModelMaintenancePacket)
def get_model_maintenance_packet(packet_id: str) -> ModelMaintenancePacket:
    packet = _model_maintenance_store().load_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="模型维护数据包不存在")
    return packet


@router.post("/api/model-maintenance/analyze", response_model=ModelMaintenanceReport)
def analyze_model_maintenance(request: Request) -> ModelMaintenanceReport:
    store = _model_maintenance_store()
    packet = store.load_latest_packet()
    if packet is None:
        packet = _build_and_save_model_maintenance_packet(
            packet_base_url=_request_base_url(request)
        )
    return store.save_report(
        analyze_model_maintenance_packet(
            packet,
            _effective_settings().ai_analysis,
            http_client=getattr(app_state().state, "model_maintenance_http_client", None),
        )
    )


@router.get("/api/model-maintenance/reports/latest", response_model=ModelMaintenanceReport | None)
def get_latest_model_maintenance_report() -> ModelMaintenanceReport | None:
    return _model_maintenance_store().load_latest_report()


@router.get("/api/model-maintenance/reports", response_model=list[ModelMaintenanceReport])
def list_model_maintenance_reports(limit: int = 20) -> list[ModelMaintenanceReport]:
    return _model_maintenance_store().list_reports(limit)


@router.post(
    "/api/model-maintenance/suggestions/{suggestion_id}/accept",
    response_model=ModelMaintenanceSuggestion,
)
def accept_model_maintenance_suggestion(suggestion_id: str) -> ModelMaintenanceSuggestion:
    try:
        return _model_maintenance_store().update_suggestion_status(suggestion_id, "accepted")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="建议不存在") from exc


@router.post(
    "/api/model-maintenance/suggestions/{suggestion_id}/ignore",
    response_model=ModelMaintenanceSuggestion,
)
def ignore_model_maintenance_suggestion(suggestion_id: str) -> ModelMaintenanceSuggestion:
    try:
        return _model_maintenance_store().update_suggestion_status(suggestion_id, "ignored")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="建议不存在") from exc


@router.post(
    "/api/model-maintenance/suggestions/{suggestion_id}/snooze",
    response_model=ModelMaintenanceSuggestion,
)
def snooze_model_maintenance_suggestion(suggestion_id: str) -> ModelMaintenanceSuggestion:
    try:
        return _model_maintenance_store().update_suggestion_status(suggestion_id, "snoozed")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="建议不存在") from exc


@router.get("/api/model-maintenance/auction-top3/training/summary")
def get_auction_top3_training_summary() -> dict[str, object]:
    settings = _effective_settings().auction_top3_training
    summary = _auction_top3_training_store().training_summary(
        training_window_days=settings.training_window_days,
        include_manual_training=settings.include_manual_trade_samples_in_training,
        enabled=settings.record_signal_samples,
        initial_capital=settings.simulated_initial_capital,
    )
    return summary.model_dump(mode="json")


@router.get("/api/model-maintenance/auction-top3/training/performance")
def get_auction_top3_training_performance() -> dict[str, object]:
    settings = _effective_settings().auction_top3_training
    trades = _auction_top3_training_store().load_simulated_trades()
    response = summarize_simulated_performance(
        trades,
        initial_capital=settings.simulated_initial_capital,
        portfolio_id="default",
    )
    return response.model_dump(mode="json")


@router.post("/api/model-maintenance/auction-top3/training/generate")
def generate_auction_top3_training_samples(trade_date: str | None = None) -> dict[str, object]:
    settings = _effective_settings().auction_top3_training
    store = _auction_top3_training_store()
    signals = store.load_signal_samples(trade_date)
    bars_by_symbol: dict[str, list[KlineBar]] = {}
    provider = _kline_provider()
    for symbol in _dedupe_symbols([sample.symbol for sample in signals]):
        try:
            bars_by_symbol[symbol] = provider.get_klines(symbol, count=260)
        except Exception:
            bars_by_symbol[symbol] = []
    trades = generate_simulated_trade_samples(
        signals,
        bars_by_symbol,
        initial_capital=settings.simulated_initial_capital,
        position_pct=settings.simulated_position_pct,
    )
    saved = store.upsert_simulated_trades(trades)
    performance = summarize_simulated_performance(
        store.load_simulated_trades(),
        initial_capital=settings.simulated_initial_capital,
        portfolio_id="default",
    )
    store.save_performance_points(performance.points)
    return {"saved_count": len(saved), "performance": performance.model_dump(mode="json")}


@router.post(
    "/api/model-maintenance/auction-top3/manual-trades", response_model=AuctionTop3ManualTradeSample
)
def save_auction_top3_manual_trade(
    sample: AuctionTop3ManualTradeSample,
) -> AuctionTop3ManualTradeSample:
    return _auction_top3_training_store().upsert_manual_trade(sample)


@router.patch(
    "/api/model-maintenance/auction-top3/manual-trades/{sample_id}",
    response_model=AuctionTop3ManualTradeSample,
)
def update_auction_top3_manual_trade(
    sample_id: str,
    sample: AuctionTop3ManualTradeSample,
) -> AuctionTop3ManualTradeSample:
    if sample.sample_id != sample_id:
        raise HTTPException(status_code=422, detail="sample_id mismatch")
    return _auction_top3_training_store().upsert_manual_trade(sample)

