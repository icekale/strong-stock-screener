import assert from "node:assert/strict";
import test from "node:test";

const { buildSectorReplicaChartOption } = (await import(
  new URL("./sectorReplicaChartOption.ts", import.meta.url).href
)) as typeof import("./sectorReplicaChartOption");

test("sector replica chart option keeps reference-like legend and fixed axis", () => {
  const option = buildSectorReplicaChartOption({
    axis: ["09:15", "09:16", "15:00"],
    series: [{ name: "芯片", type: "line", data: [1, 2, 3], smooth: true, showSymbol: false }],
  });

  assert.deepEqual(option.legend?.data, ["芯片"]);
  assert.equal(option.grid?.left, "2.5%");
  assert.deepEqual(option.xAxis?.data, ["09:15", "09:16", "15:00"]);
  assert.equal(option.series?.[0]?.showSymbol, false);
});
