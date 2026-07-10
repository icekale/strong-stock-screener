# App Shell And Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace StockMaster's icon-only dark shell and explanatory page headers with a light, responsive product shell and reusable compact workbench primitives without changing market data or business workflows.

**Architecture:** Keep the Next.js, React, and Ant Design stack. Put route grouping and route-context lookup in a pure `lib/appNavigation.ts` module so the shell uses one source of truth and tests do not need JSX. Build a small set of composable workbench components around the existing CSS compatibility classes, then migrate route wrappers and their active workspaces away from `eyebrow`, `description`, and `meta` props.

**Tech Stack:** Next.js 15, React, TypeScript, Ant Design 5, Tailwind utility classes, CSS custom properties, Node built-in test runner.

---

## File Structure

- Create: `apps/web/lib/appNavigation.ts` - typed route groups, active-route lookup, and route-context lookup used by `AppShell`.
- Create: `apps/web/lib/appNavigation.test.ts` - pure navigation behavior tests.
- Create: `apps/web/lib/workbenchPresentation.ts` - status tone type and CSS-class helper shared by workbench primitives.
- Create: `apps/web/lib/workbenchPresentation.test.ts` - pure status presentation tests.
- Create: `apps/web/lib/appShellUi.test.ts` - source-level guardrails for the responsive shell contract.
- Create: `apps/web/lib/workbenchUi.test.ts` - source-level guardrails for the compact header and product theme contract.
- Create: `apps/web/components/workbench/WorkbenchCommandBar.tsx` - compact page command header.
- Create: `apps/web/components/workbench/WorkbenchStatus.tsx` - semantic status primitive.
- Create: `apps/web/components/workbench/WorkbenchPanel.tsx` - reusable semantic panel and panel header.
- Modify: `apps/web/components/AppShell.tsx` - light grouped desktop sidebar, collapsible icon rail, and mobile drawer.
- Modify: `apps/web/components/AntdAppProvider.tsx` - cool-neutral Ant Design token system.
- Modify: `apps/web/components/workbench/WorkbenchPage.tsx` - replace the framed explanatory header with `WorkbenchCommandBar`.
- Modify: `apps/web/components/workbench/workbenchLayout.ts` - page/canvas class contracts for the new shell.
- Modify: `apps/web/components/workbench/workbenchLayout.test.ts` - update the old class-string assertions.
- Modify: `apps/web/app/globals.css` - semantic surface tokens, shell layout, command bar, panel, status, responsive, focus, and reduced-motion styles.
- Modify: route wrappers and active workspaces listed in Task 5 - remove obsolete `WorkbenchPage` header props while preserving all data-loading behavior.

### Task 1: Add Pure Navigation Configuration

**Files:**
- Create: `apps/web/lib/appNavigation.ts`
- Create: `apps/web/lib/appNavigation.test.ts`
- Modify: `apps/web/components/AppShell.tsx`

- [ ] **Step 1: Write the failing navigation tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import {
  APP_NAVIGATION_GROUPS,
  getNavigationContext,
  getSelectedNavigationKey,
} from "./appNavigation";

test("navigation groups match the confirmed trading workflow", () => {
  assert.deepEqual(
    APP_NAVIGATION_GROUPS.map((group) => [group.key, group.items.map((item) => item.key)]),
    [
      ["market", ["/", "/watchlist", "/sectors", "/heatmap"]],
      ["decision", ["/auction", "/sentiment"]],
      ["system", ["/model-maintenance", "/settings"]],
    ],
  );
});

test("nested stock routes keep the stock context without adding a persistent navigation item", () => {
  assert.equal(getSelectedNavigationKey("/stock/603823.SH"), "/stock");
  assert.deepEqual(getNavigationContext("/stock/603823.SH"), ["个股", "个股详情"]);
  assert.equal(APP_NAVIGATION_GROUPS.flatMap((group) => group.items).some((item) => item.key === "/stock"), false);
});

test("route context resolves exact routes before nested route prefixes", () => {
  assert.equal(getSelectedNavigationKey("/auction"), "/auction");
  assert.deepEqual(getNavigationContext("/auction"), ["交易决策", "竞价雷达"]);
  assert.deepEqual(getNavigationContext("/settings"), ["系统维护", "数据源配置"]);
});
```

- [ ] **Step 2: Run the new test to verify it fails because the module is absent**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/appNavigation.test.ts
```

Expected: the test fails with `Cannot find module './appNavigation'`.

- [ ] **Step 3: Implement the minimal route configuration and lookup helpers**

Create `apps/web/lib/appNavigation.ts`:

```ts
export type AppNavigationItem = {
  href: string;
  icon: "screener" | "watchlist" | "sectors" | "heatmap" | "auction" | "sentiment" | "model" | "settings";
  key: string;
  label: string;
  title: string;
};

export type AppNavigationGroup = {
  key: "market" | "decision" | "system";
  label: string;
  items: AppNavigationItem[];
};

export const APP_NAVIGATION_GROUPS: AppNavigationGroup[] = [
  {
    key: "market",
    label: "市场工作台",
    items: [
      { href: "/", icon: "screener", key: "/", label: "选股工作台", title: "选股工作台" },
      { href: "/watchlist", icon: "watchlist", key: "/watchlist", label: "自选股", title: "自选股管理" },
      { href: "/sectors", icon: "sectors", key: "/sectors", label: "板块资金流", title: "板块资金流" },
      { href: "/heatmap", icon: "heatmap", key: "/heatmap", label: "市场热力图", title: "市场热力图" },
    ],
  },
  {
    key: "decision",
    label: "交易决策",
    items: [
      { href: "/auction", icon: "auction", key: "/auction", label: "竞价雷达", title: "竞价雷达" },
      { href: "/sentiment", icon: "sentiment", key: "/sentiment", label: "短线情绪", title: "短线情绪中心" },
    ],
  },
  {
    key: "system",
    label: "系统维护",
    items: [
      { href: "/model-maintenance", icon: "model", key: "/model-maintenance", label: "AI 模型维护", title: "AI 模型维护" },
      { href: "/settings", icon: "settings", key: "/settings", label: "数据源配置", title: "数据源配置" },
    ],
  },
];

const STOCK_CONTEXT = ["个股", "个股详情"] as const;

export function getSelectedNavigationKey(pathname: string): string {
  if (pathname.startsWith("/stock/")) return "/stock";
  const item = APP_NAVIGATION_GROUPS.flatMap((group) => group.items).find(
    (candidate) => candidate.key === "/" ? pathname === "/" : pathname.startsWith(candidate.key),
  );
  return item?.key ?? "/";
}

export function getNavigationContext(pathname: string): readonly [string, string] {
  if (pathname.startsWith("/stock/")) return STOCK_CONTEXT;
  const selectedKey = getSelectedNavigationKey(pathname);
  for (const group of APP_NAVIGATION_GROUPS) {
    const item = group.items.find((candidate) => candidate.key === selectedKey);
    if (item) return [group.label, item.title];
  }
  return ["市场工作台", "选股工作台"];
}
```

In `apps/web/components/AppShell.tsx`, replace the local navigation item array and `selectedNavKey` function with imports from `../lib/appNavigation`. Do not alter the rendered sidebar in this task; this step only makes navigation data testable.

- [ ] **Step 4: Run the navigation tests and TypeScript check**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/appNavigation.test.ts
npx tsc --noEmit
```

Expected: three passing navigation tests and no TypeScript errors.

- [ ] **Step 5: Commit the navigation configuration**

```bash
git add apps/web/lib/appNavigation.ts apps/web/lib/appNavigation.test.ts apps/web/components/AppShell.tsx
git commit -m "refactor: centralize workbench navigation"
```

### Task 2: Build Status And Workbench Primitives

**Files:**
- Create: `apps/web/lib/workbenchPresentation.ts`
- Create: `apps/web/lib/workbenchPresentation.test.ts`
- Create: `apps/web/components/workbench/WorkbenchStatus.tsx`
- Create: `apps/web/components/workbench/WorkbenchCommandBar.tsx`
- Create: `apps/web/components/workbench/WorkbenchPanel.tsx`
- Modify: `apps/web/components/workbench/WorkbenchPage.tsx`

- [ ] **Step 1: Write the failing pure status-presentation test**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { buildWorkbenchStatusClassName, WORKBENCH_STATUS_TONES } from "./workbenchPresentation";

test("workbench status maps every semantic tone to a stable CSS modifier", () => {
  assert.deepEqual(WORKBENCH_STATUS_TONES, ["neutral", "info", "success", "warning", "error"]);
  assert.equal(buildWorkbenchStatusClassName(), "workbench-status workbench-status--neutral");
  assert.equal(buildWorkbenchStatusClassName("success"), "workbench-status workbench-status--success");
  assert.equal(buildWorkbenchStatusClassName("error"), "workbench-status workbench-status--error");
});
```

- [ ] **Step 2: Run the test to verify it fails because the presentation module is absent**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/workbenchPresentation.test.ts
```

Expected: the test fails with `Cannot find module './workbenchPresentation'`.

- [ ] **Step 3: Implement the presentation helper and three JSX primitives**

Create `apps/web/lib/workbenchPresentation.ts`:

```ts
export const WORKBENCH_STATUS_TONES = ["neutral", "info", "success", "warning", "error"] as const;
export type WorkbenchStatusTone = (typeof WORKBENCH_STATUS_TONES)[number];

export function buildWorkbenchStatusClassName(tone: WorkbenchStatusTone = "neutral"): string {
  return `workbench-status workbench-status--${tone}`;
}
```

Create `apps/web/components/workbench/WorkbenchStatus.tsx`:

```tsx
import type { ReactNode } from "react";
import { buildWorkbenchStatusClassName, type WorkbenchStatusTone } from "../../lib/workbenchPresentation";

type WorkbenchStatusProps = { children: ReactNode; tone?: WorkbenchStatusTone };

export function WorkbenchStatus({ children, tone = "neutral" }: WorkbenchStatusProps) {
  return <span className={buildWorkbenchStatusClassName(tone)}>{children}</span>;
}
```

Create `apps/web/components/workbench/WorkbenchCommandBar.tsx`:

```tsx
import type { ReactNode } from "react";
import { joinClassNames } from "./workbenchLayout";

type WorkbenchCommandBarProps = {
  actions?: ReactNode;
  className?: string;
  context?: ReactNode;
  status?: ReactNode;
  title: ReactNode;
};

export function WorkbenchCommandBar({ actions, className, context, status, title }: WorkbenchCommandBarProps) {
  return (
    <header className={joinClassNames("workbench-command-bar", className)}>
      <div className="min-w-0">
        {context ? <div className="workbench-command-context">{context}</div> : null}
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h1 className="workbench-command-title">{title}</h1>
          {status}
        </div>
      </div>
      {actions ? <div className="workbench-command-actions">{actions}</div> : null}
    </header>
  );
}
```

Create `apps/web/components/workbench/WorkbenchPanel.tsx`:

```tsx
import type { ElementType, ReactNode } from "react";
import { joinClassNames } from "./workbenchLayout";

type WorkbenchPanelProps = {
  as?: ElementType;
  children: ReactNode;
  className?: string;
  extra?: ReactNode;
  padded?: boolean;
  title?: ReactNode;
};

export function WorkbenchPanel({ as: Component = "section", children, className, extra, padded = false, title }: WorkbenchPanelProps) {
  return (
    <Component className={joinClassNames("workbench-panel", className)}>
      {title || extra ? <WorkbenchPanelHeader extra={extra} title={title} /> : null}
      <div className={padded ? "workbench-panel-body" : undefined}>{children}</div>
    </Component>
  );
}

export function WorkbenchPanelHeader({ extra, title }: Pick<WorkbenchPanelProps, "extra" | "title">) {
  return (
    <div className="workbench-panel-header">
      {title ? <h2 className="workbench-panel-title">{title}</h2> : <span />}
      {extra ? <div className="workbench-panel-extra">{extra}</div> : null}
    </div>
  );
}
```

Refactor `apps/web/components/workbench/WorkbenchPage.tsx` so its public props are `actions`, `children`, `className`, `contentClassName`, `context`, `status`, and `title`. Render `WorkbenchCommandBar` only when `title` exists. Delete `WorkbenchPageHeader`, `description`, `eyebrow`, and `meta` from the component API.

- [ ] **Step 4: Run the new test, full frontend suite, and TypeScript check**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/workbenchPresentation.test.ts
npm test
```

Expected: the status helper test passes and the full suite remains green. If existing source tests depend on the old `WorkbenchPage` markup, update their expectation before proceeding to the next task.

- [ ] **Step 5: Commit the primitives**

```bash
git add apps/web/lib/workbenchPresentation.ts apps/web/lib/workbenchPresentation.test.ts apps/web/components/workbench/WorkbenchStatus.tsx apps/web/components/workbench/WorkbenchCommandBar.tsx apps/web/components/workbench/WorkbenchPanel.tsx apps/web/components/workbench/WorkbenchPage.tsx
git commit -m "feat: add shared workbench primitives"
```

### Task 3: Establish The Cool-Neutral Theme Contract

**Files:**
- Create: `apps/web/lib/workbenchUi.test.ts`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/components/AntdAppProvider.tsx`
- Modify: `apps/web/components/workbench/workbenchLayout.ts`
- Modify: `apps/web/components/workbench/workbenchLayout.test.ts`

- [ ] **Step 1: Write the failing visual-contract tests**

Create `apps/web/lib/workbenchUi.test.ts`:

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
const provider = readFileSync(new URL("../components/AntdAppProvider.tsx", import.meta.url), "utf8");
const page = readFileSync(new URL("../components/workbench/WorkbenchPage.tsx", import.meta.url), "utf8");

test("workbench uses the confirmed light product tokens", () => {
  assert.match(css, /--workbench-bg:\s*#f8fafc;/);
  assert.match(css, /--workbench-surface:\s*#ffffff;/);
  assert.match(css, /--workbench-primary:\s*#2563eb;/);
  assert.match(provider, /colorPrimary:\s*"#2563eb"/);
});

test("common page headers use the compact command bar instead of explanatory props", () => {
  assert.match(page, /WorkbenchCommandBar/);
  assert.doesNotMatch(page, /description\??:/);
  assert.doesNotMatch(page, /eyebrow\??:/);
  assert.doesNotMatch(page, /meta\??:/);
  assert.match(css, /\.workbench-command-bar\s*\{/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
});
```

Extend `apps/web/components/workbench/workbenchLayout.test.ts` so the expected base class is:

```ts
assert.equal(buildWorkbenchPageClassName(), "workbench-page min-h-screen");
assert.equal(
  buildWorkbenchContentClassName(),
  "mx-auto flex w-full max-w-none flex-col gap-4 px-4 py-4 lg:px-6 lg:py-5",
);
```

- [ ] **Step 2: Run the visual-contract tests to verify they fail on the warm theme and old header**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/workbenchUi.test.ts components/workbench/workbenchLayout.test.ts
```

Expected: token, command-bar, and content-spacing assertions fail against the old implementation.

- [ ] **Step 3: Apply semantic CSS and Ant Design tokens**

At the start of `apps/web/app/globals.css`, replace the current workbench variables with:

```css
:root {
  --workbench-bg: #f8fafc;
  --workbench-surface: #ffffff;
  --workbench-surface-muted: #f1f5f9;
  --workbench-border: #e2e8f0;
  --workbench-ink: #0f172a;
  --workbench-muted: #64748b;
  --workbench-primary: #2563eb;
  --workbench-primary-hover: #1d4ed8;
}
```

Add the shared styles below the existing workbench compatibility classes. Preserve existing sector-radar classes and market red/green variables.

```css
.workbench-command-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 48px;
  border-bottom: 1px solid var(--workbench-border);
  padding-bottom: 12px;
}

.workbench-command-context { color: var(--workbench-muted); font-size: 12px; line-height: 18px; }
.workbench-command-title { margin: 0; color: var(--workbench-ink); font-size: 20px; font-weight: 700; line-height: 28px; }
.workbench-command-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.workbench-panel { border-color: var(--workbench-border) !important; border-radius: 8px !important; background: var(--workbench-surface) !important; box-shadow: none !important; }
.workbench-panel-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; border-bottom: 1px solid var(--workbench-border); padding: 0 16px; }
.workbench-panel-title { margin: 0; color: var(--workbench-ink); font-size: 14px; font-weight: 650; line-height: 20px; }
.workbench-panel-extra { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.workbench-panel-body { padding: 16px; }
.workbench-status { display: inline-flex; align-items: center; min-height: 22px; border-radius: 4px; padding: 0 6px; font-size: 12px; font-weight: 650; }
.workbench-status--neutral { background: #f1f5f9; color: #475569; }
.workbench-status--info { background: #eff6ff; color: #1d4ed8; }
.workbench-status--success { background: #ecfdf3; color: #067647; }
.workbench-status--warning { background: #fffaeb; color: #b54708; }
.workbench-status--error { background: #fef3f2; color: #b42318; }

@media (max-width: 980px) {
  .workbench-command-bar { align-items: flex-start; flex-direction: column; }
  .workbench-command-actions { justify-content: flex-start; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: 0.01ms !important; }
}
```

In `apps/web/components/AntdAppProvider.tsx`, use `#f8fafc`, `#ffffff`, `#f1f5f9`, `#e2e8f0`, `#0f172a`, `#64748b`, and `#2563eb` for the corresponding base, container, layout, border, text, secondary text, info, and primary tokens. Set `Layout.siderBg` to `#ffffff`, `Menu.itemSelectedBg` to `#eff6ff`, `Menu.itemSelectedColor` to `#1d4ed8`, and `Table.headerBg` to `#f8fafc`.

Update `buildWorkbenchContentClassName` in `apps/web/components/workbench/workbenchLayout.ts` to return `mx-auto flex w-full max-w-none flex-col gap-4 px-4 py-4 lg:px-6 lg:py-5` before appending custom classes.

- [ ] **Step 4: Run the visual-contract tests and full frontend test suite**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/workbenchUi.test.ts components/workbench/workbenchLayout.test.ts
npm test
```

Expected: the explicit token and command-bar tests pass, and no existing test fails due to the shared class changes.

- [ ] **Step 5: Commit the shared visual system**

```bash
git add apps/web/app/globals.css apps/web/components/AntdAppProvider.tsx apps/web/components/workbench/workbenchLayout.ts apps/web/components/workbench/workbenchLayout.test.ts apps/web/lib/workbenchUi.test.ts
git commit -m "feat: establish product workbench theme"
```

### Task 4: Rebuild The Responsive AppShell

**Files:**
- Create: `apps/web/lib/appShellUi.test.ts`
- Modify: `apps/web/components/AppShell.tsx`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Write the failing source-level shell test**

Create `apps/web/lib/appShellUi.test.ts`:

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../components/AppShell.tsx", import.meta.url), "utf8");
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

test("app shell exposes grouped navigation, collapse persistence, and a mobile drawer", () => {
  assert.match(source, /APP_NAVIGATION_GROUPS/);
  assert.match(source, /collapsedWidth=\{64\}/);
  assert.match(source, /width=\{216\}/);
  assert.match(source, /localStorage\.getItem\("stockmaster:app-shell-collapsed"\)/);
  assert.match(source, /localStorage\.setItem\("stockmaster:app-shell-collapsed"/);
  assert.match(source, /<Drawer/);
  assert.match(source, /getNavigationContext\(pathname\)/);
  assert.match(css, /\.app-shell__desktop-nav\s*\{/);
  assert.match(css, /\.app-shell__mobile-header\s*\{/);
});
```

- [ ] **Step 2: Run the shell test to verify it fails against the icon-only shell**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/appShellUi.test.ts
```

Expected: assertions for the 216px layout, drawer, grouped config, and persistence fail.

- [ ] **Step 3: Implement the shell around the pure route configuration**

Refactor `apps/web/components/AppShell.tsx` with these implementation constraints:

```tsx
const SHELL_COLLAPSED_STORAGE_KEY = "stockmaster:app-shell-collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const context = getNavigationContext(pathname);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(SHELL_COLLAPSED_STORAGE_KEY) === "true");
  }, []);

  function updateCollapsed(nextCollapsed: boolean) {
    setCollapsed(nextCollapsed);
    window.localStorage.setItem(SHELL_COLLAPSED_STORAGE_KEY, String(nextCollapsed));
  }

  return (
    <Layout className="app-shell min-h-screen">
      <Layout.Sider className="app-shell__desktop-nav" collapsed={collapsed} collapsedWidth={64} trigger={null} width={216}>
        <ShellNavigation collapsed={collapsed} onNavigate={() => undefined} onToggle={() => updateCollapsed(!collapsed)} pathname={pathname} />
      </Layout.Sider>
      <Layout className="app-shell__main min-w-0">
        <Layout.Header className="app-shell__mobile-header">
          <Button aria-label="打开导航" icon={<MenuOutlined />} onClick={() => setDrawerOpen(true)} type="text" />
          <span>{context[1]}</span>
        </Layout.Header>
        <Drawer closable={false} onClose={() => setDrawerOpen(false)} open={drawerOpen} placement="left" title="StockMaster" width={280}>
          <ShellNavigation collapsed={false} onNavigate={() => setDrawerOpen(false)} pathname={pathname} />
        </Drawer>
        {children}
      </Layout>
    </Layout>
  );
}
```

Implement `ShellNavigation` in the same file. It must iterate `APP_NAVIGATION_GROUPS`, map the string icon key to the existing Ant Design icons, render group labels only when not collapsed, and use `getSelectedNavigationKey(pathname)` to apply selected state. The collapse control is an icon button at the bottom of the desktop navigation. The drawer has no collapse control. Use the existing `Link`, `Tooltip`, and Ant Design icon set; do not add another icon dependency.

Add these app-shell layout rules to `apps/web/app/globals.css`:

```css
.app-shell { background: var(--workbench-bg); }
.app-shell__desktop-nav { border-right: 1px solid var(--workbench-border); background: var(--workbench-surface) !important; }
.app-shell__main { background: var(--workbench-bg); }
.app-shell__mobile-header { display: none; height: 48px; padding: 0 12px; border-bottom: 1px solid var(--workbench-border); background: var(--workbench-surface) !important; color: var(--workbench-ink); }
.app-shell__nav-item { display: flex; align-items: center; gap: 10px; min-height: 36px; border-radius: 6px; color: #475569; }
.app-shell__nav-item--active { background: #eff6ff; color: #1d4ed8; font-weight: 650; }

@media (max-width: 980px) {
  .app-shell__desktop-nav { display: none; }
  .app-shell__mobile-header { display: flex; align-items: center; gap: 8px; }
}
```

- [ ] **Step 4: Run shell, navigation, and complete frontend tests**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/appNavigation.test.ts lib/appShellUi.test.ts
npm test
```

Expected: navigation and shell guards pass; the complete test suite remains green.

- [ ] **Step 5: Commit the responsive shell**

```bash
git add apps/web/components/AppShell.tsx apps/web/app/globals.css apps/web/lib/appShellUi.test.ts
git commit -m "feat: rebuild responsive application shell"
```

### Task 5: Migrate Route Headers And Remove Decorative Labels

**Files:**
- Modify: `apps/web/app/watchlist/page.tsx`
- Modify: `apps/web/app/heatmap/page.tsx`
- Modify: `apps/web/app/sentiment/page.tsx`
- Modify: `apps/web/app/auction/page.tsx`
- Modify: `apps/web/app/settings/page.tsx`
- Modify: `apps/web/app/model-maintenance/page.tsx`
- Modify: `apps/web/app/watchlist/WatchlistWorkspace.tsx`
- Modify: `apps/web/app/heatmap/HeatmapWorkspace.tsx`
- Modify: `apps/web/app/sentiment/SentimentWorkspace.tsx`
- Modify: `apps/web/app/settings/SettingsWorkspace.tsx`
- Modify: `apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx`
- Modify: `apps/web/lib/workbenchUi.test.ts`

- [ ] **Step 1: Extend the failing UI test to forbid old common-header props in migrated files**

Append to `apps/web/lib/workbenchUi.test.ts`:

```ts
const migratedFiles = [
  "../app/watchlist/page.tsx",
  "../app/heatmap/page.tsx",
  "../app/sentiment/page.tsx",
  "../app/auction/page.tsx",
  "../app/settings/page.tsx",
  "../app/model-maintenance/page.tsx",
  "../app/watchlist/WatchlistWorkspace.tsx",
  "../app/heatmap/HeatmapWorkspace.tsx",
  "../app/sentiment/SentimentWorkspace.tsx",
  "../app/settings/SettingsWorkspace.tsx",
  "../app/model-maintenance/ModelMaintenanceWorkspace.tsx",
].map((relativePath) => readFileSync(new URL(relativePath, import.meta.url), "utf8"));

test("migrated workspaces do not keep decorative WorkbenchPage header props", () => {
  for (const source of migratedFiles) {
    assert.doesNotMatch(source, /<WorkbenchPage[\\s\\S]{0,600}eyebrow=/);
    assert.doesNotMatch(source, /<WorkbenchPage[\\s\\S]{0,600}description=/);
    assert.doesNotMatch(source, /<WorkbenchPage[\\s\\S]{0,600}meta=/);
  }
});
```

- [ ] **Step 2: Run the test to verify it fails on the current page headers**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/workbenchUi.test.ts
```

Expected: it fails because one or more migrated `WorkbenchPage` uses still pass `description`, `eyebrow`, or `meta`.

- [ ] **Step 3: Remove explanatory props and retain only decision-relevant state**

Apply the following transformation everywhere in the migrated list:

```tsx
// Before
<WorkbenchPage
  description="正在加载全 A 行业热图和行情状态。"
  eyebrow="Settings"
  meta={<span>TickFlow 实时</span>}
  title="市场热力图"
>

// After
<WorkbenchPage title="市场热力图">
```

For active workspaces, keep `title`, `actions`, and existing `status` only when they describe live data, fallback, a task result, or a risk. Do not replace a removed description with another permanent explanatory sentence. Keep all existing `Empty`, `Alert`, tooltip, error, stale-data, and recovery-action copy intact because those messages are operational rather than decorative.

Do not modify `apps/web/app/sectors/SectorReplicaPanel.tsx`, `apps/web/app/auction/AuctionWorkspace.tsx`, `apps/web/app/stock/[symbol]/StockKlineWorkspace.tsx`, or data-fetching functions in this task. They inherit the new shell and token system but retain their specific high-frequency controls.

- [ ] **Step 4: Run the migrated-header test and full frontend suite**

Run from `apps/web`:

```bash
node --experimental-strip-types --test lib/workbenchUi.test.ts
npm test
```

Expected: migrated header checks pass and existing empty/error copy tests remain valid.

- [ ] **Step 5: Commit the migration**

```bash
git add apps/web/app/watchlist/page.tsx apps/web/app/heatmap/page.tsx apps/web/app/sentiment/page.tsx apps/web/app/auction/page.tsx apps/web/app/settings/page.tsx apps/web/app/model-maintenance/page.tsx apps/web/app/watchlist/WatchlistWorkspace.tsx apps/web/app/heatmap/HeatmapWorkspace.tsx apps/web/app/sentiment/SentimentWorkspace.tsx apps/web/app/settings/SettingsWorkspace.tsx apps/web/app/model-maintenance/ModelMaintenanceWorkspace.tsx apps/web/lib/workbenchUi.test.ts
git commit -m "refactor: simplify workbench page headers"
```

### Task 6: Verify The Complete Workbench Surface

**Files:**
- Modify only files required by a failed verification from Tasks 1-5.

- [ ] **Step 1: Run all frontend checks from a clean worktree**

Run from `apps/web`:

```bash
npm test
npm run build
```

Expected: every Node test passes, TypeScript passes, and `next build` produces all application routes without errors.

- [ ] **Step 2: Start the local production-equivalent web server and run UI smoke checks**

Run from the repository root in separate terminals:

```bash
docker compose up -d --build strong-stock-screener
UI_BASE_URL=http://127.0.0.1:3110 node scripts/smoke-ui.mjs / /auction /sectors /heatmap /sentiment /watchlist /settings /model-maintenance /stock/603823.SH
```

Expected: no failed responses, Next.js error overlays, console errors, or horizontal overflow at the smoke script's desktop and mobile viewports.

- [ ] **Step 3: Manually verify the selected interaction states**

Check at `http://127.0.0.1:3110/auction` and `http://127.0.0.1:3110/heatmap`:

```text
1. Sidebar labels and group headings are visible at desktop width.
2. Collapse changes the sidebar to a 64px icon rail and persists after reload.
3. At mobile width, the header opens a drawer and the active route remains visible.
4. Page headers show only title, meaningful status, and actions; no English eyebrow or permanent explanatory description remains.
5. Primary blue, market red/green, warning, error, keyboard focus, loading, and disabled states remain visually distinct.
```

- [ ] **Step 4: Check the final diff and commit any verification fix**

Run from the repository root:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and no unexpected modified files. A failed verification is a stop condition: return to the task that owns the failing file, add a focused failing regression test there, and repeat that task's explicit staging command after the correction passes. Do not make an unscoped verification-only commit.

- [ ] **Step 5: Record completion against the acceptance criteria**

Confirm in the implementation handoff that navigation grouping, expanded/collapsed/mobile navigation, compact command headers, semantic status treatment, inherited panel styling, no new global data fetches, test/build success, and browser smoke checks all passed.

## Plan Self-Review

- Spec coverage: Tasks 1 and 4 implement the grouped, persistent, responsive shell; Tasks 2 and 5 implement the compact header and reusable components; Task 3 implements the selected light theme and semantic visual tokens; Task 6 covers build, responsive smoke testing, and no unintended behavior changes.
- Scope: the plan excludes backend, models, provider behavior, and deep domain-workspace rewrites as required by the approved design.
- Consistency: `APP_NAVIGATION_GROUPS`, `getSelectedNavigationKey`, `WorkbenchCommandBar`, and `WorkbenchStatus` retain the same names from their creation tasks through migration and verification.
- Placeholder scan: the plan contains no unresolved implementation placeholders; every task names exact files, test assertions, implementation constraints, verification commands, and commit boundaries.
