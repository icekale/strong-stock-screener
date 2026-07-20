# Task 6 Report: Holdings-First Workspace

## Status and Implementation

- Integrated `HuijinTrajectoryPanel` as the default `持仓轨迹` view at the unchanged `/etf-radar` route.
- The approved tabs are `持仓轨迹`, `日度活动`, `确认持仓`, and `方法与数据`. Daily activity reuses the trajectory overview; holders and methodology remain first-entry lazy.
- Overview and 120-day history retain independent loading/error state and the existing 15-second request cache. A trajectory refresh forces both requests and preserves prior successful refs when either request fails.
- ETF selection only updates `selectedTrajectorySymbol`; it performs no API request. Daily data states and paired validation labels use the approved wording.

## RED Evidence

- Literal brief command: `corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts src/router/product-routes.test.ts src/utils/domain/capitalSignals.test.ts` -> exit 1 before collection at the repository's existing `setupUnocss` icon-prefix error.
- Valid behavior RED with process-only overrides: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts src/router/product-routes.test.ts src/utils/domain/capitalSignals.test.ts` -> `Test Files 3 failed (3)`, `Tests 9 failed | 16 passed (25)`. Failures covered the old title/tabs, missing initial history request and trajectory panel, old route label, old data-state/validation wording, and missing refresh/error integration.

## GREEN and Build Evidence

- Final focused tests: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 test:unit --run src/views/EtfRadarView.test.ts src/components/etf-radar/HuijinTrajectoryPanel.test.ts src/utils/domain/huijinTrajectory.test.ts src/utils/domain/capitalSignals.test.ts src/router/product-routes.test.ts` -> `Test Files 5 passed (5)`, `Tests 38 passed (38)`.
- Typecheck: `corepack pnpm@9.15.0 typecheck` -> `vue-tsc --noEmit --skipLibCheck`, exit 0. An intermediate run caught and removed one stale `loading.overview` template key.
- Production build: `VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon corepack pnpm@9.15.0 build` -> `Build successful. Please see dist directory`, exit 0.

## Request Assertions

- While overview remained unresolved, history had already started with `120`, proving concurrent mount initiation. Initial counts are overview `1`, history `1`, holders `0`, methodology `0`.
- Opening activity and returning to trajectory leave overview/history at `1`; first holders/methodology entries each reach `1` and repeat entries do not increment them.
- Selecting a ranked ETF leaves all request counts unchanged. Manual trajectory refresh raises overview/history to `2` each in both overview-failure and history-failure cases.

## Files

- `apps/web-vue/src/views/EtfRadarView.vue`
- `apps/web-vue/src/views/EtfRadarView.test.ts`
- `apps/web-vue/src/router/product-routes.ts`
- `apps/web-vue/src/router/product-routes.test.ts`
- `apps/web-vue/src/locales/langs/zh-cn.ts`
- `apps/web-vue/src/locales/langs/en-us.ts`
- `apps/web-vue/src/utils/domain/capitalSignals.ts`
- `apps/web-vue/src/utils/domain/capitalSignals.test.ts`
- `.superpowers/sdd/task-6-report.md`

## Self-Review and Concerns

- Verified the route path remains `/etf-radar`, no homepage/other route was changed, `git diff --check` passes, and the build-generated `src/typings/components.d.ts` change was restored.
- Partial failures retain the prior panel data: overview errors use the page alert and history errors use the panel's independent stale-history status. No activity or ETF-selection path fetches data.
- Strict ESLint is not a Task 6 gate and remains nonzero on legacy `EtfRadarView.vue` rules. The base commit reports 26 errors and the current page reports 16 in the same import-order, nested-expression, null-comparison, and `void` categories; this task adds no new lint category.
- Focused Vitest and build require process-only `VITE_ICON_PREFIX` / `VITE_ICON_LOCAL_PREFIX` values because repository test env files still omit them.
