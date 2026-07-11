"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { DecisionQueue } from "../components/overview/DecisionQueue";
import { MarketIndexStrip, MarketPulse } from "../components/overview/MarketPulse";
import { SectorHeatmapPreview } from "../components/overview/SectorHeatmapPreview";
import { PageFrame } from "../components/workbench/PageFrame";
import {
  getAuctionModelTop3,
  getLatestScreenRun,
  getMarketOverview,
  getSectorRadar,
  getSentimentSummary,
  isAuctionModelTop3CacheMiss,
} from "../lib/api";
import {
  executeLatestOnly,
  getAuctionCacheTradeDate,
  getMarketSession,
  getShanghaiTradeDate,
  nextRequestGeneration,
  toPanelState,
  type PanelState,
} from "../lib/marketOverview";
import type {
  AuctionModelTop3Response,
  MarketOverviewResponse,
  SectorRadarResponse,
  SentimentSummaryResponse,
  StrongStockScreeningResponse,
} from "../lib/types";

export function MarketOverviewWorkbench() {
  const [screening, setScreening] = useState<PanelState<StrongStockScreeningResponse> | null>(null);
  const [market, setMarket] = useState<PanelState<MarketOverviewResponse> | null>(null);
  const [auction, setAuction] = useState<PanelState<AuctionModelTop3Response> | null>(null);
  const [sectorRadar, setSectorRadar] = useState<PanelState<SectorRadarResponse> | null>(null);
  const [sentiment, setSentiment] = useState<PanelState<SentimentSummaryResponse> | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const refreshGeneration = useRef(0);

  const refresh = useCallback(() => {
    const generation = nextRequestGeneration(refreshGeneration.current);
    refreshGeneration.current = generation;
    setRefreshing(true);
    const tradeDate = getShanghaiTradeDate();
    const auctionTradeDate = getAuctionCacheTradeDate();

    return executeLatestOnly({
      generation,
      currentGeneration: () => refreshGeneration.current,
      execute: () =>
        Promise.allSettled([
          getLatestScreenRun(),
          getMarketOverview(),
          getAuctionModelTop3(auctionTradeDate, { cacheOnly: true }),
          getSectorRadar(12),
          getSentimentSummary(tradeDate, 80, false),
        ]),
      apply: ([screeningResult, marketResult, auctionResult, sectorRadarResult, sentimentResult]) => {
        setScreening((previous) => toPanelState(screeningResult, panelValue(previous)));
        setMarket((previous) => toPanelState(marketResult, panelValue(previous)));
        setAuction((previous) => toAuctionPanelState(auctionResult, panelValue(previous)));
        setSectorRadar((previous) => toPanelState(sectorRadarResult, panelValue(previous)));
        setSentiment((previous) => toPanelState(sentimentResult, panelValue(previous)));
      },
      finishLoading: () => setRefreshing(false),
    });
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const tradeDate = getShanghaiTradeDate();
  const session = getMarketSession();

  return (
    <PageFrame
      actions={
        <Button disabled={refreshing} icon={<ReloadOutlined />} loading={refreshing} onClick={() => void refresh()} type="primary">
          刷新
        </Button>
      }
      context={`上海 ${tradeDate} · ${session}`}
      status={<Tag color="blue">只读</Tag>}
      title="市场总览"
    >
      <div className="market-overview-layout">
        <div className="market-overview-lead">
          <SectorHeatmapPreview onRefresh={() => void refresh()} sectorRadar={sectorRadar} />
          <MarketPulse market={market} onRefresh={() => void refresh()} sentiment={sentiment} />
        </div>
        <MarketIndexStrip market={market} onRefresh={() => void refresh()} />
        <DecisionQueue auction={auction} onRefresh={() => void refresh()} screening={screening} />
      </div>
    </PageFrame>
  );
}

function panelValue<T>(state: PanelState<T> | null): T | null {
  return state?.kind === "ready" || state?.kind === "stale" ? state.value : null;
}

function toAuctionPanelState(
  result: PromiseSettledResult<AuctionModelTop3Response>,
  previous: AuctionModelTop3Response | null,
): PanelState<AuctionModelTop3Response> {
  if (result.status === "rejected" && previous === null && isAuctionModelTop3CacheMiss(result.reason)) {
    return { kind: "missing", value: null };
  }
  return toPanelState(result, previous);
}
