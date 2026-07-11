"use client";

import { Alert, App, Button, Card, Skeleton, Space, Typography } from "antd";
import dynamic from "next/dynamic";
import { useEffect, useState, type ComponentType } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";
import { addWatchlistPoolItem, getWatchlistGsgfStatus, getWatchlistPool, saveWatchlistPool } from "../../lib/api";
import type { GsgfAnalysis, WatchlistPoolItem } from "../../lib/types";
import { emptyDraft, type DraftItem } from "./types";
import type { WatchlistEditorPanelProps } from "./WatchlistEditorPanel";
import type { WatchlistManagerPanelProps } from "./WatchlistManagerPanel";

const WatchlistEditorPanel = dynamic(
  () => import("./WatchlistEditorPanel").then((module) => module.WatchlistEditorPanel),
  { ssr: false, loading: () => <WatchlistEditorPlaceholder /> },
) as ComponentType<WatchlistEditorPanelProps>;

const WatchlistManagerPanel = dynamic(
  () => import("./WatchlistManagerPanel").then((module) => module.WatchlistManagerPanel),
  { ssr: false, loading: () => <WatchlistManagerPlaceholder /> },
) as ComponentType<WatchlistManagerPanelProps>;

export function WatchlistWorkspace() {
  const { message } = App.useApp();
  const [items, setItems] = useState<WatchlistPoolItem[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [gsgfBySymbol, setGsgfBySymbol] = useState<Record<string, GsgfAnalysis>>({});
  const [draft, setDraft] = useState<DraftItem>(emptyDraft());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadPool();
  }, []);

  const selectedItem = items.find((item) => item.symbol === selectedSymbol) ?? items[0] ?? null;

  useEffect(() => {
    if (!selectedItem) {
      setDraft(emptyDraft());
      return;
    }
    setSelectedSymbol(selectedItem.symbol);
    setDraft({
      symbol: selectedItem.symbol,
      name: selectedItem.name ?? "",
      industry: selectedItem.industry ?? "",
      group: selectedItem.group?.trim() || "自选",
      tagsText: selectedItem.tags.join("，"),
      note: selectedItem.note ?? "",
    });
  }, [selectedItem?.symbol]);

  async function loadPool() {
    setLoading(true);
    setError(null);
    try {
      const response = await getWatchlistPool();
      setItems(response.items);
      setSelectedSymbol(response.items[0]?.symbol ?? null);
      void refreshStructureStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取自选股失败");
    } finally {
      setLoading(false);
    }
  }

  async function refreshStructureStatus() {
    try {
      const response = await getWatchlistGsgfStatus();
      setGsgfBySymbol(Object.fromEntries(response.items.map((item) => [item.symbol, item.gsgf])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取结构触发失败");
    }
  }

  async function saveDraft() {
    if (!draft.symbol.trim()) {
      setError("股票代码不能为空");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = await addWatchlistPoolItem({
        symbol: draft.symbol,
        name: draft.name || null,
        industry: draft.industry || null,
        group: draft.group || "自选",
        tags: splitTags(draft.tagsText),
        note: draft.note || null,
      });
      setItems(response.items);
      setSelectedSymbol(response.items.find((item) => item.symbol === draft.symbol)?.symbol ?? response.items[0]?.symbol ?? null);
      void message.success("自选股已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存自选股失败");
    } finally {
      setSaving(false);
    }
  }

  async function persistItems(nextItems: WatchlistPoolItem[], successText = "自选股已保存") {
    setSaving(true);
    setError(null);
    try {
      const response = await saveWatchlistPool(formatWatchlistContent(nextItems));
      setItems(response.items);
      setSelectedSymbol(response.items[0]?.symbol ?? null);
      void message.success(successText);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存自选股失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageFrame
      actions={
        <Space wrap>
          <Button href="/screener">返回选股</Button>
          <Button
            disabled={saving}
            onClick={() => {
              setSelectedSymbol(null);
              setDraft(emptyDraft());
            }}
            type="primary"
          >
            新增股票
          </Button>
        </Space>
      }
      title="自选股管理"
    >
        {error && <Alert showIcon title={error} type="error" />}

        <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <WatchlistManagerPanel
            gsgfBySymbol={gsgfBySymbol}
            items={items}
            loading={loading}
            onPersistItems={persistItems}
            onSelectedSymbolChange={setSelectedSymbol}
            saving={saving}
            selectedSymbol={selectedSymbol}
          />

          <WatchlistEditorPanel
            draft={draft}
            onDraftChange={setDraft}
            onSave={() => void saveDraft()}
            saving={saving}
            selected={Boolean(selectedItem)}
          />
        </div>
    </PageFrame>
  );
}

function WatchlistEditorPlaceholder() {
  return (
    <Card className="border-[var(--app-border)] bg-[var(--app-surface)] xl:sticky xl:top-4" styles={{ body: { padding: 20 } }}>
      <Typography.Text className="text-[var(--app-muted)] text-sm font-medium">正在加载编辑面板...</Typography.Text>
    </Card>
  );
}

function WatchlistManagerPlaceholder() {
  return (
    <>
      <Card className="border-[var(--app-border)] bg-[var(--app-surface)]" size="small">
        <Skeleton active paragraph={{ rows: 10 }} />
      </Card>
      <Card className="border-[var(--app-border)] bg-[var(--app-surface)] min-w-0">
        <Skeleton active paragraph={{ rows: 12 }} />
      </Card>
    </>
  );
}

function groupItems(items: WatchlistPoolItem[]) {
  const groups: Array<{ name: string; items: WatchlistPoolItem[] }> = [];
  const indexByName = new Map<string, number>();
  for (const item of items) {
    const name = item.group?.trim() || "自选";
    let index = indexByName.get(name);
    if (index === undefined) {
      index = groups.length;
      indexByName.set(name, index);
      groups.push({ name, items: [] });
    }
    groups[index].items.push(item);
  }
  return groups;
}

function splitTags(value: string) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，]/)) {
    const tag = chunk.trim();
    if (tag && !seen.has(tag)) {
      seen.add(tag);
      output.push(tag);
    }
  }
  return output;
}

function formatWatchlistContent(items: WatchlistPoolItem[]) {
  return groupItems(items)
    .map((group) => {
      const lines = [`[${group.name}]`];
      for (const item of group.items) {
        lines.push(formatWatchlistLine(item));
      }
      return lines.join("\n");
    })
    .join("\n\n");
}

function formatWatchlistLine(item: WatchlistPoolItem) {
  return [
    item.symbol,
    item.name ?? "",
    ...item.tags.map((tag) => `#${tag}`),
    item.industry ? `行业=${item.industry}` : "",
    item.note ? `备注=${item.note}` : "",
  ]
    .filter(Boolean)
    .join(" ");
}
