import assert from "node:assert/strict";
import test from "node:test";

const { buildChanlunWorkspaceHref, isChanlunUnavailable, shouldRenderChanlunOverlay } = (await import(
  new URL("./stockKlineChanlun.ts", import.meta.url).href,
)) as typeof import("./stockKlineChanlun");

test("stock detail Chanlun entry preserves normalized symbol", () => {
  assert.equal(buildChanlunWorkspaceHref("600000.sh"), "/chanlun?symbol=600000.SH");
});

test("unavailable Chanlun analysis does not hide existing K-line", () => {
  assert.equal(shouldRenderChanlunOverlay({ availability: "unavailable" }), false);
  assert.equal(isChanlunUnavailable({ availability: "unavailable" }), true);
  assert.equal(shouldRenderChanlunOverlay({ availability: "ready" }), true);
});
