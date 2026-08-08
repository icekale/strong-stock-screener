"""sectors 域路由（自 app.main 拆分）。"""

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

@router.get("/api/sectors/radar")
def get_sector_radar(limit: int = 20) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 50))
    result = _cached_sector_radar(bounded_limit)
    return result.model_dump(mode="json")


@router.get("/api/sectors/plate-reference")
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


@router.get("/api/sectors/workbench")
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
            theme_source=theme_status.source
            if theme_status is not None
            else "通达信MCP涨停概念映射",
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
        item.source == "题材快照" and item.status == "stale" for item in result.source_status
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


@router.get("/api/sectors/replica/radar", response_model=SectorReplicaRadarResponse)
def get_sector_replica_radar(
    mode: SectorReplicaMode = "strength",
    selected: str = "",
    limit: int = 20,
    stock_limit: int = 50,
) -> SectorReplicaRadarResponse:
    selected_codes = [part.strip() for part in selected.split(",") if part.strip()]
    sampled_at = _sector_now()
    try:
        live_response = _sector_replica_live_provider().get_radar(
            mode=mode,
            selected_codes=selected_codes,
            limit=limit,
            trade_date=sampled_at.date().isoformat(),
            generated_at=sampled_at.isoformat(timespec="seconds"),
        )
        if live_response.plates and live_response.series:
            return live_response
    except Exception as exc:
        live_status = StrongStockSourceStatus(
            source="短线侠 qxlive",
            status="failed",
            detail=f"真实板块曲线读取失败，已回退本地工作台: {exc.__class__.__name__}",
        )
    else:
        live_status = StrongStockSourceStatus(
            source="短线侠 qxlive",
            status="stale",
            detail="真实板块曲线为空，已回退本地工作台",
        )
    workbench = SectorWorkbenchResponse.model_validate(
        get_sector_workbench(
            mode=mode,
            scope="auto",
            selected="",
            limit=limit,
            stock_limit=stock_limit,
        )
    )
    selected_names = replica_theme_names_for_codes(workbench.themes, selected_codes=selected_codes)
    if selected_names:
        workbench = SectorWorkbenchResponse.model_validate(
            get_sector_workbench(
                mode=mode,
                scope="auto",
                selected=",".join(selected_names),
                limit=limit,
                stock_limit=stock_limit,
            )
        )
    missing_series = missing_replica_series_names(workbench, selected_names)
    if missing_series:
        _schedule_sector_intraday_refresh(
            workbench.model_copy(update={"selected_themes": selected_names}, deep=True)
        )
        workbench.source_status.append(
            StrongStockSourceStatus(
                source="TickFlow 当日分钟线",
                status="stale",
                detail=f"replica 缺少 {len(missing_series)} 条选中板块曲线，已触发后台补齐",
            )
        )
    fallback_response = build_sector_radar_replica_response(
        workbench=workbench,
        mode=mode,
        selected_codes=selected_codes,
        sampled_at=sampled_at,
    )
    fallback_response.source_status.insert(0, live_status)
    return fallback_response


@router.get(
    "/api/sectors/replica/boards/{board_code:path}/stocks",
    response_model=SectorReplicaStocksResponse,
)
def get_sector_replica_board_stocks(
    board_code: str,
    mode: SectorReplicaMode = "strength",
    board_name: str | None = None,
    sub_theme: str | None = None,
    limit: int = 50,
) -> SectorReplicaStocksResponse:
    bounded_limit = max(1, min(limit, 200))
    normalized_board_code = board_code.replace("theme:", "").strip()
    live_status: StrongStockSourceStatus | None = None
    related_tags: list[str] = []
    if normalized_board_code.isdigit():
        provider = _sector_replica_live_provider()
        try:
            subplates = provider.get_board_subplates(board_code=normalized_board_code)
        except Exception:
            subplates = []
        related_tags = [name for _code, name in subplates]
        stock_board_code = normalized_board_code
        if sub_theme:
            stock_board_code = next(
                (code for code, name in subplates if name == sub_theme),
                "",
            )
        if not stock_board_code:
            live_status = StrongStockSourceStatus(
                source="短线侠 qxlive 成分股",
                status="stale",
                detail=f"未找到子题材 {sub_theme} 的真实板块代码，已回退本地工作台",
            )
        else:
            try:
                rows = provider.get_board_stocks(
                    board_code=stock_board_code,
                    limit=bounded_limit,
                )
            except Exception as exc:
                live_status = StrongStockSourceStatus(
                    source="短线侠 qxlive 成分股",
                    status="failed",
                    detail=f"真实开盘啦板块成分股读取失败，已回退本地工作台: {exc.__class__.__name__}",
                )
            else:
                if rows:
                    rows, industry_status = _enrich_sector_replica_stock_rows(
                        rows,
                        board_name=board_name,
                    )
                    source_status = [
                        StrongStockSourceStatus(
                            source="短线侠 qxlive 成分股",
                            status="success",
                            detail=f"读取真实开盘啦板块成分股 {len(rows)} 条",
                        )
                    ]
                    if industry_status is not None:
                        source_status.append(industry_status)
                    return SectorReplicaStocksResponse(
                        board_code=board_code,
                        sub_theme=sub_theme,
                        rows=rows,
                        related_tags=related_tags,
                        source_status=source_status,
                        generated_at=_sector_now().isoformat(timespec="seconds"),
                    )
                live_status = StrongStockSourceStatus(
                    source="短线侠 qxlive 成分股",
                    status="stale",
                    detail="真实开盘啦板块成分股为空，已回退本地工作台",
                )
    fallback_board_name = (board_name or "").strip() or None
    workbench = SectorWorkbenchResponse.model_validate(
        get_sector_workbench(
            mode=mode,
            scope="auto",
            selected=fallback_board_name or "",
            limit=50,
            stock_limit=bounded_limit,
        )
    )
    rows = build_sector_replica_stock_rows(
        workbench,
        board_code=board_code,
        board_name=fallback_board_name,
        sub_theme=sub_theme,
    )[:bounded_limit]
    source_status = list(workbench.source_status)
    if live_status is not None:
        source_status.insert(0, live_status)
    return SectorReplicaStocksResponse(
        board_code=board_code,
        sub_theme=sub_theme,
        rows=rows,
        related_tags=related_tags or workbench.related_tags,
        source_status=source_status,
        generated_at=_sector_now().isoformat(timespec="seconds"),
    )


@router.get("/api/sectors/replica/status")
def get_sector_replica_status(trade_date: str | None = None) -> dict[str, object]:
    status = get_sector_workbench_status(trade_date=trade_date)
    return {
        **status,
        "calibration_profile_version": "sector-replica-v1",
        "chart_refresh_seconds": 15,
        "stock_refresh_seconds": 8,
    }


@router.get("/api/sectors/workbench/status")
def get_sector_workbench_status(trade_date: str | None = None) -> dict[str, object]:
    current = _sector_now()
    date_text = (trade_date or current.date().isoformat()).strip()
    sample_window_open = is_sector_workbench_sample_window(current)
    sampler_disabled = bool(getattr(app_state().state, "sector_workbench_sampler_disabled", False))
    sampler = getattr(app_state().state, "sector_workbench_sampler", None)
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

