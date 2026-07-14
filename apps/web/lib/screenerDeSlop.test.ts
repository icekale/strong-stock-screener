import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workbench = readFileSync(new URL("../components/ScreenerWorkbench.tsx", import.meta.url), "utf8");
const overview = readFileSync(new URL("../components/screener/MarketOverviewPanels.tsx", import.meta.url), "utf8");
const filters = readFileSync(new URL("../components/screener/FilterLogicRail.tsx", import.meta.url), "utf8");
const candidates = readFileSync(new URL("../components/screener/CandidateResults.tsx", import.meta.url), "utf8");
const screenerTypes = readFileSync(new URL("../components/screener/types.ts", import.meta.url), "utf8");
const screenerUtils = readFileSync(new URL("../components/screener/screenerUtils.ts", import.meta.url), "utf8");
const czscShadow = readFileSync(new URL("./czscShadow.ts", import.meta.url), "utf8");
const globals = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

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
    "AI 模型维护",
    "Data:",
    "Delayed 15min",
  ]) {
    assert.equal(source.includes(legacy), false, `legacy screener copy remains: ${legacy}`);
  }

  assert.match(filters, /当前筛选/);
  assert.match(filters, /匹配/);
  assert.match(filters, /visibleCount/);
  assert.match(filters, /只/);
  assert.match(candidates, /title: "股票"/);
});

test("candidate metadata is text-first instead of a pill wall", () => {
  assert.match(candidates, /GsgfSummaryText/);
  assert.match(candidates, /IndustrySummary/);
  assert.doesNotMatch(candidates, /GsgfSummaryPills/);
  assert.doesNotMatch(candidates, /IndustryBadge/);
  assert.doesNotMatch(candidates, /bg-violet-50|bg-indigo-50|bg-sky-50/);
});

test("candidate results display shadow research without sorting by it", () => {
  assert.match(czscShadow, /CZSC研究/);
  assert.match(candidates, /CzscShadowSummaryText/);
  assert.doesNotMatch(candidates, /sort\([^)]*czsc_v2_shadow_rank/);
});

test("screener panels use the compact product radius", () => {
  const source = [workbench, overview, filters, candidates].join("\n");

  assert.doesNotMatch(source, /rounded-xl/);
  assert.match(overview, /screener-metrics/);
  assert.match(overview, /screener-index-strip/);
});

test("screener statuses use product tokens instead of the default Tailwind rainbow", () => {
  const source = [candidates, filters, screenerTypes, screenerUtils].join("\n");

  assert.doesNotMatch(source, /bg-(sky|amber|violet|indigo)-50/);
  assert.doesNotMatch(source, /text-(sky|amber|violet|indigo)-700/);
});

test("screener keeps dense metrics and filters readable on narrow screens", () => {
  assert.match(overview, /screener-metric--breadth/);
  assert.match(overview, /screener-metric__value/);
  assert.match(candidates, /candidate-filter-scroll/);
  assert.match(globals, /\.screener-metric--breadth \.screener-metric__value/);
  assert.match(globals, /\.candidate-filter-scroll/);
});
