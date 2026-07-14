import type { KlineData } from "kline-charts-react";
import { resolveChartDate } from "./chanlunOverlay.ts";
import type { CzscResearchSnapshot, CzscSignalEvidence } from "./types";

type CzscResearchOverlaySeries = Record<string, unknown> & { id: "czsc-research-markers" };
type ResearchSide = "bullish" | "bearish" | "neutral";

const RESEARCH_MARKER_ID = "czsc-research-markers" as const;

export function buildCzscResearchOverlaySeries(
  snapshot: CzscResearchSnapshot | null | undefined,
  options: { chartDates?: readonly string[]; chartData?: readonly KlineData[]; visibleBarCount?: number } = {},
): CzscResearchOverlaySeries {
  const chartDates = options.chartDates ?? options.chartData?.map((bar) => bar.date);
  const candlesByDate = new Map(
    (options.chartData ?? [])
      .filter(hasPrices)
      .map((bar) => [bar.date, bar]),
  );
  const groups = new Map<string, { chartDate: string; evidence: CzscSignalEvidence[]; side: ResearchSide }>();

  for (const evidence of snapshot?.status === "ready" ? snapshot.events : []) {
    const chartDate = resolveChartDate(evidence.occurred_at, chartDates);
    const side = resolveSide(evidence);
    const key = `${chartDate}|${side}`;
    const group = groups.get(key);
    if (group) {
      group.evidence.push(evidence);
    } else {
      groups.set(key, { chartDate, evidence: [evidence], side });
    }
  }

  return {
    data: [...groups.values()]
      .sort((left, right) => left.chartDate.localeCompare(right.chartDate) || sidePriority(left.side) - sidePriority(right.side))
      .flatMap((group) => {
        const candle = candlesByDate.get(group.chartDate);
        if (!candle) {
          return [];
        }
        const evidence = [...group.evidence].sort(compareEvidence);
        const primary = evidence[0];
        if (!primary) {
          return [];
        }
        const bullish = group.side === "bullish";
        const price = bullish ? candle.low : candle.high;
        return [{
          evidence,
          itemStyle: { color: markerColor(group.side) },
          label: {
            color: markerColor(group.side),
            distance: 8,
            fontSize: 11,
            fontWeight: 700,
            formatter: `${markerLabel(primary)}${evidence.length > 1 ? ` +${evidence.length - 1}` : ""}`,
            position: bullish ? "bottom" : "top",
            show: true,
          },
          symbolRotate: bullish ? 0 : 180,
          value: [group.chartDate, price],
        }];
      }),
    id: RESEARCH_MARKER_ID,
    name: "CZSC研究信号",
    silent: true,
    symbol: "triangle",
    symbolSize: 10,
    type: "scatter",
    xAxisIndex: 0,
    yAxisIndex: 0,
    z: 21,
  };
}

export function buildCzscResearchClearSeries(): CzscResearchOverlaySeries {
  return {
    data: [],
    id: RESEARCH_MARKER_ID,
    type: "scatter",
    xAxisIndex: 0,
    yAxisIndex: 0,
  };
}

function hasPrices(bar: KlineData): bar is KlineData & { high: number; low: number } {
  return bar.high !== null && bar.low !== null;
}

function resolveSide(evidence: CzscSignalEvidence): ResearchSide {
  if (evidence.direction === "bullish") {
    return "bullish";
  }
  if (evidence.direction === "bearish" || evidence.role === "risk") {
    return "bearish";
  }
  return "neutral";
}

function compareEvidence(left: CzscSignalEvidence, right: CzscSignalEvidence): number {
  return evidencePriority(left) - evidencePriority(right) || left.catalog_id.localeCompare(right.catalog_id);
}

function evidencePriority(evidence: CzscSignalEvidence): number {
  if (evidence.role === "primary" && evidence.family === "third_buy") {
    return 0;
  }
  if (evidence.role === "primary" && evidence.family === "second_buy") {
    return 1;
  }
  if (evidence.role === "risk") {
    return 2;
  }
  if (evidence.role === "confirmation") {
    return 3;
  }
  if (evidence.role === "observation") {
    return 4;
  }
  return 5;
}

function markerLabel(evidence: CzscSignalEvidence): "3B" | "2B" | "顶" | "卖" {
  if (evidence.family === "third_buy") {
    return "3B";
  }
  if (evidence.family === "second_buy") {
    return "2B";
  }
  return evidence.role === "risk" || evidence.family === "sell_risk" ? "顶" : "卖";
}

function markerColor(side: ResearchSide): string {
  if (side === "bullish") {
    return "#07845e";
  }
  if (side === "bearish") {
    return "#d9363e";
  }
  return "#64748b";
}

function sidePriority(side: ResearchSide): number {
  return { bearish: 1, bullish: 0, neutral: 2 }[side];
}
