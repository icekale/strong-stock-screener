"use client";

import { useEffect, useMemo, useState } from "react";
import { addWatchlistPoolItem, getWatchlistPool, saveWatchlistPool } from "../../lib/api";
import type { WatchlistPoolItem } from "../../lib/types";

type DraftItem = {
  symbol: string;
  name: string;
  industry: string;
  group: string;
  tagsText: string;
  note: string;
};

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistPoolItem[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [selectedSymbols, setSelectedSymbols] = useState<Set<string>>(() => new Set());
  const [activeGroup, setActiveGroup] = useState("all");
  const [activeTag, setActiveTag] = useState("all");
  const [searchText, setSearchText] = useState("");
  const [batchGroup, setBatchGroup] = useState("");
  const [draft, setDraft] = useState<DraftItem>(emptyDraft());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadPool();
  }, []);

  const groups = useMemo(() => groupItems(items), [items]);
  const tags = useMemo(() => uniqueTags(items), [items]);
  const visibleItems = useMemo(
    () =>
      items.filter((item) => {
        const group = item.group?.trim() || "自选";
        const searchable = [item.symbol, item.name, item.industry, group, item.tags.join(","), item.note]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return (
          (activeGroup === "all" || group === activeGroup) &&
          (activeTag === "all" || item.tags.includes(activeTag)) &&
          (!searchText.trim() || searchable.includes(searchText.trim().toLowerCase()))
        );
      }),
    [activeGroup, activeTag, items, searchText],
  );
  const selectedItem = items.find((item) => item.symbol === selectedSymbol) ?? visibleItems[0] ?? null;
  const selectedCount = selectedSymbols.size;

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

  useEffect(() => {
    const visibleSymbols = new Set(visibleItems.map((item) => item.symbol));
    setSelectedSymbols((current) => {
      const next = new Set(Array.from(current).filter((symbol) => visibleSymbols.has(symbol)));
      return next.size === current.size ? current : next;
    });
  }, [visibleItems]);

  async function loadPool() {
    setLoading(true);
    setError(null);
    try {
      const response = await getWatchlistPool();
      setItems(response.items);
      setSelectedSymbol(response.items[0]?.symbol ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取自选股失败");
    } finally {
      setLoading(false);
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存自选股失败");
    } finally {
      setSaving(false);
    }
  }

  async function moveSelectedToGroup() {
    if (!batchGroup.trim() || selectedSymbols.size === 0) {
      return;
    }
    await persistItems(
      items.map((item) =>
        selectedSymbols.has(item.symbol) ? { ...item, group: batchGroup.trim() } : item,
      ),
    );
    setBatchGroup("");
    setSelectedSymbols(new Set());
  }

  async function deleteSelected() {
    if (selectedSymbols.size === 0) {
      return;
    }
    await persistItems(items.filter((item) => !selectedSymbols.has(item.symbol)));
    setSelectedSymbols(new Set());
  }

  async function persistItems(nextItems: WatchlistPoolItem[]) {
    setSaving(true);
    setError(null);
    try {
      const response = await saveWatchlistPool(formatWatchlistContent(nextItems));
      setItems(response.items);
      setSelectedSymbol(response.items[0]?.symbol ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存自选股失败");
    } finally {
      setSaving(false);
    }
  }

  function toggleSelected(symbol: string, checked: boolean) {
    setSelectedSymbols((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(symbol);
      } else {
        next.delete(symbol);
      }
      return next;
    });
  }

  function selectAllVisible() {
    setSelectedSymbols(new Set(visibleItems.map((item) => item.symbol)));
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-[1680px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        <header className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">Watchlist</p>
              <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-950">自选股管理</h1>
              <p className="mt-1 text-sm font-medium text-slate-500">管理分组、标签、行业和备注。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <a
                className="inline-flex min-h-[36px] items-center rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100"
                href="/"
              >
                返回选股
              </a>
              <button
                className="min-h-[36px] rounded-md bg-slate-950 px-3 text-xs font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={saving}
                onClick={() => {
                  setSelectedSymbol(null);
                  setDraft(emptyDraft());
                }}
                type="button"
              >
                新增股票
              </button>
            </div>
          </div>
        </header>

        {error && <p className="rounded-lg bg-red-50 p-3 text-sm font-bold text-red-700">{error}</p>}

        <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <aside className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <SectionTitle title="分组" />
            <div className="space-y-2">
              <GroupButton
                active={activeGroup === "all"}
                count={items.length}
                label="全部"
                onClick={() => setActiveGroup("all")}
              />
              {groups.map((group) => (
                <GroupButton
                  active={activeGroup === group.name}
                  count={group.items.length}
                  key={group.name}
                  label={group.name}
                  onClick={() => setActiveGroup(group.name)}
                />
              ))}
            </div>

            <div className="mt-5">
              <SectionTitle title="标签" />
              <div className="flex flex-wrap gap-2">
                <TagButton active={activeTag === "all"} label="全部" onClick={() => setActiveTag("all")} />
                {tags.map((tag) => (
                  <TagButton active={activeTag === tag} key={tag} label={tag} onClick={() => setActiveTag(tag)} />
                ))}
              </div>
            </div>
          </aside>

          <section className="min-w-0 rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="grid gap-3 border-b border-slate-100 p-4 lg:grid-cols-[1fr_auto] lg:items-center">
              <input
                className="min-h-[38px] rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="搜索代码 / 名称 / 行业 / 标签 / 备注"
                value={searchText}
              />
              <span className="text-xs font-bold text-slate-500">
                显示 {visibleItems.length} / {items.length}
              </span>
            </div>

            {selectedCount > 0 && (
              <div className="grid gap-2 border-b border-slate-100 bg-sky-50 p-3 lg:grid-cols-[auto_minmax(120px,180px)_auto] lg:items-center">
                <span className="text-xs font-black text-sky-700">已选 {selectedCount}</span>
                <input
                  className="min-h-[34px] rounded-md border border-sky-100 bg-white px-2.5 text-xs font-semibold text-slate-950 outline-none focus:ring-2 focus:ring-sky-100"
                  onChange={(event) => setBatchGroup(event.target.value)}
                  placeholder="批量移动到分组"
                  value={batchGroup}
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    className="min-h-[34px] rounded-md bg-sky-700 px-3 text-xs font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                    disabled={!batchGroup.trim() || saving}
                    onClick={() => void moveSelectedToGroup()}
                    type="button"
                  >
                    批量移动
                  </button>
                  <button
                    className="min-h-[34px] rounded-md bg-red-50 px-3 text-xs font-bold text-red-700 ring-1 ring-red-100 disabled:cursor-not-allowed disabled:text-slate-300"
                    disabled={saving}
                    onClick={() => void deleteSelected()}
                    type="button"
                  >
                    删除
                  </button>
                  <button
                    className="min-h-[34px] rounded-md bg-white px-3 text-xs font-bold text-slate-600 ring-1 ring-slate-200"
                    onClick={() => setSelectedSymbols(new Set())}
                    type="button"
                  >
                    清空选择
                  </button>
                </div>
              </div>
            )}

            <div className="overflow-x-auto">
              {loading ? (
                <EmptyState text="读取自选股中..." />
              ) : visibleItems.length === 0 ? (
                <EmptyState text="当前筛选暂无自选股" />
              ) : (
                <table className="w-full min-w-[780px] border-separate border-spacing-0 text-left text-sm">
                  <thead>
                    <tr className="text-xs font-bold text-slate-400">
                      <th className="px-4 py-3">
                        <button className="text-slate-500" onClick={selectAllVisible} type="button">
                          全选
                        </button>
                      </th>
                      <th className="px-3 py-3">股票</th>
                      <th className="px-3 py-3">分组</th>
                      <th className="px-3 py-3">行业</th>
                      <th className="px-3 py-3">标签</th>
                      <th className="px-4 py-3">备注</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {visibleItems.map((item) => (
                      <tr
                        aria-selected={item.symbol === selectedItem?.symbol}
                        className={`cursor-pointer transition ${
                          item.symbol === selectedItem?.symbol ? "bg-slate-100" : "bg-white hover:bg-slate-50"
                        }`}
                        key={item.symbol}
                        onClick={() => setSelectedSymbol(item.symbol)}
                      >
                        <td className="px-4 py-3 align-top">
                          <input
                            aria-label={`选择 ${item.name ?? item.symbol}`}
                            checked={selectedSymbols.has(item.symbol)}
                            className="size-4 rounded border-slate-300"
                            onChange={(event) => toggleSelected(item.symbol, event.target.checked)}
                            onClick={(event) => event.stopPropagation()}
                            type="checkbox"
                          />
                        </td>
                        <td className="px-3 py-3 align-top">
                          <p className="font-black text-slate-950">{item.name ?? item.symbol}</p>
                          <p className="mt-1 text-xs font-semibold text-slate-400">{item.symbol}</p>
                        </td>
                        <td className="px-3 py-3 align-top text-sm font-semibold text-slate-600">
                          {item.group || "自选"}
                        </td>
                        <td className="px-3 py-3 align-top text-sm text-slate-500">{item.industry || "--"}</td>
                        <td className="px-3 py-3 align-top">
                          <TagList tags={item.tags} />
                        </td>
                        <td className="max-w-[240px] px-4 py-3 align-top text-sm leading-6 text-slate-500">
                          <span className="line-clamp-2">{item.note || "无备注"}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

          <aside className="rounded-lg border border-slate-200 bg-white shadow-sm xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto">
            <div className="border-b border-slate-100 px-5 py-4">
              <p className="text-xs font-semibold uppercase text-slate-400">Edit</p>
              <h2 className="mt-1 text-xl font-black text-slate-950">{selectedItem ? "编辑自选股" : "新增自选股"}</h2>
            </div>
            <div className="space-y-3 p-5">
              <EditorInput label="股票代码" onChange={(value) => setDraft({ ...draft, symbol: value })} value={draft.symbol} />
              <EditorInput label="名称" onChange={(value) => setDraft({ ...draft, name: value })} value={draft.name} />
              <EditorInput label="分组" onChange={(value) => setDraft({ ...draft, group: value })} value={draft.group} />
              <EditorInput label="行业" onChange={(value) => setDraft({ ...draft, industry: value })} value={draft.industry} />
              <EditorInput label="标签" onChange={(value) => setDraft({ ...draft, tagsText: value })} value={draft.tagsText} />
              <label className="block">
                <span className="text-xs font-bold text-slate-600">备注</span>
                <textarea
                  className="mt-2 min-h-[96px] w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                  onChange={(event) => setDraft({ ...draft, note: event.target.value })}
                  placeholder="记录买入观察理由、关键均线、风险点"
                  value={draft.note}
                />
              </label>
              <button
                className="min-h-[40px] w-full rounded-lg bg-slate-950 px-4 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={saving}
                onClick={() => void saveDraft()}
                type="button"
              >
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h2 className="mb-3 text-xs font-black uppercase text-slate-400">{title}</h2>;
}

function GroupButton({
  active,
  count,
  label,
  onClick,
}: {
  active: boolean;
  count: number;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`flex min-h-[34px] w-full items-center justify-between rounded-md px-3 text-xs font-black transition ${
        active ? "bg-slate-950 text-white" : "bg-slate-50 text-slate-700 hover:bg-slate-100"
      }`}
      onClick={onClick}
      type="button"
    >
      <span>{label}</span>
      <span className="tabular-nums opacity-75">{count}</span>
    </button>
  );
}

function TagButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      className={`inline-flex h-7 items-center rounded-full px-2.5 text-xs font-bold ring-1 transition ${
        active
          ? "bg-indigo-600 text-white ring-indigo-600"
          : "bg-indigo-50 text-indigo-700 ring-indigo-100 hover:bg-indigo-100"
      }`}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function TagList({ tags }: { tags: string[] }) {
  if (tags.length === 0) {
    return <span className="text-sm text-slate-400">--</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-700" key={tag}>
          {tag}
        </span>
      ))}
    </div>
  );
}

function EditorInput({
  label,
  onChange,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-bold text-slate-600">{label}</span>
      <input
        className="mt-2 min-h-[38px] w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="px-5 py-12 text-center text-sm font-bold text-slate-500">{text}</div>;
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

function uniqueTags(items: WatchlistPoolItem[]) {
  return Array.from(new Set(items.flatMap((item) => item.tags))).sort((a, b) => a.localeCompare(b, "zh-CN"));
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

function emptyDraft(): DraftItem {
  return {
    group: "自选",
    industry: "",
    name: "",
    note: "",
    symbol: "",
    tagsText: "",
  };
}
