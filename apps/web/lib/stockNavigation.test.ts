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

test("stock detail context can return to the sector workbench", () => {
  assert.equal(
    buildStockDetailHref("603690.SH", {
      from: "sectors",
      industry: "半导体",
      name: "至纯科技",
    }),
    "/stock/603690.SH?from=sectors&name=%E8%87%B3%E7%BA%AF%E7%A7%91%E6%8A%80&industry=%E5%8D%8A%E5%AF%BC%E4%BD%93",
  );

  assert.deepEqual(resolveStockDetailContext(new URLSearchParams("from=sectors")), {
    from: "sectors",
    industry: null,
    name: null,
    returnHref: "/sectors",
    returnLabel: "返回题材工作台",
  });
});

test("stock detail context can return to the auction model panel", () => {
  assert.equal(
    buildStockDetailHref("300001.SZ", {
      from: "auction-model",
      name: "模型一号",
    }),
    "/stock/300001.SZ?from=auction-model&name=%E6%A8%A1%E5%9E%8B%E4%B8%80%E5%8F%B7",
  );

  assert.deepEqual(resolveStockDetailContext(new URLSearchParams("from=auction-model")), {
    from: "auction-model",
    industry: null,
    name: null,
    returnHref: "/auction",
    returnLabel: "返回竞价模型",
  });
});

test("stock detail context can return to the heatmap workbench", () => {
  assert.equal(
    buildStockDetailHref("603690.SH", {
      from: "heatmap",
      industry: "半导体",
      name: "至纯科技",
    }),
    "/stock/603690.SH?from=heatmap&name=%E8%87%B3%E7%BA%AF%E7%A7%91%E6%8A%80&industry=%E5%8D%8A%E5%AF%BC%E4%BD%93",
  );

  assert.deepEqual(resolveStockDetailContext(new URLSearchParams("from=heatmap")), {
    from: "heatmap",
    industry: null,
    name: null,
    returnHref: "/heatmap",
    returnLabel: "返回市场热图",
  });
});
