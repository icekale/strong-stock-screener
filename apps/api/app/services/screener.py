from __future__ import annotations

from collections import Counter
from typing import Protocol

from app.models import (
    ChanlunScreeningSummary,
    GsgfFunnelDiagnostics,
    KlineBar,
    RiskCheckStatus,
    ScreenStrategy,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockRiskItem,
    StrongStockScreeningItem,
    StrongStockScreeningResult,
    StrongStockSourceStatus,
)
from app.providers.watchlist import WatchlistSnapshot
from app.rules import analyze_screening_item, analyze_watchlist_risk
from app.providers.news_risk import NegativeNewsRisk
from app.services.gsgf_trade_plan import build_gsgf_trade_plan
from app.services.chanlun.screening import passes_chanlun_screening_filters


class ScreeningFilters(Protocol):
    min_market_cap_billion: float | None
    max_market_cap_billion: float | None
    kdj_j_max: float | None
    industries: list[str]
    market_types: list[str]
    chanlun_min_confluence_score: int | None
    chanlun_require_confirmed_buy: bool


class ChanlunScreeningSummarizer(Protocol):
    def summarize(
        self,
        symbol: str,
        *,
        daily_bars: list[KlineBar],
        trade_date: str,
    ) -> ChanlunScreeningSummary: ...


class CandidateProvider(Protocol):
    source_name: str

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        ...


class KlineProvider(Protocol):
    source_name: str

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        ...


class NewsRiskProvider(Protocol):
    source_name: str

    def get_negative_news_risk(self, symbol: str) -> NegativeNewsRisk:
        ...


class StrongStockScreener:
    def __init__(
        self,
        candidate_provider: CandidateProvider,
        kline_provider: KlineProvider,
        news_risk_provider: NewsRiskProvider | None = None,
        chanlun_summarizer: ChanlunScreeningSummarizer | None = None,
    ) -> None:
        self.candidate_provider = candidate_provider
        self.kline_provider = kline_provider
        self.news_risk_provider = news_risk_provider
        self.chanlun_summarizer = chanlun_summarizer

    def screen(
        self,
        trade_date: str,
        limit: int,
        scan_limit: int,
        filters: ScreeningFilters | None = None,
        watchlist_snapshot: WatchlistSnapshot | None = None,
        strategy: ScreenStrategy = "strong_stock",
        exclude_gsgf_hard_risk: bool = False,
    ) -> StrongStockScreeningResult:
        candidates = self.candidate_provider.get_candidates(trade_date)
        if not candidates:
            raise StrongStockDataUnavailable("20日内涨停候选池为空")
        candidates_before_filter = len(candidates)
        filtered_candidates = _filter_candidates(candidates, filters)
        stable_candidates = _candidates_for_scan(self.candidate_provider, filtered_candidates)
        candidates_to_scan = stable_candidates[:scan_limit]
        industry_context = _industry_context(candidates_to_scan)
        funnel = GsgfFunnelDiagnostics(
            candidate_pool_count=candidates_before_filter,
            after_static_filters_count=len(filtered_candidates),
            scan_limit_count=len(candidates_to_scan),
        )

        source_status = [
            StrongStockSourceStatus(
                    source=self.candidate_provider.source_name,
                    status="success",
                    detail=_candidate_status_detail(
                        total=candidates_before_filter,
                        filtered=len(filtered_candidates),
                        scanned=len(candidates_to_scan),
                        kdj_j_max=filters.kdj_j_max if filters is not None else None,
                    ),
                )
            ]
        items: list[StrongStockScreeningItem] = []
        observation_items: list[StrongStockScreeningItem] = []
        bars_by_symbol: dict[str, list[KlineBar]] = {}
        failures = 0
        failed_candidates: list[str] = []
        kdj_filtered = 0
        for candidate in candidates_to_scan:
            try:
                bars = self.kline_provider.get_klines(candidate.symbol, count=220)
            except Exception:
                failures += 1
                failed_candidates.append(f"{candidate.symbol} {candidate.name}")
                continue
            funnel.kline_success_count += 1
            item = analyze_screening_item(candidate, bars, trade_date=trade_date)
            if item.status == "data_incomplete":
                funnel.data_incomplete_count += 1
                continue
            if not _passes_kdj_filter(item, filters):
                kdj_filtered += 1
                continue
            checked_item = _apply_candidate_risk_checks(
                _apply_industry_strength(item, industry_context),
                candidate=candidate,
                news_risk_provider=self.news_risk_provider,
            )
            enriched_item = _apply_gsgf_screening_risk_overlay(checked_item)
            _count_gsgf_signal(funnel, enriched_item)
            if _is_gsgf_observation_item(enriched_item):
                observation_items.append(enriched_item)
            items.append(enriched_item)
            bars_by_symbol[enriched_item.symbol] = bars

        if kdj_filtered:
            source_status[0] = source_status[0].model_copy(
                update={
                    "detail": f"{source_status[0].detail}；KDJ-J<{filters.kdj_j_max:g} 过滤 {kdj_filtered} 只"
                    if filters is not None and filters.kdj_j_max is not None
                    else source_status[0].detail
                }
            )

        if failures:
            source_status.append(
                StrongStockSourceStatus(
                    source=self.kline_provider.source_name,
                    status="failed",
                    detail=_kline_failure_detail(failures, failed_candidates),
                )
            )
        else:
            source_status.append(
                StrongStockSourceStatus(
                    source=self.kline_provider.source_name,
                    status="success",
                    detail="候选股K线获取完成",
                )
            )

        funnel.kline_failure_count = failures
        funnel.kdj_filtered_count = kdj_filtered
        if exclude_gsgf_hard_risk:
            before_hard_risk = len(items)
            items = [item for item in items if not _has_gsgf_hard_risk(item)]
            funnel.hard_risk_filtered_count = before_hard_risk - len(items)
        items = _enrich_chanlun_candidates(
            items,
            bars_by_symbol=bars_by_symbol,
            summarizer=self.chanlun_summarizer,
            trade_date=trade_date,
            limit=limit,
            strategy=strategy,
        )
        enriched_by_symbol = {item.symbol: item for item in items}
        observation_items = [
            enriched_by_symbol.get(item.symbol, item)
            for item in observation_items
            if item.symbol in enriched_by_symbol
        ]
        items = [item for item in items if _passes_chanlun_filters(item, filters)]
        observation_items = [
            item for item in observation_items if _passes_chanlun_filters(item, filters)
        ]
        ranked = sorted(items, key=lambda item: _screening_rank_key(item, strategy))[:limit]
        ranked_observations = sorted(observation_items, key=lambda item: _gsgf_observation_rank_key(item))[:limit]
        funnel.final_displayed_count = len(ranked)
        return StrongStockScreeningResult(
            strategy=strategy,
            gsgf_model_version="gsgf-v2",
            sort_version=_sort_version(strategy),
            trade_date=trade_date,
            source_status=source_status,
            items=ranked,
            gsgf_funnel=funnel,
            gsgf_observation_items=ranked_observations,
            watchlist_risk_items=self._watchlist_risks(watchlist_snapshot, trade_date),
        )

    def _watchlist_risks(
        self,
        watchlist_snapshot: WatchlistSnapshot | None,
        trade_date: str,
    ) -> list[StrongStockRiskItem]:
        if watchlist_snapshot is None:
            return []
        risks: list[StrongStockRiskItem] = []
        for item in watchlist_snapshot.items:
            try:
                bars = self.kline_provider.get_klines(item.symbol, count=220)
            except Exception:
                continue
            candidate = StrongStockCandidate(
                symbol=item.symbol,
                name=item.name or item.symbol,
                industry=item.industry,
            )
            risks.append(
                _apply_candidate_risk_checks(
                    analyze_watchlist_risk(candidate, bars, trade_date=trade_date),
                    candidate=candidate,
                    news_risk_provider=self.news_risk_provider,
                )
            )
        return risks


def _industry_context(candidates: list[StrongStockCandidate]) -> dict[str, dict[str, int]]:
    counts = Counter(candidate.industry for candidate in candidates if candidate.industry)
    ranked = sorted(counts.items(), key=lambda value: (-value[1], value[0]))
    return {
        industry: {"count": count, "rank": index + 1}
        for index, (industry, count) in enumerate(ranked)
    }


def _filter_candidates(
    candidates: list[StrongStockCandidate],
    filters: ScreeningFilters | None,
) -> list[StrongStockCandidate]:
    if filters is None:
        return candidates
    return [candidate for candidate in candidates if _passes_candidate_filters(candidate, filters)]


def _passes_candidate_filters(candidate: StrongStockCandidate, filters: ScreeningFilters) -> bool:
    if filters.min_market_cap_billion is not None and not _market_cap_matches(
        candidate,
        minimum=filters.min_market_cap_billion * 100_000_000,
        maximum=None,
    ):
        return False
    if filters.max_market_cap_billion is not None and not _market_cap_matches(
        candidate,
        minimum=None,
        maximum=filters.max_market_cap_billion * 100_000_000,
    ):
        return False
    if filters.industries and (candidate.industry or "") not in filters.industries:
        return False
    if filters.market_types and _market_type(candidate.symbol) not in set(filters.market_types):
        return False
    return True


def _market_cap_matches(
    candidate: StrongStockCandidate,
    minimum: float | None,
    maximum: float | None,
) -> bool:
    market_cap = candidate.total_market_cap_cny
    if market_cap is None:
        return False
    if minimum is not None and market_cap < minimum:
        return False
    if maximum is not None and market_cap > maximum:
        return False
    return True


def _market_type(symbol: str) -> str:
    code = symbol.split(".", 1)[0]
    if code.startswith("300"):
        return "gem"
    if code.startswith("688"):
        return "star"
    if symbol.endswith(".BJ") or code.startswith(("4", "8")):
        return "bj"
    return "main"


def _passes_kdj_filter(
    item: StrongStockScreeningItem,
    filters: ScreeningFilters | None,
) -> bool:
    if filters is None or filters.kdj_j_max is None:
        return True
    value = item.metrics.get("kdj_j")
    return isinstance(value, (int, float)) and value < filters.kdj_j_max


def _candidate_status_detail(
    total: int,
    filtered: int,
    scanned: int,
    kdj_j_max: float | None,
) -> str:
    detail = f"返回 {total} 只 20 日涨停候选"
    if filtered != total:
        detail = f"{detail}，筛选后 {filtered}/{total}"
    detail = f"{detail}，本次分析 {scanned}/{filtered}"
    if kdj_j_max is not None:
        detail = f"{detail}，KDJ-J<{kdj_j_max:g}"
    return detail


def _candidates_for_scan(
    candidate_provider: CandidateProvider,
    candidates: list[StrongStockCandidate],
) -> list[StrongStockCandidate]:
    if getattr(candidate_provider, "preserve_candidate_order", False):
        return candidates
    return sorted(candidates, key=lambda candidate: candidate.symbol)


def _screening_rank_key(item: StrongStockScreeningItem, strategy: ScreenStrategy = "strong_stock") -> tuple:
    if strategy == "gsgf":
        return _gsgf_rank_key(item)
    if strategy == "combined":
        return _combined_rank_key(item)
    return _strong_rank_key(item)


def _strong_rank_key(item: StrongStockScreeningItem) -> tuple[int, int, int, str]:
    focus_rank = 0 if item.status == "focus" else 1
    return (focus_rank, -item.score, -_chanlun_rank_score(item), item.symbol)


def _gsgf_rank_key(item: StrongStockScreeningItem) -> tuple[int, int, int, int, int, int, int, str]:
    gsgf = item.gsgf
    if gsgf is None:
        return (1, 99, 99, 99, 99, 0, -_chanlun_rank_score(item), item.symbol)
    hard_risk = 1 if _has_gsgf_hard_risk(item) or _has_screening_hard_risk(item) else 0
    status_rank = _gsgf_status_rank(gsgf.final_status)
    confirm_rank = 0 if gsgf.confirm_type == "放量突破确认" else 1 if gsgf.confirm_type else 2
    zone_rank = 0 if gsgf.zone == "a_zone" else 1 if gsgf.zone == "b_zone_a_point" else 2
    volume_rank = 0 if gsgf.volume_structure == "three_yang_controls_three_yin" else 1
    return (
        hard_risk,
        status_rank,
        confirm_rank,
        zone_rank,
        volume_rank,
        -gsgf.total_score,
        -_chanlun_rank_score(item),
        item.symbol,
    )


def _combined_rank_key(item: StrongStockScreeningItem) -> tuple[int, int, float, int, str]:
    gsgf_score = item.gsgf.total_score if item.gsgf is not None else 0
    hard_risk = 1 if _has_gsgf_hard_risk(item) else 0
    combined = item.score * 0.45 + gsgf_score * 0.45 + item.industry_score * 0.10
    if hard_risk:
        combined -= 30
    focus_rank = 0 if item.status == "focus" else 1
    return (hard_risk, focus_rank, -combined, -_chanlun_rank_score(item), item.symbol)


def _chanlun_rank_score(item: StrongStockScreeningItem) -> int:
    summary = item.chanlun_summary
    if summary is None or summary.availability != "ready" or summary.freshness != "fresh":
        return 0
    return summary.confluence_score


def _enrich_chanlun_candidates(
    items: list[StrongStockScreeningItem],
    *,
    bars_by_symbol: dict[str, list[KlineBar]],
    summarizer: ChanlunScreeningSummarizer | None,
    trade_date: str,
    limit: int,
    strategy: ScreenStrategy,
) -> list[StrongStockScreeningItem]:
    if summarizer is None or not items:
        return items
    pool_size = min(max(limit * 2, 20), 60)
    pool = sorted(items, key=lambda item: _screening_rank_key(item, strategy))[:pool_size]
    enriched: dict[str, StrongStockScreeningItem] = {}
    for item in pool:
        try:
            summary = summarizer.summarize(
                item.symbol,
                daily_bars=bars_by_symbol[item.symbol],
                trade_date=trade_date,
            )
        except Exception:
            continue
        enriched[item.symbol] = item.model_copy(update={"chanlun_summary": summary})
    return [enriched.get(item.symbol, item) for item in items]


def _passes_chanlun_filters(
    item: StrongStockScreeningItem,
    filters: ScreeningFilters | None,
) -> bool:
    return passes_chanlun_screening_filters(
        item.chanlun_summary,
        min_confluence_score=(
            getattr(filters, "chanlun_min_confluence_score", None) if filters is not None else None
        ),
        require_confirmed_buy=(
            bool(getattr(filters, "chanlun_require_confirmed_buy", False))
            if filters is not None
            else False
        ),
    )


def _gsgf_status_rank(status: str) -> int:
    if status == "确认买点":
        return 0
    if status == "低吸观察":
        return 1
    if status == "候选":
        return 2
    if status == "观察":
        return 3
    if status == "减仓":
        return 4
    return 5


def _has_gsgf_hard_risk(item: StrongStockScreeningItem) -> bool:
    if item.gsgf is None:
        return False
    return item.gsgf.zone == "c_zone" or any(
        flag in {"高位巨量长上影", "C区风险"} for flag in item.gsgf.risk_flags
    )


def _has_screening_hard_risk(item: StrongStockScreeningItem) -> bool:
    return bool(_screening_hard_risk_reasons(item))


def _apply_gsgf_screening_risk_overlay(item: StrongStockScreeningItem) -> StrongStockScreeningItem:
    gsgf = item.gsgf
    if gsgf is None or not gsgf.confirm_type:
        return item
    reasons = _screening_hard_risk_reasons(item)
    if not reasons:
        return item

    next_score = max(0, gsgf.total_score - 18)
    next_status = "减仓" if item.negative_news_status == "triggered" else "观察"
    next_action = "avoid" if next_status == "减仓" else "wait_trigger"
    note = f"确认信号降级：{'、'.join(reasons[:3])}"
    updated_gsgf = gsgf.model_copy(
        update={
            "total_score": next_score,
            "action": next_action,
            "final_status": next_status,
            "risk_flags": _dedupe([*gsgf.risk_flags, *reasons]),
            "explanation": _dedupe([*gsgf.explanation, note]),
        }
    )
    updated_gsgf = updated_gsgf.model_copy(update={"trade_plan": build_gsgf_trade_plan(updated_gsgf)})
    return item.model_copy(update={"gsgf": updated_gsgf})


def _screening_hard_risk_reasons(item: StrongStockScreeningItem) -> list[str]:
    hard_flags = {"下跌日放量", "阴线实体不弱", "MA5拐头向下"}
    reasons = [flag for flag in item.risk_flags if flag in hard_flags]
    if item.negative_news_status == "triggered":
        reasons.extend(item.negative_news_flags[:2] or ["负面新闻触发"])
    if item.severe_abnormal_warning == "triggered":
        reasons.append("异常风险触发")
    return _dedupe(reasons)


def _kline_failure_detail(failures: int, failed_candidates: list[str]) -> str:
    if not failed_candidates:
        return f"{failures} 只股票K线获取失败"
    shown = "、".join(failed_candidates[:10])
    hidden = failures - len(failed_candidates[:10])
    suffix = f"，另 {hidden} 只" if hidden > 0 else ""
    return f"{failures} 只股票K线获取失败：{shown}{suffix}"


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _count_gsgf_signal(funnel: GsgfFunnelDiagnostics, item: StrongStockScreeningItem) -> None:
    gsgf = item.gsgf
    if gsgf is None:
        return
    has_structure = gsgf.zone in {"a_zone", "b_zone_a_point"} or bool(gsgf.setup_type or gsgf.confirm_type)
    if has_structure:
        funnel.gsgf_structure_hit_count += 1
    if gsgf.final_status == "确认买点":
        funnel.confirmed_buy_count += 1
    if gsgf.final_status == "低吸观察":
        funnel.low_buy_count += 1
    if gsgf.zone == "b_zone_a_point" or gsgf.setup_type == "B区A点":
        funnel.b_zone_a_point_count += 1
    if gsgf.confirm_type == "放量突破确认":
        funnel.volume_breakout_count += 1


def _is_gsgf_observation_item(item: StrongStockScreeningItem) -> bool:
    gsgf = item.gsgf
    if gsgf is None or _has_gsgf_hard_risk(item):
        return False
    if gsgf.final_status in {"确认买点", "低吸观察"}:
        return False
    return gsgf.zone == "b_zone_a_point" or gsgf.setup_type == "B区A点"


def _gsgf_observation_rank_key(item: StrongStockScreeningItem) -> tuple[int, int, int, str]:
    gsgf = item.gsgf
    if gsgf is None:
        return (99, 99, 0, item.symbol)
    setup_rank = 0 if gsgf.setup_type == "B区A点" else 1
    volume_rank = 0 if gsgf.volume_structure == "three_yang_controls_three_yin" else 1
    return (setup_rank, volume_rank, -gsgf.total_score, item.symbol)


def _sort_version(strategy: ScreenStrategy) -> str:
    if strategy == "gsgf":
        return "gsgf-sort-v2"
    if strategy == "combined":
        return "combined-sort-v1"
    return "strong-sort-v1"


def _apply_industry_strength(
    item: StrongStockScreeningItem,
    industry_context: dict[str, dict[str, int]],
) -> StrongStockScreeningItem:
    if not item.industry or item.industry not in industry_context:
        return item.model_copy(update={"industry_strength": None, "industry_score": 0, "industry_rank": None})

    context = industry_context[item.industry]
    count = context["count"]
    if count >= 3:
        strength = "strong"
        score = 15
        notes = [f"同板块20日涨停候选 {count} 只，板块强度加分"]
        rule_hits = [*item.rule_hits, "板块强度加分"]
    elif count == 2:
        strength = "neutral"
        score = 6
        notes = [f"同板块20日涨停候选 {count} 只，板块有跟随"]
        rule_hits = item.rule_hits
    else:
        strength = "neutral"
        score = 0
        notes = ["板块集中度一般"]
        rule_hits = item.rule_hits

    return item.model_copy(
        update={
            "industry_strength": strength,
            "industry_score": score,
            "industry_rank": context["rank"],
            "industry_notes": notes,
            "rule_hits": rule_hits,
            "score": max(0, min(100, item.score + score)),
        }
    )


def _apply_candidate_risk_checks(
    item: StrongStockScreeningItem | StrongStockRiskItem,
    candidate: StrongStockCandidate,
    news_risk_provider: NewsRiskProvider | None,
) -> StrongStockScreeningItem | StrongStockRiskItem:
    news_risk = (
        news_risk_provider.get_negative_news_risk(candidate.symbol)
        if news_risk_provider is not None
        else NegativeNewsRisk(status="unknown", flags=[])
    )
    return item.model_copy(
        update={
            "severe_abnormal_warning": _severe_abnormal_status(candidate),
            "negative_news_status": news_risk.status,
            "negative_news_flags": news_risk.flags,
        }
    )


def _severe_abnormal_status(candidate: StrongStockCandidate) -> RiskCheckStatus:
    if candidate.abnormal_status != "unknown":
        return candidate.abnormal_status
    if candidate.abnormal_flags:
        return "triggered"
    return "unknown"
