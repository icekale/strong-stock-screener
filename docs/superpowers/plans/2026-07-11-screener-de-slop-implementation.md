# Screener De-slop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the confirmed AI-template visual and copy patterns from `/screener` while preserving every screening, filtering, export, navigation, and watchlist behavior.

**Architecture:** Keep the existing React component boundaries and data flow. Replace bilingual terminal-style copy, equal-weight metric cards, filter chips, and candidate metadata pills with Chinese product copy, continuous panels, plain metadata, and the existing restrained product tokens.

**Tech Stack:** Next.js 15, React 19, TypeScript 5.7, Ant Design 6, Tailwind utilities, Node test runner, `kill-ai-slop` scanner, Chrome headless.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `apps/web/lib/screenerDeSlop.test.ts` | Source contracts for approved copy, hierarchy, and metadata presentation. |
| `apps/web/components/ScreenerWorkbench.tsx` | Chinese result title and top-level panel composition. |
| `apps/web/components/screener/MarketOverviewPanels.tsx` | Index strip, data status, market metrics, and primary actions. |
| `apps/web/components/screener/FilterLogicRail.tsx` | Current-filter summary, Chinese actions, and task progress. |
| `apps/web/components/screener/CandidateResults.tsx` | Chinese table headers and compact decision/sector metadata. |
| `apps/web/app/globals.css` | Scoped screener panel, metric, metadata, and responsive geometry. |

### Task 1: Add failing presentation contracts

**Files:**
- Create: `apps/web/lib/screenerDeSlop.test.ts`

- [ ] **Step 1: Add source-level contracts**

Create tests that load the four screener source files and assert:

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workbench = readFileSync(new URL("../components/ScreenerWorkbench.tsx", import.meta.url), "utf8");
const overview = readFileSync(new URL("../components/screener/MarketOverviewPanels.tsx", import.meta.url), "utf8");
const filters = readFileSync(new URL("../components/screener/FilterLogicRail.tsx", import.meta.url), "utf8");
const candidates = readFileSync(new URL("../components/screener/CandidateResults.tsx", import.meta.url), "utf8");

test("screener uses Chinese product copy instead of terminal-style bilingual labels", () => {
  const source = [workbench, overview, filters, candidates].join("\n");

  for (const legacy of [
    "FILTER LOGIC",
    "Matched:",
    "Reset",
    "Screener Results",
    "TOTAL TURNOVER",
    "SENTIMENT",
    "ADVANCE/DECLINE",
    "Search stock, code",
    "运行 AI 筛选",
    "股票 STOCK",
    "决策 SCORE",
    "板块 SECTOR",
    "风险 RISK",
    "操作 ACTION",
  ]) {
    assert.doesNotMatch(source, new RegExp(legacy.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }

  assert.match(filters, /当前筛选/);
  assert.match(filters, /匹配.*只/);
  assert.match(candidates, /title: "股票"/);
});

test("candidate metadata is text-first instead of a pill wall", () => {
  assert.match(candidates, /GsgfSummaryText/);
  assert.match(candidates, /IndustrySummary/);
  assert.doesNotMatch(candidates, /GsgfSummaryPills/);
  assert.doesNotMatch(candidates, /IndustryBadge/);
  assert.doesNotMatch(candidates, /bg-violet-50|bg-indigo-50|bg-sky-50/);
});

test("screener panels use the compact product radius", () => {
  const source = [overview, filters, candidates].join("\n");

  assert.doesNotMatch(source, /rounded-xl/);
  assert.match(source, /screener-metrics/);
  assert.match(source, /screener-index-strip/);
});
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd apps/web
node --experimental-strip-types --test lib/screenerDeSlop.test.ts
```

Expected: FAIL on the existing bilingual labels, pill functions, `rounded-xl`, and missing scoped classes.

### Task 2: Simplify market context and metrics

**Files:**
- Modify: `apps/web/components/screener/MarketOverviewPanels.tsx`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Replace index pills with a continuous strip**

Render the four indices inside `.screener-index-strip`. Each item shows name, optional point value, and signed change. Keep red/green only on the signed change. Replace `LIVE` with `数据时间` and use a plain status line plus one real data-source `Tag`.

- [ ] **Step 2: Use Chinese primary actions**

Change the search placeholder to `搜索股票名称或代码` and the primary button to `运行筛选` / `筛选中`.

- [ ] **Step 3: Merge the metric cards into one panel**

Replace the four-card grid wrapper with one `<section className="screener-metrics">` containing the existing turnover metric, sentiment metric, breadth metric, and data-coverage metric in that order. Rename the shared metric component to `MarketMetric` and the breadth component to `MarketBreadthMetric` so their names describe product UI rather than terminal styling.

Use labels `总成交额`, `情绪指数`, `上涨 / 下跌`, and `数据覆盖`. Replace English footer labels with `交易日`, `短线情绪`, `市场广度`, and `板块覆盖`. Keep existing data values and helper text.

- [ ] **Step 4: Add stable metric geometry**

Add `.screener-index-strip`, `.screener-index-strip__item`, `.screener-metrics`, and `.screener-metric` styles with 6px outer radius, shared borders, four desktop columns, two tablet columns, and one mobile column only when needed. Do not add shadows.

- [ ] **Step 5: Run the focused test**

Run Task 1 Step 2. Expected: market copy and scoped class assertions move toward GREEN; candidate assertions remain RED.

### Task 3: Replace the filter chip rail with a text summary

**Files:**
- Modify: `apps/web/components/screener/FilterLogicRail.tsx`

- [ ] **Step 1: Build the filter summary array**

Create `currentFilterSummary(filters, scanLimit, strategy)` returning strings for the existing criteria: `20日内涨停`, strategy name, scan count, KDJ limit, market-cap limit, selected markets, and selected industries.

- [ ] **Step 2: Render the summary in normal text flow**

Render `当前筛选` as the section label and join the summary with visible middle-dot separators. Remove `FilterChip`. Show `匹配 {visibleCount} 只`, `刷新源`, `运行筛选`, and `重置` on the action side.

- [ ] **Step 3: Keep job and editor behavior unchanged**

Preserve the task status, progress bar, parameter `<details>`, source refresh, saved filters, and all callbacks. Replace `font-mono` on the progress count with `tabular-nums`.

- [ ] **Step 4: Run the focused test**

Run Task 1 Step 2. Expected: filter copy assertions pass; candidate assertions remain RED.

### Task 4: Replace the candidate pill wall with decision metadata

**Files:**
- Modify: `apps/web/components/ScreenerWorkbench.tsx`
- Modify: `apps/web/components/screener/CandidateResults.tsx`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Use Chinese result titles and table headers**

Change all result headings to `选股结果` and columns to `股票`, `决策`, `板块`, `风险`, and `操作`.

- [ ] **Step 2: Add `GsgfSummaryText`**

Replace `GsgfSummaryPills` and its evidence/diagnostic pills with a compact block:

```tsx
function GsgfSummaryText({ gsgf }: { gsgf: GsgfAnalysis | null }) {
  if (!gsgf) return null;
  const evidence = gsgf.evidence_refs.length > 0 ? `证据 ${gsgf.evidence_refs.length}` : null;
  const diagnostics = Object.entries(gsgf.diagnostics)
    .filter(([, item]) => item.flags.length > 0 || item.score !== null)
    .map(([name]) => gsgfLabel(name))
    .slice(0, 2);
  const detail = [
    gsgf.setup_type ? `形态 ${gsgfLabel(gsgf.setup_type)}` : null,
    gsgf.confirm_type ? `确认 ${gsgfLabel(gsgf.confirm_type)}` : null,
    evidence,
    diagnostics.length > 0 ? `诊断 ${diagnostics.join("/")}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <div className="candidate-decision-meta">
      <div>股是股非 {gsgf.total_score} · {gsgf.final_status} · {gsgfLabel(gsgf.zone)} · {gsgfLabel(gsgf.action)}</div>
      {detail ? <div className="candidate-decision-meta__detail" title={detail}>{detail}</div> : null}
    </div>
  );
}
```

- [ ] **Step 3: Add `IndustrySummary`**

Render the industry as primary text and `板块强度 {label} {signed score}` as muted secondary text. No colored industry pill.

- [ ] **Step 4: Update desktop and mobile candidate rows**

Keep one status badge using `statusCopy`. Show score as tabular text beside it, followed by `GsgfSummaryText`. Use `IndustrySummary` in both the table and mobile card. Preserve risk text, K-line, highlight, selection, and watchlist actions.

- [ ] **Step 5: Add scoped metadata styles**

Add `.candidate-decision`, `.candidate-decision-meta`, `.candidate-decision-meta__detail`, and `.candidate-industry-summary` with normal text, ellipsis, fixed line height, and no colored background.

- [ ] **Step 6: Run focused and full tests**

```bash
cd apps/web
node --experimental-strip-types --test lib/screenerDeSlop.test.ts
corepack pnpm test
```

Expected: the new contract and all existing tests pass.

### Task 5: Verify scanner, build, and responsive rendering

**Files:**
- Inspect the files modified in Tasks 2-4.

- [ ] **Step 1: Run production checks**

```bash
cd apps/web
corepack pnpm build
cd ../..
git diff --check
```

- [ ] **Step 2: Re-run the skill scanner**

Run `kill-ai-slop/scripts/scan.mjs apps/web --json`. Ignore `.next` and `.next-dev` output, then confirm the screener-specific bilingual, violet/indigo/sky metadata, `rounded-xl`, and pill-wall hits are gone or reduced to intentional status tags.

- [ ] **Step 3: Capture real-data screenshots**

Capture `/screener` at `1440x1100`, `781x995`, and `390x844`. Confirm market context, metrics, filters, and the first candidate remain readable with no horizontal page overflow or overlapping controls.

- [ ] **Step 4: Commit the verified implementation**

```bash
git add apps/web/lib/screenerDeSlop.test.ts apps/web/components/ScreenerWorkbench.tsx apps/web/components/screener/MarketOverviewPanels.tsx apps/web/components/screener/FilterLogicRail.tsx apps/web/components/screener/CandidateResults.tsx apps/web/app/globals.css
git commit -m "refactor: remove AI template styling from screener"
```
