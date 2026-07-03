import assert from "node:assert/strict";
import test from "node:test";

const {
  buildStockDetailHref,
  resolveStockDetailContext,
} = (await import(new URL("./stockNavigation.ts", import.meta.url).href)) as typeof import("./stockNavigation");

test("stock detail href carries auction source, stock name, and industry", () => {
  assert.equal(
    buildStockDetailHref("002080.SZ", {
      from: "auction",
      industry: "元件",
      name: "中材科技",
    }),
    "/stock/002080.SZ?from=auction&name=%E4%B8%AD%E6%9D%90%E7%A7%91%E6%8A%80&industry=%E5%85%83%E4%BB%B6",
  );
});

test("stock detail context returns to auction only for the trusted auction source", () => {
  const auctionContext = resolveStockDetailContext(
    new URLSearchParams("from=auction&name=%E4%B8%AD%E6%9D%90%E7%A7%91%E6%8A%80&industry=%E5%85%83%E4%BB%B6"),
  );
  const unsafeContext = resolveStockDetailContext(new URLSearchParams("from=https://example.com&name=Bad"));

  assert.deepEqual(auctionContext, {
    from: "auction",
    industry: "元件",
    name: "中材科技",
    returnHref: "/auction",
    returnLabel: "返回竞价雷达",
  });
  assert.deepEqual(unsafeContext, {
    from: "home",
    industry: null,
    name: "Bad",
    returnHref: "/",
    returnLabel: "返回选股工作台",
  });
});
