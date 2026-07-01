from pathlib import Path
from threading import Event

from app.models import GsgfRealCalibrationSummary
from app.services.background_jobs import BackgroundJobStore


def test_background_job_store_runs_successful_calibration_and_saves_latest(
    tmp_path: Path,
) -> None:
    store = BackgroundJobStore(tmp_path)

    job = store.create_calibration_job(
        lambda progress, should_cancel: GsgfRealCalibrationSummary(
            trade_dates=["2026-06-24"],
            windows=[1, 3],
            scanned_count=2,
            target_sample_count=1,
        )
    )
    store.wait(job.job_id, timeout=3)

    loaded = store.get(job.job_id)
    latest = store.load_latest_calibration()

    assert loaded.status == "success"
    assert loaded.progress_current == loaded.progress_total
    assert latest is not None
    assert latest.scanned_count == 2


def test_background_job_store_records_failure(tmp_path: Path) -> None:
    store = BackgroundJobStore(tmp_path)

    def fail(_progress, _should_cancel):
        raise RuntimeError("boom")

    job = store.create_calibration_job(fail)
    store.wait(job.job_id, timeout=3)

    loaded = store.get(job.job_id)

    assert loaded.status == "failed"
    assert "boom" in (loaded.error or "")


def test_background_job_store_calls_success_callback(tmp_path: Path) -> None:
    store = BackgroundJobStore(tmp_path)
    notifications: list[int] = []

    job = store.create_calibration_job(
        lambda _progress, _should_cancel: GsgfRealCalibrationSummary(scanned_count=3),
        on_success=lambda result: notifications.append(result.scanned_count),
    )
    store.wait(job.job_id, timeout=3)

    assert notifications == [3]


def test_background_job_store_marks_cancel_requested(tmp_path: Path) -> None:
    store = BackgroundJobStore(tmp_path)
    started = Event()
    continue_run = Event()

    def run(progress, should_cancel):
        progress(0, 1, "started")
        started.set()
        continue_run.wait(timeout=3)
        assert should_cancel() is True
        raise RuntimeError("校准任务已取消")

    job = store.create_calibration_job(run)
    assert started.wait(timeout=3) is True
    store.cancel(job.job_id)
    continue_run.set()
    store.wait(job.job_id, timeout=3)

    loaded = store.get(job.job_id)

    assert loaded.status == "canceled"
    assert "取消" in (loaded.error or "")
