# Task 5 Report: Approved Huijin Trajectory Panel

## Status and Implementation

- Implemented the reusable `HuijinTrajectoryPanel` with the approved typed prop/event boundary and Task 4 transforms.
- The panel renders seven-core ranking and selection, report/latest/coverage/direction metrics, source status, one-ETF null-gap trajectory, confirmed-holding details, the fixed Huijin inference warning, and compact detail rows.
- Positive ETF share deviation is red and labeled `扩张`; negative deviation is green and labeled `收缩`. Values also retain arrows and explicit signs, so color is never the only signal.
- ECharts uses `animation: false` and `connectNulls: false`. The desktop main area uses `minmax(0, 1.15fr) minmax(320px, 0.85fr)` and becomes one column at `900px`.

## RED Evidence

- Required literal command: `cd apps/web-vue && corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts` -> exit 1 before collection with the existing Vite `setupUnocss` error, `Cannot read properties of undefined (reading 'replace')`, because `.env.test` omits icon prefixes.
- Valid component-resolution RED: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts` -> `Test Files 1 failed (1)`, `Tests no tests`; Vite reported `Failed to resolve import "./HuijinTrajectoryPanel.vue"`.

## GREEN Evidence

- Focused component GREEN: the same environment-adjusted component command -> `Test Files 1 passed (1)`, `Tests 1 passed (1)`.
- Final component/domain verification: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts src/utils/domain/huijinTrajectory.test.ts` -> `Test Files 2 passed (2)`, `Tests 6 passed (6)`.
- Typecheck: `corepack pnpm@9.15.0 typecheck` -> `vue-tsc --noEmit --skipLibCheck`, exit 0.
- Lint: `corepack pnpm@9.15.0 exec eslint src/components/etf-radar/HuijinTrajectoryPanel.vue src/components/etf-radar/HuijinTrajectoryPanel.test.ts` -> exit 0 with no output.

## Files

- `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue`
- `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts`
- `.superpowers/sdd/task-5-report.md`

## Self-Review and Concerns

- No functional findings. The contract, labels, chart settings, fallback states, source statuses, responsive breakpoint, and selection event match the approved brief.
- CSS uses only existing `--wb-*` color/radius/gap tokens; there are no hex/rgb colors, gradients, custom SVGs, nested cards, or local horizontal scrollers. `git diff --check` passed.
- Verification regenerated the auto-component entry in `src/typings/components.d.ts`; it was removed after verification to preserve the requested three-file scope.
- Known repository concern: focused Vitest requires process-only `VITE_ICON_PREFIX` and `VITE_ICON_LOCAL_PREFIX` overrides. Page fetching and tab integration remain intentionally deferred to Task 6.

## Review Fix

### RED Evidence

- Command: `cd apps/web-vue && VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts`
- Output before the review fix: `Test Files 1 failed (1)` and `Tests 7 failed (7)`. Failures covered missing native list items and zero-centered bars, static EChart loading, baseline-only charts for empty/all-null selected history, missing loading live state, and missing independent error status with and without stale history.
- Zero-axis stacking RED with the focused source assertion: the same command -> `Test Files 1 failed (1)`, `Tests 1 failed | 6 passed (7)`; `.huijin-ranking__zero` lacked `z-index: 1`, allowing a positive bar to cover the center axis.
- The first full typecheck exposed an invalid test assertion: `corepack pnpm@9.15.0 typecheck` -> exit 2 with `TS2339: Property 'exists' does not exist on type 'Omit<DOMWrapper<Element>, "exists">'`. The test now uses `find().exists()`.

### Implementation

- Added a zero-centered track to every ranked core ETF. The maximum absolute deviation maps to half the track; negative bars extend left in `--wb-negative`, positive bars extend right in `--wb-positive`, and the zero axis remains visibly stacked above both.
- Ranking rows retain ETF identity, signed percentage, and explicit `扩张`/`收缩` text. Track/bar/axis selectors and a track `role="img"` label expose the visual meaning without relying on color.
- Chart eligibility now checks selected-symbol real history points directly and ignores the synthetic report baseline. Empty and all-null selected history render `暂无可用历史轨迹`; loading without history renders `历史加载中`.
- EChart now uses `defineAsyncComponent`. Stale real history remains charted while loading or after an error, and `historyError` is always rendered independently in an `aria-live="polite"` status.
- Ranking uses native `ul`/`li` semantics. Misleading explicit list/table roles were removed, detail rows are a labelled native section, and all ranking/detail selection buttons expose `aria-pressed`.
- The public props/emits remain unchanged, and the component still performs no fetching.

### GREEN Evidence

- Focused command: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts` -> `Test Files 1 passed (1)`, `Tests 7 passed (7)`.
- Final tests: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/components/etf-radar/HuijinTrajectoryPanel.test.ts src/utils/domain/huijinTrajectory.test.ts` -> `Test Files 2 passed (2)`, `Tests 12 passed (12)`.
- Final typecheck: `corepack pnpm@9.15.0 typecheck` -> `vue-tsc --noEmit --skipLibCheck`, exit 0.
- Final lint: `corepack pnpm@9.15.0 exec eslint src/components/etf-radar/HuijinTrajectoryPanel.vue src/components/etf-radar/HuijinTrajectoryPanel.test.ts` -> exit 0 with no output.

### Self-Review and Concerns

- The diff remains limited to the two Task 5 component files and this report. Generated `components.d.ts` changes were removed after verification, and `git diff --check` passes.
- CSS keeps the approved desktop columns, switches to one column at `900px`, preserves `max-width: 100%`, `min-width: 0`, and component-local `overflow-x: hidden`, and uses only existing `--wb-*` color tokens.
- No functional concerns remain. The existing Vitest icon-prefix environment requirement is unchanged.
