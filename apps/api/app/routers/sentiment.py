"""sentiment 域路由（自 app.main 拆分）。"""

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

@router.get("/api/short-term/sentiment/monitor/status")
def get_sentiment_monitor_status() -> dict[str, object]:
    return _sentiment_monitor().status().model_dump(mode="json")


@router.put("/api/short-term/sentiment/monitor/config")
def update_sentiment_monitor_config(request: SentimentMonitorConfig) -> dict[str, object]:
    _save_sentiment_monitor_config(request)
    monitor = _sentiment_monitor()
    if request.enabled:
        return monitor.start().model_dump(mode="json")
    return monitor.stop().model_dump(mode="json")


@router.post("/api/short-term/sentiment/monitor/start")
def start_sentiment_monitor() -> dict[str, object]:
    current = load_runtime_settings(_runtime_config_path()).sentiment_monitor
    _save_sentiment_monitor_config(current.model_copy(update={"enabled": True}))
    return _sentiment_monitor().start().model_dump(mode="json")


@router.post("/api/short-term/sentiment/monitor/stop")
def stop_sentiment_monitor() -> dict[str, object]:
    current = load_runtime_settings(_runtime_config_path()).sentiment_monitor
    _save_sentiment_monitor_config(current.model_copy(update={"enabled": False}))
    return _sentiment_monitor().stop().model_dump(mode="json")


@router.post("/api/short-term/sentiment/monitor/run-once")
def run_sentiment_monitor_once(trade_date: str | None = None) -> dict[str, object]:
    return _sentiment_monitor().run_once(trade_date).model_dump(mode="json")


@router.get("/api/short-term/sentiment")
def get_short_term_sentiment(trade_date: str, limit: int = 50) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    try:
        result = _cached_short_term_sentiment(trade_date, bounded_limit)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.get(
    "/api/short-term/sentiment/percentile",
    response_model=SentimentPercentileResponse,
)
def get_market_sentiment_percentile(
    as_of: date | None = None,
    refresh: bool = False,
) -> SentimentPercentileResponse:
    try:
        result = _market_sentiment_percentile_service().get(
            as_of=as_of.isoformat() if as_of else None,
            refresh=refresh,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _schedule_market_sentiment_analysis_catchup(result)
    return result


@router.get(
    "/api/short-term/sentiment/percentile/analysis",
    response_model=SentimentPercentileAnalysisResponse,
)
def get_market_sentiment_percentile_analysis(
    trade_date: date,
) -> SentimentPercentileAnalysisResponse:
    trade_date_text = trade_date.isoformat()
    percentile, point = _persisted_percentile_point_for_trade_date(trade_date_text)
    config = _effective_settings().ai_analysis
    input_payload = _build_market_sentiment_analysis_input(
        trade_date_text,
        percentile,
        point,
        refresh_missing=False,
    )
    existing = _market_sentiment_analysis_store().load(trade_date_text)
    if sentiment_analysis_record_matches(existing, input_payload, config):
        if pending_analysis_is_stale(existing):
            existing = _market_sentiment_analysis_store().save(
                existing.model_copy(
                    update={
                        "status": "failed",
                        "attempts": max(1, existing.attempts),
                        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "retry_after": (
                            datetime.now(timezone.utc) + timedelta(minutes=30)
                        ).isoformat(timespec="seconds"),
                        "error": "TimeoutError: previous AI generation did not complete",
                    }
                )
            )
        return existing

    return SentimentPercentileAnalysisResponse(
        trade_date=trade_date_text,
        status=("not_generated" if config.enabled and config.api_key else "unconfigured"),
        provider=config.provider,
        llm_model=config.model,
    )


@router.post(
    "/api/short-term/sentiment/percentile/analysis/generate",
    response_model=SentimentPercentileAnalysisResponse,
)
def generate_market_sentiment_percentile_analysis(
    trade_date: date,
    force: bool = False,
) -> SentimentPercentileAnalysisResponse:
    try:
        return _generate_market_sentiment_analysis(trade_date.isoformat(), force=force)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/short-term/sentiment/summary")
def get_short_term_sentiment_summary(
    trade_date: str,
    limit: int = 80,
    refresh: bool = False,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    cached = _sentiment_snapshot_store().load_summary(trade_date)
    if cached is not None and not refresh:
        return cached.model_dump(mode="json")
    if not refresh:
        return build_missing_sentiment_summary(trade_date).model_dump(mode="json")
    try:
        sentiment, market_emotion = _build_and_persist_sentiment_snapshots(
            trade_date,
            bounded_limit,
            refresh=True,
        )
        result = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.get("/api/short-term/sentiment/decision")
def get_short_term_sentiment_decision(
    trade_date: str,
    limit: int = 80,
    refresh: bool = False,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    store = _sentiment_snapshot_store()
    cached_summary = store.load_summary(trade_date)
    cached_emotion = store.load_market_emotion(trade_date)
    if cached_summary is not None and not refresh:
        return build_sentiment_decision(cached_summary, cached_emotion).model_dump(mode="json")
    try:
        sentiment, market_emotion = _build_and_persist_sentiment_snapshots(
            trade_date,
            bounded_limit,
            refresh=refresh,
        )
        summary = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return build_sentiment_decision(summary, market_emotion).model_dump(mode="json")


@router.post("/api/short-term/sentiment/review/archive")
def archive_sentiment_decision(trade_date: str, limit: int = 80) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 200))
    try:
        sentiment, market_emotion = _build_and_persist_sentiment_snapshots(
            trade_date,
            bounded_limit,
            refresh=True,
        )
        summary = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    decision = build_sentiment_decision(summary, market_emotion)
    _sentiment_review_store().save_decision(decision)
    return decision.model_dump(mode="json")


@router.get("/api/short-term/sentiment/watchlist-alerts")
def get_short_term_sentiment_watchlist_alerts(
    trade_date: str,
    limit: int = 80,
    refresh: bool = False,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    store = _sentiment_snapshot_store()
    cached_summary = store.load_summary(trade_date)
    cached_emotion = store.load_market_emotion(trade_date)
    if cached_summary is not None and not refresh:
        decision = build_sentiment_decision(cached_summary, cached_emotion)
    else:
        try:
            sentiment, market_emotion = _build_and_persist_sentiment_snapshots(
                trade_date,
                bounded_limit,
                refresh=refresh,
            )
            summary = build_sentiment_summary(sentiment, market_emotion, snapshot_status="fresh")
            decision = build_sentiment_decision(summary, market_emotion)
        except StrongStockDataUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    items = parse_watchlist_text(_read_watchlist_pool())
    alerts = build_sentiment_watchlist_alerts(decision, items)
    return {"trade_date": trade_date, "items": [item.model_dump(mode="json") for item in alerts]}


@router.get("/api/short-term/sentiment/detail")
def get_short_term_sentiment_detail(
    trade_date: str,
    limit: int = 80,
    refresh: bool = False,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    store = _sentiment_snapshot_store()
    sentiment = store.load_sentiment(trade_date)
    market_emotion = store.load_market_emotion(trade_date)
    if sentiment is not None and market_emotion is not None and not refresh:
        return SentimentDetailResponse(
            trade_date=trade_date,
            snapshot_status="cached",
            cached_at=market_emotion.generated_at,
            sentiment=sentiment,
            market_emotion=market_emotion,
        ).model_dump(mode="json")
    if not refresh:
        raise HTTPException(status_code=404, detail="no sentiment snapshot")
    try:
        sentiment, market_emotion = _build_and_persist_sentiment_snapshots(
            trade_date, bounded_limit
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SentimentDetailResponse(
        trade_date=trade_date,
        snapshot_status="fresh",
        sentiment=sentiment,
        market_emotion=market_emotion,
    ).model_dump(mode="json")


@router.get("/api/short-term/market-emotion")
def get_short_term_market_emotion(
    trade_date: str,
    limit: int = 80,
    include_distribution: bool = True,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    candidate_provider = _candidate_provider()
    market_overview_provider = _market_overview_provider()
    try:
        cache_key = (
            "market-emotion:"
            f"{_provider_cache_key(candidate_provider)}:"
            f"{_provider_cache_key(market_overview_provider)}:"
            f"{trade_date}:{bounded_limit}:{include_distribution}"
        )
        result = MARKET_EMOTION_CACHE.get_or_set(
            cache_key,
            lambda: build_market_emotion_snapshot(
                candidate_provider,
                market_overview_provider,
                trade_date=trade_date,
                limit=bounded_limit,
                sentiment_snapshot=_cached_short_term_sentiment(trade_date, bounded_limit),
                market_overview=_cached_market_overview(),
                include_distribution=include_distribution,
            ),
        ).model_copy(deep=True)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        history_store = _market_emotion_history_store()
        with _MARKET_EMOTION_HISTORY_WRITE_LOCK:
            samples = history_store.load(trade_date)
            sampled_at = datetime.now(ZoneInfo("Asia/Shanghai")).replace(microsecond=0)
            if _should_persist_market_emotion_sample(
                trade_date,
                samples,
                now=sampled_at,
            ):
                result.generated_at = sampled_at.isoformat(timespec="seconds")
                history_store.append(result)
                samples = history_store.load(trade_date)
            result.samples = samples
        if include_distribution and trade_date == sampled_at.date().isoformat():
            sentiment = _cached_short_term_sentiment(trade_date, bounded_limit)
            _sentiment_snapshot_store().save(sentiment=sentiment, market_emotion=result)
    except Exception as exc:
        result.source_status.append(
            StrongStockSourceStatus(
                source="市场情绪采样",
                status="failed",
                detail=f"采样写入失败: {exc.__class__.__name__}",
            )
        )
    return result.model_dump(mode="json")


@router.get("/api/short-term/sentiment/intraday")
def get_short_term_intraday_sentiment(
    trade_date: str,
    limit: int = 80,
    period: str = "1m",
    count: int = 120,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    bounded_count = max(1, min(count, 240))
    if period not in {"1m", "5m", "10m", "15m", "30m", "60m"}:
        raise HTTPException(status_code=422, detail="period must be one of 1m/5m/10m/15m/30m/60m")
    try:
        result: ShortTermIntradaySentimentResponse = build_short_term_intraday_sentiment(
            _candidate_provider(),
            _quote_provider(),
            trade_date=trade_date,
            limit=bounded_limit,
            period=period,
            count=bounded_count,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.get("/api/short-term/sentiment/intraday/digest")
def get_short_term_intraday_signal_digest(
    trade_date: str,
    limit: int = 80,
    period: str = "1m",
    count: int = 120,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    bounded_count = max(1, min(count, 240))
    if period not in {"1m", "5m", "10m", "15m", "30m", "60m"}:
        raise HTTPException(status_code=422, detail="period must be one of 1m/5m/10m/15m/30m/60m")
    try:
        snapshot = build_short_term_intraday_sentiment(
            _candidate_provider(),
            _quote_provider(),
            trade_date=trade_date,
            limit=bounded_limit,
            period=period,
            count=bounded_count,
        )
        digest: ShortTermIntradaySignalDigest = build_short_term_intraday_signal_digest(snapshot)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return digest.model_dump(mode="json")

