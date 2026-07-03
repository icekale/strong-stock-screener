import assert from "node:assert/strict";
import test from "node:test";

const { mergeStockIdentity } = (await import(new URL("./stockIdentity.ts", import.meta.url).href)) as typeof import("./stockIdentity");

test("mergeStockIdentity fills missing display metadata from quote fallback", () => {
  assert.deepEqual(
    mergeStockIdentity(
      { industry: null, name: null },
      { industry: null, name: null },
      { industry: "贵金属", name: "招金黄金" },
    ),
    { industry: "贵金属", name: "招金黄金" },
  );
});

test("mergeStockIdentity keeps higher priority candidate metadata", () => {
  assert.deepEqual(
    mergeStockIdentity(
      { industry: "消费电子", name: "春秋电子" },
      { industry: "贵金属", name: "招金黄金" },
    ),
    { industry: "消费电子", name: "春秋电子" },
  );
});
