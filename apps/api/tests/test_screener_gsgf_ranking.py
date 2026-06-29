from app.models import GsgfAnalysis, KlineBar, StrongStockCandidate, StrongStockScreeningItem
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
