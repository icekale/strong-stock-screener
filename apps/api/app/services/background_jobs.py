from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Callable
from uuid import uuid4

from app.models import BackgroundJobState, BackgroundJobStatus, GsgfRealCalibrationSummary

ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]
CalibrationRunner = Callable[[ProgressCallback, CancelCheck], GsgfRealCalibrationSummary]
TransientRunner = Callable[[ProgressCallback, CancelCheck], object]
SuccessCallback = Callable[[GsgfRealCalibrationSummary], object]


class BackgroundJobStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "gsgf_calibration"
        self.results_dir = self.root_dir / "results"
        self.latest_path = self.root_dir / "latest.json"
        self._lock = RLock()
        self._jobs: dict[str, BackgroundJobState] = {}
        self._cancel_events: dict[str, Event] = {}
        self._threads: dict[str, Thread] = {}

    def create_calibration_job(
        self,
        runner: CalibrationRunner,
        *,
        on_success: SuccessCallback | None = None,
    ) -> BackgroundJobState:
        job_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        state = BackgroundJobState(job_id=job_id, type="gsgf_calibration", progress_total=1)
        cancel_event = Event()
        with self._lock:
            self._jobs[job_id] = state
            self._cancel_events[job_id] = cancel_event
        thread = Thread(
            target=self._run_calibration,
            args=(job_id, runner, cancel_event, on_success),
            name=f"gsgf-calibration-{job_id}",
            daemon=True,
        )
        with self._lock:
            self._threads[job_id] = thread
        thread.start()
        return self.get(job_id)

    def create_transient_job(
        self,
        job_type: str,
        runner: TransientRunner,
        *,
        running_message: str,
        success_message: str,
        progress_total: int = 1,
    ) -> BackgroundJobState:
        job_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        state = BackgroundJobState(
            job_id=job_id,
            type=job_type,
            progress_total=max(1, progress_total),
            message="等待执行",
        )
        cancel_event = Event()
        with self._lock:
            self._jobs[job_id] = state
            self._cancel_events[job_id] = cancel_event
        thread = Thread(
            target=self._run_transient,
            args=(job_id, runner, cancel_event, running_message, success_message),
            name=f"{job_type}-{job_id}",
            daemon=True,
        )
        with self._lock:
            self._threads[job_id] = thread
        thread.start()
        return self.get(job_id)

    def get(self, job_id: str) -> BackgroundJobState:
        with self._lock:
            return self._jobs[job_id].model_copy(deep=True)

    def get_active(self, job_type: str) -> BackgroundJobState | None:
        with self._lock:
            for job in reversed(list(self._jobs.values())):
                if job.type == job_type and job.status in {"pending", "running"}:
                    return job.model_copy(deep=True)
        return None

    def cancel(self, job_id: str) -> BackgroundJobState:
        with self._lock:
            self._cancel_events[job_id].set()
        return self.get(job_id)

    def wait(self, job_id: str, timeout: float = 10) -> None:
        thread = self._threads.get(job_id)
        if thread is not None:
            thread.join(timeout=timeout)

    def load_latest_calibration(self) -> GsgfRealCalibrationSummary | None:
        if not self.latest_path.exists():
            return None
        return GsgfRealCalibrationSummary.model_validate_json(
            self.latest_path.read_text(encoding="utf-8")
        )

    def _run_calibration(
        self,
        job_id: str,
        runner: CalibrationRunner,
        cancel_event: Event,
        on_success: SuccessCallback | None,
    ) -> None:
        self._set_state(job_id, status="running", started_at=_now(), message="校准任务运行中")

        def progress(current: int, total: int, message: str) -> None:
            self._set_state(
                job_id,
                progress_current=max(0, int(current)),
                progress_total=max(1, int(total)),
                message=message,
            )

        try:
            result = runner(progress, cancel_event.is_set)
            self.results_dir.mkdir(parents=True, exist_ok=True)
            result_path = self.results_dir / f"{job_id}.json"
            payload = result.model_dump_json(indent=2)
            result_path.write_text(payload, encoding="utf-8")
            self.latest_path.write_text(payload, encoding="utf-8")
            if on_success is not None:
                try:
                    on_success(result)
                except Exception:
                    pass
            total = max(1, self.get(job_id).progress_total)
            self._set_state(
                job_id,
                status="success",
                progress_current=total,
                progress_total=total,
                message="校准任务完成",
                finished_at=_now(),
                result_path=str(result_path),
            )
        except Exception as exc:
            status: BackgroundJobStatus = "canceled" if cancel_event.is_set() else "failed"
            self._set_state(
                job_id,
                status=status,
                error=str(exc),
                message="校准任务已取消" if status == "canceled" else "校准任务失败",
                finished_at=_now(),
            )

    def _run_transient(
        self,
        job_id: str,
        runner: TransientRunner,
        cancel_event: Event,
        running_message: str,
        success_message: str,
    ) -> None:
        self._set_state(job_id, status="running", started_at=_now(), message=running_message)

        def progress(current: int, total: int, message: str) -> None:
            self._set_state(
                job_id,
                progress_current=max(0, int(current)),
                progress_total=max(1, int(total)),
                message=message,
            )

        try:
            runner(progress, cancel_event.is_set)
            total = max(1, self.get(job_id).progress_total)
            self._set_state(
                job_id,
                status="success",
                progress_current=total,
                progress_total=total,
                message=success_message,
                finished_at=_now(),
            )
        except Exception as exc:
            status: BackgroundJobStatus = "canceled" if cancel_event.is_set() else "failed"
            self._set_state(
                job_id,
                status=status,
                error=str(exc),
                message="任务已取消" if status == "canceled" else "任务失败",
                finished_at=_now(),
            )

    def _set_state(self, job_id: str, **updates: object) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(update=updates)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
