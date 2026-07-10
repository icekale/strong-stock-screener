import assert from "node:assert/strict";
import test from "node:test";

const {
  formatReplicaReportedMoney,
  formatReplicaReportedRatio,
  isSectorReplicaRadarCache,
  isSectorReplicaStocksCache,
  isSectorReplicaStocksForSelection,
  latestSectorReplicaSeriesTime,
  nextSectorReplicaSelection,
} = (await import(new URL("./sectorReplica.ts", import.meta.url).href)) as typeof import("./sectorReplica");

test("sector replica keeps at least one checked board", () => {
  assert.deepEqual(nextSectorReplicaSelection(["a"], "a", false), ["a"]);
  assert.deepEqual(nextSectorReplicaSelection(["a"], "b", true), ["a", "b"]);
  assert.deepEqual(nextSectorReplicaSelection(["a", "b"], "a", false), ["b"]);
});

test("sector replica keeps six comparison boards like qxlive default", () => {
  assert.deepEqual(nextSectorReplicaSelection(["a", "b", "c", "d", "e"], "f", true), ["a", "b", "c", "d", "e", "f"]);
  assert.deepEqual(nextSectorReplicaSelection(["a", "b", "c", "d", "e", "f"], "g", true), ["a", "b", "c", "d", "e", "f"]);
});

test("unreported live fields do not render numeric zero", () => {
  assert.equal(formatReplicaReportedMoney(null), "--");
  assert.equal(formatReplicaReportedMoney(0), "--");
  assert.equal(formatReplicaReportedMoney(12_000), "1.2万");
  assert.equal(formatReplicaReportedRatio(0), "--");
  assert.equal(formatReplicaReportedRatio(62.87), "62.87%");
});

test("stock cache is only used for the active board and sub-theme", () => {
  const cached = { board_code: "801001", sub_theme: null };

  assert.equal(isSectorReplicaStocksForSelection(cached, "801001", null), true);
  assert.equal(isSectorReplicaStocksForSelection(cached, "801660", null), false);
  assert.equal(isSectorReplicaStocksForSelection(cached, "801001", "存储"), false);
});

test("latest series time ignores the fixed future trading axis", () => {
  const axis = ["09:15", "09:16", "09:17", "09:18", "09:19"];

  assert.equal(
    latestSectorReplicaSeriesTime(axis, [
      { data: [100, 200, 300] },
      { data: [80, 90, null, null, null] },
    ]),
    "09:17",
  );
});

test("sector replica rejects stale session cache payloads", () => {
  const staleRadar = {
    result: "success",
    mode: "strength",
    axis: [],
    plates: [],
    checkplate: [],
    legend: [],
    series: [],
    stocks: [],
    related_tags: [],
    source_status: [],
  };
  const staleStocks = {
    board_code: "801001",
    sub_theme: null,
    rows: [],
    source_status: [],
  };

  assert.equal(isSectorReplicaRadarCache?.(staleRadar), false);
  assert.equal(isSectorReplicaStocksCache?.(staleStocks), false);
  assert.equal(isSectorReplicaRadarCache?.({ ...staleRadar, qxlive: { series: {} } }), true);
  assert.equal(isSectorReplicaStocksCache?.({ ...staleStocks, related_tags: [] }), true);
});
