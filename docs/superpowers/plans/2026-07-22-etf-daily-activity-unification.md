# ETF Daily Activity Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two repeated seven-ETF lists in `/etf-radar?tab=activity` with one sortable activity table and an on-demand single-ETF evidence detail.

**Architecture:** Merge the overview activity records and three-factor records with a pure domain helper, render the merged rows through one focused table component, and reduce the existing three-factor panel to a selected-ETF detail component. `EtfRadarView` remains the data orchestrator and controls selection, responsive detail presentation, and the collapsed validation section without changing backend APIs.

**Tech Stack:** Vue 3 Composition API, TypeScript, Ant Design Vue 4.2.6, VueUse breakpoints, Vitest, Vue Test Utils, ECharts.

## Global Constraints

- Do not change ETF universe membership, backend routes, three-factor formulas, thresholds, or source semantics.
- Continue to describe daily ETF share changes as activity proxies, never as confirmed Huijin purchases or sales.
- Preserve red-rise/green-fall classes together with explicit signs and text; color cannot be the only direction cue.
- Preserve stale-data fallbacks and keep one ETF failure from blocking other rows.
- Desktop uses an on-demand right-side detail drawer; screens below the `md` breakpoint render the same detail below the table.
- The page may contain exactly one seven-ETF list in the daily activity tab.
- Do not modify or commit the existing unrelated changes in `.superpowers/sdd/`, `apps/web-vue/src/typings/components.d.ts`, or `apps/web/pnpm-workspace.yaml`.

---

### Task 1: Unified ETF Activity Row Model

**Files:**
- Modify: `apps/web-vue/src/utils/domain/etfThreeFactor.ts`
- Test: `apps/web-vue/src/utils/domain/etfThreeFactor.test.ts`

**Interfaces:**
- Consumes: `HuijinEtfActivityItem[]` and `EtfThreeFactorItem[]` from `@/service/types`.
- Produces: `UnifiedEtfActivityRow`, `buildUnifiedEtfActivityRows(activityItems, factorItems)`, and `pickDefaultEtfActivitySymbol(rows)`.

- [ ] **Step 1: Write failing merge and default-selection tests**

Add fixtures with one complete activity item, one matching factor item, one activity-only item, and one factor-only item. Assert the union preserves all symbols, prefers overview identity and close data when available, falls back to factor close data, and picks the highest non-null signal score.

```ts
const rows = buildUnifiedEtfActivityRows(
  [activityItem({ symbol: '510050.SH', close_change_pct: 1.2 })],
  [factorItem({ symbol: '510050.SH', signal_score: 70 }), factorItem({ symbol: '510300.SH', signal_score: 90 })]
);

expect(rows.map(row => row.symbol)).toEqual(['510050.SH', '510300.SH']);
expect(rows[0]).toMatchObject({ closeChangePct: 1.2, signalScore: 70 });
expect(rows[1]).toMatchObject({ symbol: '510300.SH', signalScore: 90 });
expect(pickDefaultEtfActivitySymbol(rows)).toBe('510300.SH');
```

- [ ] **Step 2: Run the domain test and verify RED**

Run:

```bash
cd apps/web-vue
pnpm exec vitest run src/utils/domain/etfThreeFactor.test.ts
```

Expected: FAIL because the new exports do not exist.

- [ ] **Step 3: Implement the merged row model**

Add a small pure union keyed by symbol. Keep both source objects on each row so presentation components do not reimplement joins.

```ts
export type UnifiedEtfActivityRow = {
  symbol: string;
  name: string;
  indexName: string;
  closeChangePct: number | null;
  dailyChangePct: number | null;
  baselineChangePct: number | null;
  volumeRatio: number | null;
  signalScore: number | null;
  signalLevel: EtfThreeFactorLevel;
  activity: HuijinEtfActivityItem | null;
  factor: EtfThreeFactorItem | null;
};

export function buildUnifiedEtfActivityRows(
  activityItems: HuijinEtfActivityItem[],
  factorItems: EtfThreeFactorItem[]
): UnifiedEtfActivityRow[] {
  const activityBySymbol = new Map(activityItems.map(item => [item.symbol, item]));
  const factorBySymbol = new Map(factorItems.map(item => [item.symbol, item]));
  const symbols = [...activityItems.map(item => item.symbol)];
  for (const item of factorItems) if (!activityBySymbol.has(item.symbol)) symbols.push(item.symbol);

  return symbols.map(symbol => {
    const activity = activityBySymbol.get(symbol) ?? null;
    const factor = factorBySymbol.get(symbol) ?? null;
    return {
      symbol,
      name: activity?.name ?? factor?.name ?? symbol,
      indexName: activity?.index_name ?? factor?.index_name ?? '--',
      closeChangePct: activity?.close_change_pct ?? factor?.close_change_pct ?? null,
      dailyChangePct: activity?.daily_change_pct ?? null,
      baselineChangePct: activity?.cumulative_baseline_change_pct ?? activity?.baseline_change_pct ?? null,
      volumeRatio: factor?.volume_ratio ?? null,
      signalScore: factor?.signal_score ?? null,
      signalLevel: factor?.level ?? 'incomplete',
      activity,
      factor
    };
  });
}

export function pickDefaultEtfActivitySymbol(rows: UnifiedEtfActivityRow[]): string {
  return [...rows].sort((left, right) => (right.signalScore ?? -1) - (left.signalScore ?? -1))[0]?.symbol ?? '';
}
```

- [ ] **Step 4: Run the domain test and verify GREEN**

Run the command from Step 2. Expected: all `etfThreeFactor.test.ts` tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add apps/web-vue/src/utils/domain/etfThreeFactor.ts apps/web-vue/src/utils/domain/etfThreeFactor.test.ts
git commit -m "feat: merge ETF activity signal rows"
```

### Task 2: Single Sortable ETF Activity Table

**Files:**
- Create: `apps/web-vue/src/components/etf-radar/EtfActivityTable.vue`
- Create: `apps/web-vue/src/components/etf-radar/EtfActivityTable.test.ts`

**Interfaces:**
- Consumes: `rows: UnifiedEtfActivityRow[]` and `selectedSymbol: string`.
- Produces: `select(symbol: string)` when a row is activated.

- [ ] **Step 1: Write the failing component tests**

Mount three rows and assert one semantic table, all approved columns, default descending score order, sortable numeric headers, selected-row state, and selection emission.

```ts
expect(wrapper.findAll('[data-testid="activity-etf-row"]')).toHaveLength(3);
expect(wrapper.get('[data-testid="etf-activity-table"]').text()).toContain('三因子评分');
expect(rowSymbols()).toEqual(['510300.SH', '510050.SH', '159915.SZ']);
await wrapper.get('button[aria-label="收盘涨跌 可排序"]').trigger('click');
expect(rowSymbols()).toEqual(['510300.SH', '510050.SH', '159915.SZ']);
await wrapper.findAll('[data-testid="activity-etf-row"]')[1]!.trigger('click');
expect(wrapper.emitted('select')).toEqual([['510050.SH']]);
```

- [ ] **Step 2: Run the component test and verify RED**

```bash
cd apps/web-vue
pnpm exec vitest run src/components/etf-radar/EtfActivityTable.test.ts
```

Expected: FAIL because `EtfActivityTable.vue` does not exist.

- [ ] **Step 3: Implement the table**

Use a single native table in an internal horizontal scroll region. Keep sort state local and use a null-safe numeric comparator.

```ts
type SortKey = 'closeChangePct' | 'dailyChangePct' | 'baselineChangePct' | 'volumeRatio' | 'signalScore';

const sortKey = ref<SortKey>('signalScore');
const sortDirection = ref<'asc' | 'desc'>('desc');
const sortedRows = computed(() => [...props.rows].sort((left, right) => {
  const leftValue = left[sortKey.value] ?? Number.NEGATIVE_INFINITY;
  const rightValue = right[sortKey.value] ?? Number.NEGATIVE_INFINITY;
  return sortDirection.value === 'desc' ? rightValue - leftValue : leftValue - rightValue;
}));
```

Render these columns exactly once: ETF / index group, close change, daily share change, report baseline deviation, 20-day volume ratio, three-factor score, and status. Row buttons and keyboard activation emit `select` without fetching data.

- [ ] **Step 4: Run the component test and verify GREEN**

Run the command from Step 2. Expected: all table tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add apps/web-vue/src/components/etf-radar/EtfActivityTable.vue apps/web-vue/src/components/etf-radar/EtfActivityTable.test.ts
git commit -m "feat: add unified ETF activity table"
```

### Task 3: Reduce Three-Factor Panel to Selected-ETF Detail

**Files:**
- Modify: `apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.vue`
- Modify: `apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.test.ts`

**Interfaces:**
- Consumes unchanged props: `snapshot`, `history`, `selectedSymbol`, `historyLoading`, and `historyError`.
- Produces no ETF-list selection UI; the parent table owns selection.

- [ ] **Step 1: Rewrite tests to require detail-only behavior**

Keep chart, factor, history-gap, loading, error, and timeline assertions. Replace status-strip and table assertions with negative assertions proving this component cannot create a second ETF list.

```ts
expect(wrapper.get('[data-testid="factor-detail"]').text()).toContain('量能因子');
expect(wrapper.findAll('[data-testid="three-factor-chart"]')).toHaveLength(3);
expect(wrapper.find('[data-testid="dragon-status"]').exists()).toBe(false);
expect(wrapper.find('[data-testid="three-factor-table"]').exists()).toBe(false);
```

- [ ] **Step 2: Run the panel test and verify RED**

```bash
cd apps/web-vue
pnpm exec vitest run src/components/etf-radar/EtfThreeFactorPanel.test.ts
```

Expected: FAIL because the status strip and three-factor table still render.

- [ ] **Step 3: Remove repeated list responsibilities**

Delete the summary grid, seven-ETF status strip, monitor strip, table, table sorting state, `select` emit, and their orphaned styles. Keep selected-item resolution, factor evidence, three ECharts options, history states, and timeline. Rename visible headings to “ETF 活动证据” and keep the fixed disclaimer “三因子同向仅表示疑似活动”。

- [ ] **Step 4: Run the panel test and verify GREEN**

Run the command from Step 2. Expected: all panel tests pass with exactly three charts when history is usable.

- [ ] **Step 5: Commit Task 3**

```bash
git add apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.vue apps/web-vue/src/components/etf-radar/EtfThreeFactorPanel.test.ts
git commit -m "refactor: focus ETF factors on selected detail"
```

### Task 4: Integrate the Unified Daily Activity Workspace

**Files:**
- Modify: `apps/web-vue/src/views/EtfRadarView.vue`
- Modify: `apps/web-vue/src/views/EtfRadarView.test.ts`

**Interfaces:**
- Consumes: `buildUnifiedEtfActivityRows`, `pickDefaultEtfActivitySymbol`, `EtfActivityTable`, and the detail-only `EtfThreeFactorPanel`.
- Produces: one daily-activity table, desktop drawer / mobile inline detail, and a collapsed validation section.

- [ ] **Step 1: Add failing integration tests**

Update the daily activity tests to assert:

```ts
expect(wrapper.findAll('[data-testid="etf-activity-table"]')).toHaveLength(1);
expect(wrapper.find('[data-testid="three-factor-table"]').exists()).toBe(false);
expect(wrapper.find('[data-testid="factor-detail"]').exists()).toBe(false);
await wrapper.findAll('[data-testid="activity-etf-row"]')[1]!.trigger('click');
expect(wrapper.get('[data-testid="factor-detail"]').text()).toContain('三因子ETF2');
expect(api.getEtfThreeFactorHistory).toHaveBeenCalledWith('510300.SH', 40);
expect(wrapper.find('[aria-label="ETF 配对交叉验证"]').exists()).toBe(false);
await wrapper.get('button[aria-expanded="false"]').trigger('click');
expect(wrapper.get('[aria-label="ETF 配对交叉验证"]')).toBeTruthy();
```

Also update stale-response, route-symbol, overview-failure, and race-condition tests to select through the unified table instead of `dragon-status`.

- [ ] **Step 2: Run the view test and verify RED**

```bash
cd apps/web-vue
pnpm exec vitest run src/views/EtfRadarView.test.ts
```

Expected: FAIL because the page still renders two lists and validation is always expanded.

- [ ] **Step 3: Add merged rows and stable selection state**

```ts
const activityRows = computed(() => buildUnifiedEtfActivityRows(
  overview.value?.core_items ?? [],
  threeFactor.value?.items ?? []
));
const activityDetailOpen = ref(false);
const validationExpanded = ref(false);

function updateThreeFactorSelection() {
  const rows = activityRows.value;
  const requested = requestedThreeFactorSymbol();
  if (requested && rows.some(row => row.symbol === requested)) {
    selectedThreeFactorSymbol.value = requested;
    activityDetailOpen.value = true;
    return;
  }
  if (!rows.some(row => row.symbol === selectedThreeFactorSymbol.value)) {
    selectedThreeFactorSymbol.value = pickDefaultEtfActivitySymbol(rows);
  }
}

function selectThreeFactorSymbol(symbol: string) {
  if (!activityRows.value.some(row => row.symbol === symbol)) return;
  activityDetailOpen.value = true;
  if (symbol === selectedThreeFactorSymbol.value) return;
  selectedThreeFactorSymbol.value = symbol;
  threeFactorHistory.value = null;
  void loadThreeFactorHistory(symbol);
}
```

- [ ] **Step 4: Replace the repeated modules in the template**

Render in this order: one metrics row, compact metadata/source status, `EtfActivityTable`, selected detail, then validation disclosure. Use `useBreakpoints(breakpointsTailwind).smaller('md')` from `@vueuse/core`; desktop wraps detail in `ADrawer`, while compact screens render it after the table. The disclosure button controls `validationExpanded` with `aria-expanded` and `aria-controls`.

- [ ] **Step 5: Remove orphaned parent table code and styles**

Delete `coreColumns`, `coreCell`, `recordNumber`, old `core-table` template markup, and only the styles made unused by this replacement. Preserve helpers used by trajectory, holders, methodology, and validation views.

- [ ] **Step 6: Run view and component tests**

```bash
cd apps/web-vue
pnpm exec vitest run src/views/EtfRadarView.test.ts src/components/etf-radar/EtfActivityTable.test.ts src/components/etf-radar/EtfThreeFactorPanel.test.ts
```

Expected: all targeted tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add apps/web-vue/src/views/EtfRadarView.vue apps/web-vue/src/views/EtfRadarView.test.ts
git commit -m "feat: unify ETF daily activity workspace"
```

### Task 5: Full Verification and Visual QA

**Files:**
- Modify only if verification exposes a directly related defect in the files listed above.

**Interfaces:**
- Consumes the completed daily activity workspace.
- Produces verification evidence and a deployable Vue build.

- [ ] **Step 1: Run all Vue tests**

```bash
cd apps/web-vue
pnpm exec vitest run
```

Expected: all test files and tests pass.

- [ ] **Step 2: Run type checking**

```bash
cd apps/web-vue
pnpm run typecheck
```

Expected: exit code 0 with no TypeScript errors.

- [ ] **Step 3: Run the production build**

```bash
cd apps/web-vue
pnpm run build
```

Expected: `Build successful. Please see dist directory` and exit code 0.

- [ ] **Step 4: Run local visual checks**

Start the existing local stack on an unused port and inspect `/etf-radar?tab=activity` at desktop and 390px widths. Verify one ETF table, no page-level horizontal overflow, drawer/inline detail behavior, readable numeric columns, collapsed validation, and no console errors.

- [ ] **Step 5: Review the final diff**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only planned feature files plus the pre-existing unrelated user changes are present.
