import copy
from typing import get_args

import pytest
from pydantic import ValidationError

from app.models import (
    CZSC_CATALOG_VERSION,
    CZSC_SCORE_RULE_VERSION,
    CzscResearchSnapshot,
    CzscSignalEvidence,
    CzscSignalEvidenceSummary,
    CzscV2BatchResult,
    CzscV2CandidateScore,
    ScreenStatus,
    StrongStockScreeningItem,
    StrongStockScreeningResult,
)


def _evidence() -> CzscSignalEvidence:
    return CzscSignalEvidence(
        id="buy3.structure.5m:2026-07-10T10:00:00+08:00:三买",
        catalog_id="buy3.structure",
        family="third_buy",
        role="primary",
        direction="bullish",
        period="5m",
        occurred_at="2026-07-10T10:00:00+08:00",
        last_closed_bar_at="2026-07-10T10:00:00+08:00",
        signal_name="cxt_third_buy_V230228",
        params={"di": 1},
        raw_key="5分钟_D1_三买辅助V230228",
        raw_value="三买_6笔_任意_0",
        reason="5分钟结构出现三买",
        input_snapshot_id="sha256:abc",
        engine_version="1.0.0rc8",
    )


def test_research_evidence_is_versioned_auditable_and_immutable() -> None:
    evidence = _evidence()

    assert evidence.catalog_version == CZSC_CATALOG_VERSION == "czsc-v2-catalog-1"
    assert evidence.rule_version == CZSC_SCORE_RULE_VERSION == "czsc-score-v2-rule-1"
    assert evidence.model_dump(mode="json")["params"] == {"di": 1}
    with pytest.raises(TypeError):
        evidence.params["di"] = 2


def test_research_evidence_params_are_recursively_immutable_and_deepcopy_safe() -> None:
    payload = _evidence().model_dump(mode="json")
    payload["params"] = {"filters": {"windows": [5, 9]}}
    evidence = CzscSignalEvidence.model_validate(payload)

    with pytest.raises(TypeError):
        evidence.params["filters"]["windows"][0] = 8

    copied = copy.deepcopy(evidence)
    assert copied.params == evidence.params
    assert copied.model_dump(mode="json")["params"] == {"filters": {"windows": [5, 9]}}


def test_research_snapshot_and_shadow_batch_keep_compact_evidence() -> None:
    evidence = _evidence()
    summary = CzscSignalEvidenceSummary(
        id=evidence.id,
        catalog_id=evidence.catalog_id,
        family=evidence.family,
        role=evidence.role,
        direction=evidence.direction,
        period=evidence.period,
        occurred_at=evidence.occurred_at,
        reason=evidence.reason,
    )
    snapshot = CzscResearchSnapshot(
        status="ready",
        symbol="300308.SZ",
        current_states=[evidence],
        events=[evidence],
        last_closed_by_period={
            "1d": "2026-07-09T15:00:00+08:00",
            "60m": "2026-07-10T10:30:00+08:00",
            "30m": "2026-07-10T10:00:00+08:00",
            "5m": evidence.last_closed_bar_at,
        },
        input_snapshot_id=evidence.input_snapshot_id,
        score=25,
        eligible=True,
        engine_version=evidence.engine_version,
        source_status=[],
    )
    candidate = CzscV2CandidateScore(
        symbol=snapshot.symbol,
        status=snapshot.status,
        score=snapshot.score,
        shadow_rank=1,
        eligible=snapshot.eligible,
        baseline_rank=3,
        evidence=[summary],
        input_snapshot_id=snapshot.input_snapshot_id,
    )
    batch = CzscV2BatchResult(
        batch_id="batch-1",
        job_id="job-1",
        status="ready",
        trade_date="2026-07-10",
        pool_size=1,
        completed_count=1,
        items=[candidate],
    )

    assert snapshot.catalog_version == CZSC_CATALOG_VERSION
    assert snapshot.rule_version == CZSC_SCORE_RULE_VERSION
    assert batch.items[0].evidence == [summary]


def test_ready_snapshot_requires_a_score_and_all_period_boundaries() -> None:
    base = {
        "status": "ready",
        "symbol": "300308.SZ",
        "input_snapshot_id": "sha256:abc",
        "engine_version": "1.0.0rc8",
        "score": 25,
        "last_closed_by_period": {
            "1d": "2026-07-09T15:00:00+08:00",
            "60m": "2026-07-10T10:30:00+08:00",
            "30m": "2026-07-10T10:00:00+08:00",
            "5m": "2026-07-10T10:00:00+08:00",
        },
    }

    with pytest.raises(ValidationError):
        CzscResearchSnapshot.model_validate({**base, "score": None})
    with pytest.raises(ValidationError):
        CzscResearchSnapshot.model_validate(
            {**base, "last_closed_by_period": {"5m": "2026-07-10T10:00:00+08:00"}}
        )


def test_shadow_models_reject_contradictory_ready_states() -> None:
    with pytest.raises(ValidationError):
        CzscV2CandidateScore(
            symbol="300308.SZ",
            status="ready",
            score=None,
            eligible=True,
            baseline_rank=1,
            input_snapshot_id="sha256:abc",
        )
    with pytest.raises(ValidationError):
        CzscV2BatchResult(
            batch_id="batch-1",
            job_id="job-1",
            status="ready",
            trade_date="2026-07-10",
            pool_size=2,
            completed_count=1,
        )
    with pytest.raises(ValidationError):
        CzscV2BatchResult(
            batch_id="batch-1",
            job_id="job-1",
            status="ready",
            trade_date="2026-07-10",
            pool_size=1,
            completed_count=1,
            items=[],
        )
    with pytest.raises(ValidationError):
        CzscV2BatchResult(
            batch_id="batch-1",
            job_id="job-1",
            status="partial",
            trade_date="2026-07-10",
            pool_size=1,
            completed_count=2,
        )


def test_screening_contract_adds_only_nullable_shadow_fields() -> None:
    item = StrongStockScreeningItem(
        symbol="300308.SZ",
        name="中际旭创",
        status="focus",
        score=88,
    )
    result = StrongStockScreeningResult(trade_date="2026-07-10", items=[item])

    assert set(get_args(ScreenStatus)) == {
        "focus",
        "wait_pullback",
        "reduce_risk",
        "data_incomplete",
    }
    assert item.czsc_score_v2 is None
    assert item.czsc_v2_eligible is None
    assert item.czsc_v2_shadow_rank is None
    assert item.czsc_v2_evidence is None
    assert item.czsc_v2_status is None
    assert item.czsc_v2_rule_version is None
    assert result.czsc_v2_job_id is None
    assert result.czsc_v2_status is None
