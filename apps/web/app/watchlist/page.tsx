"use client";

import type { ColumnsType } from "antd/es/table";
import {
  Alert,
  App,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { addWatchlistPoolItem, getWatchlistGsgfStatus, getWatchlistPool, saveWatchlistPool } from "../../lib/api";
import type { GsgfAnalysis, WatchlistPoolItem } from "../../lib/types";

type DraftItem = {
  symbol: string;
  name: string;
  industry: string;
  group: string;
  tagsText: string;
  note: string;
};

type StructureFilter = "all" | "opportunity" | "wait" | "risk" | "avoid";

const structureFilters: Array<{ label: string; value: StructureFilter }> = [
  { label: "全部", value: "all" },
  { label: "机会触发", value: "opportunity" },
  { label: "等确认", value: "wait" },
  { label: "风险预警", value: "risk" },
  { label: "C区/回避", value: "avoid" },
];

export default function WatchlistPage() {
  const { message } = App.useApp();
  const [items, setItems] = useState<WatchlistPoolItem[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [selectedSymbols, setSelectedSymbols] = useState<Set<string>>(() => new Set());
  const [activeGroup, setActiveGroup] = useState("all");
  const [activeTag, setActiveTag] = useState("all");
  const [structureFilter, setStructureFilter] = useState<StructureFilter>("all");
  const [gsgfBySymbol, setGsgfBySymbol] = useState<Record<string, GsgfAnalysis>>({});
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
          matchesStructureFilter(gsgfBySymbol[item.symbol], structureFilter) &&
          (!searchText.trim() || searchable.includes(searchText.trim().toLowerCase()))
        );
      }),
    [activeGroup, activeTag, gsgfBySymbol, items, searchText, structureFilter],
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

  async function moveSelectedToGroup() {
    if (!batchGroup.trim() || selectedSymbols.size === 0) {
      return;
    }
    await persistItems(
      items.map((item) =>
        selectedSymbols.has(item.symbol) ? { ...item, group: batchGroup.trim() } : item,
      ),
      `已移动 ${selectedSymbols.size} 只自选股`,
    );
    setBatchGroup("");
    setSelectedSymbols(new Set());
  }

  async function deleteSelected() {
    if (selectedSymbols.size === 0) {
      return;
    }
    const deletedCount = selectedSymbols.size;
    await persistItems(items.filter((item) => !selectedSymbols.has(item.symbol)), `已删除 ${deletedCount} 只自选股`);
    setSelectedSymbols(new Set());
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

  function selectAllVisible() {
    setSelectedSymbols(new Set(visibleItems.map((item) => item.symbol)));
  }

  const columns = useMemo<ColumnsType<WatchlistPoolItem>>(
    () => [
      {
        title: "股票",
        dataIndex: "name",
        width: 170,
        render: (_, item) => (
          <button
            className="text-left"
            onClick={(event) => {
              event.stopPropagation();
              setSelectedSymbol(item.symbol);
            }}
            type="button"
          >
            <span className="block font-black text-[#11100e]">{item.name ?? item.symbol}</span>
            <span className="mt-1 block text-xs font-semibold text-[#7b756d]">{item.symbol}</span>
          </button>
        ),
      },
      {
        title: "分组",
        dataIndex: "group",
        width: 120,
        render: (_, item) => <Typography.Text strong>{item.group || "自选"}</Typography.Text>,
      },
      {
        title: "行业",
        dataIndex: "industry",
        width: 130,
        render: (_, item) => <Typography.Text type={item.industry ? undefined : "secondary"}>{item.industry || "--"}</Typography.Text>,
      },
      {
        title: "结构触发",
        width: 210,
        render: (_, item) => <StructureTriggerBadge analysis={gsgfBySymbol[item.symbol]} />,
      },
      {
        title: "标签",
        dataIndex: "tags",
        width: 180,
        render: (_, item) => <TagList tags={item.tags} />,
      },
      {
        title: "备注",
        dataIndex: "note",
        render: (_, item) => (
          <Typography.Paragraph className="mb-0 max-w-[280px]" ellipsis={{ rows: 2 }}>
            {item.note || "无备注"}
          </Typography.Paragraph>
        ),
      },
    ],
    [gsgfBySymbol],
  );

  return (
    <main className="workbench-page">
      <div className="mx-auto max-w-none space-y-4 px-5 py-4">
        <Card className="workbench-panel" styles={{ body: { padding: 18 } }}>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <Typography.Text className="workbench-muted text-xs font-semibold uppercase">Watchlist</Typography.Text>
              <Typography.Title className="workbench-ink mt-1 text-2xl font-black tracking-tight" level={1}>
                自选股管理
              </Typography.Title>
              <Typography.Text className="workbench-muted mt-1 block text-sm font-medium">
                管理分组、标签、行业和备注。
              </Typography.Text>
            </div>
            <Space wrap>
              <Button href="/">返回选股</Button>
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
          </div>
        </Card>

        {error && <Alert showIcon title={error} type="error" />}

        <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <Card className="workbench-panel" size="small">
            <SectionTitle title="分组" />
            <Space className="w-full" orientation="vertical" size={8}>
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
            </Space>

            <div className="mt-5">
              <SectionTitle title="标签" />
              <div className="flex flex-wrap gap-2">
                <TagButton active={activeTag === "all"} label="全部" onClick={() => setActiveTag("all")} />
                {tags.map((tag) => (
                  <TagButton active={activeTag === tag} key={tag} label={tag} onClick={() => setActiveTag(tag)} />
                ))}
              </div>
            </div>

            <div className="mt-5">
              <SectionTitle title="结构触发" />
              <Segmented
                block
                onChange={(value) => setStructureFilter(value as StructureFilter)}
                options={structureFilters}
                value={structureFilter}
                vertical
              />
            </div>
          </Card>

          <Card className="workbench-panel min-w-0" styles={{ body: { padding: 0 } }}>
            <div className="workbench-panel-divider grid gap-3 border-b p-4 lg:grid-cols-[1fr_auto] lg:items-center">
              <Input
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="搜索代码 / 名称 / 行业 / 标签 / 备注"
                value={searchText}
              />
              <Tag className="m-0" variant="filled">
                显示 {visibleItems.length} / {items.length}
              </Tag>
            </div>

            {selectedCount > 0 && (
              <div className="workbench-panel-divider grid gap-2 border-b bg-[#eee9df] p-3 lg:grid-cols-[auto_minmax(120px,180px)_auto] lg:items-center">
                <Tag className="m-0" color="blue">
                  已选 {selectedCount}
                </Tag>
                <Input
                  onChange={(event) => setBatchGroup(event.target.value)}
                  placeholder="批量移动到分组"
                  size="small"
                  value={batchGroup}
                />
                <Space wrap size={8}>
                  <Button
                    disabled={!batchGroup.trim() || saving}
                    onClick={() => void moveSelectedToGroup()}
                    size="small"
                    type="primary"
                  >
                    批量移动
                  </Button>
                  <Button danger disabled={saving} onClick={() => void deleteSelected()} size="small">
                    删除
                  </Button>
                  <Button onClick={() => setSelectedSymbols(new Set())} size="small">
                    清空选择
                  </Button>
                  <Button onClick={selectAllVisible} size="small" type="link">
                    全选
                  </Button>
                </Space>
              </div>
            )}

            <Table
              columns={columns}
              dataSource={visibleItems}
              loading={loading}
              locale={{
                emptyText: loading ? "读取自选股中..." : <EmptyState text="当前筛选暂无自选股" />,
              }}
              pagination={false}
              rowClassName={(item) => (item.symbol === selectedItem?.symbol ? "workbench-table-row-selected" : "")}
              rowKey="symbol"
              rowSelection={{
                selectedRowKeys: Array.from(selectedSymbols),
                onChange: (keys) => setSelectedSymbols(new Set(keys.map(String))),
              }}
              onRow={(item) => ({
                onClick: () => setSelectedSymbol(item.symbol),
              })}
              scroll={{ x: 880 }}
              size="small"
            />
          </Card>

          <Card
            className="workbench-panel xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto"
            styles={{ body: { padding: 0 } }}
          >
            <div className="workbench-panel-divider border-b px-5 py-4">
              <Typography.Text className="workbench-muted text-xs font-semibold uppercase">Edit</Typography.Text>
              <Typography.Title className="workbench-ink mt-1 text-xl font-black" level={2}>
                {selectedItem ? "编辑自选股" : "新增自选股"}
              </Typography.Title>
            </div>
            <Form className="p-5" layout="vertical">
              <EditorInput label="股票代码" onChange={(value) => setDraft({ ...draft, symbol: value })} value={draft.symbol} />
              <EditorInput label="名称" onChange={(value) => setDraft({ ...draft, name: value })} value={draft.name} />
              <EditorInput label="分组" onChange={(value) => setDraft({ ...draft, group: value })} value={draft.group} />
              <EditorInput label="行业" onChange={(value) => setDraft({ ...draft, industry: value })} value={draft.industry} />
              <EditorInput label="标签" onChange={(value) => setDraft({ ...draft, tagsText: value })} value={draft.tagsText} />
              <Form.Item label="备注">
                <Input.TextArea
                  autoSize={{ minRows: 4, maxRows: 8 }}
                  onChange={(event) => setDraft({ ...draft, note: event.target.value })}
                  placeholder="记录买入观察理由、关键均线、风险点"
                  value={draft.note}
                />
              </Form.Item>
              <Button block disabled={saving} loading={saving} onClick={() => void saveDraft()} type="primary">
                保存
              </Button>
            </Form>
          </Card>
        </div>
      </div>
    </main>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h2 className="mb-3 text-xs font-black uppercase text-[#7b756d]">{title}</h2>;
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
        active ? "bg-[#11100e] text-white" : "bg-[#f5f3f0] text-[#11100e] hover:bg-[#eee9df]"
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
    <button onClick={onClick} type="button">
      <Tag className="m-0" color={active ? "blue" : "default"}>
        {label}
      </Tag>
    </button>
  );
}

function TagList({ tags }: { tags: string[] }) {
  if (tags.length === 0) {
    return <span className="text-sm text-[#7b756d]">--</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Tag className="m-0" color="blue" key={tag}>
          {tag}
        </Tag>
      ))}
    </div>
  );
}

function StructureTriggerBadge({ analysis }: { analysis: GsgfAnalysis | undefined }) {
  if (!analysis) {
    return <Typography.Text type="secondary">等待检测</Typography.Text>;
  }
  const avoid = analysis.action === "avoid" || analysis.zone === "c_zone";
  const color = avoid ? "red" : analysis.risk_flags.length > 0 ? "orange" : "purple";
  const tags = [...analysis.trigger_tags, ...analysis.pattern_tags, ...analysis.risk_flags].slice(0, 2);

  return (
    <div className="max-w-[220px] space-y-1.5">
      <div className="flex flex-wrap gap-1">
        <Tag className="m-0" color={color}>
          {gsgfLabel(analysis.action)} {analysis.total_score}
        </Tag>
        <Tag className="m-0">{gsgfLabel(analysis.zone)}</Tag>
      </div>
      {tags.length > 0 && <p className="line-clamp-2 text-xs leading-5 text-[#7b756d]">{tags.join(" / ")}</p>}
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
    <Form.Item label={label}>
      <Input onChange={(event) => onChange(event.target.value)} value={value} />
    </Form.Item>
  );
}

function EmptyState({ text }: { text: string }) {
  return <Empty description={text} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
}

function matchesStructureFilter(analysis: GsgfAnalysis | undefined, filter: StructureFilter) {
  if (filter === "all") {
    return true;
  }
  if (!analysis) {
    return false;
  }
  if (filter === "opportunity") {
    return ["strong_candidate", "watch_candidate"].includes(analysis.action) && analysis.risk_flags.length === 0;
  }
  if (filter === "wait") {
    return analysis.action === "wait_trigger";
  }
  if (filter === "risk") {
    return analysis.risk_flags.length > 0;
  }
  return analysis.action === "avoid" || analysis.zone === "c_zone";
}

function gsgfLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    strong_candidate: "强势候选",
    watch_candidate: "观察候选",
    wait_trigger: "等触发",
    avoid: "回避",
    a_zone: "A区",
    b_zone_a_point: "B区A点",
    c_zone: "C区",
    unformed: "未成型",
    unknown: "未知",
  };
  return value ? labels[value] ?? value : "--";
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
