from app.models import CzscSignalEvidence
from app.services.chanlun.research_catalog import map_raw_state
from app.services.chanlun.research_scoring import score_czsc_v2


FRESH = {period: "fresh" for period in ("1d", "60m", "30m", "5m")}


def _evidence(
    catalog_id: str,
    family: str,
    role: str,
    direction: str,
    *,
    period: str | None = None,
    higher_period: str | None = None,
    lower_period: str | None = None,
    v1: str,
    v2: str = "任意",
) -> CzscSignalEvidence:
    scope = period or f"{higher_period}-{lower_period}"
    return CzscSignalEvidence(
        id=f"{catalog_id}.{scope}:2026-07-10T10:00:00+08:00:{v1}",
        catalog_id=catalog_id,
        family=family,
        role=role,
        direction=direction,
        period=period,
        higher_period=higher_period,
        lower_period=lower_period,
        occurred_at="2026-07-10T10:00:00+08:00",
        last_closed_bar_at="2026-07-10T10:00:00+08:00",
        signal_name=catalog_id,
        params={"v1": v1, "v2": v2, "v3": "任意", "score": 0},
        raw_key="audit-key",
        raw_value="audit-value",
        reason="test evidence",
        input_snapshot_id="sha256:abc",
        engine_version="1.0.0rc8",
    )


def _trend(catalog_id: str, period: str, *, v2: str = "延伸") -> CzscSignalEvidence:
    return _evidence(
        catalog_id,
        "trend_context",
        "primary",
        "bullish",
        period=period,
        v1="向上",
        v2=v2,
    )


def _zone(higher_period: str, lower_period: str) -> CzscSignalEvidence:
    return _evidence(
        "zone.resonance",
        "zone_confluence",
        "primary",
        "bullish",
        higher_period=higher_period,
        lower_period=lower_period,
        v1="看多",
    )


def _buy(family: str, role: str) -> CzscSignalEvidence:
    is_third = family == "third_buy"
    catalog_id = (
        "buy3.structure"
        if is_third and role == "primary"
        else "buy3.ma-confirm"
        if is_third
        else "buy2.overlap"
        if role == "primary"
        else "buy2.ma-confirm"
    )
    return _evidence(
        catalog_id,
        family,
        role,
        "bullish",
        period="5m",
        v1="三买" if is_third else "二买",
    )


def _complete_bullish_evidence() -> list[CzscSignalEvidence]:
    return [
        _trend("trend.bi-status", "1d"),
        _trend("trend.bi-base", "1d", v2="中继"),
        _trend("trend.bi-status", "60m"),
        _trend("trend.bi-base", "60m", v2="中继"),
        _trend("trend.bi-status", "30m"),
        _trend("trend.bi-base", "30m", v2="中继"),
        _zone("1d", "60m"),
        _zone("60m", "30m"),
        _buy("third_buy", "primary"),
        _buy("third_buy", "confirmation"),
    ]


def _risk(family: str, period: str) -> CzscSignalEvidence:
    common = {
        "symbol": "300308.SZ",
        "raw_key": "audit-key",
        "raw_value": "audit-value",
        "occurred_at": "2026-07-10T10:00:00+08:00",
        "last_closed_bar_at": "2026-07-10T10:00:00+08:00",
        "input_snapshot_id": "sha256:abc",
        "engine_version": "1.0.0rc8",
    }
    if family == "divergence":
        result = map_raw_state(
            **common,
            catalog_id="risk.macd-divergence",
            period=period,
            value_fields={"v1": "顶背驰", "v2": "第1次", "v3": "任意", "score": 0},
        )
    elif period == "5m":
        result = map_raw_state(
            **common,
            catalog_id="buy3.ma-confirm",
            period="5m",
            value_fields={"v1": "三卖", "v2": "均线新低", "v3": "任意", "score": 0},
        )
    elif period in {"1d", "60m"}:
        result = map_raw_state(
            **common,
            catalog_id="zone.resonance",
            higher_period=period,
            lower_period="60m" if period == "1d" else "30m",
            value_fields={"v1": "看空", "v2": "任意", "v3": "任意", "score": 0},
        )
    else:
        raise ValueError(f"no approved sell-risk fixture for {period}")
    assert result is not None
    return result


def test_score_reaches_100_for_complete_trend_continuation() -> None:
    result = score_czsc_v2(evidence=_complete_bullish_evidence(), freshness=FRESH)

    assert result.score == 100
    assert result.eligible is True
    assert result.rule_version == "czsc-score-v2-rule-1"


def test_score_applies_one_risk_penalty_per_period() -> None:
    result = score_czsc_v2(
        evidence=[*_complete_bullish_evidence(), _risk("divergence", "1d"), _risk("sell_risk", "1d")],
        freshness=FRESH,
    )

    assert result.score == 70
    assert result.eligible is False


def test_missing_or_stale_period_produces_null_score() -> None:
    result = score_czsc_v2(
        evidence=_complete_bullish_evidence(),
        freshness={"1d": "fresh", "60m": "fresh", "30m": "stale", "5m": "fresh"},
    )

    assert result.score is None
    assert result.eligible is False


def test_trigger_bucket_uses_the_best_primary_and_matching_confirmation() -> None:
    result = score_czsc_v2(
        evidence=[
            _buy("second_buy", "primary"),
            _buy("second_buy", "confirmation"),
            _buy("third_buy", "primary"),
        ],
        freshness=FRESH,
    )

    assert result.score == 25
    assert result.eligible is True


def test_risk_penalties_are_capped_by_period_and_total_score_has_a_floor() -> None:
    result = score_czsc_v2(
        evidence=[
            _risk("divergence", "1d"),
            _risk("sell_risk", "60m"),
            _risk("divergence", "30m"),
            _risk("sell_risk", "5m"),
        ],
        freshness=FRESH,
    )

    assert result.score == 0
    assert result.eligible is False


def test_five_minute_divergence_is_observed_without_sell_penalty() -> None:
    result = score_czsc_v2(
        evidence=[*_complete_bullish_evidence(), _risk("divergence", "5m")],
        freshness=FRESH,
    )

    assert result.score == 100
    assert result.eligible is True


def test_duplicate_positive_evidence_does_not_inflate_score() -> None:
    evidence = [
        _trend("trend.bi-status", "1d"),
        _zone("1d", "60m"),
        _buy("second_buy", "primary"),
        _buy("second_buy", "confirmation"),
    ]

    single = score_czsc_v2(evidence=evidence, freshness=FRESH)
    duplicated = score_czsc_v2(evidence=[*evidence, *evidence], freshness=FRESH)

    assert single.score == duplicated.score == 42
    assert single.eligible is duplicated.eligible is True
