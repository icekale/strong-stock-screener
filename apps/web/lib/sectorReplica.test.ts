import assert from "node:assert/strict";
import test from "node:test";

const { nextSectorReplicaSelection } = (await import(new URL("./sectorReplica.ts", import.meta.url).href)) as typeof import(
  "./sectorReplica"
);

test("sector replica keeps at least one checked board", () => {
  assert.deepEqual(nextSectorReplicaSelection(["a"], "a", false), ["a"]);
  assert.deepEqual(nextSectorReplicaSelection(["a"], "b", true), ["a", "b"]);
  assert.deepEqual(nextSectorReplicaSelection(["a", "b"], "a", false), ["b"]);
});
