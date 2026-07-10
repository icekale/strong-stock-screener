import assert from "node:assert/strict";
import test from "node:test";

const {
  readAppShellCollapsed,
  resolveMobileNavigationOpen,
  toggleAppShellCollapsed,
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
