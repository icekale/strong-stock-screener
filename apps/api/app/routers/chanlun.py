"""chanlun 域路由（自 app.main 拆分）。"""

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

@router.get("/api/chanlun/screening/shadow/jobs/{job_id}")
def get_chanlun_shadow_screening_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="CZSC shadow job not found") from exc
    batch = _chanlun_shadow_scheduler().get(job_id)
    return {
        "job": job.model_dump(mode="json"),
        "batch": batch.model_dump(mode="json") if batch is not None else None,
    }


@router.get("/api/chanlun/stocks/{symbol}/analysis")
def get_chanlun_analysis(
    symbol: str,
    period: ChanlunPeriod = "1d",
    lookback: int = 220,
    include_observing: bool = False,
) -> ChanlunAnalysisResponse:
    _validate_chanlun_lookback(period, lookback)
    try:
        return _chanlun_analysis_service().analysis(
            symbol,
            period=period,
            lookback=lookback,
            include_observing=include_observing,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/chanlun/stocks/{symbol}/workspace")
def get_chanlun_workspace(symbol: str, lookback: int = 220) -> ChanlunWorkspaceResponse:
    _validate_chanlun_lookback("1d", lookback)
    try:
        return _chanlun_analysis_service().workspace(symbol, lookback=lookback)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/api/chanlun/stocks/{symbol}/research-signals",
    response_model=CzscResearchSnapshot,
)
def get_chanlun_research_signals(
    symbol: str,
    lookback: int = 220,
) -> CzscResearchSnapshot:
    _validate_chanlun_lookback("1d", lookback)
    normalized_symbol = normalize_chanlun_symbol(symbol) or symbol.strip().upper()
    return _chanlun_research_service().get(normalized_symbol, lookback)


@router.get("/api/chanlun/stocks/{symbol}/replays")
def get_chanlun_replay(
    symbol: str,
    period: ChanlunPeriod = "1d",
    lookback: int = 220,
) -> ChanlunReplayResponse:
    _validate_chanlun_lookback(period, lookback)
    try:
        return _chanlun_analysis_service().replay(symbol, period=period, lookback=lookback)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/chanlun/stocks/{symbol}/backtests")
def get_chanlun_backtest(
    symbol: str,
    period: ChanlunPeriod = "1d",
    lookback: int = 220,
    horizons: str = "1,3,5,10",
) -> ChanlunBacktestResponse:
    _validate_chanlun_lookback(period, lookback)
    try:
        return _chanlun_analysis_service().backtest(
            symbol,
            period=period,
            lookback=lookback,
            horizons=_parse_chanlun_backtest_horizons(horizons),
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/chanlun/alerts")
def list_chanlun_alerts(symbol: str | None = None, limit: int = 100) -> ChanlunAlertListResponse:
    return _chanlun_alert_service().list(symbol=symbol, limit=limit)


@router.post("/api/chanlun/stocks/{symbol}/alerts/refresh")
def refresh_chanlun_alerts(
    symbol: str,
    period: ChanlunPeriod = "1d",
    lookback: int = 220,
) -> ChanlunAlertRefreshResponse:
    _validate_chanlun_lookback(period, lookback)
    try:
        return _chanlun_alert_service().refresh(symbol, period=period, lookback=lookback)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/api/chanlun/stocks/{symbol}/paper-orders/drafts")
def create_chanlun_paper_order_draft(
    symbol: str,
    request: ChanlunPaperOrderDraftRequest,
    lookback: int = 220,
) -> ChanlunPaperOrder:
    _validate_chanlun_lookback("1d", lookback)
    try:
        return _chanlun_paper_order_service().create_draft(
            symbol,
            quantity=request.quantity,
            lookback=lookback,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/api/chanlun/paper-orders/{order_id}/approve")
def approve_chanlun_paper_order(order_id: str) -> ChanlunPaperOrder:
    try:
        return _chanlun_paper_order_service().approve(order_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="模拟订单不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/chanlun/paper-orders/{order_id}/fill")
def fill_chanlun_paper_order(order_id: str) -> ChanlunPaperOrder:
    try:
        return _chanlun_paper_order_service().fill(order_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="模拟订单不存在") from exc
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"更新模拟成交失败: {exc.__class__.__name__}"
        ) from exc


@router.post("/api/chanlun/paper-orders/{order_id}/cancel")
def cancel_chanlun_paper_order(order_id: str) -> ChanlunPaperOrder:
    try:
        return _chanlun_paper_order_service().cancel(order_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="模拟订单不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/chanlun/paper-account")
def get_chanlun_paper_account() -> ChanlunPaperAccount:
    return _chanlun_paper_order_service().account()


@router.get("/api/chanlun/symbols/search")
def search_chanlun_symbols(query: str = "", limit: int = 20) -> dict[str, object]:
    try:
        items, source_status = _chanlun_symbol_search_service().search(query, limit=limit)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "source_status": [status.model_dump(mode="json") for status in source_status],
    }


@router.post("/api/chanlun/stocks/{symbol}/backfill")
def create_chanlun_backfill_job(
    symbol: str,
    request: ChanlunBackfillRequest,
) -> dict[str, object]:
    normalized_symbol = normalize_chanlun_symbol(symbol)
    if not normalized_symbol:
        raise HTTPException(status_code=422, detail="invalid Chanlun symbol")
    job_type = f"chanlun_backfill:{normalized_symbol}"
    store = _background_job_store()
    active_job = store.get_active(job_type)
    if active_job is not None:
        return active_job.model_dump(mode="json")
    job = store.create_transient_job(
        job_type,
        lambda progress, should_cancel: _chanlun_analysis_service().backfill(
            normalized_symbol,
            periods=tuple(request.periods),
            lookback=request.lookback,
            history_days=request.history_days,
            progress=progress,
            should_cancel=should_cancel,
        ),
        running_message="缠论分钟历史补齐中",
        success_message="缠论分钟历史补齐完成",
        progress_total=3,
    )
    return job.model_dump(mode="json")


@router.get("/api/chanlun/stocks/{symbol}/backfill/{job_id}")
def get_chanlun_backfill_job(symbol: str, job_id: str) -> dict[str, object]:
    normalized_symbol = normalize_chanlun_symbol(symbol)
    if not normalized_symbol:
        raise HTTPException(status_code=422, detail="invalid Chanlun symbol")
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="chanlun backfill job not found") from exc
    if job.type != f"chanlun_backfill:{normalized_symbol}":
        raise HTTPException(status_code=404, detail="chanlun backfill job not found")
    return job.model_dump(mode="json")

