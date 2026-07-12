"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { MarketIndexStrip, MarketPulse } from "../components/overview/MarketPulse";
import { MarketTrendPanels } from "../components/overview/MarketTrendPanels";
import { SectorHeatmapPreview } from "../components/overview/SectorHeatmapPreview";
import { PageFrame } from "../components/workbench/PageFrame";
import {
  getMarketEmotionSnapshot,
  getMarketOverview,
  getSectorRadar,
  getSectorReplicaRadar,
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
import type {
  MarketEmotionSnapshotResponse,
  MarketOverviewResponse,
  SectorRadarResponse,
  SectorReplicaRadarResponse,
  SentimentSummaryResponse,
} from "../lib/types";

export function MarketOverviewWorkbench() {
  const [market, setMarket] = useState<PanelState<MarketOverviewResponse> | null>(null);
  const [sectorRadar, setSectorRadar] = useState<PanelState<SectorRadarResponse> | null>(null);
  const [sentiment, setSentiment] = useState<PanelState<SentimentSummaryResponse> | null>(null);
  const [sectorTrend, setSectorTrend] = useState<PanelState<SectorReplicaRadarResponse> | null>(null);
  const [emotionTrend, setEmotionTrend] = useState<PanelState<MarketEmotionSnapshotResponse> | null>(null);
  const [trendsActivated, setTrendsActivated] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const refreshGeneration = useRef(0);
  const trendRefreshGeneration = useRef(0);
  const trendAnchorRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(() => {
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

    const pending = [
      runCorePanelRequest(getMarketOverview, (result) => {
        setMarket((previous) => toPanelState(result, panelValue(previous)));
      }),
      runCorePanelRequest(() => getSectorRadar(12), (result) => {
        setSectorRadar((previous) => toPanelState(result, panelValue(previous)));
      }),
      runCorePanelRequest(() => getSentimentSummary(tradeDate, 80, false), (result) => {
        setSentiment((previous) => toPanelState(result, panelValue(previous)));
      }),
    ];

    return Promise.allSettled(pending).then(() => {
      const isLatest = generation === refreshGeneration.current;
      if (isLatest) {
        setRefreshing(false);
      }
      return isLatest;
    });
  }, []);

  const refreshTrends = useCallback(() => {
    const generation = nextRequestGeneration(trendRefreshGeneration.current);
    trendRefreshGeneration.current = generation;
    const tradeDate = getShanghaiTradeDate();

    return executeLatestOnly({
      generation,
      currentGeneration: () => trendRefreshGeneration.current,
      execute: () =>
        Promise.allSettled([
          getSectorReplicaRadar({ mode: "strength", limit: 6, stockLimit: 1 }),
          getMarketEmotionSnapshot(tradeDate, 80),
        ]),
      apply: ([sectorResult, emotionResult]) => {
        setSectorTrend((previous) => toPanelState(sectorResult, panelValue(previous)));
        setEmotionTrend((previous) => toPanelState(emotionResult, panelValue(previous)));
      },
      finishLoading: () => undefined,
    });
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (trendsActivated || !trendAnchorRef.current) {
      return;
    }
    if (typeof IntersectionObserver === "undefined") {
      setTrendsActivated(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setTrendsActivated(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px" },
    );
    observer.observe(trendAnchorRef.current);
    return () => observer.disconnect();
  }, [trendsActivated]);

  useEffect(() => {
    if (trendsActivated) {
      void refreshTrends();
    }
  }, [refreshTrends, trendsActivated]);

  const tradeDate = getShanghaiTradeDate();
  const session = getMarketSession();

  return (
    <PageFrame
      actions={
        <Button
          disabled={refreshing}
          icon={<ReloadOutlined />}
          loading={refreshing}
          onClick={() => {
            void refresh();
            if (trendsActivated) {
              void refreshTrends();
            }
          }}
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
        <div className="market-overview-lead">
          <SectorHeatmapPreview onRefresh={() => void refresh()} sectorRadar={sectorRadar} />
          <MarketPulse market={market} onRefresh={() => void refresh()} sentiment={sentiment} />
        </div>
        <MarketIndexStrip market={market} onRefresh={() => void refresh()} />
        <div ref={trendAnchorRef}>
          <MarketTrendPanels
            emotion={emotionTrend}
            onRefreshEmotion={() => void refreshTrends()}
            onRefreshSector={() => void refreshTrends()}
            sector={sectorTrend}
          />
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
