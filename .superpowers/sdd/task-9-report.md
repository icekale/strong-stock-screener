# Task 9 Verification Report

## Final Code State

- Verification fix: `3569cba` (`fix: harden sentiment percentile release`)
- The fix maps percentile-provider failures from the manual analysis generation endpoint to HTTP 503 instead of an uncaught HTTP 500.
- Final working tree was clean before this report was written.

## Backend

- Initial full run: `1231 passed, 2 failed`. One failure required the ignored `apps/api/rc8-worker/.venv` path; the other noisy-worker timeout was transient.
- `uv sync --locked` created the required RC8 virtualenv path but dependency downloads stalled and were stopped. The two focused failures then passed because the path prerequisite existed.
- Full rerun before the release fix: `1233 passed in 30.62s`.
- RED for the real-container defect: the new provider-failure test raised `StrongStockDataUnavailable` instead of returning 503.
- GREEN after the fix: `9 passed` in the analysis API module and focused Ruff passed.
- Final full rerun after the fix: `1234 passed in 29.69s`.
- Final Ruff: `All checks passed!` for `app`, `tests`, and `scripts/run_market_sentiment_validation.py`.

## Frontend

- Exact `pnpm` scripts were blocked before execution by the Codex runtime `ERR_PNPM_IGNORED_BUILDS` preflight.
- Equivalent locked local binaries passed:
  - Vitest: `34 files, 207 tests passed`.
  - `vue-tsc --noEmit --skipLibCheck`: exit 0.
  - `vite build --mode prod`: successful.
  - `apps/web-vue/dist/index.html`: present, 560 bytes.
- `git diff --check`: passed.

## Real Source And LLM

- Real validation command exited 1 before network I/O because `STRONG_STOCK_TICKFLOW_API_KEY` and `TICKFLOW_API_KEY` are not configured.
- No fixture output was substituted for real-source evidence and no validation JSON/Markdown artifacts were claimed.
- The local verification settings also have AI analysis disabled and no AI key, so real-provider LLM deduplication could not be exercised.
- `/api/settings` masking check passed: public settings contain `api_key_configured`, preview, and source metadata, with no full `api_key` field.

## Container

- The first Docker build completed successfully, including Vue production build, API package installation, CZSC 0.10.12, RC8 1.0.0rc8, and final image export.
- Container `strong-stock-screener-sentiment-percentile` started on port 3124 and Docker health reported `healthy`.
- `/health` returned HTTP 200 and `/api/settings` returned HTTP 200.
- `/api/short-term/sentiment/percentile` returned the expected 503 because TickFlow credentials are absent.
- Manual analysis generation exposed an uncaught 500 for the same provider failure. Commit `3569cba` fixed this and added a 503 regression test.
- The post-fix Docker rebuild reached final image export, then Docker Desktop failed to unpack a cached RC8 layer with a read-only-filesystem error. A retry failed with a containerd `meta.db` input/output error. This prevented post-fix container retest.
- The verification container was stopped and removed cleanly; no task-owned container remains running.

## Visual QA

Real unconfigured state:

- The production container displayed `市场情绪百分位更新失败，请稍后重试` inside the panel without a Vue page error or horizontal overflow.
- Screenshot: `.superpowers/sdd/task-9-real-unconfigured.png`.

Deterministic rendering-only interception was used separately to exercise populated chart and AI states. This was not presented as real-source validation.

- Desktop 1440x900: no horizontal overflow, no top-level overlap, exactly five factor rows, AI ready state visible, canvas 771x360 with 191 sampled colors.
- Mobile 390x844: no horizontal overflow, no panel-child overlap, exactly five factor rows, canvas 336x360 with 170 sampled colors.
- Long model metadata wrapped within a 332px mobile container (`scrollWidth == clientWidth`).
- LLM failed state kept the nonblank chart visible and did not display a synthetic provider URL/key detail.
- Screenshots:
  - `.superpowers/sdd/task-9-desktop.png`
  - `.superpowers/sdd/task-9-mobile.png`
  - `.superpowers/sdd/task-9-mobile-ai.png`
  - `.superpowers/sdd/task-9-llm-failed.png`
- Browser console/page errors were empty for intercepted ready/failed scenarios.

## Remaining Environment Gaps

- A TickFlow key is required to produce the real `000985.SH` validation artifacts and persisted 500-point snapshot.
- An enabled AI provider/key plus the real snapshot is required for live LLM deduplication evidence.
- Docker Desktop containerd storage must be repaired or restarted before the post-fix image can be rebuilt locally.

