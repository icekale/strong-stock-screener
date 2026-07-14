from app.models import (
    ChanlunScreeningSummary,
    GsgfAnalysis,
    KlineBar,
    StrongStockCandidate,
    StrongStockScreeningItem,
)
from app.services import screener as screener_module
from app.services.screener import StrongStockScreener, _screening_rank_key


def test_gsgf_ranking_prioritizes_confirmed_and_low_buy_over_standalone_b_zone() -> None:
    confirmed = _item(
        "603000.SH",
        GsgfAnalysis(
            total_score=78,
            final_status="确认买点",
            zone="unformed",
            confirm_type="放量突破确认",
        ),
    )
    low_buy = _item(
        "603001.SH",
        GsgfAnalysis(
            total_score=74,
            final_status="低吸观察",
            zone="a_zone",
            setup_type="补仓星线",
        ),
    )
    standalone_b_zone = _item(
        "603002.SH",
        GsgfAnalysis(
            total_score=86,
            final_status="观察",
            zone="b_zone_a_point",
        ),
    )

    ranked = sorted([standalone_b_zone, low_buy, confirmed], key=lambda item: _screening_rank_key(item, "gsgf"))

    assert [item.symbol for item in ranked] == ["603000.SH", "603001.SH", "603002.SH"]


def test_gsgf_ranking_downgrades_confirmation_with_screening_risk_flags() -> None:
    clean_confirmed = _item(
        "603010.SH",
        GsgfAnalysis(
            total_score=75,
            final_status="确认买点",
            zone="a_zone",
            confirm_type="放量突破确认",
        ),
    )
    risky_confirmed = _item(
        "603011.SH",
        GsgfAnalysis(
            total_score=96,
            final_status="确认买点",
            zone="a_zone",
            confirm_type="放量突破确认",
        ),
    ).model_copy(update={"risk_flags": ["下跌日放量"]})

    ranked = sorted([risky_confirmed, clean_confirmed], key=lambda item: _screening_rank_key(item, "gsgf"))

    assert [item.symbol for item in ranked] == ["603010.SH", "603011.SH"]


def test_gsgf_screening_risk_overlay_relabels_risky_confirmation() -> None:
    item = _item(
        "603012.SH",
        GsgfAnalysis(
            total_score=92,
            final_status="确认买点",
            action="strong_candidate",
            zone="a_zone",
            confirm_type="放量突破确认",
        ),
    ).model_copy(update={"risk_flags": ["下跌日放量", "MA5拐头向下"]})

    updated = screener_module._apply_gsgf_screening_risk_overlay(item)

    assert updated.gsgf.final_status == "观察"
    assert updated.gsgf.action == "wait_trigger"
    assert updated.gsgf.total_score == 74
    assert "下跌日放量" in updated.gsgf.risk_flags
    assert "确认信号降级" in "\n".join(updated.gsgf.explanation)


def test_gsgf_screening_reports_funnel_and_keeps_b_zone_in_observation_pool(monkeypatch) -> None:
    monkeypatch.setattr(screener_module, "analyze_screening_item", fake_analyze_screening_item)
    screener = StrongStockScreener(
        candidate_provider=StaticCandidateProvider(),
        kline_provider=StaticKlineProvider(),
    )

    result = screener.screen(
        trade_date="2026-06-11",
        limit=2,
        scan_limit=6,
        strategy="gsgf",
        filters=KdjFilter(kdj_j_max=90),
    )

    assert [item.symbol for item in result.items] == ["603000.SH", "603001.SH"]
    assert [item.symbol for item in result.gsgf_observation_items] == ["603002.SH"]
    assert result.gsgf_observation_items[0].gsgf.zone == "b_zone_a_point"
    assert result.gsgf_observation_items[0].gsgf.final_status == "观察"

    funnel = result.gsgf_funnel
    assert funnel.candidate_pool_count == 7
    assert funnel.after_static_filters_count == 6
    assert funnel.scan_limit_count == 6
    assert funnel.kline_success_count == 5
    assert funnel.kline_failure_count == 1
    assert funnel.data_incomplete_count == 1
    assert funnel.kdj_filtered_count == 1
    assert funnel.gsgf_structure_hit_count == 3
    assert funnel.confirmed_buy_count == 1
    assert funnel.low_buy_count == 1
    assert funnel.b_zone_a_point_count == 1
    assert funnel.volume_breakout_count == 1
    assert funnel.hard_risk_filtered_count == 0
    assert funnel.final_displayed_count == 2
    assert result.source_status[-1].status == "failed"
    assert "603003.SH 风险股份" in result.source_status[-1].detail


def test_chanlun_enrichment_filters_complete_summaries_and_isolates_symbol_failures(monkeypatch) -> None:
    monkeypatch.setattr(screener_module, "analyze_screening_item", simple_analyze_screening_item)
    summarizer = RecordingChanlunSummarizer(
        summaries={
            "603100.SH": _chanlun_summary(score=10, confirmed_buy=False),
            "603102.SH": _chanlun_summary(score=90, confirmed_buy=True),
        },
        failing_symbols={"603101.SH"},
    )
    screener = StrongStockScreener(
        candidate_provider=ManyStaticCandidateProvider(count=3),
        kline_provider=StaticKlineProvider(),
        chanlun_summarizer=summarizer,
    )

    result = screener.screen(
        trade_date="2026-06-11",
        limit=2,
        scan_limit=3,
        filters=ChanlunFilter(min_score=50, require_buy=True),
    )

    assert [item.symbol for item in result.items] == ["603102.SH", "603101.SH"]
    assert result.items[0].chanlun_summary.confluence_score == 90
    assert result.items[1].chanlun_summary is None
    assert summarizer.calls == ["603100.SH", "603101.SH", "603102.SH"]


def test_chanlun_enrichment_is_bounded_before_final_ranking(monkeypatch) -> None:
    monkeypatch.setattr(screener_module, "analyze_screening_item", simple_analyze_screening_item)
    summarizer = RecordingChanlunSummarizer()
    screener = StrongStockScreener(
        candidate_provider=ManyStaticCandidateProvider(count=25),
        kline_provider=StaticKlineProvider(),
        chanlun_summarizer=summarizer,
    )

    screener.screen(trade_date="2026-06-11", limit=1, scan_limit=25)

    assert len(summarizer.calls) == 20


def test_shadow_scheduler_never_changes_formal_order(monkeypatch) -> None:
    monkeypatch.setattr(screener_module, "analyze_screening_item", simple_analyze_screening_item)
    scheduler = RecordingShadowScheduler(job_id="shadow-1")
    screener = StrongStockScreener(
        candidate_provider=ManyStaticCandidateProvider(count=25),
        kline_provider=StaticKlineProvider(),
        chanlun_v2_scheduler=scheduler,
    )

    result = screener.screen("2026-07-10", limit=3, scan_limit=25)

    assert [item.symbol for item in result.items] == ["603100.SH", "603101.SH", "603102.SH"]
    assert result.czsc_v2_job_id == "shadow-1"
    assert result.czsc_v2_status == "pending"
    assert all(item.czsc_score_v2 is None for item in result.items)
    assert 20 <= len(scheduler.candidates) <= 60
    assert [candidate.baseline_rank for candidate in scheduler.candidates] == list(
        range(1, len(scheduler.candidates) + 1)
    )


def test_chanlun_stale_summary_does_not_break_core_score_ties() -> None:
    stale = _item("603110.SH", GsgfAnalysis(total_score=50)).model_copy(
        update={"chanlun_summary": _chanlun_summary(score=100, confirmed_buy=True).model_copy(update={"freshness": "stale"})}
    )
    fresh = _item("603111.SH", GsgfAnalysis(total_score=50)).model_copy(
        update={"chanlun_summary": _chanlun_summary(score=50, confirmed_buy=True)}
    )

    ranked = sorted([stale, fresh], key=lambda item: _screening_rank_key(item, "strong_stock"))

    assert [item.symbol for item in ranked] == ["603111.SH", "603110.SH"]


def _item(symbol: str, gsgf: GsgfAnalysis) -> StrongStockScreeningItem:
    return StrongStockScreeningItem(
        symbol=symbol,
        name=symbol,
        status="focus",
        score=80,
        gsgf=gsgf,
    )


class StaticCandidateProvider:
    source_name = "fake候选池"
    preserve_candidate_order = True

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(symbol="603000.SH", name="确认股份", industry="AI", total_market_cap_cny=12_000_000_000),
            StrongStockCandidate(symbol="603001.SH", name="低吸股份", industry="AI", total_market_cap_cny=12_000_000_000),
            StrongStockCandidate(symbol="603002.SH", name="B点股份", industry="AI", total_market_cap_cny=12_000_000_000),
            StrongStockCandidate(symbol="603003.SH", name="风险股份", industry="AI", total_market_cap_cny=12_000_000_000),
            StrongStockCandidate(symbol="603004.SH", name="缺数股份", industry="AI", total_market_cap_cny=12_000_000_000),
            StrongStockCandidate(symbol="603005.SH", name="高KDJ股份", industry="AI", total_market_cap_cny=12_000_000_000),
            StrongStockCandidate(symbol="603006.SH", name="过滤股份", industry="AI", total_market_cap_cny=500_000_000),
        ]


class StaticKlineProvider:
    source_name = "fake K线"

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        if symbol == "603003.SH":
            raise RuntimeError("missing kline")
        length = 30 if symbol == "603004.SH" else count
        return [
            KlineBar(date=f"2026-01-{index % 28 + 1:02d}", open=10.0, high=11.0, low=9.8, close=10.5, volume=1000.0)
            for index in range(length)
        ]


class KdjFilter:
    min_market_cap_billion = 10
    max_market_cap_billion = None
    industries: list[str] = []
    market_types: list[str] = []

    def __init__(self, kdj_j_max: float) -> None:
        self.kdj_j_max = kdj_j_max


class ChanlunFilter:
    min_market_cap_billion = None
    max_market_cap_billion = None
    kdj_j_max = None
    industries: list[str] = []
    market_types: list[str] = []

    def __init__(self, *, min_score: int | None, require_buy: bool) -> None:
        self.chanlun_min_confluence_score = min_score
        self.chanlun_require_confirmed_buy = require_buy


class ManyStaticCandidateProvider:
    source_name = "fake候选池"
    preserve_candidate_order = True

    def __init__(self, *, count: int) -> None:
        self.count = count

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        return [
            StrongStockCandidate(
                symbol=f"603{100 + index:03d}.SH",
                name=f"候选{index}",
                industry="AI",
                total_market_cap_cny=12_000_000_000,
            )
            for index in range(self.count)
        ]


class RecordingShadowScheduler:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.candidates: list[object] = []

    def submit(self, *, trade_date: str, candidates: list[object]) -> str:
        self.candidates = list(candidates)
        return self.job_id


class RecordingChanlunSummarizer:
    def __init__(
        self,
        *,
        summaries: dict[str, ChanlunScreeningSummary] | None = None,
        failing_symbols: set[str] | None = None,
    ) -> None:
        self.summaries = summaries or {}
        self.failing_symbols = failing_symbols or set()
        self.calls: list[str] = []

    def summarize(
        self,
        symbol: str,
        *,
        daily_bars: list[KlineBar],
        trade_date: str,
    ) -> ChanlunScreeningSummary:
        self.calls.append(symbol)
        if symbol in self.failing_symbols:
            raise RuntimeError("broken local cache")
        return self.summaries.get(symbol, _chanlun_summary(score=50, confirmed_buy=True))


def _chanlun_summary(*, score: int, confirmed_buy: bool) -> ChanlunScreeningSummary:
    return ChanlunScreeningSummary(
        availability="ready",
        freshness="fresh",
        confluence_score=score,
        has_confirmed_buy=confirmed_buy,
    )


def simple_analyze_screening_item(
    candidate: StrongStockCandidate,
    bars: list[KlineBar],
    trade_date: str,
) -> StrongStockScreeningItem:
    return StrongStockScreeningItem(
        symbol=candidate.symbol,
        name=candidate.name,
        industry=candidate.industry,
        status="focus",
        score=80,
        metrics={"kdj_j": 20},
    )


def fake_analyze_screening_item(
    candidate: StrongStockCandidate,
    bars: list[KlineBar],
    trade_date: str,
) -> StrongStockScreeningItem:
    gsgf_by_symbol = {
        "603000.SH": GsgfAnalysis(
            total_score=78,
            final_status="确认买点",
            zone="a_zone",
            confirm_type="放量突破确认",
        ),
        "603001.SH": GsgfAnalysis(total_score=74, final_status="低吸观察", zone="a_zone"),
        "603002.SH": GsgfAnalysis(total_score=86, final_status="观察", zone="b_zone_a_point", setup_type="B区A点"),
        "603004.SH": GsgfAnalysis(total_score=0, final_status="观察", zone="unknown"),
        "603005.SH": GsgfAnalysis(total_score=60, final_status="观察", zone="unformed"),
    }
    status = "data_incomplete" if len(bars) < 220 else "focus"
    kdj_j = 95 if candidate.symbol == "603005.SH" else 20
    return StrongStockScreeningItem(
        symbol=candidate.symbol,
        name=candidate.name,
        industry=candidate.industry,
        status=status,
        score=80,
        metrics={"kdj_j": kdj_j},
        data_status="incomplete" if status == "data_incomplete" else "complete",
        gsgf=gsgf_by_symbol[candidate.symbol],
    )
