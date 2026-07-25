# ETF Radar Dynamic Dual-Axis Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 ETF 份额与收盘价对比图使用独立、非零起始的动态坐标范围，达到参考图中两条曲线都清晰可辨的效果。

**Architecture:** 在 `huijinTrajectory.ts` 增加纯函数计算带余量的数值轴范围，组件仅负责将份额和收盘价序列映射到左右轴。图表继续使用现有 ECharts 异步组件和真实数据，不改接口、缓存或份额口径。

**Tech Stack:** Vue 3, TypeScript, ECharts, Vitest, Vue Test Utils.

## Global Constraints

- 份额使用亿份原始值，价格使用元原始值，不归一化。
- 左右轴独立计算范围，上下余量为数据跨度的 `8%`。
- 折线不平滑，不连接缺失点。
- 图表响应式高度限制在 `360px` 至 `440px`。
- 不修改 ETF 后端接口和其他雷达模块。

---

### Task 1: Add deterministic dynamic axis ranges

**Files:**
- Modify: `apps/web-vue/src/utils/domain/huijinTrajectory.ts`
- Test: `apps/web-vue/src/utils/domain/huijinTrajectory.test.ts`

**Interfaces:**
- Consumes: `Array<number | null>` and optional padding ratio.
- Produces: `buildPaddedAxisRange(values, paddingRatio): { min?: number; max?: number }`.

- [ ] **Step 1: Write failing tests**

Add assertions that `[100, 120]` yields `{ min: 98.4, max: 121.6 }`, `[3]` yields a positive non-zero range around `3`, null/non-finite values are ignored, and an empty valid sequence yields `{}`.

- [ ] **Step 2: Run the focused test and verify RED**

Run `pnpm test:unit -- src/utils/domain/huijinTrajectory.test.ts` from `apps/web-vue`.

Expected: FAIL because `buildPaddedAxisRange` is not exported.

- [ ] **Step 3: Implement the minimal pure helper**

Filter finite values, calculate min/max, apply `8%` of the span as padding, use a proportional fallback for a single value, clamp only the lower bound to zero, and return stable numeric values.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the same command. Expected: all helper tests pass.

### Task 2: Apply the reference-style chart treatment

**Files:**
- Modify: `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue`
- Test: `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts`

**Interfaces:**
- Consumes: `buildPaddedAxisRange`, existing share trajectory, existing close history.
- Produces: ECharts options with independent axes and latest-value summary markup.

- [ ] **Step 1: Write failing component tests**

Assert both value axes have `scale: true`, explicit dynamic `min`/`max`, four split intervals, the share series has a restrained area fill, both series use `smooth: false`, the chart height is `clamp(360px, 42vw, 440px)`, and the heading exposes latest share and close values.

- [ ] **Step 2: Run the focused component test and verify RED**

Run `pnpm test:unit -- src/components/etf-radar/HuijinTrajectoryPanel.test.ts` from `apps/web-vue`.

Expected: FAIL on the old zero-based axes, smooth curves, fixed height, and missing latest-value summary.

- [ ] **Step 3: Implement the minimal component changes**

Compute ranges and latest non-null points, apply them to the two Y axes, limit X-axis label density while retaining first/last labels, switch to straight lines, strengthen line widths without adding decoration, and render compact latest values below the title.

- [ ] **Step 4: Run focused and full verification**

Run the two focused test files, then the full frontend unit suite and `vue-tsc --noEmit --skipLibCheck`.

Expected: all tests and type checking pass without warnings.
