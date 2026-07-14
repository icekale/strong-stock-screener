from __future__ import annotations

from pathlib import Path
from threading import Event
from time import monotonic

from app.models import CzscResearchSnapshot
from app.services.background_jobs import BackgroundJobStore
from app.services.chanlun.research_store import ChanlunResearchStore
from app.services.chanlun.shadow_service import CzscShadowCandidate, CzscShadowScheduler


PERIOD_BOUNDARIES = {
    "1d": "2026-07-10T15:00:00+08:00",
    "60m": "2026-07-10T14:00:00+08:00",
    "30m": "2026-07-10T14:30:00+08:00",
    "5m": "2026-07-10T14:55:00+08:00",
}


class BlockingResearchRunner:
    def __init__(self, failing_symbols: set[str] | None = None) -> None:
        self.failing_symbols = failing_symbols or set()
        self.started = Event()
        self.release = Event()

    def get(
        self,
        symbol: str,
        lookback: int,
        priority: int = 0,
        wait_seconds: float | None = None,
    ) -> CzscResearchSnapshot:
        self.started.set()
        self.release.wait(timeout=2)
        if symbol in self.failing_symbols:
            raise RuntimeError("rc8 unavailable")
        return _snapshot(symbol)


def test_scheduler_returns_job_id_before_any_rc8_result(tmp_path: Path) -> None:
    blocking = BlockingResearchRunner()
    jobs = BackgroundJobStore(tmp_path)
    scheduler = CzscShadowScheduler(
        jobs=jobs,
        store=ChanlunResearchStore(tmp_path / "research.sqlite3"),
        runner=blocking,
    )

    started = monotonic()
    job_id = scheduler.submit(trade_date="2026-07-10", candidates=_shadow_inputs(20))

    assert monotonic() - started < 0.1
    assert job_id
    assert blocking.started.wait(timeout=1)
    blocking.release.set()
    jobs.wait(job_id)


def test_partial_batch_keeps_null_score_for_failed_symbol(tmp_path: Path) -> None:
    runner = BlockingResearchRunner(failing_symbols={"600001.SH"})
    runner.release.set()
    jobs = BackgroundJobStore(tmp_path)
    scheduler = CzscShadowScheduler(
        jobs=jobs,
        store=ChanlunResearchStore(tmp_path / "research.sqlite3"),
        runner=runner,
    )

    job_id = scheduler.submit(trade_date="2026-07-10", candidates=_shadow_inputs(20))
    jobs.wait(job_id)
    result = scheduler.get(job_id)
    assert result is not None
    by_symbol = {item.symbol: item for item in result.items}

    assert result.status == "partial"
    assert by_symbol["600001.SH"].score is None
    assert by_symbol["600002.SH"].score is not None


def _shadow_inputs(count: int) -> list[CzscShadowCandidate]:
    return [
        CzscShadowCandidate(
            symbol=f"600{index:03d}.SH",
            baseline_rank=index + 1,
            trade_date="2026-07-10",
        )
        for index in range(count)
    ]


def _snapshot(symbol: str) -> CzscResearchSnapshot:
    return CzscResearchSnapshot(
        status="ready",
        symbol=symbol,
        last_closed_by_period=PERIOD_BOUNDARIES,
        input_snapshot_id=f"sha256:{symbol}",
        score=80,
        eligible=True,
        engine_version="1.0.0rc8",
    )
