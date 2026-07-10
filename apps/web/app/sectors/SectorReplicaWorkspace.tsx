"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getSectorReplicaBoardStocks, getSectorReplicaRadar } from "../../lib/api";
import { isSectorReplicaStocksForSelection, nextSectorReplicaSelection } from "../../lib/sectorReplica";
import type {
  SectorReplicaMode,
  SectorReplicaRadarResponse,
  SectorReplicaStocksResponse,
} from "../../lib/types";
import { SectorReplicaPanel } from "./SectorReplicaPanel";

const RADAR_CACHE_KEY = "stockmaster:sector-replica:qxlive:v2:radar";
const STOCKS_CACHE_KEY = "stockmaster:sector-replica:qxlive:v2:stocks";

export function SectorReplicaWorkspace() {
  const [mode, setMode] = useState<SectorReplicaMode>("strength");
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [activeBoardCode, setActiveBoardCode] = useState<string | null>(null);
  const [activeSubTheme, setActiveSubTheme] = useState<string | null>(null);
  const [radar, setRadar] = useState<SectorReplicaRadarResponse | null>(() => readSessionJson(RADAR_CACHE_KEY));
  const [stocks, setStocks] = useState<SectorReplicaStocksResponse | null>(() => readSessionJson(STOCKS_CACHE_KEY));
  const [loading, setLoading] = useState(false);
  const [stockLoading, setStockLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const selectedKey = selectedCodes.join(",");
  const activeBoardName = radar?.plates.find((item) => item.code === activeBoardCode)?.name ?? null;

  useEffect(() => {
    if (radar) {
      writeSessionJson(RADAR_CACHE_KEY, radar);
    }
  }, [radar]);

  useEffect(() => {
    if (stocks) {
      writeSessionJson(STOCKS_CACHE_KEY, stocks);
    }
  }, [stocks]);

  const loadRadar = useCallback(
    async (background = false) => {
      if (!background) {
        setLoading(true);
      }
      setError(null);
      try {
        const response = await getSectorReplicaRadar({
          limit: 30,
          mode,
          selected: selectedKey ? selectedKey.split(",") : [],
          stockLimit: 80,
        });
        setRadar(response);
        setSelectedCodes((current) => {
          const next = response.checkplate.length
            ? response.checkplate
            : response.plates.slice(0, 5).map((item) => item.code);
          return current.join(",") === next.join(",") ? current : next;
        });
        setActiveBoardCode((current) => {
          if (current && response.plates.some((item) => item.code === current)) {
            return current;
          }
          return response.checkplate[0] ?? response.plates[0]?.code ?? null;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "读取板块雷达失败");
      } finally {
        if (!background) {
          setLoading(false);
        }
      }
    },
    [mode, selectedKey],
  );

  const loadStocks = useCallback(
    async (background = false) => {
      if (!activeBoardCode) {
        return;
      }
      if (!background) {
        setStockLoading(true);
      }
      try {
        const response = await getSectorReplicaBoardStocks(activeBoardCode, {
          boardName: activeBoardName,
          limit: 100,
          mode,
          subTheme: activeSubTheme,
        });
        setStocks(response);
      } catch (err) {
        if (!background) {
          setError(err instanceof Error ? err.message : "读取板块成分股失败");
        }
      } finally {
        if (!background) {
          setStockLoading(false);
        }
      }
    },
    [activeBoardCode, activeBoardName, activeSubTheme, mode],
  );

  useEffect(() => {
    void loadRadar();
    const timer = window.setInterval(() => void loadRadar(true), 15_000);
    return () => window.clearInterval(timer);
  }, [loadRadar, refreshKey]);

  useEffect(() => {
    void loadStocks();
    const timer = window.setInterval(() => void loadStocks(true), 8_000);
    return () => window.clearInterval(timer);
  }, [loadStocks]);

  const rows = useMemo(
    () =>
      isSectorReplicaStocksForSelection(stocks, activeBoardCode, activeSubTheme)
        ? stocks?.rows ?? []
        : radar?.stocks ?? [],
    [activeBoardCode, activeSubTheme, radar, stocks],
  );
  const relatedTags =
    stocks?.board_code === activeBoardCode ? stocks.related_tags : radar?.related_tags ?? [];
  function changeMode(nextMode: SectorReplicaMode) {
    setMode(nextMode);
    setActiveSubTheme(null);
    setRefreshKey((value) => value + 1);
  }

  function toggleBoard(code: string, checked: boolean) {
    setSelectedCodes((current) => {
      const next = nextSectorReplicaSelection(current, code, checked);
      if (checked) {
        setStocks(null);
        setActiveBoardCode(code);
        setActiveSubTheme(null);
      } else if (activeBoardCode === code && next[0]) {
        setStocks(null);
        setActiveBoardCode(next[0]);
        setActiveSubTheme(null);
      }
      return next;
    });
  }

  function activateBoard(code: string) {
    setStocks(null);
    setActiveBoardCode(code);
    setActiveSubTheme(null);
  }

  function chooseSubTheme(tag: string | null) {
    setActiveSubTheme(tag);
  }

  return (
    <div className="sector-replica-workspace">
      <SectorReplicaPanel
        activeBoardCode={activeBoardCode}
        activeSubTheme={activeSubTheme}
        error={error}
        loading={loading}
        mode={mode}
        onActivateBoard={activateBoard}
        onModeChange={changeMode}
        onRefresh={() => setRefreshKey((value) => value + 1)}
        onSubThemeChange={chooseSubTheme}
        onToggleBoard={toggleBoard}
        radar={radar}
        relatedTags={relatedTags}
        selectedCodes={selectedCodes}
        stockLoading={stockLoading}
        stocks={rows}
      />
    </div>
  );
}

function readSessionJson<T>(key: string): T | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const value = window.sessionStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : null;
  } catch {
    return null;
  }
}

function writeSessionJson(key: string, value: unknown): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Session cache is an optimization; UI still works without it.
  }
}
