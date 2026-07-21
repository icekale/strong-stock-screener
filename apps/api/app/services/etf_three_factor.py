from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Sequence

from app.models import EtfThreeFactorItem, EtfThreeFactorLevel, EtfThreeFactorMode, EtfThreeFactorSummary


INDEX_SYMBOL_BY_ETF: Mapping[str, str] = MappingProxyType(
    {
        "510050.SH": "000016.SH",
        "510300.SH": "000300.SH",
        "510500.SH": "000905.SH",
        "512100.SH": "000852.SH",
        "159915.SZ": "399006.SZ",
        "510230.SH": "000018.SH",
        "588080.SH": "000688.SH",
    }
)


def volume_factor_score(volume_ratio: float | None) -> float | None:
    if volume_ratio is None:
        return None
    if volume_ratio >= 3.0:
        return 100
    if volume_ratio >= 2.5:
        return 85
    if volume_ratio >= 2.0:
        return 70
    if volume_ratio >= 1.5:
        return 50
    return 0


def direction_factor_score(
    etf_change_pct: float | None, index_change_pct: float | None
) -> float | None:
    if etf_change_pct is None or index_change_pct is None:
        return None
    etf_up = etf_change_pct > 0
    index_up = index_change_pct > 0
    if etf_up and not index_up:
        return 100
    if etf_up and index_up:
        return 70
    if not etf_up and index_up:
        return 20
    return 0


def share_factor_score(share_change_pct: float | None) -> float | None:
    if share_change_pct is None:
        return None
    if share_change_pct >= 5.0:
        return 100
    if share_change_pct >= 3.0:
        return 80
    if share_change_pct >= 1.0:
        return 60
    return 0


def combine_factor_scores(
    volume_score: float | None,
    direction_score: float | None,
    share_score: float | None,
    share_pending: bool,
) -> tuple[float | None, EtfThreeFactorMode]:
    if volume_score is None or direction_score is None:
        return None, "incomplete"
    if share_pending:
        return volume_score * 0.7 + direction_score * 0.3, "two_factor"
    if share_score is None:
        return None, "incomplete"
    return volume_score * 0.5 + direction_score * 0.2 + share_score * 0.3, "three_factor"


def signal_level(score: float | None) -> EtfThreeFactorLevel:
    if score is None:
        return "incomplete"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def summarize_three_factor(items: Sequence[EtfThreeFactorItem]) -> EtfThreeFactorSummary:
    valid_items = [item for item in items if item.signal_score is not None]
    valid_count = len(valid_items)
    high_count = sum(item.level == "high" for item in valid_items)
    medium_count = sum(item.level == "medium" for item in valid_items)
    if not valid_items:
        return EtfThreeFactorSummary()

    average_score = sum(item.signal_score for item in valid_items if item.signal_score is not None) / valid_count
    if valid_count < 5:
        market_state = "incomplete"
    elif average_score >= 70 and high_count >= 5:
        market_state = "high"
    elif average_score >= 50 and high_count >= 3:
        market_state = "watch"
    else:
        market_state = "normal"
    return EtfThreeFactorSummary(
        signal_score=average_score,
        level=signal_level(average_score),
        valid_count=valid_count,
        high_count=high_count,
        medium_count=medium_count,
        market_state=market_state,
    )
