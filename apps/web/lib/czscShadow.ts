import type {
  CzscV2BatchResult,
  CzscV2CandidateScore,
  StrongStockScreeningItem,
} from "./types";

export function shadowScoresBySymbol(batch: CzscV2BatchResult): Record<string, CzscV2CandidateScore> {
  return Object.fromEntries(batch.items.map((item) => [item.symbol, item]));
}

export function mergeShadowScores(
  formal: StrongStockScreeningItem[],
  scores: Record<string, CzscV2CandidateScore>,
): StrongStockScreeningItem[] {
  return formal.map((item) => {
    const score = scores[item.symbol];
    if (!score) {
      return item;
    }
    return {
      ...item,
      czsc_score_v2: score.score,
      czsc_v2_eligible: score.eligible,
      czsc_v2_shadow_rank: score.shadow_rank,
      czsc_v2_evidence: score.evidence,
      czsc_v2_status: score.status,
      czsc_v2_rule_version: score.rule_version,
    };
  });
}

export function czscShadowLabel(item: StrongStockScreeningItem, pending: boolean): string | null {
  if (item.czsc_v2_status === "ready" && item.czsc_score_v2 !== null && item.czsc_score_v2 !== undefined) {
    return `CZSC研究 ${item.czsc_score_v2} · 影子#${item.czsc_v2_shadow_rank ?? "-"}`;
  }
  if (pending || item.czsc_v2_status === "pending") {
    return "CZSC研究计算中";
  }
  if (item.czsc_v2_status) {
    return "CZSC研究数据不足";
  }
  return null;
}
