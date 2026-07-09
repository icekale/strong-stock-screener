"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getSectorReplicaBoardStocks, getSectorReplicaRadar } from "../../lib/api";
import { nextSectorReplicaSelection } from "../../lib/sectorReplica";
import type {
  SectorReplicaMode,
  SectorReplicaRadarResponse,
  SectorReplicaStocksResponse,
} from "../../lib/types";
import { SectorReplicaPanel } from "./SectorReplicaPanel";

const RADAR_CACHE_KEY = "stockmaster:sector-replica:radar";
const STOCKS_CACHE_KEY = "stockmaster:sector-replica:stocks";

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
    [activeBoardCode, activeSubTheme, mode],
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

  const rows = useMemo(() => stocks?.rows ?? radar?.stocks ?? [], [radar, stocks]);
  const activePlate = useMemo(
    () => radar?.plates.find((item) => item.code === activeBoardCode) ?? radar?.plates[0] ?? null,
    [activeBoardCode, radar],
  );

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
    setStocks(null);
    setActiveSubTheme(tag);
  }

  return (
    <div className="sector-replica-workspace">
      <div className="sector-replica-toolbar">
        <div>
          <div className="sector-replica-toolbar-title">板块强度 / 主力流入</div>
          <div className="sector-replica-toolbar-meta">
            {radar?.trade_date ?? "-"} · {activePlate?.name ?? "等待板块"} · {radar?.generated_at?.replace("T", " ").slice(0, 16) ?? "-"}
          </div>
        </div>
        <button className="sector-replica-refresh" disabled={loading} onClick={() => setRefreshKey((value) => value + 1)} type="button">
          <ReloadOutlined />
          刷新
        </button>
      </div>

      <SectorReplicaPanel
        activeBoardCode={activeBoardCode}
        activeSubTheme={activeSubTheme}
        error={error}
        loading={loading}
        mode={mode}
        onActivateBoard={activateBoard}
        onModeChange={changeMode}
        onSubThemeChange={chooseSubTheme}
        onToggleBoard={toggleBoard}
        radar={radar}
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
