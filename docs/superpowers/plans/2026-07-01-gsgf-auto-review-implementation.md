# GSGF Auto Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GSGF signal review and real TickFlow calibration automatic, persistent, progress-aware, and notification-ready.

**Architecture:** Extend the existing FastAPI screener app with small focused services: review persistence stays in `gsgf_review.py`, long-running calibration jobs live in a lightweight `background_jobs.py`, automatic daily/weekly scheduling lives in `gsgf_auto_review.py`. The Next.js home page reads latest persisted review/calibration results and starts calibration through job APIs instead of blocking on a synchronous request.

**Tech Stack:** FastAPI, Pydantic, pytest, Ruff, Next.js, TypeScript, Ant Design, existing notification channel service, TickFlow K-line provider.

---

## File Structure

- Modify `apps/api/app/models.py`
  - Add calibration job models, model-health summary, and auto-review config payload models.
- Modify `apps/api/app/services/gsgf_review.py`
  - Add deduplicated snapshot persistence and latest review summary save/load helpers.
- Modify `apps/api/app/services/gsgf_real_calibration.py`
  - Add typed progress callback and cancellation check hook.
- Create `apps/api/app/services/background_jobs.py`
  - Manage in-memory job lifecycle, result persistence, latest calibration file, and soft cancellation.
- Create `apps/api/app/services/gsgf_auto_review.py`
  - Run daily review and weekly calibration checks in a daemon thread using runtime config.
- Create `apps/api/app/services/gsgf_model_health.py`
  - Derive best, weak, insufficient, and degraded GSGF signals from review/calibration summaries.
- Modify `apps/api/app/services/runtime_settings.py`
  - Add `gsgf_auto_review` config to runtime settings and public settings payload.
- Modify `apps/api/app/main.py`
  - Auto-save snapshots after screen runs, add latest review/calibration/job APIs, and start/stop auto-review service on app lifespan.
- Modify `apps/api/tests/test_gsgf_review.py`
  - Cover dedupe and latest summary persistence.
- Add `apps/api/tests/test_background_jobs.py`
  - Cover job success, failure, progress, latest result, and cancellation.
- Modify `apps/api/tests/test_api.py`
  - Cover new endpoints and screen-run auto snapshot.
- Modify `apps/api/tests/test_sentiment_monitor.py` or add `apps/api/tests/test_gsgf_auto_review.py`
  - Cover scheduler run-once behavior with fake time/config/notifier.
- Add `apps/api/tests/test_gsgf_model_health.py`
  - Cover conservative signal health and degradation classification.
- Modify `apps/web/lib/types.ts`
  - Add job, latest result, model health, and auto-review config types.
- Modify `apps/web/lib/api.ts`
  - Add latest review/latest calibration/job APIs and settings payload updates.
- Modify `apps/web/app/HomeWorkbench.tsx`
  - Load latest review/calibration on startup and poll calibration jobs.
- Modify `apps/web/components/screener/GsgfWorkflowPanels.tsx`
  - Display automatic review status and background calibration progress.
- Modify `apps/web/app/settings/SettingsWorkspace.tsx`
  - Add editable GSGF auto-review settings.
- Modify `apps/web/lib/strongStockWorkbench.test.ts`
  - Add source-level assertions for new frontend wiring.

---

### Task 1: Review Store Dedupe And Latest Summary

**Files:**
- Modify: `apps/api/app/services/gsgf_review.py`
- Modify: `apps/api/tests/test_gsgf_review.py`

- [ ] **Step 1: Write failing tests for dedupe and latest summary**

Add tests to `apps/api/tests/test_gsgf_review.py`:

```python
def test_gsgf_review_store_dedupes_snapshot_records(tmp_path: Path) -> None:
    store = GsgfReviewStore(tmp_path)
    result = _screen_result()

    first = store.persist_snapshot(result, dedupe=True)
    second = store.persist_snapshot(result, dedupe=True)

    assert first.saved_count == 1
    assert second.saved_count == 0
    assert len(store.load_records()) == 1


def test_gsgf_review_store_saves_and_loads_latest_summary(tmp_path: Path) -> None:
    store = GsgfReviewStore(tmp_path)
    store.persist_snapshot(_screen_result(), dedupe=True)
    summary = store.recheck_snapshots({"603890.SH": _bars([10, 10.4, 10.7, 10.2])}, windows=[1, 3])

    store.save_latest_summary(summary)
    loaded = store.load_latest_summary()

    assert loaded is not None
    assert loaded.record_count == 1
    assert loaded.windows == [1, 3]
    assert (tmp_path / "gsgf_review" / "latest_summary.json").exists()
```

Add helper:

```python
def _screen_result() -> StrongStockScreeningResult:
    return StrongStockScreeningResult(
        trade_date="2026-06-11",
        strategy="gsgf",
        gsgf_model_version="gsgf-v2",
        sort_version="gsgf-sort-v1",
        items=[
            StrongStockScreeningItem(
                symbol="603890.SH",
                name="春秋电子",
                industry="消费电子",
                status="focus",
                score=90,
                gsgf=GsgfAnalysis(
                    total_score=82,
                    final_status="确认买点",
                    action="strong_candidate",
                    zone="a_zone",
                    setup_type="B区A点",
                    confirm_type="放量突破确认",
                ),
            )
        ],
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_review.py -q
```

Expected: fail because `persist_snapshot(..., dedupe=True)`, `save_latest_summary`, and `load_latest_summary` do not exist.

- [ ] **Step 3: Implement dedupe and latest summary persistence**

Change `GsgfReviewStore.persist_snapshot` signature:

```python
def persist_snapshot(
    self,
    result: StrongStockScreeningResult,
    *,
    dedupe: bool = False,
) -> GsgfReviewSnapshotResponse:
```

Add:

```python
@property
def latest_summary_path(self) -> Path:
    return self.root_dir / "latest_summary.json"

def save_latest_summary(self, summary: GsgfReviewSummary) -> None:
    self.root_dir.mkdir(parents=True, exist_ok=True)
    self.latest_summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

def load_latest_summary(self) -> GsgfReviewSummary | None:
    if not self.latest_summary_path.exists():
        return None
    return GsgfReviewSummary.model_validate_json(self.latest_summary_path.read_text(encoding="utf-8"))
```

For dedupe, build existing keys from `load_records()`:

```python
def _record_key(record: GsgfReviewRecord) -> tuple[str, str, str, str]:
    return (record.trade_date, record.symbol, record.signal_type, record.status)
```

When `dedupe=True`, only append records whose key is absent.

- [ ] **Step 4: Verify tests pass**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_review.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/gsgf_review.py apps/api/tests/test_gsgf_review.py
git commit -m "feat: persist latest gsgf review summary"
```

---

### Task 2: Calibration Progress And Background Jobs

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/services/gsgf_real_calibration.py`
- Create: `apps/api/app/services/background_jobs.py`
- Add: `apps/api/tests/test_background_jobs.py`

- [ ] **Step 1: Write failing service tests**

Create `apps/api/tests/test_background_jobs.py`:

```python
from pathlib import Path

from app.models import GsgfRealCalibrationSummary
from app.services.background_jobs import BackgroundJobStore


def test_background_job_store_runs_successful_calibration_and_saves_latest(tmp_path: Path) -> None:
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

    job = store.create_calibration_job(lambda _progress, _should_cancel: (_ for _ in ()).throw(RuntimeError("boom")))
    store.wait(job.job_id, timeout=3)

    loaded = store.get(job.job_id)

    assert loaded.status == "failed"
    assert "boom" in (loaded.error or "")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_background_jobs.py -q
```

Expected: fail because `background_jobs.py` does not exist.

- [ ] **Step 3: Add job models**

In `apps/api/app/models.py` add:

```python
BackgroundJobStatus = Literal["pending", "running", "success", "failed", "canceled"]


class BackgroundJobState(BaseModel):
    job_id: str
    type: str
    status: BackgroundJobStatus = "pending"
    progress_current: int = 0
    progress_total: int = 0
    message: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    result_path: str | None = None
```

- [ ] **Step 4: Implement `BackgroundJobStore`**

Create `apps/api/app/services/background_jobs.py` with:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Callable
from uuid import uuid4

from app.models import BackgroundJobState, GsgfRealCalibrationSummary

ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]
CalibrationRunner = Callable[[ProgressCallback, CancelCheck], GsgfRealCalibrationSummary]


class BackgroundJobStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "gsgf_calibration"
        self.results_dir = self.root_dir / "results"
        self.latest_path = self.root_dir / "latest.json"
        self._lock = RLock()
        self._jobs: dict[str, BackgroundJobState] = {}
        self._cancel_events: dict[str, Event] = {}
        self._threads: dict[str, Thread] = {}

    def create_calibration_job(self, runner: CalibrationRunner) -> BackgroundJobState:
        job_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        state = BackgroundJobState(job_id=job_id, type="gsgf_calibration", progress_total=1)
        cancel_event = Event()
        with self._lock:
            self._jobs[job_id] = state
            self._cancel_events[job_id] = cancel_event
        thread = Thread(target=self._run_calibration, args=(job_id, runner, cancel_event), daemon=True)
        with self._lock:
            self._threads[job_id] = thread
        thread.start()
        return self.get(job_id)

    def get(self, job_id: str) -> BackgroundJobState:
        with self._lock:
            return self._jobs[job_id].model_copy(deep=True)

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
        return GsgfRealCalibrationSummary.model_validate_json(self.latest_path.read_text(encoding="utf-8"))
```

Implement private `_run_calibration`, `_set_state`, and `_now` helpers in the same file. `_run_calibration` must set `running`, call `runner(progress, should_cancel)`, write `{job_id}.json`, copy the same JSON to `latest.json`, then set `success`. On exception it sets `failed`.

- [ ] **Step 5: Add calibration progress/cancel hooks**

In `gsgf_real_calibration.py`, change:

```python
ProgressReporter = Callable[[str], None]
```

to:

```python
ProgressReporter = Callable[[int, int, str], None]
CancelChecker = Callable[[], bool]
```

Change `summarize_gsgf_real_calibration` args:

```python
progress: ProgressReporter | None = None,
should_cancel: CancelChecker | None = None,
```

Update reporting calls to pass `(scanned_count, progress_total, message)`, with `progress_total = len(deduped_dates) * scan_limit`. Before each candidate, check:

```python
if should_cancel is not None and should_cancel():
    raise RuntimeError("校准任务已取消")
```

- [ ] **Step 6: Verify tests pass**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_background_jobs.py tests/test_gsgf_real_calibration.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/models.py apps/api/app/services/background_jobs.py apps/api/app/services/gsgf_real_calibration.py apps/api/tests/test_background_jobs.py
git commit -m "feat: run gsgf calibration as background job"
```

---

### Task 3: API Endpoints And Screen-Run Auto Snapshot

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests to `apps/api/tests/test_api.py`:

```python
def test_screen_run_auto_saves_gsgf_review_snapshot(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/screen/runs",
        json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"},
    )

    assert response.status_code == 200
    records = (tmp_path / "gsgf_review" / "snapshots.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(records) > 0


def test_gsgf_review_latest_endpoint_returns_persisted_summary(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/api/screen/runs", json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 10, "strategy": "gsgf"})
    client.post("/api/gsgf/review/recheck", json={"windows": [1, 3], "count": 90})

    response = client.get("/api/gsgf/review/latest")

    assert response.status_code == 200
    assert response.json()["record_count"] > 0


def test_gsgf_calibration_job_endpoint_returns_job_status(tmp_path: Path) -> None:
    client = _client(tmp_path, kline_provider=FakeCalibrationKlineProvider())

    response = client.post(
        "/api/gsgf/calibration/jobs",
        json={"trade_dates": ["2026-01-28"], "windows": [1, 3], "scan_limit": 2, "count": 90},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "gsgf_calibration"
    assert payload["job_id"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_api.py::test_screen_run_auto_saves_gsgf_review_snapshot tests/test_api.py::test_gsgf_review_latest_endpoint_returns_persisted_summary tests/test_api.py::test_gsgf_calibration_job_endpoint_returns_job_status -q
```

Expected: fail because auto snapshot and endpoints do not exist.

- [ ] **Step 3: Auto-save snapshots after `/api/screen/runs`**

In `create_screen_run`, after saving the run result, call:

```python
if any(item.gsgf is not None for item in result.items):
    _gsgf_review_store().persist_snapshot(result, dedupe=True)
```

Keep manual `/api/gsgf/review/snapshots/latest` unchanged, except pass `dedupe=True`.

- [ ] **Step 4: Persist latest review summary**

In `recheck_gsgf_review`, after building `summary`, call:

```python
store.save_latest_summary(summary)
```

Add:

```python
@app.get("/api/gsgf/review/latest")
def get_latest_gsgf_review() -> dict[str, object]:
    summary = _gsgf_review_store().load_latest_summary()
    if summary is None:
        raise HTTPException(status_code=404, detail="no gsgf review summary")
    return summary.model_dump(mode="json")
```

- [ ] **Step 5: Add calibration job endpoints**

Add:

```python
@app.post("/api/gsgf/calibration/jobs")
def create_gsgf_calibration_job(request: GsgfCalibrationRequest) -> dict[str, object]:
    store = _background_job_store()
    job = store.create_calibration_job(
        lambda progress, should_cancel: summarize_gsgf_real_calibration(
            candidate_provider=_candidate_provider(),
            kline_provider=_kline_provider(),
            trade_dates=request.trade_dates,
            windows=request.windows,
            scan_limit=request.scan_limit,
            kline_count=request.count,
            progress=progress,
            should_cancel=should_cancel,
        )
    )
    return job.model_dump(mode="json")
```

Add `GET /api/gsgf/calibration/jobs/{job_id}`, `POST /api/gsgf/calibration/jobs/{job_id}/cancel`, and `GET /api/gsgf/calibration/latest`.

- [ ] **Step 6: Verify tests pass**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_api.py::test_screen_run_auto_saves_gsgf_review_snapshot tests/test_api.py::test_gsgf_review_latest_endpoint_returns_persisted_summary tests/test_api.py::test_gsgf_calibration_job_endpoint_returns_job_status -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_api.py
git commit -m "feat: expose gsgf review and calibration job apis"
```

---

### Task 4: Auto Review Runtime Config And Scheduler

**Files:**
- Modify: `apps/api/app/services/runtime_settings.py`
- Create: `apps/api/app/services/gsgf_auto_review.py`
- Add: `apps/api/tests/test_gsgf_auto_review.py`

- [ ] **Step 1: Write failing scheduler tests**

Create `apps/api/tests/test_gsgf_auto_review.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.gsgf_auto_review import GsgfAutoReviewConfig, GsgfAutoReviewService


def test_auto_review_runs_daily_review_once_after_configured_time() -> None:
    calls: list[str] = []
    service = GsgfAutoReviewService(
        config_loader=lambda: GsgfAutoReviewConfig(daily_review_enabled=True, weekly_calibration_enabled=False),
        review_runner=lambda: calls.append("review"),
        calibration_runner=lambda _dates, _windows, _scan_limit, _count: calls.append("calibration"),
        recent_trade_dates=lambda count: ["2026-06-24"][:count],
        notifier=lambda _title, _message: None,
        now_fn=lambda: datetime(2026, 7, 1, 15, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    service.run_once()
    service.run_once()

    assert calls == ["review"]
```

Add a second test for weekly calibration:

```python
def test_auto_review_runs_weekly_calibration_once() -> None:
    calls: list[tuple[list[str], list[int], int, int]] = []
    service = GsgfAutoReviewService(
        config_loader=lambda: GsgfAutoReviewConfig(
            daily_review_enabled=False,
            weekly_calibration_enabled=True,
            weekly_calibration_weekday=5,
            weekly_calibration_time="16:10",
            weekly_calibration_trade_days=2,
            weekly_calibration_scan_limit=80,
            windows=[1, 3, 5, 10],
            kline_count=260,
        ),
        review_runner=lambda: None,
        calibration_runner=lambda dates, windows, scan_limit, count: calls.append((dates, windows, scan_limit, count)),
        recent_trade_dates=lambda count: ["2026-06-25", "2026-06-26"][:count],
        notifier=lambda _title, _message: None,
        now_fn=lambda: datetime(2026, 7, 3, 16, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    service.run_once()
    service.run_once()

    assert calls == [(["2026-06-25", "2026-06-26"], [1, 3, 5, 10], 80, 260)]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_auto_review.py -q
```

Expected: fail because `gsgf_auto_review.py` does not exist.

- [ ] **Step 3: Implement config model**

In `gsgf_auto_review.py` define:

```python
class GsgfAutoReviewConfig(BaseModel):
    auto_snapshot_enabled: bool = True
    daily_review_enabled: bool = True
    daily_review_time: str = "15:40"
    weekly_calibration_enabled: bool = True
    weekly_calibration_weekday: int = Field(default=5, ge=1, le=7)
    weekly_calibration_time: str = "16:10"
    weekly_calibration_trade_days: int = Field(default=5, ge=1, le=20)
    weekly_calibration_scan_limit: int = Field(default=80, ge=1, le=300)
    windows: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    kline_count: int = Field(default=260, ge=70, le=260)
    notify_on_success: bool = True
    notify_on_degradation: bool = True
```

- [ ] **Step 4: Implement `GsgfAutoReviewService`**

Implement a daemon-thread service similar to `SentimentMonitor`:

```python
class GsgfAutoReviewService:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def run_once(self) -> None: ...
```

Track `_last_daily_review_key` as `YYYY-MM-DD` and `_last_weekly_calibration_key` as `YYYY-Www`. Only run once per key after configured local time.

- [ ] **Step 5: Wire config into runtime settings**

In `runtime_settings.py`:

- Import `GsgfAutoReviewConfig`.
- Add `gsgf_auto_review: GsgfAutoReviewConfig = Field(default_factory=GsgfAutoReviewConfig)` to `RuntimeSettings` and `SettingsUpdate`.
- Save and expose it in `public_settings_payload`.

- [ ] **Step 6: Verify tests pass**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_auto_review.py tests/test_api.py::test_runtime_settings_roundtrip -q
```

If `test_runtime_settings_roundtrip` does not exist, run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_api.py -k runtime -q
```

Expected: all relevant tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/services/gsgf_auto_review.py apps/api/app/services/runtime_settings.py apps/api/tests/test_gsgf_auto_review.py apps/api/tests/test_api.py
git commit -m "feat: schedule automatic gsgf review"
```

---

### Task 5: Wire Auto Service Into FastAPI

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Add API tests for settings payload**

Add to `apps/api/tests/test_api.py`:

```python
def test_runtime_settings_exposes_gsgf_auto_review_config(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["gsgf_auto_review"]["daily_review_time"] == "15:40"
    assert payload["config"]["gsgf_auto_review"]["weekly_calibration_scan_limit"] == 80
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_api.py::test_runtime_settings_exposes_gsgf_auto_review_config -q
```

Expected: fail until payload includes `gsgf_auto_review`.

- [ ] **Step 3: Add service factory helpers in `main.py`**

Add helpers:

```python
def _background_job_store() -> BackgroundJobStore:
    existing = getattr(app.state, "background_job_store", None)
    if existing is not None:
        return existing
    store = BackgroundJobStore(get_settings().data_dir)
    app.state.background_job_store = store
    return store
```

Add `_gsgf_auto_review_service()` that constructs `GsgfAutoReviewService` with:

- config loader from runtime settings.
- review runner that rechecks snapshots, saves latest summary, and evaluates health.
- calibration runner that creates a background calibration job.
- recent trade dates from latest screen runs.
- notifier using `send_notification_message`.

- [ ] **Step 4: Start service on app startup**

Use existing FastAPI lifecycle pattern in `main.py`. If no lifespan exists, add startup/shutdown events:

```python
@app.on_event("startup")
def start_background_services() -> None:
    _gsgf_auto_review_service().start()


@app.on_event("shutdown")
def stop_background_services() -> None:
    _gsgf_auto_review_service().stop()
```

- [ ] **Step 5: Verify tests pass**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_api.py::test_runtime_settings_exposes_gsgf_auto_review_config tests/test_api.py::test_gsgf_calibration_job_endpoint_returns_job_status -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_api.py
git commit -m "feat: start gsgf auto review service"
```

---

### Task 6: Model Health Summary And Notifications

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/services/gsgf_model_health.py`
- Modify: `apps/api/app/services/gsgf_auto_review.py`
- Modify: `apps/api/app/main.py`
- Add: `apps/api/tests/test_gsgf_model_health.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing model-health service tests**

Create `apps/api/tests/test_gsgf_model_health.py`:

```python
from app.models import GsgfCalibrationBucket, GsgfRealCalibrationSummary, GsgfReviewBucket, GsgfReviewSummary
from app.services.gsgf_model_health import build_gsgf_model_health


def test_gsgf_model_health_marks_best_and_insufficient_signals() -> None:
    review = GsgfReviewSummary(
        record_count=8,
        buckets=[
            GsgfReviewBucket(
                signal_type="放量突破确认",
                status="确认买点",
                sample_count=6,
                confirmed_count=5,
                avg_return_pct=2.4,
                avg_max_drawdown_pct=-1.8,
            ),
            GsgfReviewBucket(
                signal_type="星线后确认",
                status="确认买点",
                sample_count=2,
                confirmed_count=2,
                avg_return_pct=1.2,
                avg_max_drawdown_pct=-0.5,
            ),
        ],
    )
    calibration = GsgfRealCalibrationSummary(
        buckets=[
            GsgfCalibrationBucket(name="放量突破确认", sample_count=8, composite_score=63, calibration_rating="中强"),
        ]
    )

    health = build_gsgf_model_health(review, calibration)

    assert "放量突破确认" in health.best_signals
    assert "星线后确认" in health.insufficient_sample_signals
    assert health.last_review_at == review.generated_at
    assert health.last_calibration_at == calibration.generated_at


def test_gsgf_model_health_marks_degraded_core_signal() -> None:
    review = GsgfReviewSummary(
        record_count=6,
        buckets=[
            GsgfReviewBucket(
                signal_type="放量突破确认",
                status="确认买点",
                sample_count=6,
                confirmed_count=1,
                avg_return_pct=-1.1,
                avg_max_drawdown_pct=-6.2,
            )
        ],
    )

    health = build_gsgf_model_health(review, None)

    assert "放量突破确认" in health.degraded_signals
    assert "仅供复盘与模型校准" in health.summary_text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_model_health.py -q
```

Expected: fail because `gsgf_model_health.py` does not exist and model type is missing.

- [ ] **Step 3: Add model-health type**

In `apps/api/app/models.py` add:

```python
class GsgfModelHealth(BaseModel):
    best_signals: list[str] = Field(default_factory=list)
    weak_signals: list[str] = Field(default_factory=list)
    insufficient_sample_signals: list[str] = Field(default_factory=list)
    degraded_signals: list[str] = Field(default_factory=list)
    last_review_at: str | None = None
    last_calibration_at: str | None = None
    summary_text: str = "仅供复盘与模型校准，不构成投资建议。"
```

- [ ] **Step 4: Implement `build_gsgf_model_health`**

Create `apps/api/app/services/gsgf_model_health.py`:

```python
from __future__ import annotations

from app.models import GsgfModelHealth, GsgfRealCalibrationSummary, GsgfReviewSummary


def build_gsgf_model_health(
    review: GsgfReviewSummary | None,
    calibration: GsgfRealCalibrationSummary | None,
) -> GsgfModelHealth:
    best: list[str] = []
    weak: list[str] = []
    insufficient: list[str] = []
    degraded: list[str] = []

    if review is not None:
        for bucket in review.buckets:
            name = bucket.signal_type
            if bucket.sample_count < 5:
                insufficient.append(name)
                continue
            confirmation_rate = bucket.confirmed_count / max(bucket.sample_count, 1)
            if (bucket.avg_return_pct or 0) < 0 or (bucket.avg_max_drawdown_pct or 0) <= -5:
                degraded.append(name)
            elif (bucket.avg_return_pct or 0) > 0 and confirmation_rate >= 0.6:
                best.append(name)
            else:
                weak.append(name)

    if calibration is not None:
        for bucket in calibration.buckets:
            if bucket.sample_count < 5:
                insufficient.append(bucket.name)
            elif bucket.calibration_rating in {"强", "中强"}:
                best.append(bucket.name)
            elif bucket.calibration_rating == "弱":
                weak.append(bucket.name)

    return GsgfModelHealth(
        best_signals=_dedupe(best),
        weak_signals=_dedupe(weak),
        insufficient_sample_signals=_dedupe(insufficient),
        degraded_signals=_dedupe(degraded),
        last_review_at=review.generated_at if review else None,
        last_calibration_at=calibration.generated_at if calibration else None,
        summary_text=_summary_text(best, weak, insufficient, degraded),
    )
```

Add `_dedupe` and `_summary_text` helpers in the same file. `_summary_text` must end with `仅供复盘与模型校准，不构成投资建议。`

- [ ] **Step 5: Add health API**

In `main.py` add:

```python
@app.get("/api/gsgf/health")
def get_gsgf_model_health() -> dict[str, object]:
    health = build_gsgf_model_health(
        _gsgf_review_store().load_latest_summary(),
        _background_job_store().load_latest_calibration(),
    )
    return health.model_dump(mode="json")
```

Add API test:

```python
def test_gsgf_health_endpoint_returns_summary(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/gsgf/health")

    assert response.status_code == 200
    assert "summary_text" in response.json()
```

- [ ] **Step 6: Use health in auto-review notifications**

In `gsgf_auto_review.py`, after daily review finishes, call `build_gsgf_model_health`. If `notify_on_degradation` is enabled and `health.degraded_signals` is non-empty, notify with title `GSGF 模型信号退化提醒`.

After weekly calibration finishes and `notify_on_success` is enabled, notify with title `GSGF 每周真实样本校准完成`.

- [ ] **Step 7: Verify tests pass**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_gsgf_model_health.py tests/test_api.py::test_gsgf_health_endpoint_returns_summary tests/test_gsgf_auto_review.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/models.py apps/api/app/services/gsgf_model_health.py apps/api/app/services/gsgf_auto_review.py apps/api/app/main.py apps/api/tests/test_gsgf_model_health.py apps/api/tests/test_gsgf_auto_review.py apps/api/tests/test_api.py
git commit -m "feat: summarize gsgf model health"
```

---

### Task 7: Frontend API And Home Panel

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/HomeWorkbench.tsx`
- Modify: `apps/web/components/screener/GsgfWorkflowPanels.tsx`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Write failing frontend source tests**

Add assertions to `apps/web/lib/strongStockWorkbench.test.ts`:

```ts
assert.match(typesSource, /BackgroundJobState/);
assert.match(typesSource, /GsgfModelHealth/);
assert.match(apiSource, /getLatestGsgfReview/);
assert.match(apiSource, /createGsgfCalibrationJob/);
assert.match(apiSource, /getGsgfCalibrationJob/);
assert.match(apiSource, /getLatestGsgfCalibration/);
assert.match(apiSource, /getGsgfModelHealth/);
assert.match(homeFeatureSource, /refreshGsgfLatest/);
assert.match(gsgfPanelsSource, /校准任务/);
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd apps/web
corepack pnpm test
```

Expected: fail on missing names.

- [ ] **Step 3: Add types**

In `types.ts` add:

```ts
export type BackgroundJobStatus = "pending" | "running" | "success" | "failed" | "canceled";

export type BackgroundJobState = {
  job_id: string;
  type: string;
  status: BackgroundJobStatus;
  progress_current: number;
  progress_total: number;
  message: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  result_path: string | null;
};

export type GsgfModelHealth = {
  best_signals: string[];
  weak_signals: string[];
  insufficient_sample_signals: string[];
  degraded_signals: string[];
  last_review_at: string | null;
  last_calibration_at: string | null;
  summary_text: string;
};
```

- [ ] **Step 4: Add API helpers**

In `api.ts` add:

```ts
export async function getLatestGsgfReview(): Promise<GsgfReviewSummary | null> {
  const response = await fetch(`${API_BASE_URL}/api/gsgf/review/latest`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`读取最新股是股非复盘失败：${response.status} ${await response.text()}`);
  return response.json() as Promise<GsgfReviewSummary>;
}
```

Add `createGsgfCalibrationJob`, `getGsgfCalibrationJob`, `cancelGsgfCalibrationJob`, `getLatestGsgfCalibration`, and `getGsgfModelHealth`.

- [ ] **Step 5: Update `HomeWorkbench`**

On startup call `refreshGsgfLatest`, which fetches latest review, latest calibration, and model health. Change `handleRunGsgfCalibration` to create a job, set job state, and poll every 2 seconds until `success`, `failed`, or `canceled`.

- [ ] **Step 6: Update `GsgfWorkflowPanels`**

Change calibration props to include:

```ts
calibrationJob: BackgroundJobState | null;
onCancelCalibration: () => void;
```

Show:

- latest result if available.
- job status badge.
- progress as `progress_current / progress_total`.
- error text if job failed.

- [ ] **Step 7: Verify frontend tests**

Run:

```bash
cd apps/web
corepack pnpm test
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add apps/web/lib/types.ts apps/web/lib/api.ts apps/web/app/HomeWorkbench.tsx apps/web/components/screener/GsgfWorkflowPanels.tsx apps/web/lib/strongStockWorkbench.test.ts
git commit -m "feat: show gsgf calibration job progress"
```

---

### Task 8: Settings UI For GSGF Automation

**Files:**
- Modify: `apps/web/app/settings/SettingsWorkspace.tsx`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Write failing frontend source tests**

Add assertions:

```ts
assert.match(settingsFeatureSource, /GSGF 自动复盘/);
assert.match(settingsFeatureSource, /weekly_calibration_scan_limit/);
assert.match(settingsFeatureSource, /notify_on_degradation/);
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd apps/web
corepack pnpm test
```

Expected: fail until settings UI is wired.

- [ ] **Step 3: Extend settings types**

Add `GsgfAutoReviewConfig` to `types.ts` and include it in `RuntimeSettingsConfig`.

- [ ] **Step 4: Extend `SettingsDraft` and defaults**

Add fields:

```ts
gsgf_auto_snapshot_enabled: boolean;
gsgf_daily_review_enabled: boolean;
gsgf_daily_review_time: string;
gsgf_weekly_calibration_enabled: boolean;
gsgf_weekly_calibration_weekday: number;
gsgf_weekly_calibration_time: string;
gsgf_weekly_calibration_trade_days: number;
gsgf_weekly_calibration_scan_limit: number;
gsgf_notify_on_success: boolean;
gsgf_notify_on_degradation: boolean;
```

- [ ] **Step 5: Add settings card**

Add an Ant Design card titled `GSGF 自动复盘` with switches and inputs for daily review, weekly calibration, scan limit, and notification options.

- [ ] **Step 6: Include config in save payload**

When calling `saveRuntimeSettings`, send:

```ts
gsgf_auto_review: {
  auto_snapshot_enabled: draft.gsgf_auto_snapshot_enabled,
  daily_review_enabled: draft.gsgf_daily_review_enabled,
  daily_review_time: draft.gsgf_daily_review_time,
  weekly_calibration_enabled: draft.gsgf_weekly_calibration_enabled,
  weekly_calibration_weekday: draft.gsgf_weekly_calibration_weekday,
  weekly_calibration_time: draft.gsgf_weekly_calibration_time,
  weekly_calibration_trade_days: draft.gsgf_weekly_calibration_trade_days,
  weekly_calibration_scan_limit: draft.gsgf_weekly_calibration_scan_limit,
  windows: [1, 3, 5, 10],
  kline_count: 260,
  notify_on_success: draft.gsgf_notify_on_success,
  notify_on_degradation: draft.gsgf_notify_on_degradation,
}
```

- [ ] **Step 7: Verify frontend tests**

Run:

```bash
cd apps/web
corepack pnpm test
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add apps/web/app/settings/SettingsWorkspace.tsx apps/web/lib/types.ts apps/web/lib/strongStockWorkbench.test.ts
git commit -m "feat: configure gsgf auto review"
```

---

### Task 9: Full Verification

**Files:**
- No source changes unless verification exposes a bug.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run backend lint**

Run:

```bash
cd apps/api
.venv/bin/python -m ruff check app tests
```

Expected: no lint errors.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd apps/web
corepack pnpm test
```

Expected: all tests pass.

- [ ] **Step 4: Run manual API smoke checks**

Run:

```bash
curl -sS http://127.0.0.1:8010/api/gsgf/review/latest | python3 -m json.tool | head -n 40
curl -sS -X POST http://127.0.0.1:8010/api/gsgf/calibration/jobs \
  -H 'Content-Type: application/json' \
  -d '{"trade_dates":["2026-06-24"],"windows":[1,3],"scan_limit":2,"count":90}' | python3 -m json.tool
```

Expected: latest review returns either JSON or 404 when no summary exists; job creation returns a `job_id`.

- [ ] **Step 5: Commit any verification fixes**

If verification required fixes:

```bash
git add <fixed-files>
git commit -m "fix: stabilize gsgf auto review workflow"
```

If no fixes were needed, do not create an empty commit.
