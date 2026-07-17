# 金融工作台产品化 UI 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变业务数据和交易行为的前提下，将 Soybean Vue 工作台统一为浅色机构金融终端，并逐批重构 AppShell、核心页面和辅助页面。

**Architecture:** 以共享的页面头、指标带、模块头、状态标签和数据列表组件承载视觉与交互规范；页面保留现有数据请求和业务动作，只重排模板和展示状态。全局 token 控制颜色、边框、间距、字体和响应式断点，AppShell 单独负责导航、标签栏和内容滚动边界。

**Tech Stack:** Vue 3、TypeScript、Ant Design Vue、UnoCSS、ECharts、Vitest、vue-tsc、Vite、in-app browser。

---

## 文件边界

- Create: `apps/web-vue/src/components/common/workbench/page-header.vue` 页面标题和操作区。
- Create: `apps/web-vue/src/components/common/workbench/metric-strip.vue` 关键指标带。
- Create: `apps/web-vue/src/components/common/workbench/section-header.vue` 模块标题、来源和更新时间。
- Create: `apps/web-vue/src/components/common/workbench/status-tag.vue` 可访问的状态标签。
- Create: `apps/web-vue/src/components/common/workbench/data-list.vue` 列表密度、空状态和错误状态。
- Create: `apps/web-vue/src/components/common/workbench/workbench.ts` 状态归一化和金融数字格式化纯函数。
- Create: `apps/web-vue/src/components/common/workbench/workbench.test.ts` 共享组件的纯状态与格式测试。
- Create: `apps/web-vue/src/styles/css/workbench.css` 全局工作台 token、通用类和 reduced-motion 规则。
- Modify: `apps/web-vue/src/styles/css/global.css` 引入工作台样式。
- Modify: `apps/web-vue/src/theme/settings.ts` 主色、背景、边框、阴影和默认布局设置。
- Modify: `apps/web-vue/src/layouts/base-layout/index.vue` AppShell footer/内容边界和移动端安全空间。
- Modify: `apps/web-vue/src/layouts/modules/global-header/index.vue` 顶栏结构和工具密度。
- Modify: `apps/web-vue/src/layouts/modules/global-sider/index.vue` 侧栏尺寸和品牌区。
- Modify: `apps/web-vue/src/layouts/modules/global-menu/index.scss` 当前导航样式。
- Modify: `apps/web-vue/src/layouts/modules/global-tab/index.vue` 标签栏视觉和间距。
- Create: `apps/web-vue/src/layouts/base-layout/layoutState.ts` footer 安全空间和侧栏状态纯函数。
- Test: `apps/web-vue/src/layouts/base-layout/base-layout.test.ts` AppShell 几何和收起/展开状态。
- Modify: `apps/web-vue/src/views/HomeView.vue` 市场总览核心布局。
- Modify: `apps/web-vue/src/views/AuctionView.vue` 竞价雷达布局。
- Modify: `apps/web-vue/src/views/ScreenerView.vue` 强势选股布局。
- Modify: `apps/web-vue/src/views/StockView.vue` 个股工作区布局。
- Modify: `apps/web-vue/src/views/ChanlunView.vue` 缠论工作台布局。
- Modify: `apps/web-vue/src/views/MarketView.vue` 板块/热图辅助布局。
- Modify: `apps/web-vue/src/views/SentimentView.vue` 情绪复盘辅助布局。
- Modify: `apps/web-vue/src/views/WatchlistView.vue` 自选风险辅助布局。
- Modify: `apps/web-vue/src/views/SystemView.vue` 模型与数据源辅助布局。
- Test: `apps/web-vue/src/components/common/workbench/workbench.test.ts`、现有页面和图表测试。

## Task 1: 建立工作台视觉 token 和共享基础组件

**Files:**
- Create: `apps/web-vue/src/styles/css/workbench.css`
- Modify: `apps/web-vue/src/styles/css/global.css`
- Modify: `apps/web-vue/src/theme/settings.ts`
- Create: `apps/web-vue/src/components/common/workbench/page-header.vue`
- Create: `apps/web-vue/src/components/common/workbench/metric-strip.vue`
- Create: `apps/web-vue/src/components/common/workbench/section-header.vue`
- Create: `apps/web-vue/src/components/common/workbench/status-tag.vue`
- Create: `apps/web-vue/src/components/common/workbench/data-list.vue`
- Create: `apps/web-vue/src/components/common/workbench/workbench.ts`
- Test: `apps/web-vue/src/components/common/workbench/workbench.test.ts`

- [ ] **Step 1: Write failing tests for shared formatting and status contracts**

  Test the public behavior rather than DOM details:

  ```ts
  import { describe, expect, it } from 'vitest';
  import { normalizeWorkbenchStatus, formatWorkbenchNumber } from './workbench';

  describe('workbench primitives', () => {
    it('normalizes data source statuses to stable labels', () => {
      expect(normalizeWorkbenchStatus('success')).toEqual({ label: '成功', tone: 'success' });
      expect(normalizeWorkbenchStatus('failed')).toEqual({ label: '失败', tone: 'error' });
      expect(normalizeWorkbenchStatus('partial')).toEqual({ label: '部分', tone: 'warning' });
      expect(normalizeWorkbenchStatus('unknown')).toEqual({ label: '待确认', tone: 'neutral' });
    });

    it('formats financial values without raw floating point noise', () => {
      expect(formatWorkbenchNumber(8.870000000000001, 'price')).toBe('8.87');
      expect(formatWorkbenchNumber(258000000000, 'money')).toBe('2.58万亿');
      expect(formatWorkbenchNumber(null, 'price')).toBe('--');
    });
  });
  ```

- [ ] **Step 2: Run the new test and verify it fails**

  Run from `apps/web-vue`:

  ```bash
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vitest run src/components/common/workbench/workbench.test.ts
  ```

  Expected: FAIL because the shared helper module and status/number contracts do not exist.

- [ ] **Step 3: Add the shared helper and component contracts**

  Create `workbench.ts` next to the test with these stable types and rules:

  ```ts
  export type WorkbenchStatusTone = 'success' | 'error' | 'warning' | 'info' | 'neutral';
  export type WorkbenchStatus = { label: string; tone: WorkbenchStatusTone };
  export function normalizeWorkbenchStatus(value: unknown): WorkbenchStatus {
    if (value === 'success') return { label: '成功', tone: 'success' };
    if (value === 'failed') return { label: '失败', tone: 'error' };
    if (value === 'partial') return { label: '部分', tone: 'warning' };
    if (value === 'running') return { label: '运行中', tone: 'info' };
    return { label: '待确认', tone: 'neutral' };
  }

  export function formatWorkbenchNumber(value: number | null | undefined, kind: 'price' | 'money' | 'percent'): string {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
    if (kind === 'price') return value.toFixed(2);
    if (kind === 'percent') return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
    const abs = Math.abs(value);
    const sign = value < 0 ? '-' : '';
    if (abs >= 100_000_000_000) return `${sign}${(abs / 100_000_000_000).toFixed(2)}万亿`;
    if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(2)}亿`;
    if (abs >= 10_000) return `${sign}${(abs / 10_000).toFixed(2)}万`;
    return value.toFixed(0);
  }
  ```

  `PageHeader` accepts `title`, optional `description`, default slot for actions, and an optional `meta` slot. `MetricStrip` accepts an array of `{ key, label, value, helper?, tone? }` and renders responsive two-column mobile / four-column desktop metrics. `SectionHeader` accepts `title`, optional `source` and `updatedAt`, with an action slot. `StatusTag` accepts a raw status and renders label plus tone class. `DataList` accepts `items`, `loading`, `emptyDescription`, `error`, and exposes the existing list-item slot so page-specific actions remain unchanged.

  Use `defineOptions` names for auto-import discovery and keep all component styles in `workbench.css`; do not add a new dependency.

- [ ] **Step 4: Define the restrained institutional token layer**

  Add `workbench.css` tokens for:

  ```css
  :root {
    --wb-primary: #245b8a;
    --wb-primary-soft: #eef5fb;
    --wb-layout: #f4f7fa;
    --wb-surface: #ffffff;
    --wb-border: #d9e2ea;
    --wb-ink: #1f2d3d;
    --wb-muted: #617184;
    --wb-positive: #c9363e;
    --wb-negative: #16805c;
    --wb-warning: #a66a00;
    --wb-radius: 6px;
    --wb-gap: 16px;
  }
  ```

  Include focus-visible outlines, selected navigation treatment, compact module spacing, `font-variant-numeric: tabular-nums`, and `@media (prefers-reduced-motion: reduce)` to disable nonessential transitions. Import the file from `global.css`.

- [ ] **Step 5: Apply theme defaults without changing business behavior**

  Change `themeSettings.themeColor` to `#245b8a`, light `layout` to `#f4f7fa`, and keep error/success semantics aligned with A-share red-up/green-down usage. Keep the existing theme drawer overrides functional. Do not remove dark mode support; make the new tokens fall back to existing dark variables when dark mode is active.

- [ ] **Step 6: Run tests and typecheck**

  ```bash
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vitest run src/components/common/workbench/workbench.test.ts
  ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
  ```

  Expected: shared tests pass and typecheck exits 0.

- [ ] **Step 7: Commit the shared visual layer**

  ```bash
  git add apps/web-vue/src/styles/css/workbench.css apps/web-vue/src/styles/css/global.css apps/web-vue/src/theme/settings.ts apps/web-vue/src/components/common/workbench
  git commit -m "feat: add institutional workbench design system"
  ```

## Task 2: Rework AppShell, navigation, tabs, and content boundaries

**Files:**
- Modify: `apps/web-vue/src/layouts/base-layout/index.vue`
- Modify: `apps/web-vue/src/layouts/modules/global-header/index.vue`
- Modify: `apps/web-vue/src/layouts/modules/global-sider/index.vue`
- Modify: `apps/web-vue/src/layouts/modules/global-menu/index.scss`
- Modify: `apps/web-vue/src/layouts/modules/global-tab/index.vue`
- Create: `apps/web-vue/src/layouts/base-layout/layoutState.ts`
- Test: `apps/web-vue/src/layouts/base-layout/base-layout.test.ts` (create focused shell-state tests if no existing shell test exists)

- [ ] **Step 1: Add shell regression tests for content/footer boundaries**

  Test pure class/measurement helpers rather than brittle rendered snapshots:

  ```ts
  it('reserves footer space only when footer is fixed', () => {
    expect(getContentBottomPadding({ fixedFooter: true, footerHeight: 48 })).toBe(72);
    expect(getContentBottomPadding({ fixedFooter: false, footerHeight: 48 })).toBe(24);
  });
  ```

  Also assert a collapsed sidebar state can toggle back to expanded through the exposed menu toggle action.

- [ ] **Step 2: Implement shell geometry and visual states**

  Keep `AdminLayout` as the layout engine. Set the content bottom padding helper to `footerHeight + 24` only for fixed footer mode, preserve the existing mobile drawer behavior, and add stable classes for header, sider, tab and content surfaces. Use `--wb-primary-soft` for selected navigation and a 2px left indicator for `.select-menu` active entries.

- [ ] **Step 3: Reduce template chrome**

  Update `GlobalHeader` to keep only brand/breadcrumb, full screen, language, theme and user actions. Update `GlobalSider` and menu styles for 208px expanded / 64px collapsed widths, clear icon alignment and tooltip-ready collapsed items. Update `GlobalTab` to use compact 36-40px tabs with visible close affordances and no heavy chrome background.

- [ ] **Step 4: Run shell tests and typecheck**

  ```bash
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vitest run src/layouts/base-layout/base-layout.test.ts
  ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
  ```

  Expected: shell tests pass and no page component loses its route rendering.

- [ ] **Step 5: Commit AppShell changes**

  ```bash
  git add apps/web-vue/src/layouts apps/web-vue/src/theme/settings.ts
  git commit -m "feat: refine financial workbench shell"
  ```

## Task 3: Refactor market overview, auction radar, and strong-stock screener

**Files:**
- Modify: `apps/web-vue/src/views/HomeView.vue`
- Modify: `apps/web-vue/src/views/AuctionView.vue`
- Modify: `apps/web-vue/src/views/ScreenerView.vue`
- Test: existing `apps/web-vue/src/utils/domain/marketOverview*.test.ts`, `apps/web-vue/src/utils/domain/auctionModel.test.ts`, and new focused pure layout helpers if needed.

- [ ] **Step 1: Replace repeated headers and metric rows**

  Use `<PageHeader>` for title/date/refresh and `<MetricStrip>` for the four headline metrics. Do not change calls to `getMarketOverview`, `getMarketRankings`, `getSectorRadar`, `getAuctionModelTop3`, or screener APIs. Keep the already-confirmed market overview order: main indices, sector flow/emotion, market metrics, then Top3 and rankings.

- [ ] **Step 2: Make the auction Top3 the primary decision surface**

  Keep the existing selected model items and click-to-stock behavior, but render them as a compact ranked list with columns for rank, name, probability, bucket and note. Keep the existing cache miss message and refresh behavior. Replace the verbose explanatory block with a `SectionHeader` source/status line.

- [ ] **Step 3: Convert auction intensity and screener results into aligned data surfaces**

  Keep every existing action (add to watchlist, open stock, filters). Align name/symbol, industry, score, open gap/pct change, liquidity, risk and action in stable columns. On mobile render each row as a two-line block with the action in the first row and key percentage on the right.

- [ ] **Step 4: Add module-local state and empty/error presentations**

  Replace generic empty text with actionable descriptions. Keep partial successful data visible when another request fails. Use `StatusTag` for model/data status and preserve A-share red/green semantics in text classes.

- [ ] **Step 5: Run core page tests and browser checks**

  ```bash
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vitest run src/utils/domain/marketOverview.test.ts src/utils/domain/marketOverviewTrend.test.ts src/utils/domain/auctionModel.test.ts
  ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
  ```

  Browser checks at `http://127.0.0.1:3123/` and `http://127.0.0.1:3123/auction`: verify first viewport hierarchy, Top3 row actions, loading/error isolation, 1280px and 390px layouts.

- [ ] **Step 6: Commit core scanning pages**

  ```bash
  git add apps/web-vue/src/views/HomeView.vue apps/web-vue/src/views/AuctionView.vue apps/web-vue/src/views/ScreenerView.vue apps/web-vue/src/components/common/workbench
  git commit -m "feat: productize market scanning pages"
  ```

## Task 4: Refactor individual stock and Chanlun workspaces

**Files:**
- Modify: `apps/web-vue/src/views/StockView.vue`
- Modify: `apps/web-vue/src/views/ChanlunView.vue`
- Modify: `apps/web-vue/src/components/charts/StockKlineChart.vue` only for container/state class hooks; keep chart option behavior unchanged.
- Test: `apps/web-vue/src/utils/domain/stockViewState.test.ts`, `apps/web-vue/src/utils/charts/chartOptions.test.ts`, `apps/web-vue/src/utils/charts/chanlunOverlay.test.ts`.

- [ ] **Step 1: Preserve existing request and indicator contracts**

  Before template changes, run the current stock/indicator tests and record the baseline. Do not change `getStockKline`, `getStockQuote`, `getChanlunAnalysis`, request-id protection, period mapping, indicator persistence, GSGF annotations, or chart option calculations.

- [ ] **Step 2: Recompose the stock workspace**

  Replace the page title row with `PageHeader`, replace the four quote cards with `MetricStrip`, and keep period tabs, MA/sub-indicator controls, GSGF and Chanlun toggles in a single responsive toolbar. Keep the `K 线 / 信息 / 战法 / 概念` tab contract. Remove redundant nested `a-card` wrappers while retaining section titles and current structure data.

- [ ] **Step 3: Recompose the Chanlun workspace**

  Use a compact `PageHeader` with symbol input, load action and period switch. Keep the K-line canvas full width. Move layer/MA/sub-indicator controls into one control strip. Preserve signal list, paper account, draft generation, human approval and simulated fill actions; make order status and reasons visually primary.

- [ ] **Step 4: Preserve footer safety and responsive chart sizing**

  Keep the fixed-footer bottom-space class from the existing stock view fix. Verify chart canvas bottoms and paper account controls remain visible above the footer at 390px and 1280px.

- [ ] **Step 5: Run chart and workspace regression tests**

  ```bash
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vitest run src/utils/domain/stockViewState.test.ts src/utils/charts/chartOptions.test.ts src/utils/charts/chanlunOverlay.test.ts src/components/charts/EChart.test.ts
  ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
  ```

  Browser checks at `http://127.0.0.1:3123/stock/600000.SH` and `http://127.0.0.1:3123/chanlun?symbol=600000.SH`: verify K-line controls, indicator numeric legends, tooltip values, Chanlun layer switches, paper-order controls and no footer overlap.

- [ ] **Step 6: Commit workspaces**

  ```bash
  git add apps/web-vue/src/views/StockView.vue apps/web-vue/src/views/ChanlunView.vue apps/web-vue/src/components/charts/StockKlineChart.vue
  git commit -m "feat: refine stock and chanlun workspaces"
  ```

## Task 5: Refactor secondary product pages

**Files:**
- Modify: `apps/web-vue/src/views/MarketView.vue`
- Modify: `apps/web-vue/src/views/SentimentView.vue`
- Modify: `apps/web-vue/src/views/WatchlistView.vue`
- Modify: `apps/web-vue/src/views/SystemView.vue`

- [ ] **Step 1: Refactor MarketView**

  Use `PageHeader` and `SectionHeader`. Keep sectors/heatmap segmented navigation, sector mode switch, board selection and stock list behavior. Make chart the primary surface, keep board rows compact, and move market summary metrics into a small strip below the heatmap.

- [ ] **Step 2: Refactor SentimentView**

  Use `MetricStrip` for emotion score, limit-up, break-board and consecutive-board height. Replace the large generic result block with a compact trade-permission status panel showing permission, market state, risk level and confidence. Keep main-sector and intraday reminder lists unchanged in data and actions.

- [ ] **Step 3: Refactor WatchlistView**

  Keep the input/save/add actions in a clear watchlist toolbar. Render structure triggers and pool details with `DataList` and `StatusTag`; preserve stock navigation and save/add behavior.

- [ ] **Step 4: Refactor SystemView**

  Place data source health and running jobs first, then cache maintenance, training performance and model maintenance packet. Make source failure details visible without hiding them behind tags. Preserve clear-cache and generate-packet actions.

- [ ] **Step 5: Run secondary-page checks**

  ```bash
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vitest run
  ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
  ```

  Browser checks at `/market`, `/sentiment`, `/watchlist`, and `/system` at 1280px and 390px. Verify list actions, filters, errors, empty states and source statuses.

- [ ] **Step 6: Commit secondary pages**

  ```bash
  git add apps/web-vue/src/views/MarketView.vue apps/web-vue/src/views/SentimentView.vue apps/web-vue/src/views/WatchlistView.vue apps/web-vue/src/views/SystemView.vue
  git commit -m "feat: unify secondary workbench pages"
  ```

## Task 6: Full regression, visual QA, and integration handoff

**Files:**
- Modify only files required by failed regression checks.
- Test: all existing Vue tests, typecheck, production build, browser screenshots.

- [ ] **Step 1: Run the complete automated suite**

  ```bash
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vitest run
  ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
  VITE_ICON_PREFIX=icon VITE_ICON_LOCAL_PREFIX=local-icon ./node_modules/.bin/vite build --mode prod
  git diff --check
  ```

  Expected: all Vue tests pass, typecheck exits 0, production build reports success, and there is no whitespace error.

- [ ] **Step 2: Run visual QA matrix**

  Capture the following routes at 1280x720 and 390x844: `/`, `/auction`, `/screener`, `/stock/600000.SH`, `/chanlun?symbol=600000.SH`, `/market`, `/sentiment`, `/watchlist`, `/system`.

  Check: first read within three seconds, no clipped text, no overlapping controls, primary action visible, selected navigation clear, loading/empty/error states readable, charts resize without blank canvas, and fixed footer does not cover content.

- [ ] **Step 3: Review changed files and verify scope**

  ```bash
  git status --short --branch
  git log --oneline -12
  git diff main...HEAD --stat
  ```

  Confirm no API, data-source, model, strategy, or order behavior files changed.

- [ ] **Step 4: Commit only final QA fixes**

  ```bash
  git add apps/web-vue/src/components/common/workbench apps/web-vue/src/styles/css/workbench.css apps/web-vue/src/styles/css/global.css apps/web-vue/src/theme/settings.ts apps/web-vue/src/layouts apps/web-vue/src/views
  git commit -m "fix: close workbench visual qa gaps"
  ```
