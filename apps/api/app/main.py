from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models import (
    AuctionBackfillResponse,
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
    ScreenStrategy,
    SectorRadarItem,
    SectorRadarResponse,
    SentimentDetailResponse,
    ShortTermIntradaySentimentResponse,
    ShortTermIntradaySignalDigest,
    ShortTermSentimentResponse,
    StockKlineResponse,
    StockQuoteResponse,
    StockResearchResponse,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.gsgf_rules import analyze_gsgf, build_gsgf_chart_annotations
from app.providers.ifind import IfindMcpProvider
from app.providers.market_overview import EastmoneyMarketOverviewProvider
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
from app.services.background_jobs import BackgroundJobStore
from app.services.gsgf_backtest import summarize_gsgf_backtest
from app.services.gsgf_auto_review import GsgfAutoReviewService
from app.services.gsgf_model_health import build_gsgf_model_health
from app.services.gsgf_real_calibration import summarize_gsgf_real_calibration
from app.services.gsgf_review import GsgfReviewStore
from app.services.gsgf_trade_plan import build_gsgf_trade_plan
from app.services.auction import build_auction_snapshot
from app.services.auction_review import build_auction_rule_buckets, finalize_auction_records
from app.services.auction_review_store import AuctionReviewStore
from app.services.auction_sampler import AuctionSnapshotSampler
from app.services.auction_snapshot_store import AuctionSnapshotStore
from app.services.market_emotion_history import MarketEmotionHistoryStore
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
    try:
        yield
    finally:
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

SHORT_TERM_SENTIMENT_CACHE: TtlCache[ShortTermSentimentResponse] = TtlCache(ttl_seconds=90)
MARKET_EMOTION_CACHE: TtlCache[MarketEmotionSnapshotResponse] = TtlCache(ttl_seconds=45)
MARKET_OVERVIEW_CACHE: TtlCache[MarketOverviewResponse] = TtlCache(ttl_seconds=45)
MARKET_RANKINGS_CACHE: TtlCache[MarketRankingsResponse] = TtlCache(ttl_seconds=45)
AUCTION_SNAPSHOT_CACHE: TtlCache[AuctionSnapshotResponse] = TtlCache(ttl_seconds=15)
SECTOR_RADAR_CACHE: TtlCache[SectorRadarResponse] = TtlCache(ttl_seconds=45)
STOCK_KLINE_CACHE: TtlCache[StockKlineResponse] = TtlCache(ttl_seconds=300)
STOCK_RESEARCH_CACHE: TtlCache[StockResearchResponse] = TtlCache(ttl_seconds=900)


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


def startup_gsgf_auto_review() -> None:
    _gsgf_auto_review_service().start()


def shutdown_gsgf_auto_review() -> None:
    service = getattr(app.state, "gsgf_auto_review_service", None)
    if service is not None:
        service.stop()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
    screener = StrongStockScreener(
        candidate_provider=_candidate_provider(),
        kline_provider=_kline_provider(),
        news_risk_provider=_news_risk_provider(),
    )
    try:
        result = screener.screen(
            trade_date=request.trade_date,
            limit=request.limit,
            scan_limit=request.scan_limit,
            filters=request.filters,
            watchlist_snapshot=_watchlist_snapshot(),
            strategy=request.strategy,
            exclude_gsgf_hard_risk=request.exclude_gsgf_hard_risk,
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _run_store().save(result)
    auto_review_config = load_runtime_settings(_runtime_config_path()).gsgf_auto_review
    if auto_review_config.auto_snapshot_enabled and any(item.gsgf is not None for item in result.items):
        _gsgf_review_store().persist_snapshot(result, dedupe=True)
    return result.model_dump(mode="json")


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
    source_status = (
        quote_provider.status()
        if hasattr(quote_provider, "status")
        else StrongStockSourceStatus(source=getattr(quote_provider, "source_name", "实时行情"), status="success", detail="实时行情源已配置")
    )
    return StockQuoteResponse(
        symbol=quote.symbol,
        name=quote.name,
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


def _cached_auction_snapshot(limit: int) -> AuctionSnapshotResponse:
    provider = _market_overview_provider()
    cache_key = f"auction-snapshot:{_provider_cache_key(provider)}:{limit}"
    result = AUCTION_SNAPSHOT_CACHE.get_or_refresh(
        cache_key,
        lambda: build_auction_snapshot(
            _cached_market_rankings(max(limit, 100)),
            limit=limit,
            now=getattr(app.state, "auction_now", None),
        ),
    ).model_copy(deep=True)
    _auction_snapshot_store().save(result, captured_at=_auction_now())
    return result


def _refresh_auction_snapshot(limit: int) -> AuctionSnapshotResponse:
    now = _auction_now()
    result = build_auction_snapshot(
        _refresh_market_rankings(max(limit, 100)),
        limit=limit,
        now=now,
    )
    return _auction_snapshot_store().save(result, captured_at=now)


def _auction_now() -> datetime:
    return getattr(app.state, "auction_now", None) or datetime.now().astimezone()


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
            return result
        tdx_result.source_status = [*result.source_status, *tdx_result.source_status]
        return tdx_result

    return SECTOR_RADAR_CACHE.get_or_set(cache_key, build).model_copy(deep=True)


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
    for cache in (
        SHORT_TERM_SENTIMENT_CACHE,
        MARKET_EMOTION_CACHE,
        MARKET_OVERVIEW_CACHE,
        MARKET_RANKINGS_CACHE,
        AUCTION_SNAPSHOT_CACHE,
        SECTOR_RADAR_CACHE,
        STOCK_KLINE_CACHE,
        STOCK_RESEARCH_CACHE,
    ):
        cache.clear()


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


def _auction_snapshot_store() -> AuctionSnapshotStore:
    injected = getattr(app.state, "auction_snapshot_store", None)
    if injected is not None:
        return injected
    store = AuctionSnapshotStore(review_store=_auction_review_store())
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
        exclude={"tickflow_api_key", "ifind_api_key", "tdx_api_key"},
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
