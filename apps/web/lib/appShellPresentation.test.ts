import assert from "node:assert/strict";
import test from "node:test";

const {
  buildWorkspaceTab,
  closeWorkspaceTab,
  readAppShellCollapsed,
  restoreWorkspaceTabs,
  resolveMobileNavigationOpen,
  toggleAppShellCollapsed,
  upsertWorkspaceTab,
} = (await import(new URL("./appShellPresentation.ts", import.meta.url).href)) as typeof import("./appShellPresentation");

test("collapsed navigation storage failures fall back safely", () => {
  const unreadableStorage = {
    getItem() {
      throw new Error("storage read blocked");
    },
    setItem() {},
  };
  const unwritableStorage = {
    getItem() {
      return null;
    },
    setItem() {
      throw new Error("storage write blocked");
    },
  };

  assert.equal(readAppShellCollapsed(unreadableStorage), false);
  assert.doesNotThrow(() => toggleAppShellCollapsed(false, unwritableStorage));
  assert.equal(toggleAppShellCollapsed(false, unwritableStorage), true);
});

test("desktop viewport transitions close only an open mobile drawer", () => {
  assert.equal(resolveMobileNavigationOpen(true, true), false);
  assert.equal(resolveMobileNavigationOpen(true, false), true);
  assert.equal(resolveMobileNavigationOpen(false, false), false);
});

test("workspace tabs reuse routes while retaining the latest query", () => {
  const home = buildWorkspaceTab("/", "");
  const heatmap = buildWorkspaceTab("/market", "view=heatmap");
  const sectors = buildWorkspaceTab("/market", "view=sectors");
  const stock = buildWorkspaceTab("/stock/603823.SH", "name=%E7%99%BE%E5%90%88%E8%8A%B1");

  assert.deepEqual(home, { closable: false, href: "/", key: "/", label: "市场总览" });
  assert.deepEqual(heatmap, { closable: true, href: "/market?view=heatmap", key: "/market", label: "板块与热图" });
  assert.deepEqual(stock, { closable: true, href: "/stock/603823.SH?name=%E7%99%BE%E5%90%88%E8%8A%B1", key: "/stock/603823.SH", label: "个股 603823.SH" });
  assert.deepEqual(upsertWorkspaceTab(upsertWorkspaceTab([home], heatmap), sectors), [home, sectors]);
});

test("workspace tabs retain home and cap recent workspaces", () => {
  const home = buildWorkspaceTab("/", "");
  const tabs = Array.from({ length: 14 }, (_, index) =>
    buildWorkspaceTab(`/stock/6000${String(index).padStart(2, "0")}.SH`, ""),
  ).reduce(upsertWorkspaceTab, [home]);

  assert.equal(tabs.length, 12);
  assert.equal(tabs[0]?.key, "/");
  assert.equal(tabs.at(-1)?.key, "/stock/600013.SH");
});

test("workspace tab restoration rebuilds only safe internal routes", () => {
  const restored = restoreWorkspaceTabs(JSON.stringify([
    { closable: false, href: "/market?view=heatmap", key: "tampered", label: "tampered" },
    { closable: true, href: "/market?view=sectors", key: "/market?view=sectors", label: "duplicate" },
    { closable: true, href: "javascript:alert(1)", key: "unsafe", label: "unsafe" },
    { closable: true, href: "//example.com/phish", key: "external", label: "external" },
  ]));

  assert.deepEqual(restored, [buildWorkspaceTab("/market", "view=sectors")]);
  assert.deepEqual(restoreWorkspaceTabs("not json"), []);
});

test("closing the active workspace tab returns to the nearest remaining tab", () => {
  const tabs = [
    buildWorkspaceTab("/", ""),
    buildWorkspaceTab("/auction", ""),
    buildWorkspaceTab("/market", "view=heatmap"),
  ];

  assert.deepEqual(closeWorkspaceTab(tabs, "/market", "/market"), {
    activeKey: "/auction",
    tabs: tabs.slice(0, 2),
  });
  assert.deepEqual(closeWorkspaceTab(tabs, "/auction", "/market"), {
    activeKey: "/market",
    tabs: [tabs[0], tabs[2]],
  });
});
