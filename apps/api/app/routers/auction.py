"""auction 域路由（自 app.main 拆分）。"""

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

@router.get("/api/auction/latest")
def get_latest_auction_snapshot(limit: int = 100) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    result = _auction_snapshot_store().latest(limit=bounded_limit)
    result = _backfill_auction_snapshot_industries(result)
    return result.model_dump(mode="json")


@router.get("/api/auction/timeline")
def get_auction_timeline(limit: int = 8) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 20))
    result: AuctionTimelineResponse = _auction_snapshot_store().timeline(limit=bounded_limit)
    return result.model_dump(mode="json")


@router.get("/api/auction/model/top3")
def get_auction_model_top3(
    trade_date: str,
    refresh: bool = False,
    cache_only: bool = False,
) -> dict[str, object]:
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
        store = _auction_model_result_store()
        if not refresh:
            cached = store.load_top3(trade_date)
            if cached is not None:
                return cached.model_dump(mode="json")
            if cache_only:
                raise HTTPException(status_code=404, detail="暂无缓存的竞价模型Top3结果")
        result = _generate_auction_top3_for_date(trade_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="trade_date must use YYYY-MM-DD") from exc
    except (FileNotFoundError, AuctionModelDataError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/api/auction/model/top3/jobs")
def create_auction_model_top3_job(trade_date: str) -> dict[str, object]:
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="trade_date must use YYYY-MM-DD") from exc
    store = _background_job_store()
    active_job = store.get_active("auction_model_top3_generate")
    if active_job is not None:
        return active_job.model_dump(mode="json")
    job = store.create_transient_job(
        "auction_model_top3_generate",
        lambda progress, should_cancel: _run_auction_model_top3_generation_job(
            trade_date,
            progress,
            should_cancel,
        ),
        running_message="竞价模型Top3生成中",
        success_message="竞价模型Top3生成完成",
        progress_total=3,
    )
    return job.model_dump(mode="json")


@router.get("/api/auction/model/top3/jobs/{job_id}")
def get_auction_model_top3_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="auction model top3 job not found") from exc
    return job.model_dump(mode="json")


@router.get("/api/auction/model/top3/live-confirmation")
def get_auction_model_top3_live_confirmation(trade_date: str) -> dict[str, object]:
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="trade_date must use YYYY-MM-DD") from exc

    model_run = _auction_model_result_store().load_top3(trade_date)
    if model_run is None:
        raise HTTPException(status_code=404, detail="暂无缓存的竞价模型Top3结果")

    latest_snapshot = _auction_snapshot_store().latest(max_age_seconds=24 * 3600, limit=100)
    snapshot = None if latest_snapshot.snapshot_status == "missing" else latest_snapshot
    result = build_auction_top3_live_confirmation(model_run, snapshot)
    saved = _auction_top3_live_confirmation_store().save(result)
    return saved.model_dump(mode="json")


@router.get("/api/auction/snapshot")
def get_auction_snapshot(limit: int = 100, refresh: bool = False) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    try:
        result = (
            _refresh_auction_snapshot(bounded_limit)
            if refresh
            else _cached_auction_snapshot(bounded_limit)
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"竞价雷达获取失败: {exc.__class__.__name__}"
        ) from exc
    return result.model_dump(mode="json")


@router.post("/api/auction/snapshot/jobs")
def create_auction_snapshot_job(limit: int = 100) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    store = _background_job_store()
    active_job = store.get_active("auction_snapshot_refresh")
    if active_job is not None:
        return active_job.model_dump(mode="json")
    job = store.create_transient_job(
        "auction_snapshot_refresh",
        lambda progress, should_cancel: _run_auction_snapshot_refresh_job(
            bounded_limit,
            progress,
            should_cancel,
        ),
        running_message="竞价刷新运行中",
        success_message="竞价刷新完成",
        progress_total=3,
    )
    return job.model_dump(mode="json")


@router.get("/api/auction/snapshot/jobs/{job_id}")
def get_auction_snapshot_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="auction snapshot job not found") from exc
    return job.model_dump(mode="json")


@router.get("/api/auction/review/latest")
def get_latest_auction_review() -> dict[str, object]:
    summary = _auction_review_store().load_latest_summary()
    if summary is None:
        raise HTTPException(status_code=404, detail="no auction review summary")
    return summary.model_dump(mode="json")


@router.get("/api/auction/review")
def get_auction_review(trade_date: str | None = None, limit: int = 100) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 500))
    records = _auction_review_store().load_records(trade_date, limit=bounded_limit)
    summary = _auction_review_summary(records, trade_date=trade_date)
    return summary.model_dump(mode="json")


@router.post("/api/auction/review/finalize")
def finalize_auction_review(trade_date: str) -> dict[str, object]:
    store = _auction_review_store()
    records = store.load_records(trade_date)
    latest_snapshot = _auction_snapshot_store().latest(max_age_seconds=24 * 3600, limit=100)
    can_seed_from_latest = (
        latest_snapshot.snapshot_status != "missing" and latest_snapshot.trade_date == trade_date
    )
    should_seed_manual = not records or (
        can_seed_from_latest
        and all(record.selected_at_label == "manual" for record in records)
        and len(latest_snapshot.items) > len(records)
    )
    if should_seed_manual:
        if not can_seed_from_latest:
            raise HTTPException(status_code=404, detail="no auction review records")
        records = build_auction_review_records(
            latest_snapshot,
            selected_at_label="manual",
            selected_at=_auction_review_selected_at(trade_date),
            limit=100,
        )
        store.upsert_records(records)
        records = store.load_records(trade_date)
    if not records:
        raise HTTPException(status_code=404, detail="no auction review records")
    provider = _kline_provider()
    symbol_bars: dict[str, list[KlineBar]] = {}
    symbol_intraday_bars: dict[str, list[KlineBar]] = {}
    kline_errors: dict[str, str] = {}
    for symbol in sorted({record.symbol for record in records}):
        try:
            symbol_bars[symbol] = provider.get_klines(symbol, count=260)
            get_minutes = getattr(provider, "get_intraday_bars", None)
            if callable(get_minutes):
                intraday = get_minutes([symbol], period="1m", count=120).get(symbol, [])
                symbol_intraday_bars[symbol] = _auction_review_minute_bars(intraday, trade_date)
        except StrongStockDataUnavailable as exc:
            symbol_bars[symbol] = []
            kline_errors[symbol] = str(exc)
    summary = finalize_auction_records(
        records,
        symbol_bars=symbol_bars,
        symbol_intraday_bars=symbol_intraday_bars,
    )
    reviewed_records = summary.records
    if kline_errors:
        reviewed_records = [
            _mark_auction_review_kline_unavailable(record, kline_errors[record.symbol])
            if record.symbol in kline_errors
            else record
            for record in reviewed_records
        ]
    summary = _auction_review_summary(
        _fill_auction_review_close_from_quotes(reviewed_records, trade_date),
        trade_date=trade_date,
    )
    store.upsert_records(summary.records)
    store.save_summary(summary)
    return summary.model_dump(mode="json")


@router.post("/api/auction/review/backfill")
def backfill_auction_review(
    start_date: str,
    end_date: str,
    max_days: int = 20,
) -> dict[str, object]:
    # 该端点当前为占位实现：不消费 start_date/end_date/max_days，统一返回
    # data_unavailable，避免调用方误以为参数已生效。
    _ = (start_date, end_date, max_days)
    return AuctionBackfillResponse().model_dump(mode="json")


@router.get("/api/auction/rules/summary")
def get_auction_rules_summary(limit: int = 2000) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 10000))
    records = _auction_review_store().load_records(limit=bounded_limit)
    summary = _auction_review_summary(records, trade_date=None)
    return summary.model_dump(mode="json")


@router.post("/api/intraday/snapshot")
def create_intraday_snapshot(request: IntradaySnapshotRequest) -> dict[str, object]:
    symbols = request.symbols
    name_map: dict[str, str] = {}
    industry_map: dict[str, str] = {}
    group_map: dict[str, str] = {}
    tag_map: dict[str, list[str]] = {}
    watchlist_items = _intraday_watchlist_items(request)
    if watchlist_items:
        symbols = [item.symbol for item in watchlist_items]
        name_map = {item.symbol: item.name or item.symbol for item in watchlist_items}
        industry_map = {item.symbol: item.industry for item in watchlist_items if item.industry}
        group_map = {item.symbol: item.group for item in watchlist_items if item.group}
        tag_map = {item.symbol: item.tags for item in watchlist_items if item.tags}
    if not symbols:
        latest = _run_store().load_latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="no screen run")
        symbols = [item.symbol for item in latest.items]
        name_map = {item.symbol: item.name for item in latest.items}
        industry_map = {item.symbol: item.industry for item in latest.items if item.industry}

    monitor = IntradayMonitor(quote_provider=_quote_provider())
    try:
        result = monitor.snapshot(
            symbols=symbols,
            name_map=name_map,
            industry_map=industry_map,
            group_map=group_map,
            tag_map=tag_map,
            gsgf_context={
                symbol.strip().upper(): value for symbol, value in request.gsgf_context.items()
            },
            limit=request.limit,
            period=request.period,
            count=request.count,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")

