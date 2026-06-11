import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("standalone strong stock workbench is wired without daily-report modules", () => {
  const typesSource = readFileSync(new URL("./types.ts", import.meta.url), "utf8");
  const apiSource = readFileSync(new URL("./api.ts", import.meta.url), "utf8");
  const componentSource = readFileSync(new URL("../components/ScreenerWorkbench.tsx", import.meta.url), "utf8");
  const pageSource = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(typesSource, /StrongStockScreeningResponse/);
  assert.match(typesSource, /status: "focus" \| "wait_pullback" \| "reduce_risk" \| "data_incomplete"/);
  assert.match(typesSource, /risk_action: "hold_watch" \| "reduce" \| "empty"/);
  assert.doesNotMatch(typesSource, /status: .*"empty"/);
  assert.match(apiSource, /createScreenRun/);
  assert.match(apiSource, /scan_limit: scanLimit/);
  assert.match(apiSource, /getDataSourceStatus/);
  assert.match(componentSource, /强势股选股工作台/);
  assert.match(componentSource, /TickFlow/);
  assert.match(componentSource, /空仓纪律触发/);
  assert.match(componentSource, /运行筛选/);
  assert.match(pageSource, /ScreenerWorkbench/);
  assert.doesNotMatch(componentSource + pageSource, /报告生成|历史报告|OCR|定时生成/);
});
