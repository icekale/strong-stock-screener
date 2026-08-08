"""应用生命周期：启动/停止采样器与后台服务（自 app.main 拆分）。"""

# ruff: noqa: F401,F403,F405
from __future__ import annotations

from contextlib import asynccontextmanager

from app.compat import *

from app.services.gsgf_auto_review import GsgfAutoReviewConfig
from app.services.runtime_settings import AuctionTop3TrainingSettings, load_runtime_settings
from app.services.sentiment_monitor import SentimentMonitorConfig
from app.services.auction_sampler import AuctionSnapshotSampler
from app.services.capital_signal_sampler import CapitalSignalSampler
from app.services.etf_three_factor_sampler import EtfThreeFactorSampler
from app.services.gsgf_auto_review import GsgfAutoReviewService
from app.services.market_sentiment_analysis_sampler import MarketSentimentAnalysisSampler
from app.services.sector_workbench_sampler import SectorWorkbenchSampler
from app.services.sentiment_monitor import SentimentMonitor


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        startup_sentiment_monitor()
        startup_gsgf_auto_review()
        startup_auction_sampler()
        startup_sector_workbench_sampler()
        startup_capital_signal_sampler()
        startup_etf_three_factor_sampler()
        startup_market_sentiment_analysis_sampler()
        yield
    finally:
        shutdown_market_sentiment_analysis_sampler()
        shutdown_etf_three_factor_sampler()
        shutdown_capital_signal_sampler()
        shutdown_chanlun_research()
        shutdown_sector_workbench_sampler()
        shutdown_auction_sampler()
        shutdown_gsgf_auto_review()
        shutdown_sentiment_monitor()
        _close_default_data_source_providers()


def startup_sentiment_monitor() -> None:
    if load_runtime_settings(_runtime_config_path()).sentiment_monitor.enabled:
        _sentiment_monitor().start()


def shutdown_sentiment_monitor() -> None:
    monitor = getattr(app_state().state, "sentiment_monitor", None)
    if monitor is not None:
        monitor.stop()


def startup_auction_sampler() -> None:
    if getattr(app_state().state, "auction_sampler_disabled", False):
        return
    sampler = getattr(app_state().state, "auction_sampler", None)
    if sampler is None:
        sampler = AuctionSnapshotSampler(
            refresh=lambda: _refresh_auction_snapshot(100),
            run_top3=_generate_auction_top3_for_date,
            clock=getattr(app_state().state, "auction_sampler_clock", None),
        )
        app_state().state.auction_sampler = sampler
    sampler.start()


def shutdown_auction_sampler() -> None:
    sampler = getattr(app_state().state, "auction_sampler", None)
    if sampler is not None:
        sampler.stop()


def startup_sector_workbench_sampler() -> None:
    if getattr(app_state().state, "sector_workbench_sampler_disabled", False):
        return
    sampler = getattr(app_state().state, "sector_workbench_sampler", None)
    if sampler is None:
        sampler = SectorWorkbenchSampler(refresh=_sample_sector_workbench)
        app_state().state.sector_workbench_sampler = sampler
    sampler.start()


def shutdown_sector_workbench_sampler() -> None:
    sampler = getattr(app_state().state, "sector_workbench_sampler", None)
    if sampler is not None:
        sampler.stop()


def startup_capital_signal_sampler() -> None:
    if getattr(app_state().state, "capital_signal_sampler_disabled", False):
        return
    sampler = getattr(app_state().state, "capital_signal_sampler", None)
    if sampler is None:
        sampler = CapitalSignalSampler(
            refresh=lambda: _capital_signal_service().overview(force=True)
        )
        app_state().state.capital_signal_sampler = sampler
    sampler.start()


def shutdown_capital_signal_sampler() -> None:
    sampler = getattr(app_state().state, "capital_signal_sampler", None)
    if sampler is not None:
        stop_and_wait = getattr(sampler, "stop_and_wait", None)
        if callable(stop_and_wait):
            stop_and_wait()
        else:
            sampler.stop()


def startup_etf_three_factor_sampler() -> None:
    if getattr(app_state().state, "etf_three_factor_sampler_disabled", False):
        return
    sampler = getattr(app_state().state, "etf_three_factor_sampler", None)
    if sampler is None:
        sampler = EtfThreeFactorSampler(
            scan=_etf_three_factor_monitor().scan,
            clock=getattr(app_state().state, "etf_three_factor_sampler_clock", None),
        )
        app_state().state.etf_three_factor_sampler = sampler
    sampler.start()


def shutdown_etf_three_factor_sampler() -> None:
    sampler = getattr(app_state().state, "etf_three_factor_sampler", None)
    if sampler is not None:
        stop_and_wait = getattr(sampler, "stop_and_wait", None)
        if callable(stop_and_wait):
            stop_and_wait()
        else:
            sampler.stop()


def startup_market_sentiment_analysis_sampler() -> None:
    _market_sentiment_analysis_sampler().start()


def shutdown_market_sentiment_analysis_sampler() -> None:
    sampler = getattr(app_state().state, "market_sentiment_analysis_sampler", None)
    if sampler is not None:
        stop_and_wait = getattr(sampler, "stop_and_wait", None)
        if callable(stop_and_wait):
            stop_and_wait()
        else:
            sampler.stop()


def startup_gsgf_auto_review() -> None:
    _gsgf_auto_review_service().start()


def shutdown_gsgf_auto_review() -> None:
    service = getattr(app_state().state, "gsgf_auto_review_service", None)
    if service is not None:
        service.stop()


def shutdown_chanlun_research() -> None:
    with _CHANLUN_RESEARCH_LOCK:
        client = getattr(app_state().state, "chanlun_rc8_client", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        for attribute in (
            "chanlun_research_service",
            "chanlun_rc8_client",
            "chanlun_shadow_scheduler",
        ):
            if hasattr(app_state().state, attribute):
                delattr(app_state().state, attribute)


def _clear_data_source_caches() -> None:
    CACHE_REGISTRY.clear()
    _close_default_data_source_providers()
    for attribute in (
        "default_capital_signal_service",
        "default_etf_excess_flow_service",
        "default_etf_three_factor_monitor",
        "market_sentiment_percentile_service",
        "default_market_overview_provider",
        "default_market_overview_provider_key",
    ):
        if hasattr(app_state().state, attribute):
            delattr(app_state().state, attribute)
    with _CHANLUN_RESEARCH_LOCK:
        shutdown_chanlun_research()
        if hasattr(app_state().state, "chanlun_analysis_service"):
            delattr(app_state().state, "chanlun_analysis_service")
        if hasattr(app_state().state, "chanlun_paper_order_service"):
            delattr(app_state().state, "chanlun_paper_order_service")


def _sample_sector_workbench() -> None:
    _refresh_sector_theme_rows()
    for mode in ("strength", "main_flow"):
        from app.routers.sectors import get_sector_workbench
        get_sector_workbench(
            mode=mode,
            scope="auto",
            selected="",
            limit=30,
            stock_limit=80,
        )

