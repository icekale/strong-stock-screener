import assert from "node:assert/strict";
import test from "node:test";

const { mergeShadowScores } = (await import(
  new URL("./czscShadow.ts", import.meta.url).href
)) as {
  mergeShadowScores: (
    formal: Array<{ symbol: string }>,
    scores: Record<string, { score: number | null; shadow_rank: number | null; eligible: boolean; status: string; evidence: unknown[]; rule_version: string }>,
  ) => Array<{ symbol: string; czsc_v2_shadow_rank?: number | null; czsc_score_v2?: number | null }>;
};

test("mergeShadowScores preserves formal order", () => {
  const formal = [{ symbol: "A" }, { symbol: "B" }, { symbol: "C" }];
  const merged = mergeShadowScores(formal, {
    C: score(95, 1),
    A: score(40, 3),
    B: score(null, null),
  });

  assert.deepEqual(merged.map((item) => item.symbol), ["A", "B", "C"]);
  assert.deepEqual(merged.map((item) => item.czsc_v2_shadow_rank), [3, null, 1]);
  assert.deepEqual(merged.map((item) => item.czsc_score_v2), [40, null, 95]);
});

function score(value: number | null, shadowRank: number | null) {
  return {
    score: value,
    shadow_rank: shadowRank,
    eligible: value !== null,
    status: value === null ? "unavailable" : "ready",
    evidence: [],
    rule_version: "czsc-score-v2-rule-1",
  };
}
