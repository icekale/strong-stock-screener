# ETF 超量资金趋势模块移除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 ETF 雷达页面移除长期无数据的市场合计超量资金趋势模块，同时保留日度活动中的十倍量份额变化标记。

**Architecture:** 仅收敛 `EtfRadarView` 的前端数据流和展示，不修改后端 `/api/etf-radar/excess-flow`、`EtfExcessFlowService` 或日度活动使用的 `build_activity_metrics`。页面继续加载监控总览、日度活动、确认持仓和三因子工作台。

**Tech Stack:** Vue 3、TypeScript、Vitest、Vite、FastAPI/Pytest。

## Global Constraints

- 只移除前端空趋势模块和对应请求。
- 保留后端超量资金接口、服务和计算逻辑。
- 保留日度活动中的十倍量买入/赎回识别。
- 不修改工作区已有的 `.superpowers/sdd/*` 和未跟踪的 `apps/web/`。

---

### Task 1: Remove ETF radar excess-flow loading and rendering

**Files:**
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`
- Test: `apps/web-vue/src/views/EtfRadarView.test.ts`

**Interfaces:**
- Consumes: existing `EtfRadarView` load pipeline and `EtfActivityTable` data.
- Produces: ETF 雷达不再请求 `getEtfExcessFlow`，也不再渲染 `EtfExcessFlowPanel`；其他模块请求和展示保持不变。

- [x] **Step 1: Update the view test expectation first**

  In `apps/web-vue/src/views/EtfRadarView.test.ts`, change the successful-load assertion from:

  ```ts
  expect(api.getEtfExcessFlow).toHaveBeenCalledWith(60);
  expect(wrapper.find('[data-testid="etf-excess-flow-panel"]').exists()).toBe(true);
  ```

  to:

  ```ts
  expect(api.getEtfExcessFlow).not.toHaveBeenCalled();
  expect(wrapper.find('[data-testid="etf-excess-flow-panel"]').exists()).toBe(false);
  ```

  Update the failure-path test to assert the excess-flow API is not called and that the activity table and three-factor panel remain available.

- [x] **Step 2: Run the focused view tests and verify the new expectation fails**

  Run:

  ```bash
  pnpm vitest run src/views/EtfRadarView.test.ts
  ```

  Expected: FAIL because the current view still calls `getEtfExcessFlow` and renders `EtfExcessFlowPanel`.

- [x] **Step 3: Remove only the excess-flow view code**

  In `apps/web-vue/src/views/EtfRadarView.vue`:

  - Remove the `getEtfExcessFlow` import.
  - Remove the `EtfExcessFlowPanel` import.
  - Remove the `EtfExcessFlowResponse` type import if it becomes unused.
  - Remove `excessFlow`, `excessFlowLoading`, and `excessFlowError` refs.
  - Remove the `loadExcessFlow` function and its call from the page loading pipeline.
  - Remove the `<EtfExcessFlowPanel ... />` template node.

  Leave the `EtfExcessFlowPanel.vue` component, domain helpers, service function, API route, and backend service untouched because they are not required for the page change and may be reused later.

- [x] **Step 4: Run the focused view tests and verify they pass**

  Run:

  ```bash
  pnpm vitest run src/views/EtfRadarView.test.ts
  ```

  Expected: PASS, including the assertion that the activity table and three-factor workbench remain usable.

- [x] **Step 5: Run the complete validation suite**

  Run:

  ```bash
  pnpm test:unit
  pnpm typecheck
  pnpm build
  (cd ../api && uv run pytest -q)
  ```

  Expected: all commands exit `0`; the backend excess-flow tests remain covered and the frontend production build succeeds.

- [x] **Step 6: Review the diff and commit only this change**

  Run:

  ```bash
  git diff --check
  git status --short
  git diff -- apps/web-vue/src/views/EtfRadarView.vue apps/web-vue/src/views/EtfRadarView.test.ts
  git add apps/web-vue/src/views/EtfRadarView.vue apps/web-vue/src/views/EtfRadarView.test.ts
  git commit -m "fix(etf-radar): remove empty excess flow panel"
  ```

  Do not stage `.superpowers/sdd/task-1-report.md`, `.superpowers/sdd/task-5-report.md`, or `apps/web/`.
