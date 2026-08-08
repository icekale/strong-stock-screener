"""跨域共用的业务辅助函数（自 app.main 拆分）。

只包含纯辅助逻辑；不定义路由、不持有 app 生命周期。
依赖 app.deps（装配层）与 app.models。
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from threading import Thread
from time import perf_counter
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request

from app.config import get_settings
import app.deps as deps
from app.deps import (
    app_state,
    AUCTION_SNAPSHOT_CACHE,
    CAPITAL_SUMMARY_CACHE,
    MARKET_RANKINGS_CACHE,
    SECTOR_INTRADAY_CACHE,
    SECTOR_RADAR_CACHE,
    SECTOR_THEME_ROWS_CACHE,
    STOCK_KLINE_CACHE,
    STOCK_RESEARCH_CACHE,
    SECTOR_STOCK_INDUSTRY_TIMEOUT_SECONDS,
    _WATCHLIST_GSGF_MAX_SYMBOLS,
    logger,
)
from app.gsgf_rules import analyze_gsgf, build_gsgf_chart_annotations
from app.models import (
    AuctionModelTop3Response,
    AuctionReviewOutcome,
    AuctionReviewRecord,
    AuctionReviewSummary,
    AuctionSnapshotResponse,
    CapitalSummaryResponse,
    ChanlunPeriod,
    GsgfAnalysis,
    HealthProbe,
    IntradaySnapshotRequest,
    KlineBar,
    MarketOverviewResponse,
    MarketRankingsResponse,
    MarketSectorStrengthItem,
    ModelMaintenancePacket,
    ScreenRunRequest,
    SectorRadarItem,
    SectorRadarResponse,
    SectorWorkbenchResponse,
    SectorWorkbenchSeries,
    SectorReplicaStockRow,
    SentimentPercentilePoint,
    SentimentPercentileResponse,
    StockKlinePeriod,
    StockKlineResponse,
    StockResearchResponse,
    StrongStockDataUnavailable,
    StrongStockScreeningResult,
    StrongStockSourceStatus,
)
from app.providers.watchlist import WatchlistItem, parse_watchlist_text
from app.services.auction import build_auction_snapshot
from app.services.auction_review import build_auction_rule_buckets, score_auction_record
from app.services.auction_top3_training import build_signal_samples_from_top3
from app.services.sentiment_monitor import SentimentMonitorConfig
from app.services.background_jobs import CancelCheck, ProgressCallback
from app.services.chanlun.bars import SHANGHAI, aggregate_closed_intraday_bars
from app.services.chanlun.screening import CachedChanlunScreeningSummarizer
from app.services.market_sentiment_analysis import sentiment_analysis_record_is_reusable
from app.services.market_sentiment_analysis_sampler import is_generation_due
from app.services.model_maintenance_packet import build_model_maintenance_packet
from app.services.runtime_settings import (
    SettingsUpdate,
    load_runtime_settings,
    save_runtime_settings,
)
from app.services.screener import StrongStockScreener
from app.services.sector_workbench import build_limit_up_theme_rows_from_candidates
from app.services.sector_workbench_intraday import build_sector_intraday_series

# ---------------------------------------------------------------------------
# 情绪分析 catchup 状态（历史遗留，供 helpers 内共享）
# ---------------------------------------------------------------------------

from threading import RLock
_MARKET_SENTIMENT_ANALYSIS_CATCHUP_LOCK = RLock()
_MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES: set[str] = set()



def _chanlun_research_health() -> dict[str, object]:
    try:
        payload = dict(_chanlun_research_service().health())
    except Exception as exc:
        payload = {
            "status": "unavailable",
            "queue_depth": 0,
            "circuit_state": "unavailable",
            "engine_version": None,
            "inflight_count": 0,
            "error": _sanitized_health_error(exc),
        }
    if payload.get("status") not in {"ready", "unavailable", "disabled"}:
        payload["status"] = "unavailable"
    payload.setdefault("queue_depth", 0)
    payload.setdefault("circuit_state", "unknown")
    payload.setdefault("engine_version", None)
    payload.setdefault("inflight_count", 0)
    if payload.get("error") is not None:
        payload["error"] = _sanitized_health_error(payload["error"])
    else:
        payload["error"] = None
    return payload


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
        chanlun_summarizer=_chanlun_screening_summarizer(),
        chanlun_v2_scheduler=_chanlun_shadow_scheduler(),
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
    if auto_review_config.auto_snapshot_enabled and any(
        item.gsgf is not None for item in result.items
    ):
        _gsgf_review_store().persist_snapshot(result, dedupe=True)
    if progress is not None:
        progress(4, 4, "筛选完成")
    return result


def _build_and_save_model_maintenance_packet(packet_base_url: str | None) -> ModelMaintenancePacket:
    latest_screen_run = _run_store().load_latest()
    source_status = latest_screen_run.source_status if latest_screen_run is not None else []
    trade_date = latest_screen_run.trade_date if latest_screen_run is not None else None
    settings = _effective_settings().auction_top3_training
    auction_top3_run = _auction_model_result_store().load_top3(trade_date) if trade_date else None
    training_summary = _auction_top3_training_store().training_summary(
        training_window_days=settings.training_window_days,
        include_manual_training=settings.include_manual_trade_samples_in_training,
        enabled=settings.record_signal_samples,
        initial_capital=settings.simulated_initial_capital,
    )
    packet = build_model_maintenance_packet(
        trade_date=trade_date,
        latest_screen_run=latest_screen_run,
        review_summary=_gsgf_review_store().load_latest_summary(),
        calibration_summary=_background_job_store().load_latest_calibration(),
        source_status=source_status,
        auction_top3_run=auction_top3_run,
        auction_top3_training_summary=training_summary,
        packet_base_url=packet_base_url,
    )
    return _model_maintenance_store().save_packet(packet)


def _generate_auction_top3_for_date(trade_date: str) -> AuctionModelTop3Response:
    datetime.strptime(trade_date, "%Y-%m-%d")
    result: AuctionModelTop3Response = _auction_model_service().predict_top3(trade_date)
    _auction_model_result_store().save_top3(result)
    if _effective_settings().auction_top3_training.record_signal_samples:
        _auction_top3_training_store().upsert_signal_samples(build_signal_samples_from_top3(result))
    return result


def _run_auction_model_top3_generation_job(
    trade_date: str,
    progress: ProgressCallback,
    should_cancel: CancelCheck,
) -> dict[str, object]:
    if should_cancel():
        raise RuntimeError("竞价模型Top3生成已取消")
    progress(1, 3, "读取候选池和K线")
    result = _generate_auction_top3_for_date(trade_date)
    progress(3, 3, "竞价模型Top3生成完成")
    return {
        "trade_date": result.trade_date,
        "run_id": result.run_id,
        "cache_status": result.cache_status,
    }


def _enrich_sector_replica_stock_rows(
    rows: list[SectorReplicaStockRow],
    *,
    board_name: str | None,
) -> tuple[list[SectorReplicaStockRow], StrongStockSourceStatus | None]:
    missing_symbols = list(dict.fromkeys(row.symbol for row in rows if not row.industry))
    industry_by_symbol: dict[str, str] = {}
    industry_status: StrongStockSourceStatus | None = None
    if missing_symbols:
        provider = _market_overview_provider()
        if not hasattr(provider, "get_stock_industries_fast") and not hasattr(
            provider, "get_stock_industries"
        ):
            industry_status = StrongStockSourceStatus(
                source="成分股行业补充",
                status="disabled",
                detail=f"{len(missing_symbols)} 只成分股缺少行业，当前数据源不支持补充",
            )
        else:
            try:
                if hasattr(provider, "get_stock_industries_fast"):
                    raw_industries = provider.get_stock_industries_fast(
                        missing_symbols,
                        timeout_seconds=SECTOR_STOCK_INDUSTRY_TIMEOUT_SECONDS,
                    )
                else:
                    raw_industries = provider.get_stock_industries(missing_symbols)
                industry_by_symbol = {
                    str(symbol).strip().upper(): str(industry).strip()
                    for symbol, industry in raw_industries.items()
                    if str(symbol).strip() and str(industry).strip()
                }
            except Exception as exc:
                industry_status = StrongStockSourceStatus(
                    source="成分股行业补充",
                    status="failed",
                    detail=f"{len(missing_symbols)} 只成分股行业补充失败: {exc.__class__.__name__}",
                )

    normalized_board_name = (board_name or "").strip()
    enriched_rows = [
        row.model_copy(
            update={
                "industry": row.industry or industry_by_symbol.get(row.symbol.strip().upper()),
                "themes": row.themes or ([normalized_board_name] if normalized_board_name else []),
            }
        )
        for row in rows
    ]
    if missing_symbols and industry_status is None:
        missing_symbol_set = {symbol.strip().upper() for symbol in missing_symbols}
        enriched_count = sum(
            1
            for row in enriched_rows
            if row.symbol.strip().upper() in missing_symbol_set and row.industry
        )
        industry_status = StrongStockSourceStatus(
            source="成分股行业补充",
            status="success" if enriched_count == len(missing_symbols) else "stale",
            detail=f"补齐 {enriched_count}/{len(missing_symbols)} 只成分股行业",
        )
    return enriched_rows, industry_status


def _build_watchlist_gsgf_status(items: list) -> dict[str, object]:
    bounded_items = items[: _WATCHLIST_GSGF_MAX_SYMBOLS]
    output: list[dict[str, object]] = []
    provider = _kline_provider()
    for item in bounded_items:
        try:
            bars = provider.get_klines(item.symbol, count=220)
            gsgf = analyze_gsgf(bars)
        except Exception as exc:
            gsgf = GsgfAnalysis(
                risk_flags=[f"K线获取失败: {exc.__class__.__name__}"],
                explanation=["自选股结构触发暂不可计算"],
            )
        output.append({**item.model_dump(mode="json"), "gsgf": gsgf.model_dump(mode="json")})
    if len(items) > len(bounded_items):
        output.append(
            {
                "symbol": "",
                "name": f"自选池过大，仅展示前 {len(bounded_items)} 只",
                "gsgf": GsgfAnalysis(
                    risk_flags=["truncated"],
                    explanation=["单次扫描条数受限，请分批"],
                ).model_dump(mode="json"),
            }
        )
    return {"items": output}


def _cached_capital_summary() -> CapitalSummaryResponse:
    service = _capital_signal_service()
    cache_key = f"capital-summary:{_provider_cache_key(service)}"
    return CAPITAL_SUMMARY_CACHE.get_or_refresh(
        cache_key, service.homepage_summary
    ).model_copy(deep=True)


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
            now=getattr(app_state().state, "auction_now", None),
            hot_themes=hot_themes,
        ),
    ).model_copy(deep=True)
    _append_empty_hot_theme_status(result, hot_themes, hot_theme_status)
    saved = _auction_snapshot_store().save(result, captured_at=_auction_now())
    return _backfill_auction_snapshot_industries(saved)


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
    saved = _auction_snapshot_store().save(result, captured_at=now)
    return _backfill_auction_snapshot_industries(saved)


def _backfill_auction_snapshot_industries(
    snapshot: AuctionSnapshotResponse,
) -> AuctionSnapshotResponse:
    missing_symbols = [item.symbol for item in snapshot.items if item.symbol and not item.industry]
    if not missing_symbols:
        return snapshot
    provider = _market_overview_provider()
    if not hasattr(provider, "get_stock_industries"):
        return snapshot
    try:
        industry_by_symbol = provider.get_stock_industries(missing_symbols)
    except Exception:
        return snapshot
    if not industry_by_symbol:
        return snapshot

    _auction_snapshot_store().backfill_industries(industry_by_symbol)
    items = [
        item.model_copy(update={"industry": industry_by_symbol[item.symbol]})
        if not item.industry and industry_by_symbol.get(item.symbol)
        else item
        for item in snapshot.items
    ]
    patched = sum(
        1 for before, after in zip(snapshot.items, items) if not before.industry and after.industry
    )
    if not patched:
        return snapshot
    return snapshot.model_copy(
        deep=True,
        update={
            "items": items,
            "source_status": [
                *snapshot.source_status,
                StrongStockSourceStatus(
                    source="竞价行业补充",
                    status="success",
                    detail=f"补齐 {patched}/{len(missing_symbols)} 只竞价股票行业",
                ),
            ],
        },
    )


def _auction_hot_theme_refs() -> tuple[
    list[tuple[str, int, float]], StrongStockSourceStatus | None
]:
    try:
        reference = _plate_rotation_reference_provider().get_today_themes(
            limit=10, source="kaipan", days=20
        )
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
    return getattr(app_state().state, "auction_now", None) or datetime.now(ZoneInfo("Asia/Shanghai"))


def _sector_now() -> datetime:
    return getattr(app_state().state, "sector_now", None) or datetime.now(ZoneInfo("Asia/Shanghai"))




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

    return SECTOR_RADAR_CACHE.get_or_refresh(cache_key, build).model_copy(deep=True)


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
            reason = (
                f"{exc.__class__.__name__}: {str(exc).strip()}"
                if str(exc).strip()
                else exc.__class__.__name__
            )
            return [], StrongStockSourceStatus(
                source="TickFlow 当日分钟线",
                status="failed",
                detail=f"历史分时曲线补齐失败: {reason[:180]}",
            )

    series, status = SECTOR_INTRADAY_CACHE.get_or_refresh(cache_key, build)
    return [item.model_copy(deep=True) for item in series], status.model_copy(deep=True)


def _cached_sector_intraday_status(
    result: SectorWorkbenchResponse,
) -> StrongStockSourceStatus | None:
    cached = SECTOR_INTRADAY_CACHE.get_if_fresh(
        _sector_intraday_cache_key(result, _quote_provider())
    )
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
    if getattr(app_state().state, "sector_intraday_async_refresh_disabled", False):
        return
    key = _sector_intraday_refresh_key(result)
    refreshing = getattr(app_state().state, "sector_intraday_refreshing", None)
    if refreshing is None:
        refreshing = set()
        app_state().state.sector_intraday_refreshing = refreshing
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
            current = getattr(app_state().state, "sector_intraday_refreshing", set())
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
        avg_change = sum(
            item.pct_change or 0 for item in members if item.pct_change is not None
        ) / max(1, sum(1 for item in members if item.pct_change is not None))
        strength_score = round(
            avg_change * 10
            + advance_count * 3
            - decline_count * 2
            + min(turnover_cny / 1_000_000_000, 20),
            2,
        )
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


def _cached_stock_kline(
    symbol: str,
    count: int,
    period: StockKlinePeriod = "1d",
) -> StockKlineResponse:
    provider = _kline_provider() if period == "1d" else _quote_provider()
    normalized_symbol = symbol.strip().upper()
    cache_key = (
        f"stock-kline:{_provider_cache_key(provider)}:{normalized_symbol}:{period}:{count}"
    )

    def build() -> StockKlineResponse:
        if period == "1d":
            bars = provider.get_klines(normalized_symbol, count=count)[-count:]
            source_status = StrongStockSourceStatus(
                source=getattr(provider, "source_name", "K线源"),
                status="success",
                detail=f"period=1d，返回 {len(bars)} 条日K",
            )
            annotations = build_gsgf_chart_annotations(bars)
        else:
            fetch_count = min(2400, max(120, count * {"5m": 5, "30m": 30, "60m": 60}[period]))
            raw_bars = provider.get_intraday_bars(
                [normalized_symbol],
                period="1m",
                count=fetch_count,
            ).get(normalized_symbol, [])
            bars = aggregate_closed_intraday_bars(
                raw_bars,
                period=period,
                now=datetime.now(tz=SHANGHAI),
            )[-count:]
            period_label = {"5m": "5分钟", "30m": "30分钟", "60m": "60分钟"}[period]
            source_status = StrongStockSourceStatus(
                source=f"{getattr(provider, 'source_name', '分钟线源')} {period_label}K",
                status="success",
                detail=(
                    f"period={period}，返回 {len(bars)} 条已闭合{period_label}K"
                    "（原始1分钟线聚合）"
                ),
            )
            annotations = []
        return StockKlineResponse(
            symbol=normalized_symbol,
            period=period,
            source_status=source_status,
            bars=bars,
            gsgf_annotations=annotations,
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


def _quote_valuation_for_symbol(
    symbol: str,
) -> tuple[object | None, StrongStockSourceStatus | None]:
    valuation_provider = _valuation_quote_provider()
    source_name = getattr(valuation_provider, "source_name", "估值行情")
    try:
        quotes = valuation_provider.get_quotes([symbol])
    except StrongStockDataUnavailable as exc:
        return None, StrongStockSourceStatus(source=source_name, status="failed", detail=str(exc))
    except Exception as exc:
        return None, StrongStockSourceStatus(
            source=source_name,
            status="failed",
            detail=f"估值行情获取失败: {exc.__class__.__name__}",
        )
    matched = next((quote for quote in quotes if getattr(quote, "symbol", "") == symbol), None)
    if matched is None:
        return None, StrongStockSourceStatus(
            source=source_name, status="failed", detail="估值行情未返回当前股票"
        )
    status = (
        valuation_provider.status()
        if hasattr(valuation_provider, "status")
        else StrongStockSourceStatus(
            source=source_name, status="success", detail="估值行情源已配置"
        )
    )
    return matched, status




def _system_jobs() -> list[dict[str, object]]:
    auction_sampler = getattr(app_state().state, "auction_sampler", None)
    sector_sampler = getattr(app_state().state, "sector_workbench_sampler", None)
    sentiment_monitor = getattr(app_state().state, "sentiment_monitor", None)
    gsgf_service = getattr(app_state().state, "gsgf_auto_review_service", None)
    runtime = load_runtime_settings(_runtime_config_path())
    auction_running, auction_detail = _auction_sampler_running_status(
        auction_sampler, "竞价时段采样器"
    )
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
            "enabled": not getattr(app_state().state, "auction_sampler_disabled", False),
            "detail": auction_detail,
        },
        {
            "name": "sector_workbench_sampler",
            "running": sector_running,
            "enabled": not getattr(app_state().state, "sector_workbench_sampler_disabled", False),
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


def _auction_sampler_running_status(worker: object | None, detail: str) -> tuple[bool, str]:
    running, base_detail = _thread_running_status(worker, detail)
    if worker is None:
        return running, base_detail
    try:
        status = getattr(worker, "top3_status", None)
        if not callable(status):
            return running, base_detail
        top3_status = status()
    except Exception:
        return running, base_detail
    status_text = str(top3_status.get("status") or "")
    trade_date = top3_status.get("last_trade_date")
    last_error = top3_status.get("last_error")
    if status_text == "generated" and trade_date:
        return running, f"{base_detail}（Top3已生成 {trade_date}）"
    if status_text == "running" and trade_date:
        return running, f"{base_detail}（Top3生成中 {trade_date}）"
    if status_text == "failed" and trade_date:
        suffix = f"Top3失败 {trade_date}"
        if last_error:
            suffix = f"{suffix}: {last_error}"
        return running, f"{base_detail}（{suffix}）"
    return running, base_detail


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


def _market_sentiment_analysis_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def _persisted_percentile_point_for_trade_date(
    trade_date: str,
) -> tuple[SentimentPercentileResponse, SentimentPercentilePoint]:
    percentile = _market_sentiment_percentile_store().load()
    if percentile is None:
        raise HTTPException(status_code=404, detail="该日期不在市场情绪分位历史中")
    point = next(
        (item for item in percentile.history if item.trade_date == trade_date),
        None,
    )
    if point is None:
        raise HTTPException(status_code=404, detail="该日期不在市场情绪分位历史中")
    return percentile, point


def _schedule_market_sentiment_analysis_catchup(
    percentile: SentimentPercentileResponse,
) -> None:
    selected = percentile.selected
    if selected is None or selected.trade_date != percentile.latest_complete_trade_date:
        return
    config = _effective_settings().ai_analysis
    if not config.enabled or not config.api_key:
        return
    now = _market_sentiment_analysis_now()
    if not is_generation_due(now, selected.trade_date):
        return
    input_payload = _build_market_sentiment_analysis_input(
        selected.trade_date,
        percentile,
        selected,
        refresh_missing=False,
    )
    try:
        existing = _market_sentiment_analysis_store().load(selected.trade_date)
        if sentiment_analysis_record_is_reusable(existing, input_payload, config):
            return
    except Exception:
        return

    with _MARKET_SENTIMENT_ANALYSIS_CATCHUP_LOCK:
        if selected.trade_date in _MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES:
            return
        _MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES.add(selected.trade_date)

    def run() -> None:
        try:
            _generate_market_sentiment_analysis(
                selected.trade_date,
                percentile_response=percentile,
            )
        except Exception:
            logger.exception("market sentiment analysis catch-up failed")
        finally:
            with _MARKET_SENTIMENT_ANALYSIS_CATCHUP_LOCK:
                _MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES.discard(selected.trade_date)

    try:
        Thread(
            target=run,
            name="market-sentiment-analysis-catchup",
            daemon=True,
        ).start()
    except Exception:
        with _MARKET_SENTIMENT_ANALYSIS_CATCHUP_LOCK:
            _MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES.discard(selected.trade_date)
        raise


def _chanlun_screening_summarizer() -> CachedChanlunScreeningSummarizer | None:
    if hasattr(app_state().state, "chanlun_screening_summarizer"):
        return app_state().state.chanlun_screening_summarizer
    summarizer = CachedChanlunScreeningSummarizer(
        store=_chanlun_minute_store(),
        adapter=_chanlun_adapter(),
        cache_seconds=get_settings().chanlun_cache_seconds,
    )
    app_state().state.chanlun_screening_summarizer = summarizer
    return summarizer


def _validate_chanlun_lookback(period: ChanlunPeriod, lookback: int) -> None:
    maximum = 260 if period == "1d" else 2400
    if lookback < 20 or lookback > maximum:
        raise HTTPException(
            status_code=422,
            detail=f"lookback for {period} must be between 20 and {maximum}",
        )


def _parse_chanlun_backtest_horizons(value: str) -> list[int]:
    try:
        horizons = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="horizons must be comma-separated integers"
        ) from exc
    if (
        not horizons
        or len(horizons) > 8
        or any(horizon < 1 or horizon > 60 for horizon in horizons)
    ):
        raise HTTPException(
            status_code=422, detail="horizons must contain up to 8 integers from 1 to 60"
        )
    return horizons


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


def _sector_theme_rows() -> tuple[list[dict[str, object]], StrongStockSourceStatus | None]:
    trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
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
    if getattr(app_state().state, "sector_theme_rows_async_refresh_disabled", False):
        return
    refreshing = getattr(app_state().state, "sector_theme_rows_refreshing", None)
    if refreshing is None:
        refreshing = set()
        app_state().state.sector_theme_rows_refreshing = refreshing
    if trade_date in refreshing:
        return
    refreshing.add(trade_date)

    def run() -> None:
        try:
            _refresh_sector_theme_rows(trade_date=trade_date)
        finally:
            current = getattr(app_state().state, "sector_theme_rows_refreshing", set())
            current.discard(trade_date)

    Thread(target=run, name=f"sector-theme-rows-refresh-{trade_date}", daemon=True).start()


def _refresh_sector_theme_rows(
    trade_date: str | None = None,
) -> tuple[list[dict[str, object]], StrongStockSourceStatus | None]:
    current_trade_date = trade_date or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
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
        provider = getattr(app_state().state, "tdx_provider", None) or _tdx_provider()
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
        data_incomplete_count=sum(
            1 for record in records if record.review_status == "data_incomplete"
        ),
        records=records,
        buckets=build_auction_rule_buckets(records),
    )


def _auction_review_minute_bars(
    intraday_bars: list[object],
    trade_date: str,
) -> list[KlineBar]:
    """把 1 分钟原始线转换为竞价复盘可消费的 KlineBar（date 为 "YYYY-MM-DD HH:MM"）。"""
    output: list[KlineBar] = []
    for bar in intraday_bars:
        timestamp = getattr(bar, "timestamp", None)
        if not isinstance(timestamp, int):
            continue
        try:
            moment = datetime.fromtimestamp(timestamp / 1000, tz=SHANGHAI)
        except (OverflowError, OSError, ValueError):
            continue
        if moment.date().isoformat() != trade_date:
            continue
        output.append(
            KlineBar(
                date=moment.strftime("%Y-%m-%d %H:%M"),
                open=float(getattr(bar, "open", 0)),
                high=float(getattr(bar, "high", 0)),
                low=float(getattr(bar, "low", 0)),
                close=float(getattr(bar, "close", 0)),
                volume=float(getattr(bar, "volume", 0) or 0),
                amount=float(getattr(bar, "amount", 0) or 0),
            )
        )
    return output


def _fill_auction_review_close_from_quotes(
    records: list[AuctionReviewRecord],
    trade_date: str,
) -> list[AuctionReviewRecord]:
    missing_symbols = sorted(
        {record.symbol for record in records if record.day_result.close_pct is None}
    )
    if not missing_symbols:
        return records
    provider = _quote_provider()
    if not hasattr(provider, "get_quotes"):
        return records

    quotes_by_symbol: dict[str, object] = {}
    quote_batch_size = 50
    for start in range(0, len(missing_symbols), quote_batch_size):
        batch = missing_symbols[start : start + quote_batch_size]
        try:
            quotes = provider.get_quotes(batch)
        except StrongStockDataUnavailable:
            continue
        quotes_by_symbol.update({quote.symbol: quote for quote in quotes})

    if not quotes_by_symbol:
        return records
    return [
        _fill_auction_review_record_close_from_quote(
            record, quotes_by_symbol.get(record.symbol), trade_date
        )
        for record in records
    ]


def _fill_auction_review_record_close_from_quote(
    record: AuctionReviewRecord,
    quote: object | None,
    trade_date: str,
) -> AuctionReviewRecord:
    if record.day_result.close_pct is not None or quote is None:
        return record
    day_result = _auction_review_quote_day_outcome(quote, trade_date)
    if day_result is None:
        return record
    updated = record.model_copy(
        deep=True,
        update={
            "day_result": day_result,
            "review_status": "day_done",
            "source_status": [
                *record.source_status,
                StrongStockSourceStatus(
                    source="竞价复盘实时行情",
                    status="success",
                    detail="日K未含当日记录，使用实时行情涨跌幅回填收盘涨幅",
                ),
            ],
        },
    )
    return updated.model_copy(update={"score": score_auction_record(updated)})


def _auction_review_quote_day_outcome(
    quote: object, trade_date: str
) -> AuctionReviewOutcome | None:
    close_pct = getattr(quote, "pct_change", None)
    if close_pct is None or not _quote_time_matches_trade_date(
        getattr(quote, "quote_time", None), trade_date
    ):
        return None
    close_pct = round(float(close_pct), 2)
    prev_close = getattr(quote, "prev_close", None)
    drawdown_pct = _quote_pct_from_base(getattr(quote, "low_price", None), prev_close)
    return AuctionReviewOutcome(
        peak_pct=_quote_pct_from_base(getattr(quote, "high_price", None), prev_close),
        close_pct=close_pct,
        drawdown_pct=min(drawdown_pct, 0) if drawdown_pct is not None else None,
        limit_up=close_pct >= 9.8,
        open_pct=_quote_pct_from_base(getattr(quote, "open_price", None), prev_close),
        status="complete",
    )


def _quote_pct_from_base(price: float | None, base_price: float | None) -> float | None:
    if price is None or base_price is None or base_price <= 0:
        return None
    return round((float(price) - float(base_price)) / float(base_price) * 100, 2)


def _quote_time_matches_trade_date(quote_time: str | None, trade_date: str) -> bool:
    if not quote_time:
        return True
    value = str(quote_time)
    compact_trade_date = trade_date.replace("-", "")
    if value.startswith(trade_date) or value.startswith(compact_trade_date):
        return True
    if value.isdigit():
        try:
            timestamp = int(value)
            seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
            return (
                datetime.fromtimestamp(seconds, ZoneInfo("Asia/Shanghai")).date().isoformat()
                == trade_date
            )
        except (OverflowError, OSError, ValueError):
            return False
    return False


def _mark_auction_review_kline_unavailable(
    record: AuctionReviewRecord, detail: str
) -> AuctionReviewRecord:
    unavailable = AuctionReviewOutcome(status="data_incomplete")
    return record.model_copy(
        deep=True,
        update={
            "intraday_result": unavailable,
            "day_result": unavailable,
            "next_day_result": unavailable,
            "review_status": "data_incomplete",
            "source_status": [
                *record.source_status,
                StrongStockSourceStatus(
                    source="竞价复盘日K",
                    status="failed",
                    detail=detail,
                ),
            ],
        },
    )


def _auction_review_selected_at(trade_date: str) -> datetime:
    current = _auction_now()
    return datetime.fromisoformat(
        f"{trade_date}T{current.hour:02d}:{current.minute:02d}:{current.second:02d}+08:00"
    )


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


def _request_base_url(request: Request) -> str:
    # 仅记录请求来源（用于数据包溯源）。Host 头是客户端可控输入：
    # 解析失败时返回占位符，不把任意 Host 头原文反射进落盘数据。
    try:
        return str(request.base_url).rstrip("/")
    except Exception:
        return "unknown-origin"


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
            provider_timeout_seconds=current.provider_timeout_seconds
            or effective.provider_timeout_seconds,
            notification_channels=current.notification_channels,
            sentiment_monitor=config,
            gsgf_auto_review=current.gsgf_auto_review,
            ai_analysis=current.ai_analysis,
            auction_top3_training=current.auction_top3_training,
        ),
    )


def _estimated_sector_radar(overview: MarketOverviewResponse, limit: int) -> SectorRadarResponse:
    items = [
        _estimated_sector_radar_item(sector)
        for sector in overview.sectors
        if sector.turnover_cny is not None
    ]
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


def _read_watchlist_pool() -> str:
    path = _watchlist_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


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
            detail=_sanitized_health_error(exc),
        )



def _auction_model_result_store(*args, **kwargs):
    return deps._auction_model_result_store(*args, **kwargs)

def _auction_model_service(*args, **kwargs):
    return deps._auction_model_service(*args, **kwargs)

def _auction_snapshot_store(*args, **kwargs):
    return deps._auction_snapshot_store(*args, **kwargs)

def _auction_top3_training_store(*args, **kwargs):
    return deps._auction_top3_training_store(*args, **kwargs)

def _background_job_store(*args, **kwargs):
    return deps._background_job_store(*args, **kwargs)

def _build_market_sentiment_analysis_input(*args, **kwargs):
    return deps._build_market_sentiment_analysis_input(*args, **kwargs)

def _cached_market_overview(*args, **kwargs):
    return deps._cached_market_overview(*args, **kwargs)

def _candidate_provider(*args, **kwargs):
    return deps._candidate_provider(*args, **kwargs)

def _capital_signal_service(*args, **kwargs):
    return deps._capital_signal_service(*args, **kwargs)

def _chanlun_adapter(*args, **kwargs):
    return deps._chanlun_adapter(*args, **kwargs)

def _chanlun_minute_store(*args, **kwargs):
    return deps._chanlun_minute_store(*args, **kwargs)

def _chanlun_research_service(*args, **kwargs):
    return deps._chanlun_research_service(*args, **kwargs)

def _chanlun_shadow_scheduler(*args, **kwargs):
    return deps._chanlun_shadow_scheduler(*args, **kwargs)

def _close_default_data_source_providers(*args, **kwargs):
    return deps._close_default_data_source_providers(*args, **kwargs)

def _concept_provider(*args, **kwargs):
    return deps._concept_provider(*args, **kwargs)

def _effective_settings(*args, **kwargs):
    return deps._effective_settings(*args, **kwargs)

def _generate_market_sentiment_analysis(*args, **kwargs):
    return deps._generate_market_sentiment_analysis(*args, **kwargs)

def _gsgf_review_store(*args, **kwargs):
    return deps._gsgf_review_store(*args, **kwargs)

def _ifind_provider(*args, **kwargs):
    return deps._ifind_provider(*args, **kwargs)

def _kline_provider(*args, **kwargs):
    return deps._kline_provider(*args, **kwargs)

def _market_overview_provider(*args, **kwargs):
    return deps._market_overview_provider(*args, **kwargs)

def _market_sentiment_analysis_store(*args, **kwargs):
    return deps._market_sentiment_analysis_store(*args, **kwargs)

def _market_sentiment_percentile_store(*args, **kwargs):
    return deps._market_sentiment_percentile_store(*args, **kwargs)

def _model_maintenance_store(*args, **kwargs):
    return deps._model_maintenance_store(*args, **kwargs)

def _news_risk_provider(*args, **kwargs):
    return deps._news_risk_provider(*args, **kwargs)

def _plate_rotation_reference_provider(*args, **kwargs):
    return deps._plate_rotation_reference_provider(*args, **kwargs)

def _provider_cache_key(*args, **kwargs):
    return deps._provider_cache_key(*args, **kwargs)

def _quote_provider(*args, **kwargs):
    return deps._quote_provider(*args, **kwargs)

def _run_store(*args, **kwargs):
    return deps._run_store(*args, **kwargs)

def _runtime_config_path(*args, **kwargs):
    return deps._runtime_config_path(*args, **kwargs)

def _sanitized_health_error(*args, **kwargs):
    return deps._sanitized_health_error(*args, **kwargs)

def _sector_theme_rows_store(*args, **kwargs):
    return deps._sector_theme_rows_store(*args, **kwargs)

def _sector_workbench_store(*args, **kwargs):
    return deps._sector_workbench_store(*args, **kwargs)

def _tdx_provider(*args, **kwargs):
    return deps._tdx_provider(*args, **kwargs)

def _valuation_quote_provider(*args, **kwargs):
    return deps._valuation_quote_provider(*args, **kwargs)

def _watchlist_path(*args, **kwargs):
    return deps._watchlist_path(*args, **kwargs)

def _watchlist_snapshot(*args, **kwargs):
    return deps._watchlist_snapshot(*args, **kwargs)


__all__ = [
    "_MARKET_SENTIMENT_ANALYSIS_CATCHUP_LOCK",
    "_MARKET_SENTIMENT_ANALYSIS_CATCHUP_DATES",
    "_chanlun_research_health",
    "_execute_screen_run_job",
    "_execute_screen_run",
    "_build_and_save_model_maintenance_packet",
    "_generate_auction_top3_for_date",
    "_run_auction_model_top3_generation_job",
    "_enrich_sector_replica_stock_rows",
    "_build_watchlist_gsgf_status",
    "_cached_capital_summary",
    "_cached_market_rankings",
    "_refresh_market_rankings",
    "_cached_auction_snapshot",
    "_refresh_auction_snapshot",
    "_backfill_auction_snapshot_industries",
    "_auction_hot_theme_refs",
    "_append_empty_hot_theme_status",
    "_run_auction_snapshot_refresh_job",
    "_auction_now",
    "_sector_now",
    "_cached_sector_radar",
    "_cached_sector_intraday_series",
    "_cached_sector_intraday_status",
    "_sector_intraday_cache_key",
    "_schedule_sector_intraday_refresh",
    "_sector_intraday_refresh_key",
    "_tickflow_sector_radar",
    "_cached_stock_kline",
    "_cached_stock_research",
    "_quote_valuation_for_symbol",
    "_system_jobs",
    "_attribute_running_status",
    "_sentiment_monitor_running_status",
    "_auction_sampler_running_status",
    "_thread_running_status",
    "_safe_status_running",
    "_safe_thread_running",
    "_system_job_degraded",
    "_diagnostic_detail",
    "_status_unavailable_detail",
    "_market_sentiment_analysis_now",
    "_persisted_percentile_point_for_trade_date",
    "_schedule_market_sentiment_analysis_catchup",
    "_chanlun_screening_summarizer",
    "_validate_chanlun_lookback",
    "_parse_chanlun_backtest_horizons",
    "_stock_industry_for_symbol",
    "_sector_theme_rows",
    "_schedule_sector_theme_rows_refresh",
    "_refresh_sector_theme_rows",
    "_build_sector_theme_rows",
    "_auction_review_summary",
    "_auction_review_minute_bars",
    "_fill_auction_review_close_from_quotes",
    "_fill_auction_review_record_close_from_quote",
    "_auction_review_quote_day_outcome",
    "_quote_pct_from_base",
    "_quote_time_matches_trade_date",
    "_mark_auction_review_kline_unavailable",
    "_auction_review_selected_at",
    "_intraday_watchlist_items",
    "_request_base_url",
    "_save_sentiment_monitor_config",
    "_estimated_sector_radar",
    "_estimated_sector_radar_item",
    "_read_watchlist_pool",
    "_probe",
    "_auction_model_result_store",
    "_auction_model_service",
    "_auction_snapshot_store",
    "_auction_top3_training_store",
    "_background_job_store",
    "_build_market_sentiment_analysis_input",
    "_cached_market_overview",
    "_candidate_provider",
    "_capital_signal_service",
    "_chanlun_adapter",
    "_chanlun_minute_store",
    "_chanlun_research_service",
    "_chanlun_shadow_scheduler",
    "_close_default_data_source_providers",
    "_concept_provider",
    "_effective_settings",
    "_generate_market_sentiment_analysis",
    "_gsgf_review_store",
    "_ifind_provider",
    "_kline_provider",
    "_market_overview_provider",
    "_market_sentiment_analysis_store",
    "_market_sentiment_percentile_store",
    "_model_maintenance_store",
    "_news_risk_provider",
    "_plate_rotation_reference_provider",
    "_provider_cache_key",
    "_quote_provider",
    "_run_store",
    "_runtime_config_path",
    "_sanitized_health_error",
    "_sector_theme_rows_store",
    "_sector_workbench_store",
    "_tdx_provider",
    "_valuation_quote_provider",
    "_watchlist_path",
    "_watchlist_snapshot",
]
