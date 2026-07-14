from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Protocol

from app.models import (
    CzscResearchSnapshot,
    CzscSignalEvidenceSummary,
    CzscV2BatchResult,
    CzscV2CandidateScore,
)
from app.services.background_jobs import BackgroundJobStore, CancelCheck, ProgressCallback
from app.services.chanlun.research_store import ChanlunResearchStore


@dataclass(frozen=True)
class CzscShadowCandidate:
    symbol: str
    baseline_rank: int
    trade_date: str


class CzscResearchRunner(Protocol):
    def get(
        self,
        symbol: str,
        lookback: int,
        priority: int = 0,
        wait_seconds: float | None = None,
    ) -> CzscResearchSnapshot: ...


class CzscShadowSchedulerProtocol(Protocol):
    def submit(self, *, trade_date: str, candidates: list[CzscShadowCandidate]) -> str: ...


class CzscShadowScheduler:
    def __init__(
        self,
        *,
        jobs: BackgroundJobStore,
        store: ChanlunResearchStore,
        runner: CzscResearchRunner,
        hard_timeout_seconds: float = 15.0,
    ) -> None:
        self.jobs = jobs
        self.store = store
        self.runner = runner
        self.hard_timeout_seconds = hard_timeout_seconds

    def submit(self, *, trade_date: str, candidates: list[CzscShadowCandidate]) -> str:
        _validate_candidates(trade_date, candidates)
        ready = Event()
        job_id: str | None = None

        def run(progress: ProgressCallback, should_cancel: CancelCheck) -> dict[str, object]:
            ready.wait()
            assert job_id is not None
            result = self._run_batch(
                job_id=job_id,
                candidates=candidates,
                progress=progress,
                should_cancel=should_cancel,
            )
            return result.model_dump(mode="json")

        job = self.jobs.create_transient_job(
            "czsc_shadow",
            run,
            running_message="CZSC 影子评分运行中",
            success_message="CZSC 影子评分完成",
            progress_total=len(candidates),
        )
        job_id = job.job_id
        try:
            self.store.create_batch(job_id, trade_date, [item.symbol for item in candidates])
        finally:
            ready.set()
        return job_id

    def get(self, job_id: str) -> CzscV2BatchResult | None:
        return self.store.load_batch(job_id)

    def _run_batch(
        self,
        *,
        job_id: str,
        candidates: list[CzscShadowCandidate],
        progress: ProgressCallback,
        should_cancel: CancelCheck,
    ) -> CzscV2BatchResult:
        scores: list[CzscV2CandidateScore] = []
        for index, candidate in enumerate(candidates, start=1):
            if should_cancel():
                raise RuntimeError("CZSC 影子评分已取消")
            score = self._score_candidate(job_id, candidate)
            self.store.save_batch_score(job_id, score)
            scores.append(score)
            progress(index, len(candidates), f"CZSC 影子评分 {index}/{len(candidates)}")

        ranked_scores = _with_shadow_ranks(scores)
        for score in ranked_scores:
            self.store.save_batch_score(job_id, score)
        status = _batch_status(ranked_scores)
        self.store.finish_batch(job_id, status)
        result = self.store.load_batch(job_id)
        assert result is not None
        return result

    def _score_candidate(
        self,
        job_id: str,
        candidate: CzscShadowCandidate,
    ) -> CzscV2CandidateScore:
        try:
            snapshot = self.runner.get(
                candidate.symbol,
                lookback=220,
                priority=10,
                wait_seconds=self.hard_timeout_seconds,
            )
        except Exception:
            return CzscV2CandidateScore(
                symbol=candidate.symbol,
                status="unavailable",
                baseline_rank=candidate.baseline_rank,
                input_snapshot_id=f"shadow:{job_id}:{candidate.symbol}",
            )
        return CzscV2CandidateScore(
            symbol=candidate.symbol,
            status=snapshot.status,
            score=snapshot.score if snapshot.status == "ready" else None,
            eligible=snapshot.eligible if snapshot.status == "ready" else False,
            baseline_rank=candidate.baseline_rank,
            evidence=[_summary(event) for event in snapshot.events],
            input_snapshot_id=snapshot.input_snapshot_id,
            rule_version=snapshot.rule_version,
        )


def _validate_candidates(trade_date: str, candidates: list[CzscShadowCandidate]) -> None:
    if not 20 <= len(candidates) <= 60:
        raise ValueError("CZSC shadow candidate pool must contain 20 to 60 symbols")
    if [item.baseline_rank for item in candidates] != list(range(1, len(candidates) + 1)):
        raise ValueError("CZSC shadow baseline ranks must be consecutive and immutable")
    if len({item.symbol for item in candidates}) != len(candidates):
        raise ValueError("CZSC shadow candidate symbols must be unique")
    if any(item.trade_date != trade_date for item in candidates):
        raise ValueError("CZSC shadow candidate trade date must match its batch")


def _summary(event: object) -> CzscSignalEvidenceSummary:
    return CzscSignalEvidenceSummary.model_validate(
        {
            "id": event.id,
            "catalog_id": event.catalog_id,
            "family": event.family,
            "role": event.role,
            "direction": event.direction,
            "period": event.period,
            "higher_period": event.higher_period,
            "lower_period": event.lower_period,
            "occurred_at": event.occurred_at,
            "reason": event.reason,
        }
    )


def _with_shadow_ranks(scores: list[CzscV2CandidateScore]) -> list[CzscV2CandidateScore]:
    ordered = sorted(
        scores,
        key=lambda item: (
            0 if item.eligible else 1,
            -(item.score if item.score is not None else -1),
            item.baseline_rank,
        ),
    )
    ranks = {item.symbol: index for index, item in enumerate(ordered, start=1)}
    return [item.model_copy(update={"shadow_rank": ranks[item.symbol]}) for item in scores]


def _batch_status(scores: list[CzscV2CandidateScore]) -> str:
    ready_count = sum(item.status == "ready" and item.score is not None for item in scores)
    if ready_count == len(scores):
        return "ready"
    if ready_count:
        return "partial"
    return "unavailable"
