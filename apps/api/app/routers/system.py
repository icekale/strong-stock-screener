"""system 域路由（自 app.main 拆分）。"""

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
from app.lifespan import _clear_data_source_caches
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "chanlun_research": _chanlun_research_health(),
    }


@router.get("/api/system/cache", response_model=SystemCacheSummary)
def get_system_cache() -> SystemCacheSummary:
    return SystemCacheSummary.model_validate(CACHE_REGISTRY.summary())


@router.post("/api/system/cache/clear", response_model=SystemCacheClearResponse)
def clear_system_cache(group: str | None = None, all: bool = False) -> SystemCacheClearResponse:
    if group is None and not all:
        raise HTTPException(status_code=400, detail="必须指定 group 或 all=true")
    if group is not None and all:
        raise HTTPException(status_code=400, detail="group 和 all=true 不能同时使用")
    if all:
        return SystemCacheClearResponse(cleared=CACHE_REGISTRY.clear())
    if group not in CACHE_GROUPS:
        raise HTTPException(status_code=400, detail=f"未知缓存分组: {group}")
    return SystemCacheClearResponse(cleared=CACHE_REGISTRY.clear(group=group))


@router.get("/api/system/status", response_model=SystemStatusResponse)
def get_system_status() -> SystemStatusResponse:
    cache = get_system_cache()
    jobs = _system_jobs()
    is_degraded = any(item.last_error is not None for item in cache.items) or any(
        _system_job_degraded(job) for job in jobs
    )
    status = "degraded" if is_degraded else "ok"
    confidence = "degraded" if is_degraded else "fresh"
    return SystemStatusResponse(
        status=status,
        generated_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        cache=cache,
        jobs=jobs,
        confidence=confidence,
    )


@router.get("/api/data-sources/status")
def data_source_status() -> dict[str, object]:
    candidate_provider = _candidate_provider()
    kline_provider = _kline_provider()
    quote_provider = _quote_provider()
    news_risk_provider = _news_risk_provider()
    candidate_status = (
        candidate_provider.status() if hasattr(candidate_provider, "status") else None
    )
    kline_status = kline_provider.status() if hasattr(kline_provider, "status") else None
    quote_status = quote_provider.status() if hasattr(quote_provider, "status") else None
    news_risk_status = (
        news_risk_provider.status() if hasattr(news_risk_provider, "status") else None
    )
    return {
        "items": [
            (
                candidate_status
                or StrongStockSourceStatus(
                    source=candidate_provider.source_name,
                    status="success",
                    detail="候选池源已配置",
                )
            ).model_dump(mode="json"),
            (
                kline_status
                or StrongStockSourceStatus(
                    source=kline_provider.source_name,
                    status="success",
                    detail="K线源已配置",
                )
            ).model_dump(mode="json"),
            (
                quote_status
                or StrongStockSourceStatus(
                    source=getattr(quote_provider, "source_name", "quote_provider"),
                    status="disabled",
                    detail="报价源未配置",
                )
            ).model_dump(mode="json"),
            (
                news_risk_status
                or StrongStockSourceStatus(
                    source=getattr(news_risk_provider, "source_name", "news_risk_provider"),
                    status="disabled",
                    detail="新闻风险源未配置",
                )
            ).model_dump(mode="json"),
        ]
    }


@router.get("/api/settings")
def get_runtime_settings() -> dict[str, object]:
    return {
        "config": public_settings_payload(_effective_settings()),
        "saved": _public_saved_settings(),
    }


@router.put("/api/settings")
def update_runtime_settings(request: SettingsUpdate) -> dict[str, object]:
    save_runtime_settings(_runtime_config_path(), request)
    _clear_data_source_caches()
    return {
        "config": public_settings_payload(_effective_settings()),
        "saved": _public_saved_settings(),
    }


@router.post("/api/notifications/send")
def send_notification(request: NotificationSendRequest) -> dict[str, object]:
    runtime = load_runtime_settings(_runtime_config_path())
    result: NotificationSendResult = send_notification_message(
        NotificationSettings(channels=runtime.notification_channels),
        title=request.title,
        message_text=request.message_text,
        channel_ids=request.channel_ids,
        http_client=getattr(app_state().state, "notification_http_client", None),
        smtp_client=getattr(app_state().state, "notification_smtp_client", None) or DefaultSmtpClient(),
    )
    return result.model_dump(mode="json")


@router.get("/api/settings/health")
def settings_health(symbol: str = "605289.SH") -> dict[str, object]:
    quote_provider = _quote_provider()
    ifind_provider = _ifind_provider()
    settings = _effective_settings()
    return {
        "config": public_settings_payload(_effective_settings()),
        "probes": [
            _probe(
                getattr(_candidate_provider(), "source_name", "候选池"),
                lambda: (
                    _candidate_provider().status()
                    if hasattr(_candidate_provider(), "status")
                    else StrongStockSourceStatus(
                        source="候选池", status="success", detail="候选池源已配置"
                    )
                ),
            ).model_dump(mode="json"),
            _probe(
                getattr(_kline_provider(), "source_name", "K线"),
                lambda: _kline_provider().get_klines(symbol, count=5),
            ).model_dump(mode="json"),
            _probe(
                "实时行情",
                lambda: quote_provider.get_quotes([symbol]),
            ).model_dump(mode="json"),
            _probe(
                "当日分钟线",
                lambda: quote_provider.get_intraday_bars([symbol], period="1m", count=5),
            ).model_dump(mode="json"),
            _probe(
                "iFinD MCP 服务",
                lambda: ifind_provider.status(),
            ).model_dump(mode="json"),
            _probe(
                "iFinD A股数据",
                lambda: ifind_provider.probe_tools(settings.ifind_service_id),
            ).model_dump(mode="json"),
            _probe(
                "通达信MCP",
                lambda: _tdx_provider().status(),
            ).model_dump(mode="json"),
        ],
    }

