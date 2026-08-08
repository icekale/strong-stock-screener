"""etf 域路由（自 app.main 拆分）。"""

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

@router.get("/api/etf-radar/overview", response_model=EtfRadarOverviewResponse)
def get_etf_radar_overview() -> EtfRadarOverviewResponse:
    return _etf_three_factor_monitor().enrich_overview(_capital_signal_service().overview())


@router.get("/api/etf-radar/excess-flow", response_model=EtfExcessFlowResponse)
def get_etf_excess_flow(
    days: int = Query(default=60, ge=20, le=120),
) -> EtfExcessFlowResponse:
    return _etf_excess_flow_service().trend(days=days)


@router.get("/api/etf-radar/history", response_model=EtfRadarHistoryResponse)
def get_etf_radar_history(
    days: int = Query(default=120, ge=1, le=365),
) -> EtfRadarHistoryResponse:
    return _capital_signal_service().history(days=days)


@router.get("/api/etf-radar/price-history/{symbol}", response_model=EtfPriceHistoryResponse)
def get_etf_price_history(
    symbol: str,
    days: int = Query(default=120, ge=1, le=365),
) -> EtfPriceHistoryResponse:
    try:
        return _etf_price_history_service().history(symbol, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EtfPriceHistoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"读取 ETF 收盘价失败：{exc}") from exc
    except Exception as exc:
        logger.exception("ETF price history failed for %s", symbol)
        raise HTTPException(status_code=503, detail=f"读取 ETF 收盘价失败：{exc}") from exc


@router.get("/api/etf-radar/holders", response_model=EtfRadarHoldersResponse)
def get_etf_radar_holders() -> EtfRadarHoldersResponse:
    return _capital_signal_service().holders()


@router.get("/api/etf-radar/methodology", response_model=EtfRadarMethodologyResponse)
def get_etf_radar_methodology() -> EtfRadarMethodologyResponse:
    return _capital_signal_service().methodology()


@router.get("/api/etf-radar/three-factor", response_model=EtfThreeFactorResponse)
def get_etf_three_factor() -> EtfThreeFactorResponse:
    return _etf_three_factor_monitor().latest()


@router.get(
    "/api/etf-radar/three-factor/{symbol}/history",
    response_model=EtfThreeFactorHistoryResponse,
)
def get_etf_three_factor_history(
    symbol: str,
    days: int = Query(default=40, ge=1, le=60),
) -> EtfThreeFactorHistoryResponse:
    if symbol not in CORE_ETFS:
        raise HTTPException(status_code=404, detail="ETF不在核心监控池")
    return _etf_three_factor_monitor().history(symbol, days)


@router.get("/api/etf-radar/alerts", response_model=EtfActivityAlertResponse)
def get_etf_activity_alerts(unread_only: bool = False) -> EtfActivityAlertResponse:
    alerts = _etf_three_factor_monitor().store.load_alerts()
    unread_count = sum(not alert.read for alert in alerts)
    return EtfActivityAlertResponse(
        unread_count=unread_count,
        alerts=[alert for alert in alerts if not alert.read] if unread_only else alerts,
    )


@router.post("/api/etf-radar/alerts/{alert_id}/read")
def mark_etf_activity_alert_read(alert_id: str) -> dict[str, str]:
    store = _etf_three_factor_monitor().store
    if not any(alert.alert_id == alert_id for alert in store.load_alerts()):
        raise HTTPException(status_code=404, detail="告警不存在")
    store.mark_read(alert_id)
    return {"status": "ok"}


@router.post("/api/etf-radar/alerts/read-all")
def mark_all_etf_activity_alerts_read() -> dict[str, str]:
    _etf_three_factor_monitor().store.mark_all_read()
    return {"status": "ok"}

