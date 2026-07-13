from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.models import CZSC_SCORE_RULE_VERSION, ChanlunPeriod, CzscSignalEvidence


_PERIODS: tuple[ChanlunPeriod, ...] = ("1d", "60m", "30m", "5m")
_RISK_PENALTIES: dict[ChanlunPeriod, int] = {
    "1d": 30,
    "60m": 20,
    "30m": 10,
    "5m": 20,
}


@dataclass(frozen=True)
class CzscV2ScoreResult:
    score: int | None
    eligible: bool
    rule_version: str = CZSC_SCORE_RULE_VERSION


def score_czsc_v2(
    *,
    evidence: list[CzscSignalEvidence],
    freshness: Mapping[ChanlunPeriod, str],
) -> CzscV2ScoreResult:
    if not all(freshness.get(period) == "fresh" for period in _PERIODS):
        return CzscV2ScoreResult(score=None, eligible=False)

    daily_points = _trend_points(evidence, "1d", status_points=12, continuation_points=8, turn_points=4)
    hour_points = _trend_points(evidence, "60m", status_points=10, continuation_points=5)
    hour_points += _zone_points(evidence, "1d", "60m")
    half_hour_points = _trend_points(evidence, "30m", status_points=10, continuation_points=5)
    half_hour_points += _zone_points(evidence, "60m", "30m")
    trigger_points, has_primary_trigger = _trigger_points(evidence)
    alignment_points = 10 if _all_trend_statuses_bullish(evidence) else 0

    risk_periods = {
        _evidence_period(item)
        for item in evidence
        if _is_penalized_risk(item)
    }
    risk_penalty = sum(
        _RISK_PENALTIES[period]
        for period in risk_periods
        if period in _RISK_PENALTIES
    )
    score = (
        min(daily_points, 20)
        + min(hour_points, 20)
        + min(half_hour_points, 20)
        + min(trigger_points, 30)
        + min(alignment_points, 10)
        - risk_penalty
    )
    score = max(0, min(100, score))

    has_daily_risk = "1d" in risk_periods
    has_mid_period_sell_risk = any(
        item.family == "sell_risk"
        and item.role == "risk"
        and item.direction == "bearish"
        and _evidence_period(item) in {"60m", "30m"}
        for item in evidence
    )
    eligible = not has_daily_risk and not has_mid_period_sell_risk and has_primary_trigger
    return CzscV2ScoreResult(score=score, eligible=eligible)


def _trend_points(
    evidence: list[CzscSignalEvidence],
    period: ChanlunPeriod,
    *,
    status_points: int,
    continuation_points: int,
    turn_points: int = 0,
) -> int:
    points = 0
    if _has_evidence(evidence, "trend.bi-status", period, v1="向上"):
        points += status_points
    if _has_evidence(evidence, "trend.bi-base", period, v1="向上", v2="中继"):
        points += continuation_points
    elif turn_points and _has_evidence(evidence, "trend.bi-base", period, v1="向上", v2="转折"):
        points += turn_points
    return points


def _zone_points(
    evidence: list[CzscSignalEvidence],
    higher_period: ChanlunPeriod,
    lower_period: ChanlunPeriod,
) -> int:
    return 5 if any(
        item.catalog_id == "zone.resonance"
        and item.direction == "bullish"
        and item.higher_period == higher_period
        and item.lower_period == lower_period
        for item in evidence
    ) else 0


def _trigger_points(evidence: list[CzscSignalEvidence]) -> tuple[int, bool]:
    primary_families = {
        item.family
        for item in evidence
        if item.period == "5m"
        and item.role == "primary"
        and item.direction == "bullish"
        and item.family in {"second_buy", "third_buy"}
    }
    if "third_buy" in primary_families:
        confirmation = _has_trigger_confirmation(evidence, "third_buy")
        return 25 + (5 if confirmation else 0), True
    if "second_buy" in primary_families:
        confirmation = _has_trigger_confirmation(evidence, "second_buy")
        return 20 + (5 if confirmation else 0), True
    return 0, False


def _has_trigger_confirmation(evidence: list[CzscSignalEvidence], family: str) -> bool:
    return any(
        item.period == "5m"
        and item.family == family
        and item.role == "confirmation"
        and item.direction == "bullish"
        for item in evidence
    )


def _all_trend_statuses_bullish(evidence: list[CzscSignalEvidence]) -> bool:
    return all(
        _has_evidence(evidence, "trend.bi-status", period, v1="向上")
        for period in ("1d", "60m", "30m")
    )


def _has_evidence(
    evidence: list[CzscSignalEvidence],
    catalog_id: str,
    period: ChanlunPeriod,
    *,
    v1: str,
    v2: str | None = None,
) -> bool:
    return any(
        item.catalog_id == catalog_id
        and item.period == period
        and item.direction == "bullish"
        and item.params.get("v1") == v1
        and (v2 is None or item.params.get("v2") == v2)
        for item in evidence
    )


def _evidence_period(evidence: CzscSignalEvidence) -> ChanlunPeriod | None:
    return evidence.period or evidence.higher_period


def _is_penalized_risk(evidence: CzscSignalEvidence) -> bool:
    if evidence.role != "risk" or evidence.direction != "bearish":
        return False
    period = _evidence_period(evidence)
    if evidence.family == "sell_risk":
        return period in _RISK_PENALTIES
    if evidence.family == "divergence":
        return period in {"1d", "60m", "30m"}
    return False
