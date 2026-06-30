"use client";

import type { ColumnsType } from "antd/es/table";
import { Alert, Button, Card, Checkbox, Empty, Input, Segmented, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type {
  GsgfAnalysis,
  StrongStockScreeningItem,
  WatchlistPoolItem,
} from "../../lib/types";
import {
  filterStockListByGsgf,
  type GsgfSignalFilter,
  gsgfSignalFilterOptions,
} from "../../lib/stockListFilter";
import {
  candidateStatusFilters,
  industryStrengthCopy,
  statusCopy,
  type CandidateStatusFilter,
} from "./types";
import {
  gsgfFinalStatusTone,
  gsgfLabel,
  primaryRiskSummary,
  splitTags,
} from "./screenerUtils";

export type CandidateTableProps = {
  generatedAt: string | null;
  items: StrongStockScreeningItem[];
  onAddManyToWatchlist: (items: StrongStockScreeningItem[], group: string, tags: string[]) => void;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  running: boolean;
  selectedSymbol: string | null;
  watchlistMessage: string | null;
  watchlistPoolItems: WatchlistPoolItem[];
};

export function CandidateResults(props: CandidateTableProps) {
  return <DesignScreenerResultsTable {...props} />;
}

function DesignScreenerResultsTable(props: CandidateTableProps) {
  return <CandidateTable {...props} />;
}

function CandidateTable({
  generatedAt,
  items,
  onAddManyToWatchlist,
  onAddToWatchlist,
  onSelect,
  running,
  selectedSymbol,
  watchlistMessage,
  watchlistPoolItems,
}: CandidateTableProps) {
  const [selectedCandidateSymbols, setSelectedCandidateSymbols] = useState<Set<string>>(() => new Set());
  const [batchGroup, setBatchGroup] = useState("");
  const [batchTagsText, setBatchTagsText] = useState("");
  const [candidateStatusFilter, setCandidateStatusFilter] = useState<CandidateStatusFilter>("all");
  const [gsgfSignalFilter, setGsgfSignalFilter] = useState<GsgfSignalFilter>("all");
  const [excludeGsgfGlobalRisk, setExcludeGsgfGlobalRisk] = useState(false);
  const [strongIndustryOnly, setStrongIndustryOnly] = useState(false);
  const statusCounts = useMemo(() => {
    const counts: Record<CandidateStatusFilter, number> = {
      all: items.length,
      data_incomplete: 0,
      focus: 0,
      reduce_risk: 0,
      wait_pullback: 0,
    };
    for (const item of items) {
      counts[item.status] += 1;
    }
    return counts;
  }, [items]);
  const strongIndustryCount = useMemo(
    () => items.filter((item) => item.industry_strength === "strong").length,
    [items],
  );
  const visibleCandidates = useMemo(
    () =>
      filterStockListByGsgf(
        items.filter(
          (item) =>
            (candidateStatusFilter === "all" || item.status === candidateStatusFilter) &&
            (!strongIndustryOnly || item.industry_strength === "strong"),
        ),
        gsgfSignalFilter,
        excludeGsgfGlobalRisk,
      ),
    [candidateStatusFilter, excludeGsgfGlobalRisk, gsgfSignalFilter, items, strongIndustryOnly],
  );
  const selectedCandidateItems = visibleCandidates.filter((item) => selectedCandidateSymbols.has(item.symbol));
  const watchlistSymbols = useMemo(
    () => new Set(watchlistPoolItems.map((item) => item.symbol)),
    [watchlistPoolItems],
  );

  useEffect(() => {
    const validSymbols = new Set(visibleCandidates.map((item) => item.symbol));
    setSelectedCandidateSymbols((current) => {
      const next = new Set(Array.from(current).filter((symbol) => validSymbols.has(symbol)));
      return next.size === current.size ? current : next;
    });
  }, [visibleCandidates]);

  function toggleCandidateSelection(symbol: string, checked: boolean) {
    setSelectedCandidateSymbols((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(symbol);
      } else {
        next.delete(symbol);
      }
      return next;
    });
  }

  function clearBatchSelection() {
    setSelectedCandidateSymbols(new Set());
  }

  function selectAllCandidates() {
    setSelectedCandidateSymbols(new Set(visibleCandidates.map((item) => item.symbol)));
  }

  function addSelectedCandidates() {
    onAddManyToWatchlist(selectedCandidateItems, batchGroup, splitTags(batchTagsText));
    clearBatchSelection();
  }

  const columns = useMemo<ColumnsType<StrongStockScreeningItem>>(
    () => [
      {
        title: "股票 STOCK",
        dataIndex: "name",
        width: 260,
        render: (_, item) => (
          <div className="min-w-0">
            <Link
              className="block font-black text-[#11100e] transition hover:text-[#f04438]"
              href={`/stock/${item.symbol}`}
              onClick={(event) => event.stopPropagation()}
            >
              {item.name}
            </Link>
            <p className="mt-1 text-xs font-medium text-[#7b756d]">{item.symbol}</p>
          </div>
        ),
      },
      {
        title: "决策 SCORE",
        width: 150,
        render: (_, item) => {
          const view = statusCopy[item.status];
          return (
            <Space orientation="vertical" size={6}>
              <span className={`inline-flex h-7 items-center whitespace-nowrap rounded-full px-2.5 text-xs font-bold ring-1 ${view.tone}`}>
                {view.label}
              </span>
              <Typography.Text className="text-xs font-black tabular-nums text-[#11100e]">
                得分 {item.score}
              </Typography.Text>
              {item.gsgf && <div className="flex max-w-[180px] flex-wrap gap-1"><GsgfSummaryPills gsgf={item.gsgf} /></div>}
            </Space>
          );
        },
      },
      {
        title: "板块 SECTOR",
        width: 170,
        render: (_, item) => (
          <div className="flex flex-wrap items-center gap-1.5">
            <IndustryBadge industry={item.industry} />
            <IndustryStrengthBadge item={item} />
          </div>
        ),
      },
      {
        title: "风险 RISK",
        width: 220,
        render: (_, item) => {
          const riskSummary = primaryRiskSummary(item);
          return <p className={`line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>{riskSummary.text}</p>;
        },
      },
      {
        title: "操作 ACTION",
        align: "right",
        fixed: "right",
        width: 180,
        render: (_, item) => {
          const alreadyAdded = watchlistSymbols.has(item.symbol);
          return (
            <Space size={8}>
              <Button
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect(item.symbol);
                }}
                size="small"
              >
                高亮
              </Button>
              <Button
                href={`/stock/${item.symbol}`}
                onClick={(event) => event.stopPropagation()}
                size="small"
              >
                K线
              </Button>
              <Button
                disabled={alreadyAdded}
                onClick={(event) => {
                  event.stopPropagation();
                  onAddToWatchlist(item, "自选", []);
                }}
                size="small"
                type={alreadyAdded ? "default" : "primary"}
              >
                {alreadyAdded ? "已在自选" : "加入自选"}
              </Button>
            </Space>
          );
        },
      },
    ],
    [onAddToWatchlist, onSelect, watchlistSymbols],
  );

  return (
    <Card className="mt-4 min-w-0 overflow-hidden rounded-xl border-[#ddd8d0] bg-[#f8f7f4]" styles={{ body: { padding: 0 } }}>
      <div className="flex flex-col gap-3 border-b border-[#ddd8d0] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-black text-[#11100e]">选股结果 · Screener Results</h2>
            <span className="rounded-md border border-[#ddd8d0] px-2 py-0.5 text-xs font-bold text-[#7b756d]">{items.length}</span>
          </div>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
            {generatedAt ? new Date(generatedAt).toLocaleString("zh-CN") : "暂无运行结果"}
          </p>
        </div>
        <span className="rounded-lg border border-[#ddd8d0] bg-[#f5f3f0] px-3 py-1.5 text-xs font-bold text-[#7b756d]">
          点击股票名称查看 K 线详情
        </span>
      </div>
      {watchlistMessage && (
        <Alert aria-live="polite" className="rounded-none border-x-0 border-t-0" showIcon title={watchlistMessage} type="success" />
      )}
      {items.length > 0 && (
        <>
          <CandidateFilterBar
            candidateStatusFilter={candidateStatusFilter}
            excludeGsgfGlobalRisk={excludeGsgfGlobalRisk}
            gsgfSignalFilter={gsgfSignalFilter}
            onExcludeGsgfGlobalRiskChange={setExcludeGsgfGlobalRisk}
            onGsgfSignalFilterChange={setGsgfSignalFilter}
            onStatusFilterChange={setCandidateStatusFilter}
            onStrongIndustryOnlyChange={setStrongIndustryOnly}
            statusCounts={statusCounts}
            strongIndustryCount={strongIndustryCount}
            strongIndustryOnly={strongIndustryOnly}
            visibleCount={visibleCandidates.length}
          />
          {visibleCandidates.length > 0 && (
            <BatchActionBar
              batchGroup={batchGroup}
              batchTagsText={batchTagsText}
              onAddSelected={addSelectedCandidates}
              onBatchGroupChange={setBatchGroup}
              onBatchTagsTextChange={setBatchTagsText}
              onClearSelection={clearBatchSelection}
              onSelectAll={selectAllCandidates}
              selectedCount={selectedCandidateItems.length}
              totalCount={visibleCandidates.length}
            />
          )}
        </>
      )}
      <div className="hidden overflow-x-auto lg:block">
        <Table
          columns={columns}
          dataSource={visibleCandidates}
          loading={running}
          locale={{
            emptyText: items.length > 0 ? <FilteredTableState /> : <EmptyTableState running={running} />,
          }}
          pagination={false}
          rowClassName={(item) => (item.symbol === selectedSymbol ? "workbench-table-row-selected" : "")}
          rowKey="symbol"
          rowSelection={{
            selectedRowKeys: Array.from(selectedCandidateSymbols),
            onChange: (keys) => setSelectedCandidateSymbols(new Set(keys.map(String))),
          }}
          onRow={(item) => ({
            onClick: () => onSelect(item.symbol),
          })}
          scroll={{ x: 900 }}
          size="small"
        />
      </div>
      <div className="border-t border-slate-100 p-3 lg:hidden">
        {items.length > 0 ? (
          visibleCandidates.length > 0 ? (
            <CandidateCardList
              isBatchSelected={(symbol) => selectedCandidateSymbols.has(symbol)}
              items={visibleCandidates}
              isInWatchlist={(symbol) => watchlistSymbols.has(symbol)}
              onAddToWatchlist={onAddToWatchlist}
              onSelect={onSelect}
              onToggleBatchSelect={toggleCandidateSelection}
              selectedSymbol={selectedSymbol}
            />
          ) : (
            <FilteredTableState />
          )
        ) : (
          <EmptyTableState running={running} />
        )}
      </div>
    </Card>
  );
}

function CandidateCardList({
  isInWatchlist,
  isBatchSelected,
  items,
  onAddToWatchlist,
  onSelect,
  onToggleBatchSelect,
  selectedSymbol,
}: {
  isInWatchlist: (symbol: string) => boolean;
  isBatchSelected: (symbol: string) => boolean;
  items: StrongStockScreeningItem[];
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onSelect: (symbol: string) => void;
  onToggleBatchSelect: (symbol: string, checked: boolean) => void;
  selectedSymbol: string | null;
}) {
  return (
    <div className="space-y-3">
      {items.map((item) => {
        const view = statusCopy[item.status];
        const riskSummary = primaryRiskSummary(item);
        const alreadyAdded = isInWatchlist(item.symbol);
        return (
          <article
            aria-selected={item.symbol === selectedSymbol}
            className={`rounded-lg border p-3 transition ${
              item.symbol === selectedSymbol ? "border-slate-950 bg-slate-50" : "border-slate-200 bg-white"
            }`}
            key={item.symbol}
          >
            <div className="flex items-start gap-3">
              <input
                aria-label={`选择 ${item.name}`}
                checked={isBatchSelected(item.symbol)}
                className="mt-1 size-4 rounded border-slate-300"
                onChange={(event) => onToggleBatchSelect(item.symbol, event.target.checked)}
                type="checkbox"
              />
              <button className="min-w-0 flex-1 text-left" onClick={() => onSelect(item.symbol)} type="button">
                <span className="block truncate text-sm font-black text-slate-950">{item.name}</span>
                <span className="mt-1 block text-xs font-semibold text-slate-400">{item.symbol}</span>
              </button>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${view.tone}`}>
                {view.label}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-2 text-[11px] font-bold text-slate-700">
                得分 {item.score}
              </span>
              <GsgfSummaryPills gsgf={item.gsgf} />
              <IndustryBadge industry={item.industry} />
              <IndustryStrengthBadge item={item} />
            </div>
            <p className={`mt-3 line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>{riskSummary.text}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <a
                className="inline-flex min-h-[36px] items-center justify-center rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200"
                href={`/stock/${item.symbol}`}
              >
                K线
              </a>
              <button
                className="min-h-[36px] rounded-md bg-slate-950 px-3 text-xs font-bold text-white disabled:cursor-not-allowed disabled:bg-[var(--market-green-bg)] disabled:text-[var(--market-green-text)]"
                disabled={alreadyAdded}
                onClick={() => onAddToWatchlist(item, "自选", [])}
                type="button"
              >
                {alreadyAdded ? "已在自选" : "加入自选"}
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function CandidateFilterBar({
  candidateStatusFilter,
  excludeGsgfGlobalRisk,
  gsgfSignalFilter,
  onExcludeGsgfGlobalRiskChange,
  onGsgfSignalFilterChange,
  onStatusFilterChange,
  onStrongIndustryOnlyChange,
  statusCounts,
  strongIndustryCount,
  strongIndustryOnly,
  visibleCount,
}: {
  candidateStatusFilter: CandidateStatusFilter;
  excludeGsgfGlobalRisk: boolean;
  gsgfSignalFilter: GsgfSignalFilter;
  onExcludeGsgfGlobalRiskChange: (value: boolean) => void;
  onGsgfSignalFilterChange: (value: GsgfSignalFilter) => void;
  onStatusFilterChange: (value: CandidateStatusFilter) => void;
  onStrongIndustryOnlyChange: (value: boolean) => void;
  statusCounts: Record<CandidateStatusFilter, number>;
  strongIndustryCount: number;
  strongIndustryOnly: boolean;
  visibleCount: number;
}) {
  return (
    <div className="border-b border-slate-100 bg-white px-5 py-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black text-slate-700">候选筛选</span>
          <Tag className="m-0" variant="filled">
            显示 {visibleCount}
          </Tag>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            onChange={(value) => onStatusFilterChange(value as CandidateStatusFilter)}
            options={candidateStatusFilters.map((filter) => ({
              label: `${filter.label} ${statusCounts[filter.value]}`,
              value: filter.value,
            }))}
            size="small"
            value={candidateStatusFilter}
          />
          <Button
            aria-pressed={strongIndustryOnly}
            onClick={() => onStrongIndustryOnlyChange(!strongIndustryOnly)}
            size="small"
            type={strongIndustryOnly ? "primary" : "default"}
          >
            强板块 {strongIndustryCount}
          </Button>
        </div>
      </div>
      <div className="mt-3 flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
        <Segmented
          onChange={(value) => onGsgfSignalFilterChange(value as GsgfSignalFilter)}
          options={gsgfSignalFilterOptions}
          size="small"
          value={gsgfSignalFilter}
        />
        <Checkbox
          checked={excludeGsgfGlobalRisk}
          onChange={(event) => onExcludeGsgfGlobalRiskChange(event.target.checked)}
        >
          排除全局阴量压制
        </Checkbox>
      </div>
    </div>
  );
}

function BatchActionBar({
  batchGroup,
  batchTagsText,
  onAddSelected,
  onBatchGroupChange,
  onBatchTagsTextChange,
  onClearSelection,
  onSelectAll,
  selectedCount,
  totalCount,
}: {
  batchGroup: string;
  batchTagsText: string;
  onAddSelected: () => void;
  onBatchGroupChange: (value: string) => void;
  onBatchTagsTextChange: (value: string) => void;
  onClearSelection: () => void;
  onSelectAll: () => void;
  selectedCount: number;
  totalCount: number;
}) {
  return (
    <div className="grid gap-2 border-b border-slate-100 bg-slate-50 px-5 py-3 lg:grid-cols-[auto_minmax(90px,120px)_minmax(120px,1fr)_auto] lg:items-center">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-600">
        <Tag className="m-0">已选 {selectedCount}</Tag>
        <Button onClick={onSelectAll} size="small" type="link">
          全选 {totalCount}
        </Button>
        <Button
          disabled={selectedCount === 0}
          onClick={onClearSelection}
          size="small"
          type="link"
        >
          清空选择
        </Button>
      </div>
      <Input
        onChange={(event) => onBatchGroupChange(event.target.value)}
        placeholder="批量分组"
        size="small"
        value={batchGroup}
      />
      <Input
        onChange={(event) => onBatchTagsTextChange(event.target.value)}
        placeholder="批量标签，逗号分隔"
        size="small"
        value={batchTagsText}
      />
      <Button
        disabled={selectedCount === 0}
        onClick={onAddSelected}
        size="small"
        type="primary"
      >
        批量加入自选
      </Button>
    </div>
  );
}

function EmptyTableState({ running }: { running: boolean }) {
  return (
    <div className="px-5 py-12 text-center">
      <Empty
        description={
          <span className="text-sm text-slate-500">
            {running ? "正在读取候选和板块强度。" : "运行筛选后显示候选。"}
          </span>
        }
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      >
        <p className="text-sm font-bold text-slate-700">{running ? "筛选中..." : "未运行筛选"}</p>
      </Empty>
    </div>
  );
}

function FilteredTableState() {
  return (
    <div className="px-5 py-12 text-center">
      <Empty
        description={<span className="text-sm text-slate-500">切换候选筛选后显示匹配股票。</span>}
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      >
        <p className="text-sm font-bold text-slate-700">当前筛选暂无候选</p>
      </Empty>
    </div>
  );
}

function GsgfSummaryPills({ gsgf }: { gsgf: GsgfAnalysis | null }) {
  if (!gsgf) {
    return null;
  }
  const riskTone =
    gsgf.action === "avoid" || gsgf.zone === "c_zone"
      ? "bg-red-50 text-red-700 ring-red-100"
      : "bg-violet-50 text-violet-700 ring-violet-100";
  const statusTone = gsgfFinalStatusTone(gsgf.final_status);
  return (
    <>
      <span className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${riskTone}`}>
        股是股非 {gsgf.total_score}
      </span>
      <span className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${statusTone}`}>
        {gsgf.final_status}
      </span>
      <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-2 text-[11px] font-bold text-slate-700 ring-1 ring-slate-200">
        {gsgfLabel(gsgf.zone)}
      </span>
      <span className="inline-flex h-6 items-center rounded-full bg-white px-2 text-[11px] font-bold text-slate-600 ring-1 ring-slate-200">
        {gsgfLabel(gsgf.action)}
      </span>
      {gsgf.setup_type && (
        <span className="inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 market-green-badge market-green-ring">
          setup {gsgfLabel(gsgf.setup_type)}
        </span>
      )}
      {gsgf.confirm_type && (
        <span className="inline-flex h-6 items-center rounded-full bg-sky-50 px-2 text-[11px] font-bold text-sky-700 ring-1 ring-sky-100">
          确认信号 {gsgfLabel(gsgf.confirm_type)}
        </span>
      )}
    </>
  );
}

function IndustryStrengthBadge({ item }: { item: StrongStockScreeningItem }) {
  if (!item.industry_strength) {
    return null;
  }
  const view = industryStrengthCopy[item.industry_strength];
  const scoreText = item.industry_score > 0 ? ` +${item.industry_score}` : "";
  return (
    <span className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-bold ring-1 ${view.tone}`}>
      板块强度 {view.label}
      {scoreText}
    </span>
  );
}

function IndustryBadge({ industry }: { industry: string | null }) {
  if (!industry) {
    return null;
  }
  return (
    <span className="inline-flex h-6 items-center rounded-full bg-indigo-50 px-2 text-[11px] font-bold text-indigo-700 ring-1 ring-indigo-100">
      行业 {industry}
    </span>
  );
}
