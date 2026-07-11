"use client";

import type { ColumnsType } from "antd/es/table";
import { Button, Card, Empty, Input, Segmented, Space, Table, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import type { GsgfAnalysis, WatchlistPoolItem } from "../../lib/types";

type StructureFilter = "all" | "opportunity" | "wait" | "risk" | "avoid";

const structureFilters: Array<{ label: string; value: StructureFilter }> = [
  { label: "全部", value: "all" },
  { label: "机会触发", value: "opportunity" },
  { label: "等确认", value: "wait" },
  { label: "风险预警", value: "risk" },
  { label: "C区/回避", value: "avoid" },
];

export type WatchlistManagerPanelProps = {
  gsgfBySymbol: Record<string, GsgfAnalysis>;
  items: WatchlistPoolItem[];
  loading: boolean;
  onPersistItems: (nextItems: WatchlistPoolItem[], successText?: string) => Promise<void>;
  onSelectedSymbolChange: (symbol: string | null) => void;
  saving: boolean;
  selectedSymbol: string | null;
};

export function WatchlistManagerPanel({
  gsgfBySymbol,
  items,
  loading,
  onPersistItems,
  onSelectedSymbolChange,
  saving,
  selectedSymbol,
}: WatchlistManagerPanelProps) {
  const [selectedSymbols, setSelectedSymbols] = useState<Set<string>>(() => new Set());
  const [activeGroup, setActiveGroup] = useState("all");
  const [activeTag, setActiveTag] = useState("all");
  const [structureFilter, setStructureFilter] = useState<StructureFilter>("all");
  const [searchText, setSearchText] = useState("");
  const [batchGroup, setBatchGroup] = useState("");

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
  const selectedCount = selectedSymbols.size;

  useEffect(() => {
    const visibleSymbols = new Set(visibleItems.map((item) => item.symbol));
    setSelectedSymbols((current) => {
      const next = new Set(Array.from(current).filter((symbol) => visibleSymbols.has(symbol)));
      return next.size === current.size ? current : next;
    });
    if (!selectedSymbol || !visibleSymbols.has(selectedSymbol)) {
      onSelectedSymbolChange(visibleItems[0]?.symbol ?? null);
    }
  }, [onSelectedSymbolChange, selectedSymbol, visibleItems]);

  async function moveSelectedToGroup() {
    if (!batchGroup.trim() || selectedSymbols.size === 0) {
      return;
    }
    await onPersistItems(
      items.map((item) => (selectedSymbols.has(item.symbol) ? { ...item, group: batchGroup.trim() } : item)),
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
    await onPersistItems(items.filter((item) => !selectedSymbols.has(item.symbol)), `已删除 ${deletedCount} 只自选股`);
    setSelectedSymbols(new Set());
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
              onSelectedSymbolChange(item.symbol);
            }}
            type="button"
          >
            <span className="block font-black text-[var(--app-ink)]">{item.name ?? item.symbol}</span>
            <span className="mt-1 block text-xs font-semibold text-[var(--app-muted)]">{item.symbol}</span>
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
    [gsgfBySymbol, onSelectedSymbolChange],
  );

  return (
    <>
      <Card className="workbench-panel" size="small">
        <SectionTitle title="分组" />
        <Space className="w-full" orientation="vertical" size={8}>
          <GroupButton active={activeGroup === "all"} count={items.length} label="全部" onClick={() => setActiveGroup("all")} />
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
          <div className="workbench-panel-divider grid gap-2 border-b bg-[var(--app-raised)] p-3 lg:grid-cols-[auto_minmax(120px,180px)_auto] lg:items-center">
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
              <Button disabled={!batchGroup.trim() || saving} onClick={() => void moveSelectedToGroup()} size="small" type="primary">
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
          onRow={(item) => ({
            onClick: () => onSelectedSymbolChange(item.symbol),
          })}
          pagination={false}
          rowClassName={(item) => (item.symbol === selectedSymbol ? "workbench-table-row-selected" : "")}
          rowKey="symbol"
          rowSelection={{
            selectedRowKeys: Array.from(selectedSymbols),
            onChange: (keys) => setSelectedSymbols(new Set(keys.map(String))),
          }}
          scroll={{ x: 880 }}
          size="small"
        />
      </Card>
    </>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h2 className="mb-3 text-xs font-black uppercase text-[var(--app-muted)]">{title}</h2>;
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
        active ? "bg-[var(--app-ink)] text-white" : "bg-[var(--app-raised)] text-[var(--app-ink)] hover:bg-[var(--app-border)]"
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
    return <span className="text-sm text-[var(--app-muted)]">--</span>;
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
      {tags.length > 0 && <p className="line-clamp-2 text-xs leading-5 text-[var(--app-muted)]">{tags.join(" / ")}</p>}
    </div>
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
