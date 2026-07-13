import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  activeChanlunFilterCount,
  chanlunFilterFields,
  chanlunScreeningView,
} from "./chanlunScreener.ts";
import type { ChanlunScreeningSummary } from "./types.ts";


test("screen filters preserve enabled Chanlun conditions", () => {
  const filters = chanlunFilterFields({
    chanlun_min_confluence_score: 0,
    chanlun_require_confirmed_buy: true,
  });

  assert.deepEqual(filters, {
    chanlun_min_confluence_score: 0,
    chanlun_require_confirmed_buy: true,
  });
  assert.equal(activeChanlunFilterCount(filters), 2);
});


test("Chanlun screening view summarizes complete confluence and latest signal", () => {
  const summary: ChanlunScreeningSummary = {
    availability: "ready",
    freshness: "fresh",
    periods: [
      {
        period: "5m",
        availability: "ready",
        direction: "up",
        latest_signal_type: "three_buy",
        latest_signal_at: "2026-07-10T14:55:00+08:00",
        latest_divergence_type: null,
        latest_divergence_at: null,
        signal_age_seconds: 600,
        last_closed_bar_at: "2026-07-10T15:00:00+08:00",
      },
    ],
    confluence_score: 76,
    bullish_periods: 3,
    bearish_periods: 1,
    has_confirmed_buy: true,
    has_confirmed_sell: false,
    latest_confirmed_at: "2026-07-10T14:55:00+08:00",
    rule_version: "cl-v1",
  };

  assert.deepEqual(chanlunScreeningView(summary), {
    title: "缠论共振 76 · 3周期向上",
    detail: "5分钟三买",
    insufficient: false,
  });
});


test("Chanlun screening view labels missing and partial structures explicitly", () => {
  assert.deepEqual(chanlunScreeningView(null), {
    title: "结构数据不足",
    detail: "进入工作台补充分钟历史",
    insufficient: true,
  });
  assert.equal(
    chanlunScreeningView({
      availability: "partial",
      freshness: "insufficient",
      periods: [],
      confluence_score: 15,
      bullish_periods: 1,
      bearish_periods: 0,
      has_confirmed_buy: true,
      has_confirmed_sell: false,
      latest_confirmed_at: null,
      rule_version: "cl-v1",
    }).title,
    "结构数据不足",
  );
});


test("screener controls and results expose Chanlun filters and workbench entry", () => {
  const filters = readFileSync(
    new URL("../components/screener/FilterLogicRail.tsx", import.meta.url),
    "utf8",
  );
  const candidates = readFileSync(
    new URL("../components/screener/CandidateResults.tsx", import.meta.url),
    "utf8",
  );
  const home = readFileSync(new URL("../app/HomeWorkbench.tsx", import.meta.url), "utf8");

  assert.match(filters, /最低缠论共振分/);
  assert.match(filters, /仅保留确认买点/);
  assert.match(filters, /结构数据不足的候选仍会保留/);
  assert.match(candidates, /ChanlunSummaryText/);
  assert.match(candidates, /\/chanlun\?symbol=/);
  assert.match(home, /chanlun_min_confluence_score/);
  assert.match(home, /chanlun_require_confirmed_buy/);
});
