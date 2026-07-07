import assert from "node:assert/strict";
import test from "node:test";

const {
  buildWorkbenchContentClassName,
  buildWorkbenchPageClassName,
} = (await import(new URL("./workbenchLayout.ts", import.meta.url).href)) as typeof import("./workbenchLayout");

test("buildWorkbenchPageClassName preserves the shared page shell class", () => {
  assert.equal(buildWorkbenchPageClassName(), "workbench-page min-h-screen");
  assert.equal(
    buildWorkbenchPageClassName("auction-command-page"),
    "workbench-page min-h-screen auction-command-page",
  );
});

test("buildWorkbenchContentClassName applies consistent page spacing", () => {
  assert.equal(
    buildWorkbenchContentClassName(),
    "mx-auto flex w-full max-w-none flex-col gap-4 px-3 py-4 lg:px-5",
  );
  assert.equal(
    buildWorkbenchContentClassName("xl:gap-5"),
    "mx-auto flex w-full max-w-none flex-col gap-4 px-3 py-4 lg:px-5 xl:gap-5",
  );
});
