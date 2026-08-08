"""stocks 域路由（自 app.main 拆分）。"""

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

@router.get("/api/stocks/{symbol}/kline")
def get_stock_kline(
    symbol: str,
    count: int = 220,
    period: StockKlinePeriod = "1d",
) -> dict[str, object]:
    bounded_count = max(1, min(count, 260))
    try:
        result = _cached_stock_kline(symbol, bounded_count, period)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"K线获取失败: {exc.__class__.__name__}"
        ) from exc
    return result.model_dump(mode="json")


@router.get("/api/stocks/{symbol}/quote")
def get_stock_quote(symbol: str) -> dict[str, object]:
    quote_provider = _quote_provider()
    try:
        quotes = quote_provider.get_quotes([symbol])
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"实时行情获取失败: {exc.__class__.__name__}"
        ) from exc
    if not quotes:
        raise HTTPException(status_code=503, detail="实时行情未返回数据")
    quote = quotes[0]
    industry = _stock_industry_for_symbol(quote.symbol)
    valuation_quote, valuation_status = _quote_valuation_for_symbol(quote.symbol)
    source_status = (
        quote_provider.status()
        if hasattr(quote_provider, "status")
        else StrongStockSourceStatus(
            source=getattr(quote_provider, "source_name", "实时行情"),
            status="success",
            detail="实时行情源已配置",
        )
    )
    return StockQuoteResponse(
        symbol=quote.symbol,
        name=quote.name,
        industry=industry,
        last_price=quote.last_price,
        prev_close=quote.prev_close,
        open_price=quote.open_price,
        high_price=quote.high_price,
        low_price=quote.low_price,
        pct_change=quote.pct_change,
        turnover_rate=getattr(quote, "turnover_rate", None),
        turnover_cny=quote.turnover_cny,
        volume=quote.volume,
        quote_time=quote.quote_time,
        total_market_cap_cny=getattr(valuation_quote, "total_market_cap_cny", None),
        circulating_market_cap_cny=getattr(valuation_quote, "circulating_market_cap_cny", None),
        pe_ttm=getattr(valuation_quote, "pe_ttm", None),
        pe_static=getattr(valuation_quote, "pe_static", None),
        pb=getattr(valuation_quote, "pb", None),
        valuation_source_status=valuation_status,
        source_status=source_status,
    ).model_dump(mode="json")


@router.get("/api/stocks/{symbol}/research")
def get_stock_research(symbol: str) -> dict[str, object]:
    research = _cached_stock_research(symbol)
    return research.model_dump(mode="json")

