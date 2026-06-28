import assert from "node:assert/strict";
import test from "node:test";

const {
  filterStockList,
  filterStockListByGsgf,
  getChineseInitials,
  gsgfSignalFilterOptions,
  stockListStatusOptions,
} = (await import(new URL("./stockListFilter.ts", import.meta.url).href)) as typeof import("./stockListFilter");

const items = [
  { industry: "玻璃玻纤", name: "中材科技", status: "focus", symbol: "002080.SZ" },
  { industry: "化学制品", name: "爱普股份", status: "wait_pullback", symbol: "603020.SH" },
  { industry: "元件", name: "超声电子", status: "reduce_risk", symbol: "000823.SZ" },
  { industry: null, name: null, status: null, symbol: "605289.SH" },
] as const;

const gsgfItems = [
  {
    industry: "消费电子",
    name: "确认股份",
    status: "focus",
    symbol: "600001.SH",
    gsgf: {
      final_status: "确认买点",
      setup_type: null,
      confirm_type: "放量突破确认",
      risk_flags: [],
    },
  },
  {
    industry: "元件",
    name: "低吸股份",
    status: "wait_pullback",
    symbol: "600002.SH",
    gsgf: {
      final_status: "低吸观察",
      setup_type: "双星止跌",
      confirm_type: null,
      risk_flags: [],
    },
  },
  {
    industry: "半导体",
    name: "风险股份",
    status: "focus",
    symbol: "600003.SH",
    gsgf: {
      final_status: "候选",
      setup_type: "B区A点",
      confirm_type: null,
      risk_flags: ["全局阴量压制"],
    },
  },
] as const;

test("getChineseInitials builds searchable pinyin initials for stock names", () => {
  assert.equal(getChineseInitials("中材科技"), "zckj");
  assert.equal(getChineseInitials("爱普股份"), "apgf");
  assert.equal(getChineseInitials("超声电子"), "csdz");
});

test("filterStockList matches stock code, name, industry, and initials", () => {
  assert.deepEqual(filterStockList(items, "002080", "all").map((item) => item.symbol), ["002080.SZ"]);
  assert.deepEqual(filterStockList(items, "爱普", "all").map((item) => item.symbol), ["603020.SH"]);
  assert.deepEqual(filterStockList(items, "元件", "all").map((item) => item.symbol), ["000823.SZ"]);
  assert.deepEqual(filterStockList(items, "zckj", "all").map((item) => item.symbol), ["002080.SZ"]);
  assert.deepEqual(filterStockList(items, "apgf", "all").map((item) => item.symbol), ["603020.SH"]);
});

test("filterStockList filters candidate status without dropping all option", () => {
  assert.deepEqual(filterStockList(items, "", "all").map((item) => item.symbol), [
    "002080.SZ",
    "603020.SH",
    "000823.SZ",
    "605289.SH",
  ]);
  assert.deepEqual(filterStockList(items, "", "focus").map((item) => item.symbol), ["002080.SZ"]);
  assert.deepEqual(filterStockList(items, "", "reduce_risk").map((item) => item.symbol), ["000823.SZ"]);
  assert.deepEqual(
    stockListStatusOptions.map((item) => item.value),
    ["all", "focus", "wait_pullback", "reduce_risk", "data_incomplete"],
  );
});

test("filterStockListByGsgf filters setup, confirmation, and hard risk flags", () => {
  assert.deepEqual(filterStockListByGsgf(gsgfItems, "all", false).map((item) => item.symbol), [
    "600001.SH",
    "600002.SH",
    "600003.SH",
  ]);
  assert.deepEqual(filterStockListByGsgf(gsgfItems, "confirmed_buy", false).map((item) => item.symbol), [
    "600001.SH",
  ]);
  assert.deepEqual(filterStockListByGsgf(gsgfItems, "low_absorb", false).map((item) => item.symbol), [
    "600002.SH",
  ]);
  assert.deepEqual(filterStockListByGsgf(gsgfItems, "volume_breakout", false).map((item) => item.symbol), [
    "600001.SH",
  ]);
  assert.deepEqual(filterStockListByGsgf(gsgfItems, "b_zone_a_point", false).map((item) => item.symbol), [
    "600003.SH",
  ]);
  assert.deepEqual(filterStockListByGsgf(gsgfItems, "all", true).map((item) => item.symbol), [
    "600001.SH",
    "600002.SH",
  ]);
  assert.deepEqual(
    gsgfSignalFilterOptions.map((item) => item.value),
    ["all", "confirmed_buy", "low_absorb", "volume_breakout", "b_zone_a_point"],
  );
});
