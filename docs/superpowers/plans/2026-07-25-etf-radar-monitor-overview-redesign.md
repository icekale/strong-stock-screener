# ETF Radar Monitor Overview Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `/etf-radar` 默认视图重构为“监控总览”，以单一主趋势图、异常列表和核心 ETF 排行替代重复摘要，保留现有数据口径和全部既有工作流。

**Architecture:** 继续由 `EtfRadarView.vue` 负责标签与数据加载，使用 `HuijinTrajectoryPanel.vue` 承担总览的趋势图、异常列表和排行。将归一化序列和异常筛选放入 `utils/domain/huijinTrajectory.ts`，用纯函数测试保证不会混淆确认持仓与 ETF 份额代理。今日异动、确认持仓和方法与数据沿用现有组件，仅压缩默认暴露的信息。

**Tech Stack:** Vue 3 `<script setup>`, TypeScript, Ant Design Vue, ECharts, Vitest, Vue Test Utils, CSS variables from the existing workbench token system.

---

### Task 1: Lock the new default tab and preserve legacy routes

**Files:**
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`
- Modify: `apps/web-vue/src/views/EtfRadarView.test.ts`

- [ ] **Step 1: Write the failing tests**

Update the existing first-render test so the tab labels are expected to be:

```ts
expect(wrapper.findAll('.etf-tab-trigger').map(tab => tab.text())).toEqual([
  '监控总览', '今日异动', '确认持仓', '方法与数据'
]);
expect(wrapper.get('[data-testid="huijin-trajectory-panel"]').exists()).toBe(true);
expect(wrapper.find('[data-testid="daily-activity-home"]').exists()).toBe(false);
```

Add a test that sets `routeState.route.query = { tab: 'trajectory' }` and verifies the same `监控总览` view renders, then sets `tab=activity` and verifies the existing `etf-excess-flow-panel` and activity table render.

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
pnpm --dir apps/web-vue test:unit -- src/views/EtfRadarView.test.ts
```

Expected: FAIL because the current labels are `持仓轨迹` and `日度活动`, and the default view still renders `daily-activity-home`.

- [ ] **Step 3: Implement the minimal tab change**

In `EtfRadarView.vue`, keep the internal `EtfTab` values and route query compatibility unchanged, but change only the visible labels:

```vue
<a-tab-pane key="trajectory" tab="监控总览" />
<a-tab-pane key="activity" tab="今日异动" />
```

Remove the `daily-activity-home` block from the `trajectory` template branch. Keep `overview` loading, `HuijinTrajectoryPanel`, route query handling, and all activity-tab requests unchanged.

- [ ] **Step 4: Run the focused test to verify it passes**

Run the same Vitest command. Expected: the updated tab and route tests pass; existing activity tests continue to pass after their visible-label assertions are updated.

- [ ] **Step 5: Commit**

```bash
git add apps/web-vue/src/views/EtfRadarView.vue apps/web-vue/src/views/EtfRadarView.test.ts
git commit -m "refactor: simplify ETF radar tabs"
```

### Task 2: Add pure helpers for normalized trends and exception rows

**Files:**
- Modify: `apps/web-vue/src/utils/domain/huijinTrajectory.ts`
- Modify: `apps/web-vue/src/utils/domain/huijinTrajectory.test.ts`
- Modify: `apps/web-vue/src/service/types.ts` only if an existing exported type is required by the helper; do not add API fields.

- [ ] **Step 1: Write failing helper tests**

Add tests covering these exact behaviors:

```ts
it('normalizes ETF and index cumulative series to the first valid point', () => {
  expect(buildNormalizedTrend([0, 5, null, 15], [0, -10, -5, null])).toEqual({
    etf: [100, 105, null, 115],
    index: [100, 90, 95, null]
  });
});

it('keeps all-null trend series unavailable instead of converting it to zero', () => {
  expect(buildNormalizedTrend([null, null], [null, null])).toEqual({
    etf: [null, null],
    index: [null, null]
  });
});

it('returns only tenfold, divergent, or incomplete exception items', () => {
  expect(buildHuijinExceptions(items, validationGroups).map(item => item.symbol)).toEqual(['510050.SH', '510300.SH']);
});
```

Use fixtures with one tenfold event, one high/medium factor signal, one validation divergence, and ordinary rows. The helper must not classify a row as exceptional solely because its close change is non-zero.

- [ ] **Step 2: Run the helper tests to verify the intended failures**

Run:

```bash
pnpm --dir apps/web-vue test:unit -- src/utils/domain/huijinTrajectory.test.ts
```

Expected: FAIL because `buildNormalizedTrend` and `buildHuijinExceptions` do not exist.

- [ ] **Step 3: Implement minimal pure helpers**

Add to `huijinTrajectory.ts`:

```ts
export function buildNormalizedTrend(etf: Array<number | null>, index: Array<number | null>) {
  const normalize = (values: Array<number | null>) => {
    const base = values.find(value => value !== null);
    return values.map(value => (value === null || base === undefined ? null : 100 + value - base));
  };
  return { etf: normalize(etf), index: normalize(index) };
}

export function buildHuijinExceptions(items: HuijinEtfActivityItem[], validationGroups: HuijinEtfValidationGroup[]) {
  const groupByCore = new Map(validationGroups.map(group => [group.core_symbol, group]));
  return items
    .filter(item => item.role === 'core')
    .filter(item => {
      const group = groupByCore.get(item.symbol);
      return item.is_tenfold || item.total_shares === null || item.previous_total_shares === null
        || group?.state === 'divergent' || group?.state === 'incomplete';
    })
    .sort((left, right) => Math.abs(right.baseline_change_pct ?? 0) - Math.abs(left.baseline_change_pct ?? 0));
}
```

The component will apply the validation state when rendering; factor-level signals remain in the existing “今日异动” view. The helper remains deterministic and does not invent missing backend values. Preserve `buildHuijinTrajectory` for existing history tests and route behavior.

- [ ] **Step 4: Run the helper tests to verify green**

Run the same Vitest command. Expected: all existing and new helper tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web-vue/src/utils/domain/huijinTrajectory.ts apps/web-vue/src/utils/domain/huijinTrajectory.test.ts
git commit -m "feat: add ETF radar trend view models"
```

### Task 3: Rebuild the trajectory panel as a monitor overview

**Files:**
- Modify: `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue`
- Modify: `apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts`

- [ ] **Step 1: Write failing component tests**

Add assertions for the new visible structure:

```ts
expect(wrapper.get('[data-testid="huijin-overview-chart"]').exists()).toBe(true);
expect(wrapper.get('[data-testid="huijin-exception-list"]').exists()).toBe(true);
expect(wrapper.get('[data-testid="huijin-ranking-list"]').exists()).toBe(true);
expect(wrapper.text()).toContain('ETF 份额代理趋势');
expect(wrapper.text()).toContain('今日异常');
expect(wrapper.text()).toContain('汇金确认持仓只在报告期更新');
expect(wrapper.find('[data-testid="daily-activity-home"]').exists()).toBe(false);
```

Add a chart assertion that the ECharts option has a single y-axis, one `ETF 份额代理` series and one `指数走势` series, with `animation: false`. Add a no-exception fixture assertion for `今日无显著份额异常`.

- [ ] **Step 2: Run the focused component test to verify it fails**

Run:

```bash
pnpm --dir apps/web-vue test:unit -- src/components/etf-radar/HuijinTrajectoryPanel.test.ts
```

Expected: FAIL because the current panel has the old metrics, ranking labels, and chart series.

- [ ] **Step 3: Implement the panel layout and data mapping**

In `HuijinTrajectoryPanel.vue`:

1. Keep the existing props and `select` emit.
2. Keep `buildHuijinRanking`, selected ETF behavior, history loading, error rendering, and the existing detail rows.
3. Replace the top metrics/source text and old ranking-plus-chart arrangement with:

```vue
<div class="huijin-overview__main">
  <section data-testid="huijin-overview-chart" class="huijin-overview__chart">
    <header>ETF 份额代理趋势 <small>报告期确认持仓仅显示为节点</small></header>
    <EChart :option="chartOption" :height="320" :loading="historyLoading || Boolean(indexHistoryLoading)" />
  </section>
  <section data-testid="huijin-exception-list" class="huijin-overview__exceptions">
    <header><strong>今日异常</strong><span v-if="!exceptions.length">今日无显著份额异常</span></header>
    <button v-for="item in exceptions" :key="item.symbol" type="button" @click="emit('select', item.symbol)">
      <strong>{{ item.name }}</strong>
      <span>{{ formatDirectionalPercent(item.daily_change_pct) }} · {{ item.symbol }}</span>
    </button>
  </section>
</div>
<section data-testid="huijin-ranking-list" class="huijin-overview__ranking">
  <header><strong>核心 ETF 趋势排行</strong><span>累计基线偏离 · 今日份额变化 · 收盘涨跌</span></header>
  <!-- retain the seven selectable rows with the existing accessible button contract -->
</section>
```

4. Build chart dates from the union of real ETF and index dates. Use normalized values from `buildNormalizedTrend`; use a solid ETF series, dashed index series, and no connecting across nulls. Keep the report date as a point annotation or tooltip text, not a connected daily value.
5. Put the existing confirmation metrics and detailed selected-ETF facts behind the existing detail interaction, preserving `data-testid="huijin-detail-row"` and `aria-pressed` behavior.
6. Replace the source sentence block with one compact coverage label, e.g. `数据覆盖 ${availableCount} / ${overview.activity.core_count}`. Keep detailed source data available through the parent’s method/data tab.

- [ ] **Step 4: Add responsive styles and accessibility states**

Use the existing `--wb-*` tokens and `min-width: 0`. Add a desktop `grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr)` layout, collapse to one column at `900px`, and keep the ranking table’s horizontal overflow local. Every exception and ranking row remains a keyboard-focusable button. Add `@media (prefers-reduced-motion: reduce)` with no transitions.

- [ ] **Step 5: Run focused component tests to verify green**

Run the same Vitest command. Expected: all panel tests pass, including old selection, null-history, responsive contract, and error tests.

- [ ] **Step 6: Commit**

```bash
git add apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.test.ts
git commit -m "refactor: redesign ETF radar monitor overview"
```

### Task 4: Keep today activity compact and preserve existing workflows

**Files:**
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`
- Modify: `apps/web-vue/src/views/EtfRadarView.test.ts`
- Modify: `apps/web-vue/src/components/etf-radar/EtfActivityTable.vue` only if its status/header wording needs to match `今日异动`.

- [ ] **Step 1: Add regression assertions before changing activity markup**

Extend `EtfRadarView.test.ts` to assert that the `今日异动` branch still renders exactly one `etf-activity-table`, the `etf-excess-flow-panel`, the collapsed validation region, and the drawer/inline detail after selecting a row. Assert that the default `监控总览` branch does not render `etf-excess-flow-panel`.

- [ ] **Step 2: Run the view tests and confirm the new regression test fails only for the old default structure**

```bash
pnpm --dir apps/web-vue test:unit -- src/views/EtfRadarView.test.ts
```

- [ ] **Step 3: Make the activity branch compact without changing its data flow**

Keep `loadActivityWorkbench`, `getEtfExcessFlow(60)`, `getEtfThreeFactor`, row selection, sorting, and drawer behavior. Move verbose source metadata to the existing method/data tab; retain one compact status line and the existing error alerts. Keep cross-validation collapsed by default.

- [ ] **Step 4: Run the full ETF view/component test set**

```bash
pnpm --dir apps/web-vue test:unit -- src/views/EtfRadarView.test.ts src/components/etf-radar/EtfActivityTable.test.ts src/components/etf-radar/EtfThreeFactorPanel.test.ts src/components/etf-radar/EtfExcessFlowPanel.test.ts
```

Expected: all selected ETF, sorting, missing data, error fallback, alert route, and chart tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web-vue/src/views/EtfRadarView.vue apps/web-vue/src/views/EtfRadarView.test.ts apps/web-vue/src/components/etf-radar/EtfActivityTable.vue
git commit -m "refactor: compact ETF radar activity view"
```

### Task 5: Run static checks and visual acceptance

**Files:**
- Modify only files from Tasks 1–4 if a verified type, lint, or responsive issue is found.

- [ ] **Step 1: Run the full frontend unit suite**

```bash
pnpm --dir apps/web-vue test:unit
```

Expected: zero failed tests.

- [ ] **Step 2: Run type checking and lint checks**

```bash
pnpm --dir apps/web-vue typecheck
pnpm --dir apps/web-vue exec eslint src/views/EtfRadarView.vue src/views/EtfRadarView.test.ts src/components/etf-radar/HuijinTrajectoryPanel.vue src/components/etf-radar/HuijinTrajectoryPanel.test.ts src/utils/domain/huijinTrajectory.ts src/utils/domain/huijinTrajectory.test.ts
```

Expected: zero TypeScript errors and zero ESLint errors.

- [ ] **Step 3: Start or reuse the local Vite server and capture desktop/mobile screenshots**

Open `/etf-radar` at `1440×1000`, `768×1024`, and `390×844`. Verify the status line, chart, exception list, and ranking are visible without page-level horizontal overflow. Verify selecting an exception updates the selected symbol and that `?tab=activity&symbol=510300.SH` still opens the activity detail.

- [ ] **Step 4: Run final diff checks**

```bash
git diff --check HEAD~4..HEAD
git status --short
```

Expected: no whitespace errors. Existing unrelated `.superpowers/sdd/*` and `apps/web/` changes remain untouched and are not included in the feature commits.

- [ ] **Step 5: Commit any final verified adjustment**

```bash
git add apps/web-vue/src/views/EtfRadarView.vue apps/web-vue/src/components/etf-radar/HuijinTrajectoryPanel.vue apps/web-vue/src/utils/domain/huijinTrajectory.ts
git commit -m "fix: polish ETF radar responsive states"
```
