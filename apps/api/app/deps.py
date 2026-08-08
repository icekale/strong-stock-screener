"""应用装配依赖层。

把 main.py 中与 app.state 绑定的装配基础设施（数据源工厂所需的服务定位、
运行时设置、缓存注册表）集中在此，并通过 bind_app() 后绑定 FastAPI 实例，
从而断开「路由/工厂 import main → main import 路由」的循环依赖。

约定：本模块及其消费方一律不 import app.main；main.py 在创建 app 后调用
bind_app(app)，并把需要对外保留的符号（含测试导入的缓存常量）再导出。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import FastAPI

from app.config import get_settings
from app.models import (
    AuctionSnapshotResponse,
    CapitalSummaryResponse,
    MarketEmotionSnapshotResponse,
    MarketOverviewResponse,
    MarketRankingsResponse,
    SectorRadarResponse,
    SectorWorkbenchSeries,
    ShortTermSentimentResponse,
    StockKlineResponse,
    StockResearchResponse,
    StrongStockSourceStatus,
)
from app.providers.capital_signals import OfficialCapitalDataProvider, SinaEtfHolderProvider
from app.providers.concept_blocks import EastmoneyConceptBlockProvider
from app.providers.heatmap import HeatmapProvider
from app.providers.ifind import IfindMcpProvider
from app.providers.market_overview import TICKFLOW_A_SHARE_UNIVERSE, EastmoneyMarketOverviewProvider
from app.providers.news_risk import EastmoneyNewsRiskProvider
from app.providers.recent_limit_up_candidates import RecentLimitUpCandidateProvider
from app.providers.tdx_mcp import TdxMcpProvider
from app.providers.tdx_minute_history import TdxMinuteHistoryProvider
from app.providers.tencent_quote import TencentQuoteProvider
from app.providers.thsdk_candidates import ThsdkCandidateProvider
from app.providers.eastmoney_kline import EastmoneyKlineProvider
from app.providers.eastmoney_quote import EastmoneyQuoteProvider
from app.providers.tickflow import TickFlowDailyKlineProvider, TickFlowQuoteProvider
from app.services.auction_model import (
    AuctionModelResultStore,
    AuctionModelService,
    ProviderAuctionModelSource,
)
from app.services.auction_review_store import AuctionReviewStore
from app.services.auction_snapshot_store import AuctionSnapshotStore
from app.services.auction_top3_live_confirmation import AuctionTop3LiveConfirmationStore
from app.services.auction_top3_training import AuctionTop3TrainingStore
from app.services.background_jobs import BackgroundJobStore
from app.services.cache_registry import CacheRegistry
from app.services.capital_signal_store import CapitalSignalStore
from app.services.capital_signals import CapitalSignalService
from app.services.chanlun import symbols as chanlun_symbols
from app.services.chanlun.adapter import ChanlunAdapter
from app.services.chanlun.alert_service import ChanlunAlertService
from app.services.chanlun.alerts import ChanlunAlertStore
from app.services.chanlun.paper import ChanlunPaperOrderStore
from app.services.chanlun.paper_service import ChanlunPaperOrderService
from app.services.chanlun.rc8_client import Rc8WorkerClient
from app.services.chanlun.research_catalog import ResearchCatalog, load_research_catalog
from app.services.chanlun.research_service import CzscResearchService
from app.services.chanlun.research_store import ChanlunResearchStore
from app.services.chanlun.shadow_service import CzscShadowScheduler
from app.services.chanlun.service import ChanlunAnalysisService
from app.services.chanlun.store import ChanlunMinuteBarStore
from app.services.chanlun.symbols import ChanlunSymbolSearchService
from app.services.etf_excess_flow import EtfExcessFlowService
from app.services.etf_price_history import EtfPriceHistoryService
from app.services.etf_three_factor_monitor import EtfThreeFactorMonitor
from app.services.etf_three_factor_store import EtfThreeFactorStore
from app.services.gsgf_auto_review import GsgfAutoReviewService
from app.services.gsgf_review import GsgfReviewStore
from app.services.market_emotion_history import MarketEmotionHistoryStore
from app.services.market_sentiment_analysis import (
    MarketSentimentAnalysisService,
    MarketSentimentAnalysisStore,
    build_sentiment_analysis_input,
)
from app.services.market_sentiment_analysis_sampler import MarketSentimentAnalysisSampler
from app.services.market_sentiment_percentile_service import MarketSentimentPercentileService
from app.services.market_sentiment_percentile_store import MarketSentimentPercentileStore
from app.services.model_maintenance_store import ModelMaintenanceStore
from app.services.notification_channels import (
    NotificationSendResult,
    NotificationSettings,
    public_notification_settings,
)
from app.services.plate_rotation_reference import PlateRotationReferenceProvider
from app.services.runs import RunStore
from app.services.runtime_settings import (
    effective_runtime_settings,
    load_runtime_settings,
)
from app.services.sector_replica_live import SectorReplicaLiveProvider
from app.services.sector_workbench_store import SectorThemeRowsStore, SectorWorkbenchSampleStore
from app.services.sentiment_monitor import SentimentMonitor
from app.services.sentiment_review_store import SentimentReviewStore
from app.services.sentiment_snapshot_store import SentimentSnapshotStore
from app.services.short_term_cache import TtlCache

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.models import (
    GsgfModelHealth,
    GsgfReviewSummary,
    KlineBar,
    SentimentPercentileAnalysisResponse,
    SentimentPercentilePoint,
    SentimentPercentileResponse,
    SentimentSummaryResponse,
)
from app.providers.watchlist import WatchlistSnapshot
from app.services.common import dedupe_symbols as _dedupe_symbols
from app.services.gsgf_model_health import build_gsgf_model_health
from app.services.gsgf_real_calibration import summarize_gsgf_real_calibration
from app.services.market_emotion_history import MarketEmotionSample  # noqa: F401
from app.services.market_sentiment_validation import SentimentValidationReport
from app.services.notification_channels import DefaultSmtpClient, send_notification_message
from app.services.plate_rotation_reference import PlateRotationReferenceResponse
from app.services.sentiment_decision import build_sentiment_decision
from app.services.sentiment_monitor import is_trading_session
from app.services.short_term_sentiment import build_market_emotion_snapshot, build_sentiment_summary, build_short_term_sentiment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI 后绑定持有器
# ---------------------------------------------------------------------------

_app: FastAPI | None = None


def bind_app(app: FastAPI) -> None:
    global _app
    _app = app


def app_state() -> FastAPI:
    if _app is None:
        raise RuntimeError("app 尚未绑定：请在创建 FastAPI 实例后调用 deps.bind_app(app)")
    return _app


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def _cors_allow_origins() -> list[str]:
    settings = get_settings()
    return [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]


def _cors_allow_origin_regex() -> str:
    # Local Vite preview/dev servers use an ephemeral port during development.
    return r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$"


# ---------------------------------------------------------------------------
# 运行时设置与路径
# ---------------------------------------------------------------------------


def _runtime_config_path() -> Path:
    injected = getattr(app_state().state, "runtime_config_path", None)
    if injected is not None:
        return Path(injected)
    return get_settings().data_dir / "runtime_config.json"


def _watchlist_path() -> Path:
    injected = getattr(app_state().state, "watchlist_path", None)
    if injected is not None:
        return Path(injected)
    return get_settings().watchlist_path


def _effective_settings():
    return effective_runtime_settings(get_settings(), _runtime_config_path())


def _public_saved_settings() -> dict[str, object]:
    runtime = load_runtime_settings(_runtime_config_path())
    payload = runtime.model_dump(
        mode="json",
        exclude={
            "tickflow_api_key": True,
            "ifind_api_key": True,
            "tdx_api_key": True,
            "ai_analysis": {"api_key": True},
        },
        exclude_none=True,
    )
    payload["notification_channels"] = public_notification_settings(
        NotificationSettings(channels=runtime.notification_channels)
    )["channels"]
    return payload


# ---------------------------------------------------------------------------
# 数据源 provider 生命周期
# ---------------------------------------------------------------------------


def _close_provider(provider: object | None) -> None:
    close = getattr(provider, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            logger.exception("failed to close data source provider")


def _close_default_data_source_providers() -> None:
    for attribute in (
        "default_market_overview_provider",
        "default_kline_provider",
        "default_chanlun_daily_provider",
        "default_quote_provider",
        "default_ifind_provider",
        "default_tdx_provider",
        "default_valuation_quote_provider",
    ):
        provider = getattr(app_state().state, attribute, None)
        if provider is not None:
            _close_provider(provider)
        if hasattr(app_state().state, attribute):
            delattr(app_state().state, attribute)
        key_attribute = f"{attribute}_key"
        if hasattr(app_state().state, key_attribute):
            delattr(app_state().state, key_attribute)


def _cached_default_provider(
    *,
    attribute: str,
    key: tuple[object, ...],
    factory: Any,
) -> object:
    key_attribute = f"{attribute}_key"
    state = app_state().state
    current = getattr(state, attribute, None)
    if current is not None and getattr(state, key_attribute, None) == key:
        return current
    if current is not None:
        _close_provider(current)
    provider = factory()
    setattr(state, attribute, provider)
    setattr(state, key_attribute, key)
    return provider


def _sanitized_health_error(error: object) -> str:
    if isinstance(error, BaseException):
        return error.__class__.__name__
    message = str(error).splitlines()[0].strip()
    if "Traceback" in message or "/" in message or "\\" in message:
        return "worker unavailable"
    return message[:160] if message else "unavailable"


# ---------------------------------------------------------------------------
# 缓存注册表
# ---------------------------------------------------------------------------

SHORT_TERM_SENTIMENT_CACHE: TtlCache[ShortTermSentimentResponse] = TtlCache(
    ttl_seconds=90, name="short_term_sentiment"
)
WATCHLIST_GSGF_CACHE: TtlCache[dict[str, object]] = TtlCache(
    ttl_seconds=300, name="watchlist_gsgf_status"
)
# 自选池单次 gsgf 状态扫描上限，防止超大池把请求阻塞到分钟级。
_WATCHLIST_GSGF_MAX_SYMBOLS = 60
MARKET_EMOTION_CACHE: TtlCache[MarketEmotionSnapshotResponse] = TtlCache(
    ttl_seconds=45, name="market_emotion"
)
MARKET_OVERVIEW_CACHE: TtlCache[MarketOverviewResponse] = TtlCache(
    ttl_seconds=45, name="market_overview"
)
MARKET_RANKINGS_CACHE: TtlCache[MarketRankingsResponse] = TtlCache(
    ttl_seconds=45, name="market_rankings"
)
CAPITAL_SUMMARY_CACHE: TtlCache[CapitalSummaryResponse] = TtlCache(
    ttl_seconds=60, name="capital_summary"
)
AUCTION_SNAPSHOT_CACHE: TtlCache[AuctionSnapshotResponse] = TtlCache(
    ttl_seconds=15, name="auction_snapshot"
)
SECTOR_RADAR_CACHE: TtlCache[SectorRadarResponse] = TtlCache(ttl_seconds=45, name="sector_radar")
PLATE_ROTATION_REFERENCE_CACHE: TtlCache[PlateRotationReferenceResponse] = TtlCache(
    ttl_seconds=120, name="plate_rotation_reference"
)
SECTOR_INTRADAY_CACHE: TtlCache[tuple[list[SectorWorkbenchSeries], StrongStockSourceStatus]] = (
    TtlCache(
        ttl_seconds=90,
        name="sector_intraday",
    )
)
SECTOR_THEME_ROWS_CACHE: TtlCache[
    tuple[list[dict[str, object]], StrongStockSourceStatus | None]
] = TtlCache(
    ttl_seconds=300,
    name="sector_theme_rows",
)
STOCK_KLINE_CACHE: TtlCache[StockKlineResponse] = TtlCache(ttl_seconds=300, name="stock_kline")
STOCK_RESEARCH_CACHE: TtlCache[StockResearchResponse] = TtlCache(
    ttl_seconds=900, name="stock_research"
)
SECTOR_STOCK_INDUSTRY_TIMEOUT_SECONDS = 2.0
CACHE_DEFINITIONS = (
    ("short_term_sentiment", "sentiment", SHORT_TERM_SENTIMENT_CACHE),
    ("market_emotion", "sentiment", MARKET_EMOTION_CACHE),
    ("market_overview", "home", MARKET_OVERVIEW_CACHE),
    ("market_rankings", "home", MARKET_RANKINGS_CACHE),
    ("capital_summary", "home", CAPITAL_SUMMARY_CACHE),
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


def _gsgf_auto_review_service() -> GsgfAutoReviewService:
    injected = getattr(app_state().state, "gsgf_auto_review_service", None)
    if injected is not None:
        return injected
    service = GsgfAutoReviewService(
        config_loader=lambda: load_runtime_settings(_runtime_config_path()).gsgf_auto_review,
        review_runner=_run_gsgf_daily_review,
        calibration_runner=_start_gsgf_weekly_calibration,
        recent_trade_dates=_recent_screen_trade_dates,
        notifier=_send_sentiment_monitor_notification,
    )
    app_state().state.gsgf_auto_review_service = service
    return service



def _sentiment_monitor() -> SentimentMonitor:
    injected = getattr(app_state().state, "sentiment_monitor", None)
    if injected is not None:
        return injected
    builder = getattr(app_state().state, "sentiment_monitor_snapshot_builder", None)
    monitor = SentimentMonitor(
        snapshot_builder=builder or _build_and_persist_sentiment_snapshots,
        config_loader=lambda: load_runtime_settings(_runtime_config_path()).sentiment_monitor,
        notifier=_send_sentiment_monitor_notification,
    )
    app_state().state.sentiment_monitor = monitor
    return monitor



def _sentiment_snapshot_store() -> SentimentSnapshotStore:
    settings = get_settings()
    data_dir = getattr(app_state().state, "runs_dir", None)
    if data_dir is not None:
        return SentimentSnapshotStore(Path(data_dir))
    return SentimentSnapshotStore(
        settings.data_dir,
        retention_days=settings.sentiment_snapshot_retention_days,
    )



def _market_emotion_history_store() -> MarketEmotionHistoryStore:
    settings = get_settings()
    data_dir = getattr(app_state().state, "runs_dir", None)
    if data_dir is not None:
        return MarketEmotionHistoryStore(Path(data_dir))
    return MarketEmotionHistoryStore(
        settings.data_dir,
        retention_days=settings.market_emotion_history_retention_days,
        samples_per_day=settings.market_emotion_samples_per_day,
    )



def _auction_top3_training_store() -> AuctionTop3TrainingStore:
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    existing = getattr(app_state().state, "auction_top3_training_store", None)
    existing_data_dir = getattr(app_state().state, "auction_top3_training_store_data_dir", None)
    if existing is not None and existing_data_dir == data_dir:
        return existing
    store = AuctionTop3TrainingStore(data_dir)
    app_state().state.auction_top3_training_store = store
    app_state().state.auction_top3_training_store_data_dir = data_dir
    return store



def _model_maintenance_store() -> ModelMaintenanceStore:
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    existing = getattr(app_state().state, "model_maintenance_store", None)
    existing_data_dir = getattr(app_state().state, "model_maintenance_store_data_dir", None)
    if existing is not None and existing_data_dir == data_dir:
        return existing
    store = ModelMaintenanceStore(data_dir)
    app_state().state.model_maintenance_store = store
    app_state().state.model_maintenance_store_data_dir = data_dir
    return store



def _background_job_store() -> BackgroundJobStore:
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    existing = getattr(app_state().state, "background_job_store", None)
    existing_data_dir = getattr(app_state().state, "background_job_store_data_dir", None)
    if existing is not None and existing_data_dir == data_dir:
        return existing
    store = BackgroundJobStore(data_dir)
    app_state().state.background_job_store = store
    app_state().state.background_job_store_data_dir = data_dir
    return store



def _sentiment_review_store() -> SentimentReviewStore:
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    injected = getattr(app_state().state, "sentiment_review_store", None)
    injected_data_dir = getattr(app_state().state, "sentiment_review_store_data_dir", None)
    if injected is not None and injected_data_dir == data_dir:
        return injected
    store = SentimentReviewStore(data_dir)
    app_state().state.sentiment_review_store = store
    app_state().state.sentiment_review_store_data_dir = data_dir
    return store



def _gsgf_review_store() -> GsgfReviewStore:
    settings = get_settings()
    data_dir = getattr(app_state().state, "runs_dir", None)
    if data_dir is not None:
        return GsgfReviewStore(Path(data_dir))
    return GsgfReviewStore(settings.data_dir, max_records=settings.gsgf_review_retention_records)



def _run_store() -> RunStore:
    settings = get_settings()
    runs_dir = getattr(app_state().state, "runs_dir", None)
    if runs_dir is not None:
        return RunStore(Path(runs_dir))
    return RunStore(settings.runs_dir, retention_count=settings.screen_run_retention_count)



def _sector_theme_rows_store() -> SectorThemeRowsStore:
    injected = getattr(app_state().state, "sector_theme_rows_store", None)
    if injected is not None:
        return injected
    data_dir = Path(
        getattr(
            app_state().state,
            "sector_theme_rows_dir",
            Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
            / "sectors"
            / "theme-rows",
        )
    )
    store = SectorThemeRowsStore(data_dir)
    app_state().state.sector_theme_rows_store = store
    return store



def _sector_workbench_store() -> SectorWorkbenchSampleStore:
    injected = getattr(app_state().state, "sector_workbench_store", None)
    if injected is not None:
        return injected
    data_dir = Path(
        getattr(
            app_state().state,
            "sector_workbench_dir",
            Path(getattr(app_state().state, "runs_dir", get_settings().data_dir)) / "sectors",
        )
    )
    store = SectorWorkbenchSampleStore(data_dir)
    app_state().state.sector_workbench_store = store
    return store



def _auction_review_store() -> AuctionReviewStore:
    injected = getattr(app_state().state, "auction_review_store", None)
    if injected is not None:
        return injected
    settings = get_settings()
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    store = AuctionReviewStore(data_dir, retention_days=settings.auction_review_retention_days)
    app_state().state.auction_review_store = store
    return store



def _auction_snapshot_store() -> AuctionSnapshotStore:
    injected = getattr(app_state().state, "auction_snapshot_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    store = AuctionSnapshotStore(review_store=_auction_review_store(), data_dir=data_dir)
    app_state().state.auction_snapshot_store = store
    return store



def _sector_replica_live_provider() -> object:
    injected = getattr(app_state().state, "sector_replica_live_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    provider = SectorReplicaLiveProvider(timeout_seconds=settings.provider_timeout_seconds)
    app_state().state.sector_replica_live_provider = provider
    return provider



def _plate_rotation_reference_provider() -> object:
    injected = getattr(app_state().state, "plate_rotation_reference_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    provider = PlateRotationReferenceProvider(timeout_seconds=settings.provider_timeout_seconds)
    app_state().state.plate_rotation_reference_provider = provider
    return provider



def _market_overview_provider() -> object:
    injected = getattr(app_state().state, "market_overview_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    base_settings = get_settings()
    quote_provider = _quote_provider()
    ifind_provider = _ifind_provider()
    kline_provider = _kline_provider()
    return _cached_default_provider(
        attribute="default_market_overview_provider",
        key=(
            settings.provider_timeout_seconds,
            id(quote_provider),
            id(ifind_provider),
            id(kline_provider),
            str(base_settings.data_dir),
        ),
        factory=lambda: EastmoneyMarketOverviewProvider(
            timeout_seconds=settings.provider_timeout_seconds,
            realtime_quote_provider=quote_provider,
            ifind_index_provider=ifind_provider,
            ifind_stock_provider=ifind_provider,
            daily_kline_provider=kline_provider,
            turnover_cache_path=base_settings.data_dir / "market-overview" / "turnover-history.json",
            sentiment_snapshot_dir=base_settings.data_dir / "sentiment_snapshots",
        ),
    )



def _ifind_provider() -> IfindMcpProvider:
    injected = getattr(app_state().state, "ifind_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return _cached_default_provider(
        attribute="default_ifind_provider",
        key=(
            settings.ifind_api_key,
            settings.ifind_base_url,
            settings.provider_timeout_seconds,
            settings.ifind_service_id,
        ),
        factory=lambda: IfindMcpProvider(
            api_key=settings.ifind_api_key,
            base_url=settings.ifind_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            http_client=getattr(app_state().state, "ifind_http_client", None),
        ),
    )



def _chanlun_symbol_search_service() -> ChanlunSymbolSearchService:
    injected = getattr(app_state().state, "chanlun_symbol_search_service", None)
    if injected is not None:
        return injected

    def load_symbols() -> object:
        try:
            rows = _quote_provider().get_quotes_by_universe(TICKFLOW_A_SHARE_UNIVERSE)
        except Exception:
            return chanlun_symbols._load_default_symbols()
        return rows or chanlun_symbols._load_default_symbols()

    service = ChanlunSymbolSearchService(
        loader=load_symbols,
        watchlist_loader=lambda: _watchlist_snapshot().items if _watchlist_snapshot() else [],
        latest_screen_loader=lambda: (
            _run_store().load_latest().items if _run_store().load_latest() is not None else []
        ),
    )
    app_state().state.chanlun_symbol_search_service = service
    return service



def _chanlun_paper_order_service() -> ChanlunPaperOrderService:
    injected = getattr(app_state().state, "chanlun_paper_order_service", None)
    if injected is not None:
        return injected
    service = ChanlunPaperOrderService(
        analysis_service=_chanlun_analysis_service(),
        quote_provider=_quote_provider(),
        store=_chanlun_paper_order_store(),
        initial_cash=get_settings().chanlun_paper_initial_cash,
    )
    app_state().state.chanlun_paper_order_service = service
    return service



def _chanlun_paper_order_store() -> ChanlunPaperOrderStore:
    injected = getattr(app_state().state, "chanlun_paper_order_store", None)
    if injected is not None:
        return injected
    store = ChanlunPaperOrderStore(get_settings().data_dir / "chanlun" / "paper.sqlite3")
    app_state().state.chanlun_paper_order_store = store
    return store



def _chanlun_alert_service() -> ChanlunAlertService:
    injected = getattr(app_state().state, "chanlun_alert_service", None)
    if injected is not None:
        return injected
    service = ChanlunAlertService(
        analysis_service=_chanlun_analysis_service(),
        store=_chanlun_alert_store(),
    )
    app_state().state.chanlun_alert_service = service
    return service



def _chanlun_alert_store() -> ChanlunAlertStore:
    injected = getattr(app_state().state, "chanlun_alert_store", None)
    if injected is not None:
        return injected
    store = ChanlunAlertStore(get_settings().data_dir / "chanlun" / "alerts.sqlite3")
    app_state().state.chanlun_alert_store = store
    return store



def _chanlun_shadow_scheduler() -> CzscShadowScheduler:
    with _CHANLUN_RESEARCH_LOCK:
        injected = getattr(app_state().state, "chanlun_shadow_scheduler", None)
        if injected is not None:
            return injected
        scheduler = CzscShadowScheduler(
            jobs=_background_job_store(),
            store=_chanlun_research_store(),
            runner=_chanlun_research_service(),
            hard_timeout_seconds=get_settings().chanlun_rc8_hard_timeout_seconds,
        )
        app_state().state.chanlun_shadow_scheduler = scheduler
        return scheduler



def _chanlun_research_service() -> CzscResearchService:
    with _CHANLUN_RESEARCH_LOCK:
        injected = getattr(app_state().state, "chanlun_research_service", None)
        if injected is not None:
            return injected
        service = CzscResearchService(
            store=_chanlun_research_store(),
            client=_chanlun_rc8_client(),
            input_provider=_chanlun_analysis_service(),
            catalog=_chanlun_research_catalog(),
            settings=get_settings(),
        )
        app_state().state.chanlun_research_service = service
        return service



def _chanlun_research_store() -> ChanlunResearchStore:
    with _CHANLUN_RESEARCH_LOCK:
        injected = getattr(app_state().state, "chanlun_research_store", None)
        if injected is not None:
            return injected
        store = ChanlunResearchStore(get_settings().data_dir / "chanlun" / "research.sqlite3")
        app_state().state.chanlun_research_store = store
        return store



def _chanlun_analysis_service() -> ChanlunAnalysisService:
    with _CHANLUN_RESEARCH_LOCK:
        injected = getattr(app_state().state, "chanlun_analysis_service", None)
        if injected is not None:
            return injected
        settings = get_settings()
        service = ChanlunAnalysisService(
            store=_chanlun_minute_store(),
            intraday_provider=_quote_provider(),
            history_provider=_chanlun_history_provider(),
            adapter=_chanlun_adapter(),
            daily_provider=_chanlun_daily_provider(),
            cache_seconds=settings.chanlun_cache_seconds,
            minute_retention_days=settings.chanlun_minute_retention_days,
            history_max_bars=settings.chanlun_backfill_max_bars,
        )
        app_state().state.chanlun_analysis_service = service
        return service



def _chanlun_minute_store() -> ChanlunMinuteBarStore:
    injected = getattr(app_state().state, "chanlun_minute_store", None)
    if injected is not None:
        return injected
    store = ChanlunMinuteBarStore(get_settings().data_dir / "chanlun" / "minute.sqlite3")
    app_state().state.chanlun_minute_store = store
    return store



def _chanlun_history_provider() -> TdxMinuteHistoryProvider:
    injected = getattr(app_state().state, "chanlun_history_provider", None)
    if injected is not None:
        return injected
    settings = get_settings()
    return TdxMinuteHistoryProvider(
        enabled=settings.chanlun_tdx_enabled,
        timeout_seconds=settings.chanlun_tdx_timeout_seconds,
    )



def _tdx_provider() -> TdxMcpProvider:
    injected = getattr(app_state().state, "tdx_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return _cached_default_provider(
        attribute="default_tdx_provider",
        key=(settings.tdx_api_key, settings.tdx_base_url, settings.provider_timeout_seconds),
        factory=lambda: TdxMcpProvider(
            api_key=settings.tdx_api_key,
            base_url=settings.tdx_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            http_client=getattr(app_state().state, "tdx_http_client", None),
        ),
    )



def _heatmap_provider() -> HeatmapProvider:
    provider = getattr(app_state().state, "heatmap_provider", None)
    if provider is None:
        settings = get_settings()
        provider = HeatmapProvider(
            turnover_cache_path=settings.data_dir / "heatmap" / "turnover-history.json"
        )
        app_state().state.heatmap_provider = provider
    return provider



def _concept_provider() -> object:
    injected = getattr(app_state().state, "concept_provider", None)
    if injected is not None:
        return injected
    cached = getattr(app_state().state, "default_concept_provider", None)
    if cached is None:
        settings = _effective_settings()
        cached = EastmoneyConceptBlockProvider(timeout_seconds=settings.provider_timeout_seconds)
        app_state().state.default_concept_provider = cached
    return cached



def _news_risk_provider() -> object:
    injected = getattr(app_state().state, "news_risk_provider", None)
    if injected is not None:
        return injected
    return EastmoneyNewsRiskProvider.from_akshare()



def _valuation_quote_provider() -> object:
    injected = getattr(app_state().state, "valuation_quote_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    return _cached_default_provider(
        attribute="default_valuation_quote_provider",
        key=(settings.provider_timeout_seconds,),
        factory=lambda: TencentQuoteProvider(timeout_seconds=settings.provider_timeout_seconds),
    )



def _etf_price_history_service() -> EtfPriceHistoryService:
    injected = getattr(app_state().state, "etf_price_history_service", None)
    if injected is not None:
        return injected
    service = EtfPriceHistoryService(provider=_daily_kline_provider())
    app_state().state.etf_price_history_service = service
    return service



def _etf_three_factor_monitor() -> EtfThreeFactorMonitor:
    injected = getattr(app_state().state, "etf_three_factor_monitor", None)
    if injected is not None:
        return injected
    cached = getattr(app_state().state, "default_etf_three_factor_monitor", None)
    if cached is None:
        settings = get_settings()
        capital_service = _capital_signal_service()
        cached = EtfThreeFactorMonitor(
            quote_provider=_quote_provider(),
            daily_kline_provider=_daily_kline_provider(),
            share_snapshot_provider=capital_service,
            capital_store=capital_service.store,
            store=EtfThreeFactorStore(settings.data_dir),
        )
        app_state().state.default_etf_three_factor_monitor = cached
    return cached



def _etf_excess_flow_service() -> EtfExcessFlowService:
    injected = getattr(app_state().state, "etf_excess_flow_service", None)
    if injected is not None:
        return injected
    capital_service = _capital_signal_service()
    cached = getattr(app_state().state, "default_etf_excess_flow_service", None)
    if cached is None or cached.store.root_dir != capital_service.store.root_dir:
        cached = EtfExcessFlowService(capital_service.store)
        app_state().state.default_etf_excess_flow_service = cached
    return cached



def _capital_signal_service() -> CapitalSignalService:
    injected = getattr(app_state().state, "capital_signal_service", None)
    if injected is not None:
        return injected
    cached = getattr(app_state().state, "default_capital_signal_service", None)
    if cached is None:
        settings = get_settings()
        cached = CapitalSignalService(
            provider=OfficialCapitalDataProvider(
                timeout_seconds=settings.provider_timeout_seconds
            ),
            store=CapitalSignalStore(settings.data_dir),
            quote_provider=_quote_provider(),
            holder_provider=SinaEtfHolderProvider(
                timeout_seconds=settings.provider_timeout_seconds
            ),
        )
        app_state().state.default_capital_signal_service = cached
    return cached



def _quote_provider() -> object:
    injected = getattr(app_state().state, "quote_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    if getattr(settings, "quote_provider", "eastmoney") == "eastmoney":
        return _cached_default_provider(
            attribute="default_quote_provider",
            key=("eastmoney", settings.provider_timeout_seconds),
            factory=lambda: EastmoneyQuoteProvider(
                timeout_seconds=settings.provider_timeout_seconds,
            ),
        )
    return _cached_default_provider(
        attribute="default_quote_provider",
        key=(settings.tickflow_api_key, settings.tickflow_base_url, settings.provider_timeout_seconds),
        factory=lambda: TickFlowQuoteProvider(
            api_key=settings.tickflow_api_key,
            base_url=settings.tickflow_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
        ),
    )



def _chanlun_daily_provider() -> object:
    injected = getattr(app_state().state, "kline_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    if getattr(settings, "kline_provider", "eastmoney") == "eastmoney":
        return _cached_default_provider(
            attribute="default_chanlun_daily_provider",
            key=("eastmoney", settings.provider_timeout_seconds),
            factory=lambda: EastmoneyKlineProvider(
                timeout_seconds=settings.provider_timeout_seconds,
                adjust="none",
            ),
        )
    return _cached_default_provider(
        attribute="default_chanlun_daily_provider",
        key=(settings.tickflow_api_key, settings.tickflow_base_url, settings.provider_timeout_seconds),
        factory=lambda: TickFlowDailyKlineProvider(
            api_key=settings.tickflow_api_key,
            base_url=settings.tickflow_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            adjust="none",
        ),
    )



def _market_sentiment_analysis_sampler() -> MarketSentimentAnalysisSampler:
    injected = getattr(app_state().state, "market_sentiment_analysis_sampler", None)
    if injected is not None:
        return injected
    sampler = MarketSentimentAnalysisSampler(
        latest_completed_trade_date=_latest_completed_market_sentiment_trade_date,
        generate_latest=_generate_latest_market_sentiment_analysis,
        clock=getattr(app_state().state, "market_sentiment_analysis_sampler_clock", None),
    )
    app_state().state.market_sentiment_analysis_sampler = sampler
    return sampler



def _market_sentiment_analysis_service() -> MarketSentimentAnalysisService:
    injected = getattr(app_state().state, "market_sentiment_analysis_service", None)
    if injected is not None:
        return injected
    service = MarketSentimentAnalysisService(
        _market_sentiment_analysis_store(),
        http_client=getattr(app_state().state, "market_sentiment_analysis_http_client", None),
    )
    app_state().state.market_sentiment_analysis_service = service
    return service



def _market_sentiment_analysis_store() -> MarketSentimentAnalysisStore:
    injected = getattr(app_state().state, "market_sentiment_analysis_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    store = MarketSentimentAnalysisStore(data_dir)
    app_state().state.market_sentiment_analysis_store = store
    return store



def _market_sentiment_percentile_service() -> MarketSentimentPercentileService:
    injected = getattr(app_state().state, "market_sentiment_percentile_service", None)
    if injected is not None:
        return injected
    service = MarketSentimentPercentileService(
        provider=_daily_kline_provider(),
        store=_market_sentiment_percentile_store(),
    )
    app_state().state.market_sentiment_percentile_service = service
    return service



def _market_sentiment_percentile_store() -> MarketSentimentPercentileStore:
    injected = getattr(app_state().state, "market_sentiment_percentile_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    store = MarketSentimentPercentileStore(data_dir)
    app_state().state.market_sentiment_percentile_store = store
    return store



def _daily_kline_provider() -> object:
    return _kline_provider()



def _kline_provider() -> object:
    injected = getattr(app_state().state, "kline_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    provider_name = getattr(settings, "kline_provider", "eastmoney")
    if provider_name == "eastmoney":
        return _cached_default_provider(
            attribute="default_kline_provider",
            key=("eastmoney", settings.provider_timeout_seconds),
            factory=lambda: EastmoneyKlineProvider(
                timeout_seconds=settings.provider_timeout_seconds,
                adjust="forward",
            ),
        )
    return _cached_default_provider(
        attribute="default_kline_provider",
        key=(settings.tickflow_api_key, settings.tickflow_base_url, settings.provider_timeout_seconds),
        factory=lambda: TickFlowDailyKlineProvider(
            api_key=settings.tickflow_api_key,
            base_url=settings.tickflow_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
        ),
    )



def _candidate_provider() -> object:
    injected = getattr(app_state().state, "candidate_provider", None)
    if injected is not None:
        return injected
    settings = _effective_settings()
    if settings.candidate_provider == "thsdk":
        return ThsdkCandidateProvider.from_installed_package()
    return RecentLimitUpCandidateProvider.from_akshare()



def _auction_top3_live_confirmation_store() -> AuctionTop3LiveConfirmationStore:
    injected = getattr(app_state().state, "auction_top3_live_confirmation_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    store = AuctionTop3LiveConfirmationStore(data_dir)
    app_state().state.auction_top3_live_confirmation_store = store
    return store



def _auction_model_result_store() -> AuctionModelResultStore:
    injected = getattr(app_state().state, "auction_model_result_store", None)
    if injected is not None:
        return injected
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    return AuctionModelResultStore(data_dir)



def _auction_model_service() -> AuctionModelService:
    injected = getattr(app_state().state, "auction_model_service", None)
    if injected is not None:
        return injected
    settings = get_settings()
    return AuctionModelService(
        source=ProviderAuctionModelSource(
            candidate_provider=_candidate_provider(),
            kline_provider=_kline_provider(),
        ),
        model_path=Path(settings.auction_model_model_path),
        metadata_path=Path(settings.auction_model_metadata_path),
        performance_path=Path(settings.auction_model_performance_path),
        lookback=settings.auction_model_lookback,
        top_n=settings.auction_model_top_n,
        max_items=settings.auction_model_max_items,
        max_kline_workers=settings.auction_model_kline_workers,
    )


def _send_sentiment_monitor_notification(title: str, message_text: str) -> NotificationSendResult:
    runtime = load_runtime_settings(_runtime_config_path())
    return send_notification_message(
        NotificationSettings(channels=runtime.notification_channels),
        title=title,
        message_text=message_text,
        http_client=getattr(app_state().state, "notification_http_client", None),
        smtp_client=getattr(app_state().state, "notification_smtp_client", None) or DefaultSmtpClient(),
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
    return deduped[-max(1, count) :]



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
            lambda result: (
                _send_sentiment_monitor_notification(
                    "GSGF 每周真实样本校准完成",
                    build_gsgf_model_health(
                        _gsgf_review_store().load_latest_summary(), result
                    ).summary_text,
                )
                if config.notify_on_success
                else None
            )
        ),
    )



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



def _watchlist_snapshot() -> WatchlistSnapshot | None:
    return getattr(app_state().state, "watchlist_snapshot", None)



def _chanlun_rc8_client() -> Rc8WorkerClient | None:
    with _CHANLUN_RESEARCH_LOCK:
        if hasattr(app_state().state, "chanlun_rc8_client"):
            return app_state().state.chanlun_rc8_client
        settings = get_settings()
        if not settings.chanlun_rc8_enabled:
            app_state().state.chanlun_rc8_client = None
            return None
        python_path = Path(settings.chanlun_rc8_python)
        worker_path = Path(__file__).resolve().parent / "services" / "chanlun" / "rc8_worker.py"
        if not python_path.is_file() or not worker_path.is_file():
            app_state().state.chanlun_rc8_client = None
            return None
        client = Rc8WorkerClient(
            python_path=python_path,
            worker_path=worker_path,
            hard_timeout_seconds=settings.chanlun_rc8_hard_timeout_seconds,
        )
        app_state().state.chanlun_rc8_client = client
        return client



def _chanlun_research_catalog() -> ResearchCatalog:
    with _CHANLUN_RESEARCH_LOCK:
        injected = getattr(app_state().state, "chanlun_research_catalog", None)
        if injected is not None:
            return injected
        catalog = load_research_catalog()
        app_state().state.chanlun_research_catalog = catalog
        return catalog



def _chanlun_adapter() -> ChanlunAdapter:
    injected = getattr(app_state().state, "chanlun_adapter", None)
    if injected is not None:
        return injected
    adapter = ChanlunAdapter()
    app_state().state.chanlun_adapter = adapter
    return adapter



def _latest_completed_market_sentiment_trade_date(now: datetime) -> str:
    percentile = _market_sentiment_percentile_service().get(now=now)
    return percentile.latest_complete_trade_date



def _generate_latest_market_sentiment_analysis(
    now: datetime,
) -> SentimentPercentileAnalysisResponse:
    percentile = _market_sentiment_percentile_service().get(now=now)
    return _generate_market_sentiment_analysis(
        percentile.latest_complete_trade_date,
        percentile_response=percentile,
    )



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
            market_overview=_cached_market_overview(),
        ),
    ).model_copy(deep=True)
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
                market_emotion.generated_at = sampled_at.isoformat(timespec="seconds")
                history_store.append(market_emotion)
                samples = history_store.load(trade_date)
            market_emotion.samples = samples
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



_CHANLUN_RESEARCH_LOCK = RLock()


def _gsgf_model_health() -> GsgfModelHealth:
    return build_gsgf_model_health(
        _gsgf_review_store().load_latest_summary(),
        _background_job_store().load_latest_calibration(),
    )



def _generate_market_sentiment_analysis(
    trade_date: str,
    *,
    force: bool = False,
    percentile_response: SentimentPercentileResponse | None = None,
) -> SentimentPercentileAnalysisResponse:
    percentile, point = _percentile_point_for_trade_date(
        trade_date,
        response=percentile_response,
    )
    input_payload = _build_market_sentiment_analysis_input(
        trade_date,
        percentile,
        point,
        refresh_missing=True,
    )
    return _market_sentiment_analysis_service().generate(
        input_payload,
        _effective_settings().ai_analysis,
        force=force,
    )



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



def _should_persist_market_emotion_sample(
    trade_date: str,
    samples: list[object],
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    if (
        trade_date != current.date().isoformat()
        or current.weekday() >= 5
        or current.time() > time(15, 0)
        or not is_trading_session(current)
    ):
        return False
    latest = _latest_market_emotion_sampled_at(samples)
    return latest is None or current - latest >= _MARKET_EMOTION_SAMPLE_INTERVAL



def _cached_market_overview() -> MarketOverviewResponse:
    provider = _market_overview_provider()
    cache_key = f"market-overview:{_provider_cache_key(provider)}"
    return MARKET_OVERVIEW_CACHE.get_or_refresh(cache_key, provider.get_overview).model_copy(
        deep=True
    )



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



_MARKET_EMOTION_HISTORY_WRITE_LOCK = RLock()


def _build_market_sentiment_analysis_input(
    trade_date: str,
    percentile: SentimentPercentileResponse,
    point: SentimentPercentilePoint,
    *,
    refresh_missing: bool,
) -> dict[str, object]:
    summary, market_emotion = _optional_sentiment_analysis_context(
        trade_date,
        refresh_missing=refresh_missing,
    )
    decision = None
    if summary is not None:
        try:
            decision = build_sentiment_decision(summary, market_emotion)
        except Exception:
            decision = None
    return build_sentiment_analysis_input(
        point,
        percentile.history,
        summary,
        decision,
        _load_sentiment_validation(),
    )



def _percentile_point_for_trade_date(
    trade_date: str,
    *,
    response: SentimentPercentileResponse | None = None,
) -> tuple[SentimentPercentileResponse, SentimentPercentilePoint]:
    percentile = response or _market_sentiment_percentile_service().get(as_of=trade_date)
    point = next(
        (item for item in percentile.history if item.trade_date == trade_date),
        None,
    )
    if point is None:
        raise HTTPException(status_code=404, detail="该日期不在市场情绪分位历史中")
    return percentile, point



def _latest_market_emotion_sampled_at(
    samples: list[object],
) -> datetime | None:
    latest: datetime | None = None
    for sample in samples:
        sampled_at = getattr(sample, "sampled_at", None)
        if not sampled_at:
            continue
        try:
            candidate = datetime.fromisoformat(str(sampled_at))
        except ValueError:
            continue
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        candidate = candidate.astimezone(ZoneInfo("Asia/Shanghai"))
        if latest is None or candidate > latest:
            latest = candidate
    return latest



_MARKET_EMOTION_SAMPLE_INTERVAL = timedelta(minutes=3)


def _load_sentiment_validation() -> dict[str, object]:
    unavailable = {"status": "unavailable", "sample_count": 0}
    data_dir = Path(getattr(app_state().state, "runs_dir", get_settings().data_dir))
    path = data_dir / "sentiment-percentile" / "validation-v1.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SentimentValidationReport.model_validate(payload).model_dump(mode="json")
    except Exception:
        return unavailable



def _optional_sentiment_analysis_context(
    trade_date: str,
    *,
    refresh_missing: bool = True,
) -> tuple[SentimentSummaryResponse | None, MarketEmotionSnapshotResponse | None]:
    snapshot_store = _sentiment_snapshot_store()
    try:
        summary = snapshot_store.load_summary(trade_date)
    except Exception:
        summary = None
    try:
        market_emotion = snapshot_store.load_market_emotion(trade_date)
    except Exception:
        market_emotion = None

    if (summary is not None and market_emotion is not None) or not refresh_missing:
        return summary, market_emotion
    try:
        sentiment, refreshed_emotion = _build_and_persist_sentiment_snapshots(
            trade_date,
            80,
            refresh=True,
        )
        refreshed_summary = build_sentiment_summary(
            sentiment,
            refreshed_emotion,
            snapshot_status="fresh",
        )
    except Exception:
        return summary, market_emotion
    return refreshed_summary, refreshed_emotion


__all__ = [
    "logger",
    "_app",
    "bind_app",
    "app_state",
    "_cors_allow_origins",
    "_cors_allow_origin_regex",
    "_runtime_config_path",
    "_watchlist_path",
    "_effective_settings",
    "_public_saved_settings",
    "_close_provider",
    "_close_default_data_source_providers",
    "_cached_default_provider",
    "_sanitized_health_error",
    "SHORT_TERM_SENTIMENT_CACHE",
    "WATCHLIST_GSGF_CACHE",
    "_WATCHLIST_GSGF_MAX_SYMBOLS",
    "MARKET_EMOTION_CACHE",
    "MARKET_OVERVIEW_CACHE",
    "MARKET_RANKINGS_CACHE",
    "CAPITAL_SUMMARY_CACHE",
    "AUCTION_SNAPSHOT_CACHE",
    "SECTOR_RADAR_CACHE",
    "PLATE_ROTATION_REFERENCE_CACHE",
    "SECTOR_INTRADAY_CACHE",
    "SECTOR_THEME_ROWS_CACHE",
    "STOCK_KLINE_CACHE",
    "STOCK_RESEARCH_CACHE",
    "SECTOR_STOCK_INDUSTRY_TIMEOUT_SECONDS",
    "CACHE_DEFINITIONS",
    "CACHE_GROUPS",
    "CACHE_REGISTRY",
    "_gsgf_auto_review_service",
    "_sentiment_monitor",
    "_sentiment_snapshot_store",
    "_market_emotion_history_store",
    "_auction_top3_training_store",
    "_model_maintenance_store",
    "_background_job_store",
    "_sentiment_review_store",
    "_gsgf_review_store",
    "_run_store",
    "_sector_theme_rows_store",
    "_sector_workbench_store",
    "_auction_review_store",
    "_auction_snapshot_store",
    "_sector_replica_live_provider",
    "_plate_rotation_reference_provider",
    "_market_overview_provider",
    "_ifind_provider",
    "_chanlun_symbol_search_service",
    "_chanlun_paper_order_service",
    "_chanlun_paper_order_store",
    "_chanlun_alert_service",
    "_chanlun_alert_store",
    "_chanlun_shadow_scheduler",
    "_chanlun_research_service",
    "_chanlun_research_store",
    "_chanlun_analysis_service",
    "_chanlun_minute_store",
    "_chanlun_history_provider",
    "_tdx_provider",
    "_heatmap_provider",
    "_concept_provider",
    "_news_risk_provider",
    "_valuation_quote_provider",
    "_etf_price_history_service",
    "_etf_three_factor_monitor",
    "_etf_excess_flow_service",
    "_capital_signal_service",
    "_quote_provider",
    "_chanlun_daily_provider",
    "_market_sentiment_analysis_sampler",
    "_market_sentiment_analysis_service",
    "_market_sentiment_analysis_store",
    "_market_sentiment_percentile_service",
    "_market_sentiment_percentile_store",
    "_daily_kline_provider",
    "_kline_provider",
    "_candidate_provider",
    "_auction_top3_live_confirmation_store",
    "_auction_model_result_store",
    "_auction_model_service",
    "_send_sentiment_monitor_notification",
    "_recent_screen_trade_dates",
    "_start_gsgf_weekly_calibration",
    "_run_gsgf_daily_review",
    "_watchlist_snapshot",
    "_chanlun_rc8_client",
    "_chanlun_research_catalog",
    "_chanlun_adapter",
    "_latest_completed_market_sentiment_trade_date",
    "_generate_latest_market_sentiment_analysis",
    "_build_and_persist_sentiment_snapshots",
    "_CHANLUN_RESEARCH_LOCK",
    "_gsgf_model_health",
    "_generate_market_sentiment_analysis",
    "_provider_cache_key",
    "_should_persist_market_emotion_sample",
    "_cached_market_overview",
    "_cached_short_term_sentiment",
    "_MARKET_EMOTION_HISTORY_WRITE_LOCK",
    "_build_market_sentiment_analysis_input",
    "_percentile_point_for_trade_date",
    "_latest_market_emotion_sampled_at",
    "_MARKET_EMOTION_SAMPLE_INTERVAL",
    "_load_sentiment_validation",
    "_optional_sentiment_analysis_context",
]
