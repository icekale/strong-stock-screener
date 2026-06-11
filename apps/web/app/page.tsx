"use client";

import { useEffect, useState } from "react";
import { ScreenerWorkbench } from "../components/ScreenerWorkbench";
import { createScreenRun, getDataSourceStatus, getLatestScreenRun } from "../lib/api";
import type { DataSourceStatusResponse, StrongStockScreeningResponse } from "../lib/types";

export default function HomePage() {
  const [tradeDate, setTradeDate] = useState(defaultTradeDate());
  const [sources, setSources] = useState<DataSourceStatusResponse | null>(null);
  const [result, setResult] = useState<StrongStockScreeningResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshSources();
    void refreshLatest();
  }, []);

  async function refreshSources() {
    try {
      setSources(await getDataSourceStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取数据源状态失败");
    }
  }

  async function refreshLatest() {
    try {
      setResult(await getLatestScreenRun());
    } catch {
      setResult(null);
    }
  }

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const response = await createScreenRun(tradeDate, 30);
      setResult(response);
      await refreshSources();
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行筛选失败");
    } finally {
      setRunning(false);
    }
  }

  return (
    <ScreenerWorkbench
      error={error}
      onRefreshSources={() => void refreshSources()}
      onRun={() => void handleRun()}
      result={result}
      running={running}
      sources={sources}
      tradeDate={tradeDate}
      onTradeDateChange={setTradeDate}
    />
  );
}

function defaultTradeDate(): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(new Date());
}

