from __future__ import annotations

import json
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from threading import Thread
from time import perf_counter
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models import (
    AuctionBackfillResponse,
    AuctionModelTop3Response,
    AuctionReviewSummary,
    AuctionSnapshotResponse,
    AuctionTimelineResponse,
    GsgfAnalysis,
    GsgfBacktestSummary,
    GsgfModelHealth,
    GsgfRealCalibrationSummary,
    GsgfReviewSnapshotResponse,
    GsgfReviewSummary,
    GsgfTradePlan,
    KlineBar,
    MarketEmotionSnapshotResponse,
    MarketOverviewResponse,
    MarketRankingsResponse,
    MarketSectorStrengthItem,
    ModelMaintenancePacket,
    ModelMaintenanceReport,
    ModelMaintenanceSuggestion,
    ScreenStrategy,
    SectorWorkbenchMode,
    SectorRadarItem,
    SectorRadarResponse,
    SectorWorkbenchCacheSummary,
    SectorWorkbenchScopeRequest,
    SectorWorkbenchResponse,
    SectorWorkbenchSeries,
    SectorWorkbenchStatusResponse,
    SentimentDetailResponse,
    ShortTermIntradaySentimentResponse,
    ShortTermIntradaySignalDigest,
    ShortTermSentimentResponse,
    StockKlineResponse,
    StockQuoteResponse,
    StockResearchResponse,
    StrongStockDataUnavailable,
    StrongStockScreeningResult,
    StrongStockSourceStatus,
    SystemCacheClearResponse,
    SystemCacheSummary,
    SystemStatusResponse,
)
from app.gsgf_rules import analyze_gsgf, build_gsgf_chart_annotations
from app.providers.ifind import IfindMcpProvider
from app.providers.market_overview import EastmoneyMarketOverviewProvider
from app.providers.concept_blocks import EastmoneyConceptBlockProvider
from app.providers.news_risk import EastmoneyNewsRiskProvider
from app.providers.recent_limit_up_candidates import RecentLimitUpCandidateProvider
from app.providers.thsdk_candidates import ThsdkCandidateProvider
from app.providers.tdx_mcp import TdxMcpProvider
from app.providers.tickflow import TickFlowDailyKlineProvider, TickFlowQuoteProvider
from app.providers.watchlist import (
    WatchlistItem,
    WatchlistSnapshot,
    parse_watchlist_text,
    upsert_watchlist_item,
)
from app.services.intraday import IntradayMonitor
from app.services.background_jobs import BackgroundJobStore, CancelCheck, ProgressCallback
from app.services.cache_registry import CacheRegistry
from app.services.gsgf_backtest import summarize_gsgf_backtest
from app.services.gsgf_auto_review import GsgfAutoReviewService
from app.services.gsgf_model_health import build_gsgf_model_health
from app.services.gsgf_real_calibration import summarize_gsgf_real_calibration
from app.services.gsgf_review import GsgfReviewStore
from app.services.gsgf_trade_plan import build_gsgf_trade_plan
from app.services.ai_model_analysis import analyze_model_maintenance_packet
from app.services.auction import build_auction_snapshot
from app.services.auction_model import (
    AuctionModelDataError,
    AuctionModelResultStore,
    AuctionModelService,
    FreeStockDbAuctionModelSource,
)
from app.services.auction_review import (
    build_auction_review_records,
    build_auction_rule_buckets,
    finalize_auction_records,
)
from app.services.auction_review_store import AuctionReviewStore
from app.services.auction_sampler import AuctionSnapshotSampler
from app.services.sector_workbench_sampler import SectorWorkbenchSampler, is_sector_workbench_sample_window
from app.services.auction_snapshot_store import AuctionSnapshotStore
from app.services.market_emotion_history import MarketEmotionHistoryStore
from app.services.model_maintenance_packet import build_model_maintenance_packet
from app.services.model_maintenance_store import ModelMaintenanceStore
from app.services.plate_rotation_reference import (
    PlateRotationReferenceProvider,
    PlateRotationReferenceResponse,
)
from app.services.runs import RunStore
from app.services.runtime_settings import (
    SettingsUpdate,
    effective_runtime_settings,
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
from app.services.screener import StrongStockScreener
from app.services.sector_workbench import (
    build_limit_up_theme_rows_from_candidates,
    build_sector_workbench_from_radar,
    build_sector_workbench_response,
)
from app.services.sector_workbench_intraday import build_sector_intraday_series
from app.services.sector_workbench_store import SectorThemeRowsStore, SectorWorkbenchSampleStore
from app.services.short_term_cache import TtlCache
from app.services.sentiment_snapshot_store import SentimentSnapshotStore
from app.services.sentiment_monitor import SentimentMonitor, SentimentMonitorConfig
from app.services.sentiment_decision import build_sentiment_decision
from app.services.sentiment_review_store import SentimentReviewStore
from app.services.sentiment_watchlist import build_sentiment_watchlist_alerts
from app.services.short_term_sentiment import (
    build_missing_sentiment_summary,
    build_market_emotion_snapshot,
    build_sentiment_summary,
    build_short_term_intraday_sentiment,
    build_short_term_intraday_signal_digest,
    build_short_term_sentiment,
)


class ScreenFiltersRequest(BaseModel):
    min_market_cap_billion: float | None = Field(default=None, ge=0)
    max_market_cap_billion: float | None = Field(default=None, ge=0)
    kdj_j_max: float | None = None
    industries: list[str] = Field(default_factory=list, max_length=20)
    market_types: list[str] = Field(default_factory=list, max_length=4)


class ScreenRunRequest(BaseModel):
    trade_date: str
    limit: int = Field(default=30, ge=1, le=100)
    scan_limit: int = Field(default=160, ge=1, le=300)
    filters: ScreenFiltersRequest = Field(default_factory=ScreenFiltersRequest)
    strategy: ScreenStrategy = "strong_stock"
    include_gsgf: bool = True
    exclude_gsgf_hard_risk: bool = False


class GsgfBacktestRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, min_length=1, max_length=50)
    windows: list[int] = Field(default_factory=lambda: [1, 3, 5, 10], max_length=8)
    min_history: int = Field(default=60, ge=60, le=220)
    count: int = Field(default=180, ge=70, le=260)


class GsgfCalibrationRequest(BaseModel):
    trade_dates: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    windows: list[int] = Field(default_factory=lambda: [1, 3, 5, 10], max_length=8)
    scan_limit: int = Field(default=80, ge=1, le=300)
    count: int = Field(default=260, ge=70, le=260)


class GsgfTradePlanRequest(BaseModel):
    analysis: GsgfAnalysis


class GsgfReviewRecheckRequest(BaseModel):
    windows: list[int] = Field(default_factory=lambda: [1, 3, 5, 10], max_length=8)
    count: int = Field(default=180, ge=20, le=260)


class IntradaySnapshotRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=100)
    watchlist_text: str = ""
    use_watchlist_pool: bool = False
    gsgf_context: dict[str, dict[str, object]] = Field(default_factory=dict)
    limit: int = Field(default=30, ge=1, le=100)
    period: str = Field(default="1m", pattern=r"^(1m|5m|10m|15m|30m|60m)$")
    count: int = Field(default=120, ge=1, le=240)


class WatchlistPoolRequest(BaseModel):
    content: str = ""


class WatchlistPoolItemRequest(BaseModel):
    symbol: str
    name: str | None = None
    industry: str | None = None
    group: str = "自选"
    tags: list[str] = Field(default_factory=list, max_length=20)
    note: str | None = None


class HealthProbe(BaseModel):
    name: str
    status: str
    latency_ms: int
    detail: str


class NotificationSendRequest(BaseModel):
    title: str
    message_text: str
    channel_ids: list[str] = Field(default_factory=list, max_length=20)


def _cors_allow_origins() -> list[str]:
    settings = get_settings()
    return [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup_sentiment_monitor()
    startup_gsgf_auto_review()
    startup_auction_sampler()
    startup_sector_workbench_sampler()
    try:
        yield
    finally:
        shutdown_sector_workbench_sampler()
        shutdown_auction_sampler()
        shutdown_gsgf_auto_review()
        shutdown_sentiment_monitor()


app = FastAPI(title="强势股选股 API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SHORT_TERM_SENTIMENT_CACHE: TtlCache[ShortTermSentimentResponse] = TtlCache(
    ttl_seconds=90, name="short_term_sentiment"
)
MARKET_EMOTION_CACHE: TtlCache[MarketEmotionSnapshotResponse] = TtlCache(
    ttl_seconds=45, name="market_emotion"
)
MARKET_OVERVIEW_CACHE: TtlCache[MarketOverviewResponse] = TtlCache(
    ttl_seconds=45, name="market_overview"
)
MARKET_RANKINGS_CACHE: TtlCache[MarketRankingsResponse] = TtlCache(
    ttl_seconds=45, name="market_rankings"
)
AUCTION_SNAPSHOT_CACHE: TtlCache[AuctionSnapshotResponse] = TtlCache(
    ttl_seconds=15, name="auction_snapshot"
)
SECTOR_RADAR_CACHE: TtlCache[SectorRadarResponse] = TtlCache(ttl_seconds=45, name="sector_radar")
PLATE_ROTATION_REFERENCE_CACHE: TtlCache[PlateRotationReferenceResponse] = TtlCache(
    ttl_seconds=120, name="plate_rotation_reference"
)
SECTOR_INTRADAY_CACHE: TtlCache[tuple[list[SectorWorkbenchSeries], StrongStockSourceStatus]] = TtlCache(
    ttl_seconds=90,
    name="sector_intraday",
)
SECTOR_THEME_ROWS_CACHE: TtlCache[tuple[list[dict[str, object]], StrongStockSourceStatus | None]] = TtlCache(
    ttl_seconds=300,
    name="sector_theme_rows",
)
STOCK_KLINE_CACHE: TtlCache[StockKlineResponse] = TtlCache(ttl_seconds=300, name="stock_kline")
STOCK_RESEARCH_CACHE: TtlCache[StockResearchResponse] = TtlCache(
    ttl_seconds=900, name="stock_research"
)
CACHE_DEFINITIONS = (
    ("short_term_sentiment", "sentiment", SHORT_TERM_SENTIMENT_CACHE),
    ("market_emotion", "sentiment", MARKET_EMOTION_CACHE),
    ("market_overview", "home", MARKET_OVERVIEW_CACHE),
    ("market_rankings", "home", MARKET_RANKINGS_CACHE),
    ("auction_snapshot", "auction", AUCTION_SNAPSHOT_CACHE),
    ("sector_radar", "sectors", SECTOR_RADAR_CACHE),
    ("plate_rotation_reference", "sectors", PLATE_ROTATION_REFERENCE_CACHE),
    ("sector_intraday", "sectors", SECTOR_INTRADAY_CACHE),
    ("sector_theme_rows", "sectors", SECTOR_THEME_ROWS_CACHE),
    ("stock_kline", "stocks", STOCK_KLINE_CACHE),
    ("stock_research", "stocks", STOCK_RESEARCH_CACHE),
)
CACHE_GROUPS = frozenset(cache_group for _cache_name, cache_group, _cache in CACHE_DEFINITIONS)
CACHE_REGISTRY = CacheRegistry()
for cache_name, cache_group, cache in CACHE_DEFINITIONS:
    CACHE_REGISTRY.register(cache_name, cache, group=cache_group)


def startup_sentiment_monitor() -> None:
    if load_runtime_settings(_runtime_config_path()).sentiment_monitor.enabled:
        _sentiment_monitor().start()


def shutdown_sentiment_monitor() -> None:
    monitor = getattr(app.state, "sentiment_monitor", None)
    if monitor is not None:
        monitor.stop()


def startup_auction_sampler() -> None:
    if getattr(app.state, "auction_sampler_disabled", False):
        return
    sampler = getattr(app.state, "auction_sampler", None)
    if sampler is None:
        sampler = AuctionSnapshotSampler(refresh=lambda: _refresh_auction_snapshot(100))
        app.state.auction_sampler = sampler
    sampler.start()


def shutdown_auction_sampler() -> None:
    sampler = getattr(app.state, "auction_sampler", None)
    if sampler is not None:
        sampler.stop()


def startup_sector_workbench_sampler() -> None:
    if getattr(app.state, "sector_workbench_sampler_disabled", False):
        return
    sampler = getattr(app.state, "sector_workbench_sampler", None)
    if sampler is None:
        sampler = SectorWorkbenchSampler(refresh=_sample_sector_workbench)
        app.state.sector_workbench_sampler = sampler
    sampler.start()


def shutdown_sector_workbench_sampler() -> None:
    sampler = getattr(app.state, "sector_workbench_sampler", None)
    if sampler is not None:
        sampler.stop()


def startup_gsgf_auto_review() -> None:
    _gsgf_auto_review_service().start()


def shutdown_gsgf_auto_review() -> None:
    service = getattr(app.state, "gsgf_auto_review_service", None)
    if service is not None:
        service.stop()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/system/cache", response_model=SystemCacheSummary)
def get_system_cache() -> SystemCacheSummary:
    return SystemCacheSummary.model_validate(CACHE_REGISTRY.summary())


@app.post("/api/system/cache/clear", response_model=SystemCacheClearResponse)
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


@app.get("/api/system/status", response_model=SystemStatusResponse)
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


@app.get("/api/data-sources/status")
def data_source_status() -> dict[str, object]:
    candidate_provider = _candidate_provider()
    kline_provider = _kline_provider()
    quote_provider = _quote_provider()
    news_risk_provider = _news_risk_provider()
    candidate_status = candidate_provider.status() if hasattr(candidate_provider, "status") else None
    kline_status = kline_provider.status() if hasattr(kline_provider, "status") else None
    quote_status = quote_provider.status() if hasattr(quote_provider, "status") else None
    news_risk_status = news_risk_provider.status() if hasattr(news_risk_provider, "status") else None
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


@app.get("/api/settings")
def get_runtime_settings() -> dict[str, object]:
    return {
        "config": public_settings_payload(_effective_settings()),
        "saved": _public_saved_settings(),
    }


@app.put("/api/settings")
def update_runtime_settings(request: SettingsUpdate) -> dict[str, object]:
    save_runtime_settings(_runtime_config_path(), request)
    _clear_data_source_caches()
    return {
        "config": public_settings_payload(_effective_settings()),
        "saved": _public_saved_settings(),
    }


@app.post("/api/notifications/send")
def send_notification(request: NotificationSendRequest) -> dict[str, object]:
    runtime = load_runtime_settings(_runtime_config_path())
    result: NotificationSendResult = send_notification_message(
        NotificationSettings(channels=runtime.notification_channels),
        title=request.title,
        message_text=request.message_text,
        channel_ids=request.channel_ids,
        http_client=getattr(app.state, "notification_http_client", None),
        smtp_client=getattr(app.state, "notification_smtp_client", None) or DefaultSmtpClient(),
    )
    return result.model_dump(mode="json")


@app.get("/api/short-term/sentiment/monitor/status")
def get_sentiment_monitor_status() -> dict[str, object]:
    return _sentiment_monitor().status().model_dump(mode="json")


@app.put("/api/short-term/sentiment/monitor/config")
def update_sentiment_monitor_config(request: SentimentMonitorConfig) -> dict[str, object]:
    _save_sentiment_monitor_config(request)
    monitor = _sentiment_monitor()
    if request.enabled:
        return monitor.start().model_dump(mode="json")
    return monitor.stop().model_dump(mode="json")


@app.post("/api/short-term/sentiment/monitor/start")
def start_sentiment_monitor() -> dict[str, object]:
    current = load_runtime_settings(_runtime_config_path()).sentiment_monitor
    _save_sentiment_monitor_config(current.model_copy(update={"enabled": True}))
    return _sentiment_monitor().start().model_dump(mode="json")


@app.post("/api/short-term/sentiment/monitor/stop")
def stop_sentiment_monitor() -> dict[str, object]:
    current = load_runtime_settings(_runtime_config_path()).sentiment_monitor
    _save_sentiment_monitor_config(current.model_copy(update={"enabled": False}))
    return _sentiment_monitor().stop().model_dump(mode="json")


@app.post("/api/short-term/sentiment/monitor/run-once")
def run_sentiment_monitor_once(trade_date: str | None = None) -> dict[str, object]:
    return _sentiment_monitor().run_once(trade_date).model_dump(mode="json")


@app.get("/api/settings/health")
def settings_health(symbol: str = "605289.SH") -> dict[str, object]:
    quote_provider = _quote_provider()
    ifind_provider = _ifind_provider()
    settings = _effective_settings()
    return {
        "config": public_settings_payload(_effective_settings()),
        "probes": [
            _probe(
                getattr(_candidate_provider(), "source_name", "候选池"),
                lambda: _candidate_provider().status()
                if hasattr(_candidate_provider(), "status")
                else StrongStockSourceStatus(source="候选池", status="success", detail="候选池源已配置"),
            ).model_dump(mode="json"),
            _probe(
                getattr(_kline_provider(), "source_name", "K线"),
                lambda: _kline_provider().get_klines(symbol, count=5),
            ).model_dump(mode="json"),
            _probe(
                "TickFlow 实时行情",
                lambda: quote_provider.get_quotes([symbol]),
            ).model_dump(mode="json"),
            _probe(
                "TickFlow 当日分钟线",
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


@app.post("/api/screen/runs")
def create_screen_run(request: ScreenRunRequest) -> dict[str, object]:
    try:
        result = _execute_screen_run(request)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.post("/api/screen/runs/jobs")
def create_screen_run_job(request: ScreenRunRequest) -> dict[str, object]:
    store = _background_job_store()
    active_job = store.get_active("screen_run")
    if active_job is not None:
        return active_job.model_dump(mode="json")
    job_request = request.model_copy(deep=True)
    job = store.create_transient_job(
        "screen_run",
        lambda progress, should_cancel: _execute_screen_run_job(job_request, progress, should_cancel),
        running_message="选股任务运行中",
        success_message="选股任务完成",
        progress_total=4,
    )
    return job.model_dump(mode="json")


@app.get("/api/screen/runs/jobs/{job_id}")
def get_screen_run_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="screen run job not found") from exc
    return job.model_dump(mode="json")


def _execute_screen_run_job(
    request: ScreenRunRequest,
    progress: ProgressCallback,
    should_cancel: CancelCheck,
) -> dict[str, object]:
    if should_cancel():
        raise RuntimeError("筛选任务已取消")
    result = _execute_screen_run(request, progress=progress, should_cancel=should_cancel)
    return result.model_dump(mode="json")


def _execute_screen_run(
    request: ScreenRunRequest,
    progress: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> StrongStockScreeningResult:
    if progress is not None:
        progress(1, 4, "准备候选池和数据源")
    if should_cancel is not None and should_cancel():
        raise RuntimeError("筛选任务已取消")
    screener = StrongStockScreener(
        candidate_provider=_candidate_provider(),
        kline_provider=_kline_provider(),
        news_risk_provider=_news_risk_provider(),
    )
    if progress is not None:
        progress(2, 4, f"扫描 {request.scan_limit} 只候选并计算K线结构")
    if should_cancel is not None and should_cancel():
        raise RuntimeError("筛选任务已取消")
    result = screener.screen(
        trade_date=request.trade_date,
        limit=request.limit,
        scan_limit=request.scan_limit,
        filters=request.filters,
        watchlist_snapshot=_watchlist_snapshot(),
        strategy=request.strategy,
        exclude_gsgf_hard_risk=request.exclude_gsgf_hard_risk,
    )
    if progress is not None:
        progress(3, 4, "保存筛选记录")
    _run_store().save(result)
    auto_review_config = load_runtime_settings(_runtime_config_path()).gsgf_auto_review
    if auto_review_config.auto_snapshot_enabled and any(item.gsgf is not None for item in result.items):
        _gsgf_review_store().persist_snapshot(result, dedupe=True)
    if progress is not None:
        progress(4, 4, "筛选完成")
    return result


@app.get("/api/screen/runs/latest")
def get_latest_screen_run() -> dict[str, object]:
    result = _run_store().load_latest()
    if result is None:
        raise HTTPException(status_code=404, detail="no screen run")
    return result.model_dump(mode="json")


@app.post("/api/gsgf/backtest")
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


@app.post("/api/gsgf/calibration")
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


@app.post("/api/gsgf/calibration/jobs")
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


@app.get("/api/gsgf/calibration/jobs/{job_id}")
def get_gsgf_calibration_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="calibration job not found") from exc
    return job.model_dump(mode="json")


@app.post("/api/gsgf/calibration/jobs/{job_id}/cancel")
def cancel_gsgf_calibration_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="calibration job not found") from exc
    return job.model_dump(mode="json")


@app.get("/api/gsgf/calibration/latest")
def get_latest_gsgf_calibration() -> dict[str, object]:
    result = _background_job_store().load_latest_calibration()
    if result is None:
        raise HTTPException(status_code=404, detail="no gsgf calibration result")
    return result.model_dump(mode="json")


@app.post("/api/gsgf/trade-plan")
def create_gsgf_trade_plan(request: GsgfTradePlanRequest) -> dict[str, object]:
    plan: GsgfTradePlan = build_gsgf_trade_plan(request.analysis)
    return plan.model_dump(mode="json")


@app.post("/api/gsgf/review/snapshots/latest")
def create_gsgf_review_snapshot_from_latest() -> dict[str, object]:
    result = _run_store().load_latest()
    if result is None:
        raise HTTPException(status_code=404, detail="no screen run")
    snapshot: GsgfReviewSnapshotResponse = _gsgf_review_store().persist_snapshot(result, dedupe=True)
    return snapshot.model_dump(mode="json")


@app.post("/api/gsgf/review/recheck")
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


@app.get("/api/gsgf/review/latest")
def get_latest_gsgf_review() -> dict[str, object]:
    summary = _gsgf_review_store().load_latest_summary()
    if summary is None:
        raise HTTPException(status_code=404, detail="no gsgf review summary")
    return summary.model_dump(mode="json")


@app.get("/api/gsgf/health")
def get_gsgf_model_health() -> dict[str, object]:
    health = _gsgf_model_health()
    return health.model_dump(mode="json")


@app.post("/api/model-maintenance/packets/generate", response_model=ModelMaintenancePacket)
def generate_model_maintenance_packet() -> ModelMaintenancePacket:
    latest_screen_run = _run_store().load_latest()
    source_status = latest_screen_run.source_status if latest_screen_run is not None else []
    packet = build_model_maintenance_packet(
        trade_date=latest_screen_run.trade_date if latest_screen_run is not None else None,
        latest_screen_run=latest_screen_run,
        review_summary=_gsgf_review_store().load_latest_summary(),
        calibration_summary=_background_job_store().load_latest_calibration(),
        source_status=source_status,
    )
    return _model_maintenance_store().save_packet(packet)


@app.get("/api/model-maintenance/packets/latest", response_model=ModelMaintenancePacket | None)
def get_latest_model_maintenance_packet() -> ModelMaintenancePacket | None:
    return _model_maintenance_store().load_latest_packet()


@app.post("/api/model-maintenance/analyze", response_model=ModelMaintenanceReport)
def analyze_model_maintenance() -> ModelMaintenanceReport:
    store = _model_maintenance_store()
    packet = store.load_latest_packet()
    if packet is None:
        packet = generate_model_maintenance_packet()
    return store.save_report(
        analyze_model_maintenance_packet(
            packet,
            _effective_settings().ai_analysis,
            http_client=getattr(app.state, "model_maintenance_http_client", None),
        )
    )


@app.get("/api/model-maintenance/reports/latest", response_model=ModelMaintenanceReport | None)
def get_latest_model_maintenance_report() -> ModelMaintenanceReport | None:
    return _model_maintenance_store().load_latest_report()


@app.get("/api/model-maintenance/reports", response_model=list[ModelMaintenanceReport])
def list_model_maintenance_reports(limit: int = 20) -> list[ModelMaintenanceReport]:
    return _model_maintenance_store().list_reports(limit)


@app.post("/api/model-maintenance/suggestions/{suggestion_id}/accept", response_model=ModelMaintenanceSuggestion)
def accept_model_maintenance_suggestion(suggestion_id: str) -> ModelMaintenanceSuggestion:
    try:
        return _model_maintenance_store().update_suggestion_status(suggestion_id, "accepted")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="建议不存在") from exc


@app.post("/api/model-maintenance/suggestions/{suggestion_id}/ignore", response_model=ModelMaintenanceSuggestion)
def ignore_model_maintenance_suggestion(suggestion_id: str) -> ModelMaintenanceSuggestion:
    try:
        return _model_maintenance_store().update_suggestion_status(suggestion_id, "ignored")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="建议不存在") from exc


@app.post("/api/model-maintenance/suggestions/{suggestion_id}/snooze", response_model=ModelMaintenanceSuggestion)
def snooze_model_maintenance_suggestion(suggestion_id: str) -> ModelMaintenanceSuggestion:
    try:
        return _model_maintenance_store().update_suggestion_status(suggestion_id, "snoozed")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="建议不存在") from exc


@app.get("/api/market/overview")
def get_market_overview() -> dict[str, object]:
    result = _cached_market_overview()
    return result.model_dump(mode="json")


@app.get("/api/market/rankings")
def get_market_rankings(limit: int = 50) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    try:
        result = _cached_market_rankings(bounded_limit)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"全A实时排行榜获取失败: {exc.__class__.__name__}") from exc
    return result.model_dump(mode="json")


@app.get("/api/auction/latest")
def get_latest_auction_snapshot(limit: int = 100) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    result = _auction_snapshot_store().latest(limit=bounded_limit)
    return result.model_dump(mode="json")


@app.get("/api/auction/timeline")
def get_auction_timeline(limit: int = 8) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 20))
    result: AuctionTimelineResponse = _auction_snapshot_store().timeline(limit=bounded_limit)
    return result.model_dump(mode="json")


@app.get("/api/auction/model/top3")
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
        result: AuctionModelTop3Response = _auction_model_service().predict_top3(trade_date)
        store.save_top3(result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="trade_date must use YYYY-MM-DD") from exc
    except (FileNotFoundError, AuctionModelDataError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.get("/api/auction/snapshot")
def get_auction_snapshot(limit: int = 100, refresh: bool = False) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    try:
        result = _refresh_auction_snapshot(bounded_limit) if refresh else _cached_auction_snapshot(bounded_limit)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"竞价雷达获取失败: {exc.__class__.__name__}") from exc
    return result.model_dump(mode="json")


@app.post("/api/auction/snapshot/jobs")
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


@app.get("/api/auction/snapshot/jobs/{job_id}")
def get_auction_snapshot_job(job_id: str) -> dict[str, object]:
    try:
        job = _background_job_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="auction snapshot job not found") from exc
    return job.model_dump(mode="json")


@app.get("/api/auction/review/latest")
def get_latest_auction_review() -> dict[str, object]:
    summary = _auction_review_store().load_latest_summary()
    if summary is None:
        raise HTTPException(status_code=404, detail="no auction review summary")
    return summary.model_dump(mode="json")


@app.get("/api/auction/review")
def get_auction_review(trade_date: str | None = None, limit: int = 100) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 500))
    records = _auction_review_store().load_records(trade_date, limit=bounded_limit)
    summary = _auction_review_summary(records, trade_date=trade_date)
    return summary.model_dump(mode="json")


@app.post("/api/auction/review/finalize")
def finalize_auction_review(trade_date: str) -> dict[str, object]:
    store = _auction_review_store()
    records = store.load_records(trade_date)
    latest_snapshot = _auction_snapshot_store().latest(max_age_seconds=24 * 3600, limit=100)
    can_seed_from_latest = latest_snapshot.snapshot_status != "missing" and latest_snapshot.trade_date == trade_date
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
    symbol_bars = {
        symbol: provider.get_klines(symbol, count=260)
        for symbol in sorted({record.symbol for record in records})
    }
    summary = finalize_auction_records(records, symbol_bars=symbol_bars)
    store.upsert_records(summary.records)
    store.save_summary(summary)
    return summary.model_dump(mode="json")


@app.post("/api/auction/review/backfill")
def backfill_auction_review(
    start_date: str,
    end_date: str,
    max_days: int = 20,
) -> dict[str, object]:
    _ = (start_date, end_date, max_days)
    return AuctionBackfillResponse().model_dump(mode="json")


@app.get("/api/auction/rules/summary")
def get_auction_rules_summary(limit: int = 2000) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 10000))
    records = _auction_review_store().load_records(limit=bounded_limit)
    summary = _auction_review_summary(records, trade_date=None)
    return summary.model_dump(mode="json")


@app.get("/api/sectors/radar")
def get_sector_radar(limit: int = 20) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 50))
    result = _cached_sector_radar(bounded_limit)
    return result.model_dump(mode="json")


@app.get("/api/sectors/plate-reference")
def get_plate_rotation_reference(
    limit: int = 20,
    source: str = "kaipan",
    days: int = 20,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 50))
    bounded_days = max(1, min(days, 50))
    normalized_source = "ths" if source == "ths" else "kaipan"
    cache_key = f"plate-reference:{normalized_source}:{bounded_days}:{bounded_limit}:{_provider_cache_key(_plate_rotation_reference_provider())}"
    result = PLATE_ROTATION_REFERENCE_CACHE.get_or_set(
        cache_key,
        lambda: _plate_rotation_reference_provider().get_today_themes(
            limit=bounded_limit,
            source=normalized_source,
            days=bounded_days,
        ),
    )
    return result.model_dump(mode="json")


@app.get("/api/sectors/workbench")
def get_sector_workbench(
    mode: SectorWorkbenchMode = "strength",
    scope: SectorWorkbenchScopeRequest = "auto",
    selected: str = "",
    limit: int = 20,
    stock_limit: int = 50,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 50))
    bounded_stock_limit = max(1, min(stock_limit, 200))
    selected_names = [part.strip() for part in selected.split(",") if part.strip()]
    sampled_at = _sector_now()
    try:
        rankings = _cached_market_rankings(100)
    except Exception:
        radar = _cached_sector_radar(bounded_limit)
        result = build_sector_workbench_from_radar(
            radar=radar,
            mode=mode,
            scope=scope,
            selected=selected_names,
            limit=bounded_limit,
            sampled_at=sampled_at,
        )
    else:
        limit_up_rows: list[dict[str, object]] = []
        theme_status: StrongStockSourceStatus | None = None
        if scope in ("auto", "theme"):
            limit_up_rows, theme_status = _sector_theme_rows()
        result = build_sector_workbench_response(
            rankings=rankings,
            limit_up_rows=limit_up_rows,
            mode=mode,
            scope=scope,
            selected=selected_names,
            limit=bounded_limit,
            stock_limit=bounded_stock_limit,
            sampled_at=sampled_at,
            theme_source=theme_status.source if theme_status is not None else "通达信MCP涨停概念映射",
        )
        if theme_status is not None and result.scope == "industry" and scope != "industry":
            result.source_status.insert(0, theme_status)
    snapshot_result = result.model_copy(deep=True)
    store = _sector_workbench_store()
    intraday_history = store.series_for(
        trade_date=result.trade_date,
        mode=result.mode,
        scope=result.scope,
        selected=result.selected_themes,
        metric=result.mode,
        sample_source="intraday",
    )
    sampled_history = store.series_for(
        trade_date=result.trade_date,
        mode=result.mode,
        scope=result.scope,
        selected=result.selected_themes,
        metric=result.mode,
        sample_source="snapshot",
    )
    is_trading_sample_time = is_sector_workbench_sample_window(sampled_at)
    theme_snapshot_pending = any(
        item.source == "题材快照" and item.status == "stale"
        for item in result.source_status
    )
    if intraday_history:
        result.series = intraday_history
        result.source_status.append(
            StrongStockSourceStatus(
                source="TickFlow 当日分钟线",
                status="success",
                detail=f"读取本地持久化分钟线曲线 {len(intraday_history)} 条",
            )
        )
    elif sampled_history:
        result.series = sampled_history
        result.source_status.append(
            StrongStockSourceStatus(
                source="板块分时本地采样",
                status="success",
                detail=f"读取本地采样曲线 {len(sampled_history)} 条；分钟线仍以后台补齐状态为准",
            )
        )
        intraday_status = _cached_sector_intraday_status(result)
        if intraday_status is not None:
            result.source_status.append(intraday_status)
        else:
            _schedule_sector_intraday_refresh(result)
            result.source_status.append(
                StrongStockSourceStatus(
                    source="TickFlow 当日分钟线",
                    status="stale",
                    detail="本地分钟线曲线未就绪，已触发后台补齐；本次先返回采样曲线",
                )
            )
    elif theme_snapshot_pending:
        if not is_trading_sample_time:
            result.series = []
        result.source_status.append(
            StrongStockSourceStatus(
                source="TickFlow 当日分钟线",
                status="disabled",
                detail="题材快照未就绪，跳过分钟线补齐以保证首屏速度",
            )
        )
    else:
        _schedule_sector_intraday_refresh(result)
        if not is_trading_sample_time:
            result.series = []
        result.source_status.append(
            StrongStockSourceStatus(
                source="TickFlow 当日分钟线",
                status="stale",
                detail=(
                    "本地分时曲线未就绪，已触发后台补齐；本次先返回当前快照"
                    if is_trading_sample_time
                    else "本地分时曲线未就绪，已触发后台补齐；当前不在交易时段，暂不返回盘后快照点"
                ),
            )
        )
    if is_trading_sample_time:
        store.append(snapshot_result, sample_source="snapshot")
    return result.model_dump(mode="json")


@app.get("/api/sectors/workbench/status")
def get_sector_workbench_status(trade_date: str | None = None) -> dict[str, object]:
    current = _sector_now()
    date_text = (trade_date or current.date().isoformat()).strip()
    sample_window_open = is_sector_workbench_sample_window(current)
    sampler_disabled = bool(getattr(app.state, "sector_workbench_sampler_disabled", False))
    sampler = getattr(app.state, "sector_workbench_sampler", None)
    sampler_running = bool(getattr(sampler, "running", False))
    interval_seconds = getattr(sampler, "interval_seconds", None)
    idle_seconds = getattr(sampler, "idle_seconds", None)
    cache_summary = SectorWorkbenchCacheSummary.model_validate(
        _sector_workbench_store().summary(date_text)
    )
    if cache_summary.sample_count > 0:
        cache_detail = (
            f"本地缓存 {cache_summary.sample_count} 个采样点"
            f"，最近 {cache_summary.latest_sampled_at or '--'}"
        )
        cache_status = StrongStockSourceStatus(
            source="板块分时持久化",
            status="success",
            detail=cache_detail,
        )
    else:
        cache_status = StrongStockSourceStatus(
            source="板块分时持久化",
            status="stale",
            detail=f"{date_text} 暂无本地采样曲线",
        )
    if sampler_disabled:
        sampler_status = StrongStockSourceStatus(
            source="板块后台采样器",
            status="disabled",
            detail="当前测试或配置禁用了后台采样",
        )
    elif sampler_running:
        sampler_status = StrongStockSourceStatus(
            source="板块后台采样器",
            status="success",
            detail=(
                f"采样器运行中；交易时段约 {interval_seconds or '--'} 秒一次，"
                f"非交易时段约 {idle_seconds or '--'} 秒巡检"
            ),
        )
    else:
        sampler_status = StrongStockSourceStatus(
            source="板块后台采样器",
            status="stale",
            detail="采样器未运行，页面仅能读取已有缓存或当前快照",
        )
    response = SectorWorkbenchStatusResponse(
        trade_date=date_text,
        sample_window_open=sample_window_open,
        sampler_enabled=not sampler_disabled,
        sampler_running=sampler_running,
        interval_seconds=interval_seconds,
        idle_seconds=idle_seconds,
        cache=cache_summary,
        source_status=[cache_status, sampler_status],
    )
    return response.model_dump(mode="json")


@app.get("/api/short-term/sentiment")
def get_short_term_sentiment(trade_date: str, limit: int = 50) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    try:
        result = _cached_short_term_sentiment(trade_date, bounded_limit)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.get("/api/short-term/sentiment/summary")
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


@app.get("/api/short-term/sentiment/decision")
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


@app.post("/api/short-term/sentiment/review/archive")
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


@app.get("/api/short-term/sentiment/watchlist-alerts")
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


@app.get("/api/short-term/sentiment/detail")
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
        sentiment, market_emotion = _build_and_persist_sentiment_snapshots(trade_date, bounded_limit)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SentimentDetailResponse(
        trade_date=trade_date,
        snapshot_status="fresh",
        sentiment=sentiment,
        market_emotion=market_emotion,
    ).model_dump(mode="json")


@app.get("/api/short-term/market-emotion")
def get_short_term_market_emotion(trade_date: str, limit: int = 80) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    candidate_provider = _candidate_provider()
    market_overview_provider = _market_overview_provider()
    try:
        cache_key = (
            "market-emotion:"
            f"{_provider_cache_key(candidate_provider)}:"
            f"{_provider_cache_key(market_overview_provider)}:"
            f"{trade_date}:{bounded_limit}"
        )
        result = MARKET_EMOTION_CACHE.get_or_set(
            cache_key,
            lambda: build_market_emotion_snapshot(
                candidate_provider,
                market_overview_provider,
                trade_date=trade_date,
                limit=bounded_limit,
                sentiment_snapshot=_cached_short_term_sentiment(trade_date, bounded_limit),
            ),
        ).model_copy(deep=True)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        history_store = _market_emotion_history_store()
        history_store.append(result)
        result.samples = history_store.load(trade_date)
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


@app.get("/api/short-term/sentiment/intraday")
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


@app.get("/api/short-term/sentiment/intraday/digest")
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


@app.get("/api/stocks/{symbol}/kline")
def get_stock_kline(symbol: str, count: int = 220) -> dict[str, object]:
    bounded_count = max(1, min(count, 260))
    try:
        result = _cached_stock_kline(symbol, bounded_count)
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"K线获取失败: {exc.__class__.__name__}") from exc
    return result.model_dump(mode="json")


@app.get("/api/stocks/{symbol}/quote")
def get_stock_quote(symbol: str) -> dict[str, object]:
    quote_provider = _quote_provider()
    try:
        quotes = quote_provider.get_quotes([symbol])
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"实时行情获取失败: {exc.__class__.__name__}") from exc
    if not quotes:
        raise HTTPException(status_code=503, detail="实时行情未返回数据")
    quote = quotes[0]
    industry = _stock_industry_for_symbol(quote.symbol)
    source_status = (
        quote_provider.status()
        if hasattr(quote_provider, "status")
        else StrongStockSourceStatus(source=getattr(quote_provider, "source_name", "实时行情"), status="success", detail="实时行情源已配置")
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
        source_status=source_status,
    ).model_dump(mode="json")


@app.get("/api/stocks/{symbol}/research")
def get_stock_research(symbol: str) -> dict[str, object]:
    research = _cached_stock_research(symbol)
    return research.model_dump(mode="json")


@app.post("/api/intraday/snapshot")
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
            gsgf_context={symbol.strip().upper(): value for symbol, value in request.gsgf_context.items()},
            limit=request.limit,
            period=request.period,
            count=request.count,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.get("/api/watchlist/pool")
def get_watchlist_pool() -> dict[str, object]:
    content = _read_watchlist_pool()
    items = parse_watchlist_text(content)
    return {
        "content": content,
        "items": [item.model_dump(mode="json") for item in items],
    }


@app.put("/api/watchlist/pool")
def update_watchlist_pool(request: WatchlistPoolRequest) -> dict[str, object]:
    path = _watchlist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = request.content.strip()
    path.write_text(content, encoding="utf-8")
    items = parse_watchlist_text(content)
    return {
        "content": content,
        "items": [item.model_dump(mode="json") for item in items],
    }


@app.post("/api/watchlist/pool/items")
def add_watchlist_pool_item(request: WatchlistPoolItemRequest) -> dict[str, object]:
    path = _watchlist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = upsert_watchlist_item(
        _read_watchlist_pool(),
        WatchlistItem(
            symbol=request.symbol,
            name=request.name,
            industry=request.industry,
            group=request.group,
            tags=request.tags,
            note=request.note,
        ),
    )
    path.write_text(content, encoding="utf-8")
    items = parse_watchlist_text(content)
    return {
        "content": content,
        "items": [item.model_dump(mode="json") for item in items],
    }


@app.get("/api/watchlist/gsgf-status")
def get_watchlist_gsgf_status() -> dict[str, object]:
    items = parse_watchlist_text(_read_watchlist_pool())
    output: list[dict[str, object]] = []
    for item in items:
        try:
            bars = _kline_provider().get_klines(item.symbol, count=220)
            gsgf = analyze_gsgf(bars)
        except Exception as exc:
            gsgf = GsgfAnalysis(
                risk_flags=[f"K线获取失败: {exc.__class__.__name__}"],
                explanation=["自选股结构触发暂不可计算"],
            )
        output.append({**item.model_dump(mode="json"), "gsgf": gsgf.model_dump(mode="json")})
    return {"items": output}


def _cached_short_term_sentiment(trade_date: str, limit: int) -> ShortTermSentimentResponse:
    candidate_provider = _candidate_provider()
    cache_key = f"sentiment:{_provider_cache_key(candidate_provider)}:{trade_date}:{limit}"
    return SHORT_TERM_SENTIMENT_CACHE.get_or_set(
        cache_key,
        lambda: build_short_term_sentiment(
            candidate_provider,
            trade_date=trade_date,
            limit=limit,
        ),
    ).model_copy(deep=True)


def _cached_market_overview() -> MarketOverviewResponse:
    provider = _market_overview_provider()
    cache_key = f"market-overview:{_provider_cache_key(provider)}"
    return MARKET_OVERVIEW_CACHE.get_or_set(cache_key, provider.get_overview).model_copy(deep=True)


def _cached_market_rankings(limit: int) -> MarketRankingsResponse:
    provider = _market_overview_provider()
    cache_key = f"market-rankings:{_provider_cache_key(provider)}:{limit}"
    if not hasattr(provider, "get_market_rankings"):
        raise StrongStockDataUnavailable("当前市场概览源不支持全A实时排行榜")
    return MARKET_RANKINGS_CACHE.get_or_refresh(
        cache_key,
        lambda: provider.get_market_rankings(limit=limit),
    ).model_copy(deep=True)


def _refresh_market_rankings(limit: int) -> MarketRankingsResponse:
    provider = _market_overview_provider()
    if not hasattr(provider, "get_market_rankings"):
        raise StrongStockDataUnavailable("当前市场概览源不支持全A实时排行榜")
    return provider.get_market_rankings(limit=limit).model_copy(deep=True)


def _auction_model_service() -> AuctionModelService:
    injected = getattr(app.state, "auction_model_service", None)
    if injected is not None:
        return injected
    settings = get_settings()
    return AuctionModelService(
        source=FreeStockDbAuctionModelSource(
            base_url=settings.auction_model_free_stockdb_base_url,
            timeout_seconds=settings.auction_model_timeout_seconds,
        ),
        model_path=Path(settings.auction_model_model_path),
        metadata_path=Path(settings.auction_model_metadata_path),
        performance_path=Path(settings.auction_model_performance_path),
        lookback=settings.auction_model_lookback,
        top_n=settings.auction_model_top_n,
        max_items=settings.auction_model_max_items,
    )


def _auction_model_result_store() -> AuctionModelResultStore:
    injected = getattr(app.state, "auction_model_result_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    return AuctionModelResultStore(data_dir)


def _cached_auction_snapshot(limit: int) -> AuctionSnapshotResponse:
    provider = _market_overview_provider()
    hot_themes, hot_theme_status = _auction_hot_theme_refs()
    cache_key = (
        f"auction-snapshot:{_provider_cache_key(provider)}:"
        f"{_provider_cache_key(_plate_rotation_reference_provider())}:"
        f"{json.dumps(hot_themes, ensure_ascii=False, sort_keys=True)}:{limit}"
    )
    result = AUCTION_SNAPSHOT_CACHE.get_or_refresh(
        cache_key,
        lambda: build_auction_snapshot(
            _cached_market_rankings(max(limit, 100)),
            limit=limit,
            now=getattr(app.state, "auction_now", None),
            hot_themes=hot_themes,
        ),
    ).model_copy(deep=True)
    _append_empty_hot_theme_status(result, hot_themes, hot_theme_status)
    _auction_snapshot_store().save(result, captured_at=_auction_now())
    return result


def _refresh_auction_snapshot(limit: int) -> AuctionSnapshotResponse:
    now = _auction_now()
    hot_themes, hot_theme_status = _auction_hot_theme_refs()
    result = build_auction_snapshot(
        _refresh_market_rankings(max(limit, 100)),
        limit=limit,
        now=now,
        hot_themes=hot_themes,
    )
    _append_empty_hot_theme_status(result, hot_themes, hot_theme_status)
    return _auction_snapshot_store().save(result, captured_at=now)


def _auction_hot_theme_refs() -> tuple[list[tuple[str, int, float]], StrongStockSourceStatus | None]:
    try:
        reference = _plate_rotation_reference_provider().get_today_themes(limit=10, source="kaipan", days=20)
    except Exception as exc:
        return [], StrongStockSourceStatus(
            source="短线题材联动",
            status="failed",
            detail=f"读取短线题材参考榜失败: {exc.__class__.__name__}",
        )
    refs = [(item.name, item.rank, item.score) for item in reference.themes[:10]]
    status = reference.source_status[0] if reference.source_status else None
    return refs, status


def _append_empty_hot_theme_status(
    result: AuctionSnapshotResponse,
    hot_themes: list[tuple[str, int, float]],
    status: StrongStockSourceStatus | None,
) -> None:
    if hot_themes or status is None:
        return
    result.source_status.append(
        StrongStockSourceStatus(
            source="短线题材联动",
            status=status.status,
            detail=status.detail,
        )
    )


def _run_auction_snapshot_refresh_job(
    limit: int,
    progress: ProgressCallback,
    should_cancel: CancelCheck,
) -> AuctionSnapshotResponse:
    if should_cancel():
        raise RuntimeError("竞价刷新已取消")
    progress(0, 3, "准备刷新竞价快照")
    progress(1, 3, "读取 TickFlow 全A实时行情")
    result = _refresh_auction_snapshot(limit)
    if should_cancel():
        raise RuntimeError("竞价刷新已取消")
    progress(2, 3, f"已保存 {len(result.items)} 只竞价候选")
    return result


def _auction_now() -> datetime:
    return getattr(app.state, "auction_now", None) or datetime.now().astimezone()


def _sector_now() -> datetime:
    return getattr(app.state, "sector_now", None) or datetime.now(ZoneInfo("Asia/Shanghai"))


def _sample_sector_workbench() -> None:
    _refresh_sector_theme_rows()
    for mode in ("strength", "main_flow"):
        get_sector_workbench(
            mode=mode,
            scope="auto",
            selected="",
            limit=30,
            stock_limit=80,
        )


def _cached_sector_radar(limit: int) -> SectorRadarResponse:
    provider = _market_overview_provider()
    cache_key = f"sector-radar:{_provider_cache_key(provider)}:{limit}"

    def build() -> SectorRadarResponse:
        result: SectorRadarResponse | None = None
        if hasattr(provider, "get_sector_radar"):
            result = provider.get_sector_radar(limit=limit)
        else:
            result = _estimated_sector_radar(_cached_market_overview(), limit)
        if result.inflow or result.outflow:
            return result
        try:
            tdx_result = _tdx_provider().get_sector_radar(limit=limit)
        except Exception as exc:
            result.source_status.append(
                StrongStockSourceStatus(
                    source="通达信MCP板块兜底",
                    status="failed",
                    detail=f"TDX fallback failed: {exc.__class__.__name__}",
                )
            )
            try:
                tickflow_result = _tickflow_sector_radar(provider, limit=limit)
            except Exception as tickflow_exc:
                result.source_status.append(
                    StrongStockSourceStatus(
                        source="TickFlow行业聚合",
                        status="failed",
                        detail=f"TickFlow fallback failed: {tickflow_exc.__class__.__name__}",
                    )
                )
                return result
            tickflow_result.source_status = [*result.source_status, *tickflow_result.source_status]
            return tickflow_result
        tdx_result.source_status = [*result.source_status, *tdx_result.source_status]
        return tdx_result

    return SECTOR_RADAR_CACHE.get_or_set(cache_key, build).model_copy(deep=True)


def _cached_sector_intraday_series(
    result: SectorWorkbenchResponse,
) -> tuple[list[SectorWorkbenchSeries], StrongStockSourceStatus]:
    provider = _quote_provider()
    cache_key = _sector_intraday_cache_key(result, provider)

    def build() -> tuple[list[SectorWorkbenchSeries], StrongStockSourceStatus]:
        try:
            return build_sector_intraday_series(
                response=result,
                quote_provider=provider,
                mode=result.mode,
                count=260,
            )
        except Exception as exc:
            reason = f"{exc.__class__.__name__}: {str(exc).strip()}" if str(exc).strip() else exc.__class__.__name__
            return [], StrongStockSourceStatus(
                source="TickFlow 当日分钟线",
                status="failed",
                detail=f"历史分时曲线补齐失败: {reason[:180]}",
            )

    series, status = SECTOR_INTRADAY_CACHE.get_or_refresh(cache_key, build)
    return [item.model_copy(deep=True) for item in series], status.model_copy(deep=True)


def _cached_sector_intraday_status(result: SectorWorkbenchResponse) -> StrongStockSourceStatus | None:
    cached = SECTOR_INTRADAY_CACHE.get_if_fresh(_sector_intraday_cache_key(result, _quote_provider()))
    if cached is None:
        return None
    _series, status = cached
    return status.model_copy(deep=True)


def _sector_intraday_cache_key(result: SectorWorkbenchResponse, provider: object) -> str:
    selected = [item.strip() for item in getattr(result, "selected_themes", [])[:5] if item.strip()]
    selected_set = set(selected)
    symbols: list[str] = []
    seen: set[str] = set()
    for stock in getattr(result, "stocks", []):
        if not selected_set.intersection(getattr(stock, "themes", [])):
            continue
        symbol = getattr(stock, "symbol", "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
        if len(symbols) >= 80:
            break
    cache_payload = {
        "provider": _provider_cache_key(provider),
        "trade_date": getattr(result, "trade_date", ""),
        "mode": getattr(result, "mode", ""),
        "scope": getattr(result, "scope", ""),
        "selected": selected,
        "symbols": symbols,
        "count": 260,
    }
    return f"sector-intraday:{json.dumps(cache_payload, ensure_ascii=False, sort_keys=True)}"


def _schedule_sector_intraday_refresh(result: SectorWorkbenchResponse) -> None:
    if getattr(app.state, "sector_intraday_async_refresh_disabled", False):
        return
    key = _sector_intraday_refresh_key(result)
    refreshing = getattr(app.state, "sector_intraday_refreshing", None)
    if refreshing is None:
        refreshing = set()
        app.state.sector_intraday_refreshing = refreshing
    if key in refreshing:
        return
    refreshing.add(key)

    def run() -> None:
        try:
            series, _status = _cached_sector_intraday_series(result)
            if series:
                refreshed = result.model_copy(update={"series": series}, deep=True)
                _sector_workbench_store().append(refreshed, sample_source="intraday")
        finally:
            current = getattr(app.state, "sector_intraday_refreshing", set())
            current.discard(key)

    Thread(target=run, name="sector-intraday-refresh", daemon=True).start()


def _sector_intraday_refresh_key(result: SectorWorkbenchResponse) -> str:
    return json.dumps(
        {
            "trade_date": result.trade_date,
            "mode": result.mode,
            "scope": result.scope,
            "selected": result.selected_themes[:5],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _tickflow_sector_radar(provider: object, limit: int) -> SectorRadarResponse:
    if not hasattr(provider, "get_market_rankings"):
        raise StrongStockDataUnavailable("当前市场概览源不支持 TickFlow 全A实时排行榜")
    ranking_limit = max(50, min(100, limit * 5))
    rankings = provider.get_market_rankings(limit=ranking_limit)
    items_by_symbol = {
        item.symbol: item
        for item in [*rankings.pct_change_rank, *rankings.turnover_rank]
        if item.symbol and item.industry
    }
    if not items_by_symbol:
        raise StrongStockDataUnavailable("TickFlow 全A排行缺少行业分类，无法聚合板块")

    grouped: dict[str, list[object]] = defaultdict(list)
    for item in items_by_symbol.values():
        grouped[str(item.industry)].append(item)

    sector_items: list[SectorRadarItem] = []
    for industry, members in grouped.items():
        turnover_cny = sum(item.turnover_cny or 0 for item in members)
        net_flow_cny = sum(
            (item.turnover_cny or 0) * (item.pct_change or 0) / 100
            for item in members
            if item.turnover_cny is not None and item.pct_change is not None
        )
        advance_count = sum(1 for item in members if (item.pct_change or 0) > 0)
        decline_count = sum(1 for item in members if (item.pct_change or 0) < 0)
        leader = max(
            members,
            key=lambda item: (item.pct_change or -999, item.turnover_cny or 0, item.symbol),
        )
        avg_change = (
            sum(item.pct_change or 0 for item in members if item.pct_change is not None)
            / max(1, sum(1 for item in members if item.pct_change is not None))
        )
        strength_score = round(avg_change * 10 + advance_count * 3 - decline_count * 2 + min(turnover_cny / 1_000_000_000, 20), 2)
        sector_items.append(
            SectorRadarItem(
                name=industry,
                source="TickFlow全A实时行情行业聚合",
                change_pct=round(avg_change, 2),
                turnover_cny=round(turnover_cny, 2),
                advance_count=advance_count,
                decline_count=decline_count,
                leader=leader.name or leader.symbol,
                net_flow_cny=round(net_flow_cny, 2),
                strength_score=strength_score,
            )
        )

    inflow = sorted(
        [item for item in sector_items if (item.net_flow_cny or 0) > 0],
        key=lambda item: (item.net_flow_cny or 0, item.strength_score),
        reverse=True,
    )[:limit]
    outflow = sorted(
        [item for item in sector_items if (item.net_flow_cny or 0) < 0],
        key=lambda item: (item.net_flow_cny or 0, -item.strength_score),
    )[:limit]
    if not inflow and not outflow:
        raise StrongStockDataUnavailable("TickFlow 行业聚合没有生成有效净流向")

    return SectorRadarResponse(
        trade_date=rankings.trade_date,
        capital_flow_status="estimated",
        flow_source="TickFlow全A实时行情行业聚合",
        inflow=inflow,
        outflow=outflow,
        source_status=[
            StrongStockSourceStatus(
                source="TickFlow行业聚合",
                status="success",
                detail=f"按 {len(items_by_symbol)} 只全A排行股票聚合 {len(sector_items)} 个行业",
            ),
            *rankings.source_status,
        ],
    )


def _cached_stock_kline(symbol: str, count: int) -> StockKlineResponse:
    kline_provider = _kline_provider()
    normalized_symbol = symbol.strip().upper()
    cache_key = f"stock-kline:{_provider_cache_key(kline_provider)}:{normalized_symbol}:{count}"

    def build() -> StockKlineResponse:
        bars = kline_provider.get_klines(normalized_symbol, count=count)[-count:]
        return StockKlineResponse(
            symbol=normalized_symbol,
            source_status=StrongStockSourceStatus(
                source=getattr(kline_provider, "source_name", "K线源"),
                status="success",
                detail=f"返回 {len(bars)} 条日K",
            ),
            bars=bars,
            gsgf_annotations=build_gsgf_chart_annotations(bars),
        )

    return STOCK_KLINE_CACHE.get_or_set(cache_key, build).model_copy(deep=True)


def _cached_stock_research(symbol: str) -> StockResearchResponse:
    ifind_provider = _ifind_provider()
    normalized_symbol = symbol.strip().upper()
    cache_key = f"stock-research:{_provider_cache_key(ifind_provider)}:{normalized_symbol}"

    def build() -> StockResearchResponse:
        try:
            return ifind_provider.get_stock_research(normalized_symbol)
        except StrongStockDataUnavailable as exc:
            return StockResearchResponse(
                symbol=normalized_symbol,
                source_status=[
                    StrongStockSourceStatus(
                        source=ifind_provider.source_name,
                        status="failed",
                        detail=str(exc),
                    )
                ],
            )

    return STOCK_RESEARCH_CACHE.get_or_set(cache_key, build).model_copy(deep=True)


def _clear_data_source_caches() -> None:
    CACHE_REGISTRY.clear()


def _system_jobs() -> list[dict[str, object]]:
    auction_sampler = getattr(app.state, "auction_sampler", None)
    sector_sampler = getattr(app.state, "sector_workbench_sampler", None)
    sentiment_monitor = getattr(app.state, "sentiment_monitor", None)
    gsgf_service = getattr(app.state, "gsgf_auto_review_service", None)
    runtime = load_runtime_settings(_runtime_config_path())
    auction_running, auction_detail = _thread_running_status(auction_sampler, "竞价时段采样器")
    sector_running, sector_detail = _attribute_running_status(
        sector_sampler,
        "running",
        "板块工作台交易时段采样器",
    )
    sentiment_running, sentiment_detail = _sentiment_monitor_running_status(
        sentiment_monitor,
        "短线情绪监控",
    )
    gsgf_running, gsgf_detail = _thread_running_status(gsgf_service, "GSGF 自动复盘")
    return [
        {
            "name": "auction_sampler",
            "running": auction_running,
            "enabled": not getattr(app.state, "auction_sampler_disabled", False),
            "detail": auction_detail,
        },
        {
            "name": "sector_workbench_sampler",
            "running": sector_running,
            "enabled": not getattr(app.state, "sector_workbench_sampler_disabled", False),
            "detail": sector_detail,
        },
        {
            "name": "sentiment_monitor",
            "running": sentiment_running,
            "enabled": runtime.sentiment_monitor.enabled,
            "detail": sentiment_detail,
        },
        {
            "name": "gsgf_auto_review",
            "running": gsgf_running,
            "enabled": runtime.gsgf_auto_review.daily_review_enabled,
            "detail": gsgf_detail,
        },
    ]


def _attribute_running_status(
    worker: object | None,
    attribute: str,
    detail: str,
) -> tuple[bool, str]:
    if worker is None:
        return False, detail
    try:
        return bool(getattr(worker, attribute)), detail
    except Exception:
        return False, _status_unavailable_detail(detail)


def _sentiment_monitor_running_status(
    monitor: object | None,
    detail: str,
) -> tuple[bool, str]:
    running, diagnostic = _safe_status_running(monitor)
    if diagnostic is not None:
        return False, _diagnostic_detail(detail, diagnostic)
    return running, detail


def _thread_running_status(worker: object | None, detail: str) -> tuple[bool, str]:
    running, diagnostic = _safe_thread_running(worker)
    if diagnostic is not None:
        return False, _diagnostic_detail(detail, diagnostic)
    return running, detail


def _safe_status_running(service: object | None) -> tuple[bool, str | None]:
    if service is None:
        return False, None
    try:
        status = getattr(service, "status", None)
        if not callable(status):
            return False, "status unavailable"
        service_status = status()
        running = bool(getattr(service_status, "running"))
    except Exception:
        return False, "status unavailable"
    if not running:
        return False, "unexpectedly stopped"
    return True, None


def _safe_thread_running(
    worker: object | None,
    attr_name: str = "_thread",
) -> tuple[bool, str | None]:
    if worker is None:
        return False, None
    try:
        thread = getattr(worker, attr_name, None)
        if thread is None:
            return False, "unexpectedly stopped"
        is_alive = getattr(thread, "is_alive", None)
        if not callable(is_alive):
            return False, "thread status unavailable"
        running = bool(is_alive())
    except Exception:
        return False, "thread status unavailable"
    if not running:
        return False, "unexpectedly stopped"
    return True, None


def _system_job_degraded(job: dict[str, object]) -> bool:
    if job.get("enabled") is not True:
        return False
    if job.get("running") is True:
        return False
    detail = str(job.get("detail") or "")
    return "状态不可用" in detail or "异常停止" in detail


def _diagnostic_detail(detail: str, diagnostic: str) -> str:
    if diagnostic == "unexpectedly stopped":
        return f"{detail}（异常停止）"
    return _status_unavailable_detail(detail)


def _status_unavailable_detail(detail: str) -> str:
    return f"{detail}（状态不可用）"


def _build_and_persist_sentiment_snapshots(
    trade_date: str,
    limit: int,
    refresh: bool = False,
) -> tuple[ShortTermSentimentResponse, MarketEmotionSnapshotResponse]:
    if refresh:
        SHORT_TERM_SENTIMENT_CACHE.clear()
        MARKET_EMOTION_CACHE.clear()
    sentiment = _cached_short_term_sentiment(trade_date, limit)
    candidate_provider = _candidate_provider()
    market_overview_provider = _market_overview_provider()
    cache_key = (
        "market-emotion:"
        f"{_provider_cache_key(candidate_provider)}:"
        f"{_provider_cache_key(market_overview_provider)}:"
        f"{trade_date}:{limit}"
    )
    market_emotion = MARKET_EMOTION_CACHE.get_or_set(
        cache_key,
        lambda: build_market_emotion_snapshot(
            candidate_provider,
            market_overview_provider,
            trade_date=trade_date,
            limit=limit,
            sentiment_snapshot=sentiment,
        ),
    ).model_copy(deep=True)
    try:
        history_store = _market_emotion_history_store()
        history_store.append(market_emotion)
        market_emotion.samples = history_store.load(trade_date)
    except Exception as exc:
        market_emotion.source_status.append(
            StrongStockSourceStatus(
                source="市场情绪采样",
                status="failed",
                detail=f"采样写入失败: {exc.__class__.__name__}",
            )
        )
    _sentiment_snapshot_store().save(sentiment=sentiment, market_emotion=market_emotion)
    return sentiment, market_emotion


def _provider_cache_key(provider: object) -> str:
    parts = [
        provider.__class__.__module__,
        provider.__class__.__name__,
        str(getattr(provider, "source_name", "")),
    ]
    for attr in (
        "trading_days",
        "calendar_day_factor",
        "timeout_seconds",
        "base_url",
        "api_key_source",
        "ifind_service_id",
    ):
        value = getattr(provider, attr, None)
        if value not in (None, ""):
            parts.append(f"{attr}={value}")
    return "|".join(parts)


def _candidate_provider() -> object:
    injected = getattr(app.state, "candidate_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    if settings.candidate_provider == "thsdk":
        return ThsdkCandidateProvider.from_installed_package()
    return RecentLimitUpCandidateProvider.from_akshare()


def _kline_provider() -> object:
    injected = getattr(app.state, "kline_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return TickFlowDailyKlineProvider(
        api_key=settings.tickflow_api_key,
        base_url=settings.tickflow_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
    )


def _quote_provider() -> object:
    injected = getattr(app.state, "quote_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return TickFlowQuoteProvider(
        api_key=settings.tickflow_api_key,
        base_url=settings.tickflow_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
    )


def _news_risk_provider() -> object:
    injected = getattr(app.state, "news_risk_provider", None)
    if injected is not None:
        return injected
    return EastmoneyNewsRiskProvider.from_akshare()


def _concept_provider() -> object:
    injected = getattr(app.state, "concept_provider", None)
    if injected is not None:
        return injected
    cached = getattr(app.state, "default_concept_provider", None)
    if cached is None:
        settings = _effective_settings()
        cached = EastmoneyConceptBlockProvider(timeout_seconds=settings.provider_timeout_seconds)
        app.state.default_concept_provider = cached
    return cached


def _tdx_provider() -> TdxMcpProvider:
    injected = getattr(app.state, "tdx_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return TdxMcpProvider(
        api_key=settings.tdx_api_key,
        base_url=settings.tdx_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        http_client=getattr(app.state, "tdx_http_client", None),
    )


def _ifind_provider() -> IfindMcpProvider:
    injected = getattr(app.state, "ifind_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return IfindMcpProvider(
        api_key=settings.ifind_api_key,
        base_url=settings.ifind_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        http_client=getattr(app.state, "ifind_http_client", None),
    )


def _market_overview_provider() -> object:
    injected = getattr(app.state, "market_overview_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return EastmoneyMarketOverviewProvider(
        timeout_seconds=settings.provider_timeout_seconds,
        realtime_quote_provider=_quote_provider(),
        ifind_index_provider=_ifind_provider(),
        ifind_stock_provider=_ifind_provider(),
    )


def _plate_rotation_reference_provider() -> object:
    injected = getattr(app.state, "plate_rotation_reference_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    provider = PlateRotationReferenceProvider(timeout_seconds=settings.provider_timeout_seconds)
    app.state.plate_rotation_reference_provider = provider
    return provider


def _stock_industry_for_symbol(symbol: str) -> str | None:
    provider = _market_overview_provider()
    if not hasattr(provider, "get_stock_industries"):
        return None
    normalized_symbol = symbol.strip().upper()
    try:
        industries = provider.get_stock_industries([normalized_symbol])
    except Exception:
        return None
    industry = industries.get(normalized_symbol)
    return industry.strip() if isinstance(industry, str) and industry.strip() else None


def _auction_snapshot_store() -> AuctionSnapshotStore:
    injected = getattr(app.state, "auction_snapshot_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    store = AuctionSnapshotStore(review_store=_auction_review_store(), data_dir=data_dir)
    app.state.auction_snapshot_store = store
    return store


def _auction_review_store() -> AuctionReviewStore:
    injected = getattr(app.state, "auction_review_store", None)
    if injected is not None:
        return injected
    settings = get_settings()
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    store = AuctionReviewStore(data_dir, retention_days=settings.auction_review_retention_days)
    app.state.auction_review_store = store
    return store


def _sector_workbench_store() -> SectorWorkbenchSampleStore:
    injected = getattr(app.state, "sector_workbench_store", None)
    if injected is not None:
        return injected
    data_dir = Path(
        getattr(
            app.state,
            "sector_workbench_dir",
            Path(getattr(app.state, "runs_dir", get_settings().data_dir)) / "sectors",
        )
    )
    store = SectorWorkbenchSampleStore(data_dir)
    app.state.sector_workbench_store = store
    return store


def _sector_theme_rows_store() -> SectorThemeRowsStore:
    injected = getattr(app.state, "sector_theme_rows_store", None)
    if injected is not None:
        return injected
    data_dir = Path(
        getattr(
            app.state,
            "sector_theme_rows_dir",
            Path(getattr(app.state, "runs_dir", get_settings().data_dir)) / "sectors" / "theme-rows",
        )
    )
    store = SectorThemeRowsStore(data_dir)
    app.state.sector_theme_rows_store = store
    return store


def _sector_theme_rows() -> tuple[list[dict[str, object]], StrongStockSourceStatus | None]:
    trade_date = datetime.now().astimezone().date().isoformat()
    rows, status = _sector_theme_rows_store().load(trade_date)
    if rows:
        return rows, status or StrongStockSourceStatus(
            source="题材快照",
            status="success",
            detail=f"读取后台题材快照 {len(rows)} 只股票",
        )
    _schedule_sector_theme_rows_refresh(trade_date)
    return [], StrongStockSourceStatus(
        source="题材快照",
        status="stale",
        detail="后台题材快照未就绪，已触发刷新；本次暂用行业兜底",
    )


def _schedule_sector_theme_rows_refresh(trade_date: str) -> None:
    if getattr(app.state, "sector_theme_rows_async_refresh_disabled", False):
        return
    refreshing = getattr(app.state, "sector_theme_rows_refreshing", None)
    if refreshing is None:
        refreshing = set()
        app.state.sector_theme_rows_refreshing = refreshing
    if trade_date in refreshing:
        return
    refreshing.add(trade_date)

    def run() -> None:
        try:
            _refresh_sector_theme_rows(trade_date=trade_date)
        finally:
            current = getattr(app.state, "sector_theme_rows_refreshing", set())
            current.discard(trade_date)

    Thread(target=run, name=f"sector-theme-rows-refresh-{trade_date}", daemon=True).start()


def _refresh_sector_theme_rows(trade_date: str | None = None) -> tuple[list[dict[str, object]], StrongStockSourceStatus | None]:
    current_trade_date = trade_date or datetime.now().astimezone().date().isoformat()
    candidate_provider = _candidate_provider()
    concept_provider = _concept_provider()
    cache_key = (
        "sector-theme-rows:"
        f"{current_trade_date}:"
        f"{_provider_cache_key(candidate_provider)}:"
        f"{_provider_cache_key(concept_provider)}"
    )
    rows, status = SECTOR_THEME_ROWS_CACHE.get_or_refresh(
        cache_key,
        lambda: _build_sector_theme_rows(
            trade_date=current_trade_date,
            candidate_provider=candidate_provider,
            concept_provider=concept_provider,
        ),
    )
    if status is not None:
        _sector_theme_rows_store().save(
            trade_date=current_trade_date,
            rows=rows,
            status_source=status.source,
            status=status.status,
            status_detail=status.detail,
        )
    return rows, status


def _build_sector_theme_rows(
    *,
    trade_date: str,
    candidate_provider: object,
    concept_provider: object,
) -> tuple[list[dict[str, object]], StrongStockSourceStatus | None]:
    tdx_status: StrongStockSourceStatus | None = None
    try:
        provider = getattr(app.state, "tdx_provider", None) or _tdx_provider()
        if not hasattr(provider, "query_rows"):
            tdx_status = StrongStockSourceStatus(
                source="通达信MCP涨停概念映射",
                status="disabled",
                detail="当前 TDX provider 不支持 query_rows，使用行业兜底",
            )
        else:
            rows = provider.query_rows(
                "今日涨停股列表 封单金额 首次涨停时间 涨停原因 连续涨停天数 板型 封成比 所属概念 所属通达信风格",
                size=100,
            )
            if rows:
                return rows, StrongStockSourceStatus(
                    source="通达信MCP涨停概念映射",
                    status="success",
                    detail=f"返回 {len(rows)} 只涨停股概念映射",
                )
            tdx_status = StrongStockSourceStatus(
                source="通达信MCP涨停概念映射",
                status="stale",
                detail="TDX 今日涨停题材映射返回空，尝试东财 slist 概念归属 fallback",
            )
    except Exception as exc:
        tdx_status = StrongStockSourceStatus(
            source="通达信MCP涨停概念映射",
            status="failed",
            detail=f"题材映射获取失败: {exc.__class__.__name__}",
        )

    try:
        candidates = candidate_provider.get_candidates(trade_date)
        rows = build_limit_up_theme_rows_from_candidates(
            candidates=candidates,
            concept_provider=concept_provider,
            limit=80,
            trade_date=trade_date,
        )
    except Exception as exc:
        detail = f"东财 slist 概念 fallback 失败: {exc.__class__.__name__}"
        if tdx_status is not None:
            detail = f"{tdx_status.detail}; {detail}"
        return [], StrongStockSourceStatus(
            source="东财 slist 概念归属",
            status="failed",
            detail=detail,
        )
    if rows:
        detail = f"基于当日涨停候选/可识别候选 {len(candidates)} 只，补齐 {len(rows)} 只股票题材"
        if tdx_status is not None:
            detail = f"{tdx_status.detail}; {detail}"
        return rows, StrongStockSourceStatus(
            source="东财 slist 概念归属",
            status="success",
            detail=detail,
        )
    detail = "东财 slist 未返回可用概念标签，使用行业兜底"
    if tdx_status is not None:
        detail = f"{tdx_status.detail}; {detail}"
    return [], StrongStockSourceStatus(
        source="东财 slist 概念归属",
        status="stale",
        detail=detail,
    )


def _auction_review_summary(records: list, *, trade_date: str | None) -> AuctionReviewSummary:
    return AuctionReviewSummary(
        trade_date=trade_date,
        record_count=len(records),
        pending_count=sum(1 for record in records if record.review_status == "pending"),
        completed_count=sum(1 for record in records if record.review_status == "next_day_done"),
        data_incomplete_count=sum(1 for record in records if record.review_status == "data_incomplete"),
        records=records,
        buckets=build_auction_rule_buckets(records),
    )


def _auction_review_selected_at(trade_date: str) -> datetime:
    current = _auction_now()
    return datetime.fromisoformat(f"{trade_date}T{current.hour:02d}:{current.minute:02d}:{current.second:02d}+08:00")


def _watchlist_snapshot() -> WatchlistSnapshot | None:
    return getattr(app.state, "watchlist_snapshot", None)


def _intraday_watchlist_items(request: IntradaySnapshotRequest) -> list[WatchlistItem]:
    if request.watchlist_text.strip():
        return parse_watchlist_text(request.watchlist_text)
    if request.use_watchlist_pool:
        content = _read_watchlist_pool()
        if content:
            return parse_watchlist_text(content)
        snapshot = _watchlist_snapshot()
        return snapshot.items if snapshot is not None else []
    return []


def _run_store() -> RunStore:
    settings = get_settings()
    runs_dir = getattr(app.state, "runs_dir", None)
    if runs_dir is not None:
        return RunStore(Path(runs_dir))
    return RunStore(settings.runs_dir, retention_count=settings.screen_run_retention_count)


def _gsgf_review_store() -> GsgfReviewStore:
    settings = get_settings()
    data_dir = getattr(app.state, "runs_dir", None)
    if data_dir is not None:
        return GsgfReviewStore(Path(data_dir))
    return GsgfReviewStore(settings.data_dir, max_records=settings.gsgf_review_retention_records)


def _sentiment_review_store() -> SentimentReviewStore:
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    injected = getattr(app.state, "sentiment_review_store", None)
    injected_data_dir = getattr(app.state, "sentiment_review_store_data_dir", None)
    if injected is not None and injected_data_dir == data_dir:
        return injected
    store = SentimentReviewStore(data_dir)
    app.state.sentiment_review_store = store
    app.state.sentiment_review_store_data_dir = data_dir
    return store


def _background_job_store() -> BackgroundJobStore:
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    existing = getattr(app.state, "background_job_store", None)
    existing_data_dir = getattr(app.state, "background_job_store_data_dir", None)
    if existing is not None and existing_data_dir == data_dir:
        return existing
    store = BackgroundJobStore(data_dir)
    app.state.background_job_store = store
    app.state.background_job_store_data_dir = data_dir
    return store


def _model_maintenance_store() -> ModelMaintenanceStore:
    data_dir = Path(getattr(app.state, "runs_dir", get_settings().data_dir))
    existing = getattr(app.state, "model_maintenance_store", None)
    existing_data_dir = getattr(app.state, "model_maintenance_store_data_dir", None)
    if existing is not None and existing_data_dir == data_dir:
        return existing
    store = ModelMaintenanceStore(data_dir)
    app.state.model_maintenance_store = store
    app.state.model_maintenance_store_data_dir = data_dir
    return store


def _market_emotion_history_store() -> MarketEmotionHistoryStore:
    settings = get_settings()
    data_dir = getattr(app.state, "runs_dir", None)
    if data_dir is not None:
        return MarketEmotionHistoryStore(Path(data_dir))
    return MarketEmotionHistoryStore(
        settings.data_dir,
        retention_days=settings.market_emotion_history_retention_days,
        samples_per_day=settings.market_emotion_samples_per_day,
    )


def _sentiment_snapshot_store() -> SentimentSnapshotStore:
    settings = get_settings()
    data_dir = getattr(app.state, "runs_dir", None)
    if data_dir is not None:
        return SentimentSnapshotStore(Path(data_dir))
    return SentimentSnapshotStore(
        settings.data_dir,
        retention_days=settings.sentiment_snapshot_retention_days,
    )


def _sentiment_monitor() -> SentimentMonitor:
    injected = getattr(app.state, "sentiment_monitor", None)
    if injected is not None:
        return injected
    builder = getattr(app.state, "sentiment_monitor_snapshot_builder", None)
    monitor = SentimentMonitor(
        snapshot_builder=builder or _build_and_persist_sentiment_snapshots,
        config_loader=lambda: load_runtime_settings(_runtime_config_path()).sentiment_monitor,
        notifier=_send_sentiment_monitor_notification,
    )
    app.state.sentiment_monitor = monitor
    return monitor


def _gsgf_auto_review_service() -> GsgfAutoReviewService:
    injected = getattr(app.state, "gsgf_auto_review_service", None)
    if injected is not None:
        return injected
    service = GsgfAutoReviewService(
        config_loader=lambda: load_runtime_settings(_runtime_config_path()).gsgf_auto_review,
        review_runner=_run_gsgf_daily_review,
        calibration_runner=_start_gsgf_weekly_calibration,
        recent_trade_dates=_recent_screen_trade_dates,
        notifier=_send_sentiment_monitor_notification,
    )
    app.state.gsgf_auto_review_service = service
    return service


def _run_gsgf_daily_review() -> GsgfReviewSummary:
    config = load_runtime_settings(_runtime_config_path()).gsgf_auto_review
    store = _gsgf_review_store()
    records = store.load_records()
    kline_provider = _kline_provider()
    bars_by_symbol: dict[str, list[KlineBar]] = {}
    for symbol in _dedupe_symbols([record.symbol for record in records]):
        try:
            bars_by_symbol[symbol] = kline_provider.get_klines(symbol, count=config.kline_count)
        except Exception:
            bars_by_symbol[symbol] = []
    summary = store.recheck_snapshots(bars_by_symbol, windows=config.windows)
    store.save_latest_summary(summary)
    health = _gsgf_model_health()
    if config.notify_on_degradation and health.degraded_signals:
        _send_sentiment_monitor_notification("GSGF 模型信号退化提醒", health.summary_text)
    return summary


def _start_gsgf_weekly_calibration(
    trade_dates: list[str],
    windows: list[int],
    scan_limit: int,
    count: int,
):
    config = load_runtime_settings(_runtime_config_path()).gsgf_auto_review
    return _background_job_store().create_calibration_job(
        lambda progress, should_cancel: summarize_gsgf_real_calibration(
            candidate_provider=_candidate_provider(),
            kline_provider=_kline_provider(),
            trade_dates=trade_dates,
            windows=windows,
            scan_limit=scan_limit,
            kline_count=count,
            progress=progress,
            should_cancel=should_cancel,
        ),
        on_success=(
            lambda result: _send_sentiment_monitor_notification(
                "GSGF 每周真实样本校准完成",
                build_gsgf_model_health(_gsgf_review_store().load_latest_summary(), result).summary_text,
            )
            if config.notify_on_success
            else None
        ),
    )


def _recent_screen_trade_dates(count: int) -> list[str]:
    dates: list[str] = []
    dates.extend(record.trade_date for record in _gsgf_review_store().load_records())
    runs_dir = _run_store().runs_dir
    if runs_dir.exists():
        for path in sorted(runs_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            trade_date = payload.get("trade_date")
            if isinstance(trade_date, str):
                dates.append(trade_date)
    deduped = []
    seen: set[str] = set()
    for trade_date in sorted(dates):
        if trade_date not in seen:
            seen.add(trade_date)
            deduped.append(trade_date)
    return deduped[-max(1, count):]


def _gsgf_model_health() -> GsgfModelHealth:
    return build_gsgf_model_health(
        _gsgf_review_store().load_latest_summary(),
        _background_job_store().load_latest_calibration(),
    )


def _watchlist_path() -> Path:
    injected = getattr(app.state, "watchlist_path", None)
    if injected is not None:
        return Path(injected)
    return get_settings().watchlist_path


def _runtime_config_path() -> Path:
    injected = getattr(app.state, "runtime_config_path", None)
    if injected is not None:
        return Path(injected)
    return get_settings().data_dir / "runtime_config.json"


def _save_sentiment_monitor_config(config: SentimentMonitorConfig) -> None:
    current = load_runtime_settings(_runtime_config_path())
    effective = _effective_settings()
    save_runtime_settings(
        _runtime_config_path(),
        SettingsUpdate(
            candidate_provider=current.candidate_provider or effective.candidate_provider,
            kline_provider=current.kline_provider or effective.kline_provider,
            quote_provider=current.quote_provider or effective.quote_provider,
            tickflow_base_url=current.tickflow_base_url or effective.tickflow_base_url,
            ifind_base_url=current.ifind_base_url or effective.ifind_base_url,
            ifind_service_id=current.ifind_service_id or effective.ifind_service_id,
            tdx_base_url=current.tdx_base_url or effective.tdx_base_url,
            provider_timeout_seconds=current.provider_timeout_seconds or effective.provider_timeout_seconds,
            notification_channels=current.notification_channels,
            sentiment_monitor=config,
        ),
    )


def _send_sentiment_monitor_notification(title: str, message_text: str) -> NotificationSendResult:
    runtime = load_runtime_settings(_runtime_config_path())
    return send_notification_message(
        NotificationSettings(channels=runtime.notification_channels),
        title=title,
        message_text=message_text,
        http_client=getattr(app.state, "notification_http_client", None),
        smtp_client=getattr(app.state, "notification_smtp_client", None) or DefaultSmtpClient(),
    )


def _effective_settings():
    return effective_runtime_settings(get_settings(), _runtime_config_path())


def _estimated_sector_radar(overview: MarketOverviewResponse, limit: int) -> SectorRadarResponse:
    items = [_estimated_sector_radar_item(sector) for sector in overview.sectors if sector.turnover_cny is not None]
    inflow = sorted(
        [item for item in items if item.net_flow_cny is not None and item.net_flow_cny > 0],
        key=lambda item: item.net_flow_cny or 0,
        reverse=True,
    )[:limit]
    outflow = sorted(
        [item for item in items if item.net_flow_cny is not None and item.net_flow_cny < 0],
        key=lambda item: item.net_flow_cny or 0,
    )[:limit]
    return SectorRadarResponse(
        trade_date=overview.trade_date,
        capital_flow_status="estimated",
        flow_source="东方财富行业板块涨跌额估算",
        inflow=inflow,
        outflow=outflow,
        source_status=overview.source_status,
    )


def _estimated_sector_radar_item(sector: MarketSectorStrengthItem) -> SectorRadarItem:
    net_flow_cny = None
    if sector.turnover_cny is not None and sector.change_pct is not None:
        net_flow_cny = round(sector.turnover_cny * sector.change_pct / 100, 2)

    breadth_score = 0.0
    if sector.advance_count is not None and sector.decline_count is not None:
        total = sector.advance_count + sector.decline_count
        if total > 0:
            breadth_score = (sector.advance_count - sector.decline_count) / total * 10

    turnover_score = min((sector.turnover_cny or 0) / 10_000_000_000, 20)
    change_score = (sector.change_pct or 0) * 10
    return SectorRadarItem(
        name=sector.name,
        source=sector.source,
        change_pct=sector.change_pct,
        turnover_cny=sector.turnover_cny,
        advance_count=sector.advance_count,
        decline_count=sector.decline_count,
        leader=sector.leader,
        net_flow_cny=net_flow_cny,
        strength_score=round(change_score + breadth_score + turnover_score, 2),
    )


def _public_saved_settings() -> dict[str, object]:
    return load_runtime_settings(_runtime_config_path()).model_dump(
        mode="json",
        exclude={
            "tickflow_api_key": True,
            "ifind_api_key": True,
            "tdx_api_key": True,
            "ai_analysis": {"api_key": True},
        },
        exclude_none=True,
    )


def _read_watchlist_pool() -> str:
    path = _watchlist_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _probe(name: str, action) -> HealthProbe:
    started = perf_counter()
    try:
        result = action()
        latency_ms = round((perf_counter() - started) * 1000)
        if isinstance(result, StrongStockSourceStatus):
            return HealthProbe(
                name=result.source,
                status=result.status,
                latency_ms=latency_ms,
                detail=result.detail,
            )
        size = len(result) if hasattr(result, "__len__") else 1
        return HealthProbe(
            name=name,
            status="success",
            latency_ms=latency_ms,
            detail=f"返回 {size} 条数据",
        )
    except Exception as exc:
        return HealthProbe(
            name=name,
            status="failed",
            latency_ms=round((perf_counter() - started) * 1000),
            detail=str(exc),
        )
