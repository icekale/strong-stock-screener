import assert from "node:assert/strict";
import test from "node:test";

const { dataStateCopy, joinClassNames } = (await import(
  new URL("./workbenchPresentation.ts", import.meta.url).href
)) as typeof import("./workbenchPresentation");

test("presentation helpers compose CSS classes and state copy", () => {
  assert.equal(joinClassNames("page-frame", false, null, undefined, "page-frame--compact"), "page-frame page-frame--compact");
  assert.deepEqual(dataStateCopy("empty", "候选"), {
    title: "暂无候选",
    description: "当前条件下没有符合规则的标的。",
  });
  assert.equal(dataStateCopy("stale", "竞价").action, "重新读取");
});
