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
import { createMemoryRequestCache } from "../lib/marketOverviewCache";
import type {
  MarketEmotionSnapshotResponse,
  MarketOverviewResponse,
  SectorRadarResponse,
  SectorReplicaRadarResponse,
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
  const [sectorTrend, setSectorTrend] = useState<PanelState<SectorReplicaRadarResponse> | null>(null);
  const [emotionTrend, setEmotionTrend] = useState<PanelState<MarketEmotionSnapshotResponse> | null>(null);
  const [trendsActivated, setTrendsActivated] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const refreshGeneration = useRef(0);
  const trendRefreshGeneration = useRef(0);
  const emotionRefreshGeneration = useRef(0);
  const trendAnchorRef = useRef<HTMLDivElement>(null);

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

  const refreshTrends = useCallback((force = false) => {
    const generation = nextRequestGeneration(trendRefreshGeneration.current);
    trendRefreshGeneration.current = generation;
    const tradeDate = getShanghaiTradeDate();

    return executeLatestOnly({
      generation,
      currentGeneration: () => trendRefreshGeneration.current,
      execute: () =>
        Promise.allSettled([
          getHomepagePanel(
            "sector-trend",
            tradeDate,
            () => getSectorReplicaRadar({ mode: "strength", limit: 6, stockLimit: 1 }),
            force,
          ),
          getHomepagePanel("emotion-trend", tradeDate, () => getMarketEmotionSnapshot(tradeDate, 80, false), force),
        ]),
      apply: ([sectorResult, emotionResult]) => {
        setSectorTrend((previous) => toPanelState(sectorResult, panelValue(previous)));
        setEmotionTrend((previous) => toPanelState(emotionResult, panelValue(previous)));
      },
      finishLoading: () => undefined,
    });
  }, []);

  const refreshEmotion = useCallback((force = true) => {
    const generation = nextRequestGeneration(emotionRefreshGeneration.current);
    emotionRefreshGeneration.current = generation;
    const tradeDate = getShanghaiTradeDate();

    return executeLatestOnly({
      generation,
      currentGeneration: () => emotionRefreshGeneration.current,
      execute: () =>
        settleRequest(() =>
          getHomepagePanel("emotion-trend", tradeDate, () => getMarketEmotionSnapshot(tradeDate, 80, false), force),
        ),
      apply: (result) => {
        setEmotionTrend((previous) => toPanelState(result, panelValue(previous)));
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

  useEffect(() => {
    if (!trendsActivated) {
      return;
    }
    const sampleEmotion = () => {
      if (document.visibilityState === "visible" && getMarketSession() === "盘中") {
        void refreshEmotion(true);
      }
    };
    const interval = window.setInterval(sampleEmotion, 180_000);
    return () => window.clearInterval(interval);
  }, [refreshEmotion, trendsActivated]);

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
            void refresh(true);
            if (trendsActivated) {
              void refreshTrends(true);
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
          <SectorHeatmapPreview onRefresh={() => void refresh(true)} sectorRadar={sectorRadar} />
          <MarketPulse market={market} onRefresh={() => void refresh(true)} sentiment={sentiment} />
        </div>
        <MarketIndexStrip market={market} onRefresh={() => void refresh(true)} />
        <div ref={trendAnchorRef}>
          <MarketTrendPanels
            emotion={emotionTrend}
            onRefreshEmotion={() => void refreshEmotion(true)}
            onRefreshSector={() => void refreshTrends(true)}
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
