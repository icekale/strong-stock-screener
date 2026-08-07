from __future__ import annotations

import re
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
    """内存 job 注册表：完成任务会清理，防止字典与结果无限增长。

    - 最多同时 MAX_ACTIVE_JOBS 个进行中任务，超出抛 RuntimeError。
    - 已完成任务保留 MAX_FINISHED_JOBS 个（便于 API 短时间查回），更早的从内存清除。
    - 瞬时任务的大结果（选股 JSON）完成后不常驻内存，仅保留指向结果路径的引用。
    """

    MAX_ACTIVE_JOBS = 8
    MAX_FINISHED_JOBS = 50
    _JOB_TYPE_RE = re.compile(r"^[a-zA-Z0-9_:\-.]{1,64}$")

    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "gsgf_calibration"
        self.results_dir = self.root_dir / "results"
        self.latest_path = self.root_dir / "latest.json"
        self._lock = RLock()
        self._jobs: dict[str, BackgroundJobState] = {}
        self._cancel_events: dict[str, Event] = {}
        self._threads: dict[str, Thread] = {}

    def _register_job(
        self,
        *,
        job_type: str,
        message: str,
        progress_total: int,
        runner_target: Callable[..., object],
        runner_args: tuple[object, ...],
        thread_name: str,
    ) -> BackgroundJobState:
        self._prune_finished_locked()
        active = sum(
            1 for job in self._jobs.values() if job.status in {"pending", "running"}
        )
        if active >= self.MAX_ACTIVE_JOBS:
            raise RuntimeError(f"后台任务已达上限（{self.MAX_ACTIVE_JOBS} 个进行中），请稍后再试")
        job_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        state = BackgroundJobState(
            job_id=job_id,
            type=job_type,
            progress_total=max(1, progress_total),
            message=message,
        )
        cancel_event = Event()
        with self._lock:
            self._jobs[job_id] = state
            self._cancel_events[job_id] = cancel_event
            thread = Thread(
                target=runner_target,
                args=(job_id, *runner_args),
                name=thread_name,
                daemon=True,
            )
            self._threads[job_id] = thread
        thread.start()
        return self.get(job_id)

    def create_calibration_job(
        self,
        runner: CalibrationRunner,
        *,
        on_success: SuccessCallback | None = None,
    ) -> BackgroundJobState:
        return self._register_job(
            job_type="gsgf_calibration",
            message="等待执行",
            progress_total=1,
            runner_target=self._run_calibration,
            runner_args=(runner, on_success),
            thread_name="gsgf-calibration",
        )

    def create_transient_job(
        self,
        job_type: str,
        runner: TransientRunner,
        *,
        running_message: str,
        success_message: str,
        progress_total: int = 1,
    ) -> BackgroundJobState:
        if not self._JOB_TYPE_RE.fullmatch(job_type or ""):
            raise ValueError("后台任务类型仅允许小写字母、数字、下划线、冒号和短横线（最长 64 字符）")
        return self._register_job(
            job_type=job_type,
            message="等待执行",
            progress_total=progress_total,
            runner_target=self._run_transient,
            runner_args=(runner, running_message, success_message),
            thread_name=f"{job_type[:40]}",
        )

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
            current = self._jobs[job_id]
            if current.status not in {"pending", "running"}:
                return current.model_copy(deep=True)
            self._cancel_events[job_id].set()
            return current.model_copy(deep=True)

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
        on_success: SuccessCallback | None,
    ) -> None:
        cancel_event = self._cancel_events[job_id]
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
        finally:
            self._cleanup_finished_job(job_id)

    def _run_transient(
        self,
        job_id: str,
        runner: TransientRunner,
        running_message: str,
        success_message: str,
    ) -> None:
        cancel_event = self._cancel_events[job_id]
        self._set_state(job_id, status="running", started_at=_now(), message=running_message)

        def progress(current: int, total: int, message: str) -> None:
            self._set_state(
                job_id,
                progress_current=max(0, int(current)),
                progress_total=max(1, int(total)),
                message=message,
            )

        try:
            result = runner(progress, cancel_event.is_set)
            total = max(1, self.get(job_id).progress_total)
            self._set_state(
                job_id,
                status="success",
                progress_current=total,
                progress_total=total,
                message=success_message,
                finished_at=_now(),
                result=result if isinstance(result, dict) else None,
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
        finally:
            self._cleanup_finished_job(job_id)

    def _set_state(self, job_id: str, **updates: object) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(update=updates)

    def _cleanup_finished_job(self, job_id: str) -> None:
        """任务结束后移除线程与取消事件引用，并裁剪已完成任务保留数。"""
        with self._lock:
            self._threads.pop(job_id, None)
            self._cancel_events.pop(job_id, None)
            self._prune_finished_locked()

    def _prune_finished_locked(self) -> None:
        """在持锁状态下保留最近 MAX_FINISHED_JOBS 个已完成任务，其余从内存清除。"""
        finished_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status not in {"pending", "running"}
        ]
        for stale_id in finished_ids[:-self.MAX_FINISHED_JOBS] if len(finished_ids) > self.MAX_FINISHED_JOBS else []:
            self._jobs.pop(stale_id, None)
            self._threads.pop(stale_id, None)
            self._cancel_events.pop(stale_id, None)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
