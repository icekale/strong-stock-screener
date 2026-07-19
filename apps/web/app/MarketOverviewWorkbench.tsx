"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { CapitalSignalPanels } from "../components/overview/CapitalSignalPanels";
import { MarketIndexStrip, MarketPulse } from "../components/overview/MarketPulse";
import { SectorHeatmapPreview } from "../components/overview/SectorHeatmapPreview";
import { PageFrame } from "../components/workbench/PageFrame";
import {
  getCapitalSummary,
  getMarketOverview,
  getSectorRadar,
  getSentimentSummary,
} from "../lib/api";
import {
  executeLatestOnly,
  getMarketSession,
  getShanghaiTradeDate,
  nextRequestGeneration,
  toPanelState,
  type PanelState,
} from "../lib/marketOverview";
import { createMemoryRequestCache } from "../lib/marketOverviewCache";
import type {
  CapitalSummaryResponse,
  MarketOverviewResponse,
  SectorRadarResponse,
  SentimentSummaryResponse,
} from "../lib/types";

const homepageCache = createMemoryRequestCache({ ttlMs: 15_000 });

function getHomepagePanel<T>(
  name: string,
  tradeDate: string,
  request: () => Promise<T>,
  force = false,
): Promise<T> {
  return homepageCache.get(`homepage:${name}:${tradeDate}`, request, { force });
}

export function MarketOverviewWorkbench() {
  const [market, setMarket] = useState<PanelState<MarketOverviewResponse> | null>(null);
  const [sectorRadar, setSectorRadar] = useState<PanelState<SectorRadarResponse> | null>(null);
  const [sentiment, setSentiment] = useState<PanelState<SentimentSummaryResponse> | null>(null);
  const [capital, setCapital] = useState<PanelState<CapitalSummaryResponse> | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const refreshGeneration = useRef(0);

  const refresh = useCallback((force = false) => {
    const generation = nextRequestGeneration(refreshGeneration.current);
    refreshGeneration.current = generation;
    setRefreshing(true);
    const tradeDate = getShanghaiTradeDate();

    const runCorePanelRequest = <T,>(
      request: () => Promise<T>,
      apply: (result: PromiseSettledResult<T>) => void,
    ) =>
      executeLatestOnly({
        generation,
        currentGeneration: () => refreshGeneration.current,
        execute: () => settleRequest(request),
        apply,
        finishLoading: () => undefined,
      });

    const marketRequest = runCorePanelRequest(
      () => getHomepagePanel("market", tradeDate, getMarketOverview, force),
      (result) => {
        setMarket((previous) => toPanelState(result, panelValue(previous)));
      },
    );
    const backgroundRequests = [
      runCorePanelRequest(
        () => getHomepagePanel("sector-radar", tradeDate, () => getSectorRadar(12), force),
        (result) => {
          setSectorRadar((previous) => toPanelState(result, panelValue(previous)));
        },
      ),
      runCorePanelRequest(
        () => getHomepagePanel("sentiment-summary", tradeDate, () => getSentimentSummary(tradeDate, 80, false), force),
        (result) => {
          setSentiment((previous) => toPanelState(result, panelValue(previous)));
        },
      ),
      runCorePanelRequest(
        () => getHomepagePanel("capital-summary", tradeDate, getCapitalSummary, force),
        (result) => {
          setCapital((previous) => toPanelState(result, panelValue(previous)));
        },
      ),
    ];

    void marketRequest.then((isLatest) => {
      if (isLatest) {
        setRefreshing(false);
      }
    });

    return Promise.allSettled([marketRequest, ...backgroundRequests]).then(() => {
      const isLatest = generation === refreshGeneration.current;
      return isLatest;
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
        <Button
          disabled={refreshing}
          icon={<ReloadOutlined />}
          loading={refreshing}
          onClick={() => void refresh(true)}
          type="primary"
        >
          刷新
        </Button>
      }
      context={`上海 ${tradeDate} · ${session}`}
      status={<Tag color="blue">只读</Tag>}
      title="市场总览"
    >
      <div className="market-overview-layout">
        <MarketIndexStrip market={market} onRefresh={() => void refresh(true)} />
        <MarketPulse market={market} onRefresh={() => void refresh(true)} sentiment={sentiment} />
        <div className="market-overview-lead market-capital-grid">
          <SectorHeatmapPreview onRefresh={() => void refresh(true)} sectorRadar={sectorRadar} />
          <CapitalSignalPanels capital={capital} onRefresh={() => void refresh(true)} />
        </div>
      </div>
    </PageFrame>
  );
}

function panelValue<T>(state: PanelState<T> | null): T | null {
  return state?.kind === "ready" || state?.kind === "stale" ? state.value : null;
}

async function settleRequest<T>(request: () => Promise<T>): Promise<PromiseSettledResult<T>> {
  try {
    return { status: "fulfilled", value: await request() };
  } catch (reason) {
    return { status: "rejected", reason };
  }
}
