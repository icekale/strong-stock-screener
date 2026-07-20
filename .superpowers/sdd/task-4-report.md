# Task 4 Report

- Status: Implemented pure Huijin ranking, default selection, trajectory, and data-state transforms.
- RED: Initial command exposed an existing Vite config error because icon prefix env values were unset.
- RED: With `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon`, Vitest failed on missing `./huijinTrajectory` as required.
- GREEN: Focused Vitest passed: 1 file, 4 tests.
- Typecheck: `vue-tsc --noEmit --skipLibCheck` passed.
- Files: `apps/web-vue/src/utils/domain/huijinTrajectory.ts`; `apps/web-vue/src/utils/domain/huijinTrajectory.test.ts`.
- Implementation: Absolute-deviation ranking ignores nulls; trajectory prepends a zero report baseline and preserves date gaps as null.
- Implementation: Data-state precedence is disclosure, baseline, prior-day history, then calculable.
- Self-review: Pure transforms, no API/UI changes, no caller-array mutation, and nulls are never treated as zero except the report baseline.
- Concerns: Existing `.env.test` omits icon prefix values, so the focused command needs the two environment overrides above.

## Review Fix

- Implementation: `buildHuijinRanking` now filters `role === 'core'` before ranking; the regression proves a validator with the largest deviation is excluded from ranking and default selection.
- Test-first RED command: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/utils/domain/huijinTrajectory.test.ts`
- Test-first RED output: `Test Files 1 failed (1)`; `Tests 1 failed | 4 passed (5)`; validator ranking assertion received `['159919.SZ', '510050.SH']`.
- GREEN command: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/utils/domain/huijinTrajectory.test.ts`
- GREEN output: `Test Files 1 passed (1)`; `Tests 5 passed (5)`.
- Typecheck command: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 typecheck`
- Typecheck output: `vue-tsc --noEmit --skipLibCheck` exited with code 0.
- Added assertions confirm ranking leaves its input unchanged and trajectory construction leaves `points` and `realDates` unchanged.
- Self-review: Changes are limited to the Task 4 source/test files and this report; no UI, API, or unrelated refactors were added.
