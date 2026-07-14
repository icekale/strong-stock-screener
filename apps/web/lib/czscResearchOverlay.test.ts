import assert from "node:assert/strict";
import test from "node:test";
import type { CzscResearchSnapshot } from "./types";

const { buildCzscResearchOverlaySeries } = (await import(
  new URL("./czscResearchOverlay.ts", import.meta.url).href
)) as typeof import("./czscResearchOverlay");

function snapshot(events: CzscResearchSnapshot["events"]): CzscResearchSnapshot {
  return {
    adjustment_mode: "raw_unadjusted",
    calculated_at: "2026-07-10T15:00:00+08:00",
    catalog_version: "czsc-v2-catalog-1",
    current_states: [],
    eligible: false,
    engine_version: "0.10.8",
    events,
    input_snapshot_id: "sha256:test",
    last_closed_by_period: { "1d": "2026-07-10", "5m": "2026-07-10T15:00:00+08:00", "30m": "2026-07-10T15:00:00+08:00", "60m": "2026-07-10T15:00:00+08:00" },
    rule_version: "czsc-score-v2-rule-1",
    score: 72,
    source_status: [],
    status: "ready",
    symbol: "600000.SH",
  };
}

function event(catalogId: string, occurredAt: string, direction: "bullish" | "bearish"): CzscResearchSnapshot["events"][number] {
  return {
    catalog_id: catalogId,
    catalog_version: "czsc-v2-catalog-1",
    direction,
    engine_version: "0.10.8",
    family: catalogId.startsWith("buy3") ? "third_buy" : catalogId.startsWith("buy") ? "second_buy" : "sell_risk",
    higher_period: null,
    id: catalogId,
    last_closed_bar_at: occurredAt,
    lower_period: null,
    occurred_at: occurredAt,
    params: {},
    period: "5m",
    role: catalogId.startsWith("buy") ? "primary" : "risk",
    rule_version: "czsc-score-v2-rule-1",
    signal_name: catalogId,
  };
}

test("same-candle same-side research evidence collapses into one marker", () => {
  const series = buildCzscResearchOverlaySeries(snapshot([
    event("buy2.overlap", "2026-07-10T10:00:00+08:00", "bullish"),
    event("buy3.ma-confirm", "2026-07-10T10:00:00+08:00", "bullish"),
  ]), { chartData: [{ date: "2026-07-10 10:00", high: 11, low: 9 }] as never });
  const data = series.data as Array<{ label: { formatter: string }; evidence: unknown[] }>;

  assert.equal(data.length, 1);
  assert.equal(data[0]?.label.formatter, "3B +1");
  assert.equal(data[0]?.evidence.length, 2);
});

test("research markers stay grouped across zoom and separate bullish from bearish placement", () => {
  const input = snapshot([
    event("buy2.overlap", "2026-07-10T10:00:00+08:00", "bullish"),
    event("sell.risk", "2026-07-10T10:00:00+08:00", "bearish"),
  ]);
  const chartData = [{ date: "2026-07-10 10:00", high: 11, low: 9 }] as never;
  const compact = buildCzscResearchOverlaySeries(input, { chartData, visibleBarCount: 20 });
  const zoomedOut = buildCzscResearchOverlaySeries(input, { chartData, visibleBarCount: 220 });
  const compactData = compact.data as Array<{ label: { position: string }; value: unknown[] }>;
  const zoomedOutData = zoomedOut.data as Array<{ value: unknown[] }>;

  assert.equal(compactData.length, 2);
  assert.deepEqual(compactData.map((item) => item.label.position), ["bottom", "top"]);
  assert.deepEqual(zoomedOutData.map((item) => item.value), compactData.map((item) => item.value));
});
