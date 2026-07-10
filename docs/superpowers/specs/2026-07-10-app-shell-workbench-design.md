# AppShell And Workbench Design

## Background

StockMaster has grown from a stock screener into a multi-page trading workbench. Its existing Next.js, React, and Ant Design stack is stable and should remain in place. The UI now has a narrow, icon-only dark sidebar and a page wrapper that exposes optional English eyebrows, explanatory descriptions, and metadata. Individual pages then create their own toolbars and panel headings.

This leads to three user-facing issues:

- Navigation requires hover tooltips to identify most destinations and does not communicate module grouping.
- Page headers spend vertical space on explanatory copy that does not help repeated trading decisions.
- Similar panels, actions, and status messages have different visual treatments across pages.

The user selected a contextual sidebar, a compact command header, and a light product shell. The design borrows the structural discipline of Soybean Admin Ant Design without importing the template or changing the application framework.

## Goals

1. Make every main route feel like part of one professional workbench.
2. Make navigation and the current working context obvious without relying on hover text.
3. Remove decorative or repeated labels while preserving data freshness, fallback, risk, error, and action context.
4. Establish reusable shell, page, panel, and status primitives that work with existing Ant Design and Tailwind usage.
5. Keep data fetching, market models, route behavior, and current domain workflows unchanged.

## Non-Goals

- Do not migrate from Next.js/React/Ant Design to Vue, Naive UI, UnoCSS, or SoybeanAdmin-antd.
- Do not import template code, pages, authentication, permission, tab management, or mock data from Soybean Admin.
- Do not change any backend endpoint, provider, caching behavior, model, training, or trading logic.
- Do not rewrite the inner domain layouts of the auction, sector radar, heatmap, K-line, or model-maintenance workspaces in this change.
- Do not add a global live-data request merely to populate shell decoration.

## Chosen Approach

Use a medium structural refactor rather than a CSS-only reskin or a full page-by-page rebuild.

- A CSS-only reskin would preserve fragmented navigation and inconsistent page headers.
- A full rebuild would unnecessarily destabilize trading workflows that are already being iterated.
- The selected approach rebuilds shared structure, supplies a disciplined visual system, and lets existing content inherit the new vocabulary with narrowly scoped page migrations.

## Information Architecture

### Navigation Groups

The desktop navigation uses a light, contextual sidebar with visible labels. It is grouped by the user workflow instead of presenting an undifferentiated icon rail.

| Group | Routes |
| --- | --- |
| Market Workbench | 选股工作台, 自选股, 板块资金流, 市场热力图 |
| Trading Decision | 竞价雷达, 短线情绪 |
| System And Maintenance | AI 模型维护, 数据源配置 |

The grouping labels are navigation structure, not page eyebrows. They remain concise and only appear in the expanded desktop sidebar.

### AppShell

`AppShell` remains the root client shell and owns only application navigation and responsive chrome.

- Desktop expanded width: 216px. It shows brand, grouped labeled navigation, active route, and a single settings route.
- Desktop collapsed width: 64px. It shows the same navigation as icons with accessible tooltips; collapse state is persistent in local storage.
- Tablet and mobile: the sidebar becomes an Ant Design drawer triggered from a compact top bar. The active route and page title remain visible before opening the drawer.
- The current duplicate settings entry is removed. Data-source configuration lives once in the System And Maintenance group.
- The shell derives the human-readable route hierarchy from the same navigation configuration used to render links. Individual pages can override the context only for dynamic pages such as a stock detail route.
- The shell does not fetch market or provider status. A page may pass meaningful status into its own command bar when that status is already loaded for the workflow.

### Workbench Page Structure

`WorkbenchPage` becomes the common route canvas. Its header changes from a framed content card into a compact command bar.

The normal reading order is:

1. Route context in the shell top bar or a compact breadcrumb.
2. Page title.
3. A short, semantic status when it changes the decision, such as `实时 09:24`, `数据过期`, or `部分 fallback`.
4. One primary action and any necessary adjacent utility actions.
5. The existing domain content.

`eyebrow`, descriptive introduction copy, and free-form metadata are removed from the common page API. The replacement API is intentionally small:

- `title`
- `status`
- `actions`
- `context` for an explicit route override
- `children`, `className`, and `contentClassName`

No page must render a command bar when the content already supplies a more specific high-frequency control surface. The stock K-line and sector radar can use the common canvas while retaining their domain-specific command areas.

## Reusable Components

The refactor introduces only components that have a repeated, current purpose across three or more screens.

### `WorkbenchCommandBar`

Renders a title, optional semantic status, actions, and optional compact context. It is used by `WorkbenchPage` and can be used directly inside domain workspaces that need to control placement.

### `WorkbenchPanel`

Provides a semantic section surface with optional `title`, `extra`, and padding control. It is suitable for existing non-Card section panels. Existing Ant Design `Card` usage remains valid and inherits the same surface tokens through the `workbench-panel` class; there is no forced conversion of every panel in this release.

### `WorkbenchPanelHeader`

Provides the common panel title, optional status, and right-aligned actions. It replaces repeated border-bottom header markup only where the migration is already touching that panel.

### `WorkbenchStatus`

Displays one of `neutral`, `info`, `success`, `warning`, or `error` with optional timestamp. It is used for freshness, source fallback, background task, and error states. It does not replace numeric market performance colours.

### Shared Styling

The existing `workbench-page`, `workbench-panel`, `workbench-card`, `workbench-panel-divider`, `workbench-muted`, and selected-table-row classes remain compatibility points. Their styling changes to the new semantic token system so unchanged domain panels become visually consistent without a mass markup rewrite.

## Visual System

The application moves from a warm, terminal-like shell to a restrained cool-neutral product surface.

| Role | Use |
| --- | --- |
| App background | Cool light gray for the page canvas |
| Surface | White for panels and navigation |
| Subtle surface | Neutral light gray for table headers and passive controls |
| Primary | Blue only for current navigation, primary actions, focus, and selected state |
| Market semantics | Existing red/green language for price, risk, and market direction only |
| Warning and error | Amber and red only when the data or action state warrants it |

Component rules:

- Panels and controls use an 8px radius, precise 1px borders, and no decorative soft shadows.
- Default controls are quiet. Hover, keyboard focus, pressed, disabled, loading, selected, warning, and error states are visually distinct.
- Transitions are limited to short color, border, and opacity changes. `prefers-reduced-motion` disables non-essential transitions.
- Typography uses the existing system Chinese sans stack. Display-scale text and tracked all-caps labels are not introduced.
- The page width remains full-workbench width. Tables and visual analysis panels retain their current room instead of being boxed into a narrow centered dashboard.

## Label Reduction Policy

Remove labels that describe the interface rather than the data or next decision:

- Remove English page eyebrows such as `Watchlist`, `Settings`, and `Model Maintenance`.
- Remove static page descriptions such as “正在加载…” or long purpose statements from normal loaded views.
- Remove duplicate source names and repeated “current status” labels when an adjacent semantic status already communicates the condition.
- Remove the duplicate settings navigation entry.

Keep information that changes trust, timing, or the next user action:

- Trade date, intraday timestamp, and data freshness.
- Fallback, partial, stale, error, and risk state.
- Empty-state recovery actions and error explanations.
- Panel titles that distinguish separate datasets or workflows.
- Accessibility names and tooltip text when navigation is collapsed.

## Migration Scope

### Shared Code

- Rebuild `apps/web/components/AppShell.tsx` around a single typed navigation configuration.
- Update `apps/web/components/AntdAppProvider.tsx` and `apps/web/app/globals.css` with the new semantic tokens and Ant Design component tokens.
- Replace the current `WorkbenchPage` header and extend `apps/web/components/workbench/` with the four shared primitives.
- Update `apps/web/components/workbench/workbenchLayout.ts` and its tests for the new canvas and header contracts.

### Route-Level Adoption

Migrate the page wrappers and loading placeholders for:

- `/`, `/watchlist`, `/sectors`, `/heatmap`
- `/auction`, `/sentiment`
- `/model-maintenance`, `/settings`, `/stock/[symbol]`

Each route retains its data loading and domain components. Where an active workspace currently passes `description`, `eyebrow`, or `meta` to `WorkbenchPage`, remove those props and replace any decision-relevant state with `WorkbenchStatus` only when the state is already available.

## Responsive And Accessibility Requirements

- Sidebar labels are visible at desktop width, with a deliberate collapse control rather than accidental clipping.
- At widths below the desktop breakpoint, the navigation becomes a keyboard-accessible drawer; page content remains usable without horizontal page overflow.
- Focus-visible outlines meet contrast requirements on light and dark interactive states.
- Icons used without adjacent visible labels have `aria-label` and tooltip coverage.
- The command bar wraps actions before truncating them. Primary action text remains fully visible.
- Loading, empty, error, disabled, and stale-data states remain textually clear after decorative descriptions are removed.

## Verification

1. Add focused tests for navigation grouping, active route resolution, collapse-state behavior, and compact workbench class contracts.
2. Update existing source-level UI tests that assert old header structure or old layout classes.
3. Run the complete frontend TypeScript and Node test suite.
4. Run a production build.
5. Run browser smoke checks for `/`, `/auction`, `/sectors`, `/heatmap`, `/sentiment`, `/watchlist`, `/settings`, `/model-maintenance`, and a stock detail page at desktop and mobile viewports.
6. Confirm that the shell introduces no additional API calls and that unchanged domain routes preserve their existing data behavior.

## Acceptance Criteria

- All main routes render within the new light AppShell without losing route navigation.
- The selected route is visible in the expanded sidebar, collapsed sidebar, and mobile drawer.
- Common page headers use the compact command layout and no longer render eyebrows or persistent explanatory descriptions.
- Existing panels inherit coherent surface, border, table, and control styling without requiring every domain component to be rewritten.
- Market red/green semantics remain intact and are not reused for generic application navigation.
- No route adds a global data fetch solely for shell display.
- Desktop and mobile smoke checks show no Next.js error overlay, clipping, or horizontal page overflow.
