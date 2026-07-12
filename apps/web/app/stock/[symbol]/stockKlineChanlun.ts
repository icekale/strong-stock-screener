import type { ChanlunAnalysisResponse } from "../../../lib/types";

export function buildChanlunWorkspaceHref(symbol: string): string {
  return `/chanlun?symbol=${encodeURIComponent(symbol.trim().toUpperCase())}`;
}

export function shouldRenderChanlunOverlay(
  analysis: Pick<ChanlunAnalysisResponse, "availability"> | null | undefined,
): boolean {
  return analysis?.availability === "ready";
}

export function isChanlunUnavailable(
  analysis: Pick<ChanlunAnalysisResponse, "availability"> | null | undefined,
): boolean {
  return analysis?.availability === "unavailable";
}
