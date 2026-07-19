import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("ETF radar route lazy-loads the client workspace", () => {
  const source = readFileSync(new URL("../app/etf-radar/page.tsx", import.meta.url), "utf8");

  assert.match(source, /dynamic\(/);
  assert.match(source, /EtfRadarWorkspace/);
  assert.match(source, /ssr: false/);
});

test("ETF radar workspace exposes four independently loaded evidence views", () => {
  const source = readFileSync(new URL("../app/etf-radar/EtfRadarWorkspace.tsx", import.meta.url), "utf8");

  assert.match(source, /盘中雷达/);
  assert.match(source, /份额变化/);
  assert.match(source, /持有人披露/);
  assert.match(source, /方法与验证/);
  assert.match(source, /getEtfRadarOverview/);
  assert.match(source, /getEtfRadarHistory/);
  assert.match(source, /getEtfRadarHolders/);
  assert.match(source, /getEtfRadarMethodology/);
  assert.match(source, /证据强度/);
  assert.doesNotMatch(source, /概率/);
});
