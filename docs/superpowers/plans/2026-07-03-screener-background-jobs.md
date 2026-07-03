# Screener Background Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the homepage screener run path from a long synchronous request to a background job with polling.

**Architecture:** Reuse the existing `BackgroundJobStore` for transient jobs. Add `POST /api/screen/runs/jobs` and `GET /api/screen/runs/jobs/{job_id}` while keeping the existing synchronous `/api/screen/runs` endpoint unchanged. The web client starts a job, polls it every 2 seconds, and renders the returned screening result when the job succeeds.

**Tech Stack:** FastAPI, Pydantic, existing Python background thread store, Next.js/React, TypeScript, existing Node test runner.

---

### Task 1: Backend Job Result Support

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/services/background_jobs.py`
- Test: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests near existing screen run tests:

```python
def test_screen_run_job_runs_in_background_and_persists_latest(tmp_path: Path) -> None:
    kline_provider = BlockingKlineProvider()
    client = _client(tmp_path, kline_provider=kline_provider)

    response = client.post("/api/screen/runs/jobs", json={"trade_date": "2026-06-11", "limit": 10, "scan_limit": 4})

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "screen_run"
    assert payload["status"] in {"pending", "running"}
    assert payload["result"] is None

    kline_provider.release.set()
    completed = payload
    for _ in range(30):
        completed = client.get(f"/api/screen/runs/jobs/{payload['job_id']}").json()
        if completed["status"] == "success":
            break
        sleep(0.05)

    assert completed["status"] == "success"
    assert completed["result"]["trade_date"] == "2026-06-11"
    assert len(completed["result"]["items"]) > 0
    assert client.get("/api/screen/runs/latest").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `apps/api/.venv/bin/python -m pytest apps/api/tests/test_api.py::test_screen_run_job_runs_in_background_and_persists_latest -q`

Expected: fails because `/api/screen/runs/jobs` does not exist.

- [ ] **Step 3: Implement result support**

Add `result: dict[str, Any] | None = None` to `BackgroundJobState`.

Change `TransientRunner` to return `object`, store the returned value in `_run_transient`, and set `result` when the job succeeds if the value is not `None`.

- [ ] **Step 4: Add screen job endpoints**

In `apps/api/app/main.py`, extract the current synchronous body into a helper that returns the `StrongStockScreeningResponse`. Use it from both `/api/screen/runs` and the new job runner. Add:

- `POST /api/screen/runs/jobs`
- `GET /api/screen/runs/jobs/{job_id}`

- [ ] **Step 5: Verify backend tests**

Run:

```bash
apps/api/.venv/bin/python -m pytest apps/api/tests/test_api.py::test_screen_run_job_runs_in_background_and_persists_latest -q
apps/api/.venv/bin/python -m pytest apps/api/tests/test_api.py -q
```

Expected: both pass.

### Task 2: Frontend Polling

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/HomeWorkbench.tsx`
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Modify: `apps/web/components/screener/FilterLogicRail.tsx`
- Test: `apps/web/lib/strongStockWorkbench.test.ts`

- [ ] **Step 1: Write failing frontend assertions**

In `strongStockWorkbench.test.ts`, assert that:

```ts
assert.match(apiSource, /createScreenRunJob/);
assert.match(apiSource, /getScreenRunJob/);
assert.match(homeFeatureSource, /pollScreenRunJob/);
assert.match(screenerFeatureSource, /screenJob/);
assert.match(screenerFeatureSource, /筛选任务/);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && corepack pnpm test`

Expected: fails because the new API helpers and UI state are missing.

- [ ] **Step 3: Add TypeScript types and API helpers**

Extend `BackgroundJobState` with:

```ts
result: unknown | null;
```

Add:

```ts
export type ScreenRunJobState = BackgroundJobState & {
  result: StrongStockScreeningResponse | null;
};
```

Add `createScreenRunJob()` and `getScreenRunJob()` in `api.ts`.

- [ ] **Step 4: Update homepage run flow**

Replace the synchronous `createScreenRun()` call in `handleRun()` with `createScreenRunJob()`. Poll with `getScreenRunJob()` every 2 seconds until `success`, `failed`, or `canceled`. On success, set `result` from `job.result`.

- [ ] **Step 5: Display job status**

Pass `screenJob` to `ScreenerWorkbench` and `FilterLogicRail`. Show a compact progress line with job message and `progress_current/progress_total`.

- [ ] **Step 6: Verify frontend**

Run:

```bash
cd apps/web && corepack pnpm test
cd apps/web && corepack pnpm build
```

Expected: both pass.

### Task 3: End-to-End Verification

**Files:**
- No additional source files.

- [ ] **Step 1: Run full backend tests**

Run: `apps/api/.venv/bin/python -m pytest apps/api/tests -q`

Expected: all pass.

- [ ] **Step 2: Run API lint**

Run: `cd apps/api && .venv/bin/python -m ruff check app tests`

Expected: no errors.

- [ ] **Step 3: Run local job request**

Run the local app, then:

```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"trade_date":"2026-07-03","limit":30,"scan_limit":40,"filters":{},"strategy":"gsgf"}' \
  http://127.0.0.1:3110/api/screen/runs/jobs
```

Expected: returns a job ID immediately, not after the screening run completes.

- [ ] **Step 4: Commit implementation**

Commit backend and frontend changes with:

```bash
git add apps/api apps/web docs/superpowers/plans/2026-07-03-screener-background-jobs.md
git commit -m "Run screener through background jobs"
```
