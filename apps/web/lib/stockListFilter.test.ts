import assert from "node:assert/strict";
import test from "node:test";

const {
  filterStockList,
  getChineseInitials,
  stockListStatusOptions,
} = (await import(new URL("./stockListFilter.ts", import.meta.url).href)) as typeof import("./stockListFilter");

const items = [
  { industry: "玻璃玻纤", name: "中材科技", status: "focus", symbol: "002080.SZ" },
  { industry: "化学制品", name: "爱普股份", status: "wait_pullback", symbol: "603020.SH" },
  { industry: "元件", name: "超声电子", status: "reduce_risk", symbol: "000823.SZ" },
  { industry: null, name: null, status: null, symbol: "605289.SH" },
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
