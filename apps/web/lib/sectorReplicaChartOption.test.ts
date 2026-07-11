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

test("sector replica chart option reduces key-time labels for compact charts", () => {
  const axis = ["09:15", "09:30", "10:00", "10:30", "11:00", "13:00", "13:30", "14:00", "14:30", "15:00"];
  const option = buildSectorReplicaChartOption({
    axis,
    compact: true,
    series: [{ name: "芯片", type: "line", data: axis.map(() => 1), smooth: true, showSymbol: false }],
  });
  const interval = option.xAxis?.axisLabel?.interval;

  assert.equal(typeof interval, "function");
  assert.equal(interval?.(0, axis[0]), true);
  assert.equal(interval?.(1, axis[1]), false);
  assert.equal(interval?.(2, axis[2]), true);
  assert.equal(interval?.(9, axis[9]), true);
  assert.equal(option.grid?.right, "4%");
});

test("sector replica chart option uses the product canvas palette", () => {
  const option = buildSectorReplicaChartOption({
    axis: ["09:15", "15:00"],
    series: [{ name: "芯片", type: "line", data: [1, 2], smooth: true, showSymbol: false }],
  });

  assert.equal(option.backgroundColor, "#f7f9fc");
  assert.equal(option.legend?.textStyle?.color, "#182336");
  assert.equal(option.xAxis?.axisLine?.lineStyle?.color, "#d9e2ed");
});
