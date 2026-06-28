from app.models import GsgfAnalysis, StrongStockScreeningItem
from app.services.screener import _screening_rank_key


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


def _item(symbol: str, gsgf: GsgfAnalysis) -> StrongStockScreeningItem:
    return StrongStockScreeningItem(
        symbol=symbol,
        name=symbol,
        status="focus",
        score=80,
        gsgf=gsgf,
    )
