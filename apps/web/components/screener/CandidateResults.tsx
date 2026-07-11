"use client";

import type { ColumnsType } from "antd/es/table";
import { Alert, Button, Card, Checkbox, Empty, Input, Segmented, Space, Table, Tag } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type {
  GsgfAnalysis,
  StrongStockScreeningItem,
  WatchlistPoolItem,
} from "../../lib/types";
import { buildStockDetailHref } from "../../lib/stockNavigation";
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
        title: "股票",
        dataIndex: "name",
        width: 200,
        render: (_, item) => (
          <div className="min-w-0">
            <Link
              className="block font-black text-[var(--app-ink)] transition hover:text-[var(--market-rise)]"
              href={buildStockDetailHref(item.symbol, { from: "screener" })}
              onClick={(event) => event.stopPropagation()}
            >
              {item.name}
            </Link>
            <p className="mt-1 text-xs font-medium text-[var(--app-muted)]">{item.symbol}</p>
          </div>
        ),
      },
      {
        title: "决策",
        width: 300,
        render: (_, item) => {
          const view = statusCopy[item.status];
          return (
            <div className="candidate-decision">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex min-h-6 items-center rounded-md px-2 text-xs font-semibold ring-1 ${view.tone}`}>
                  {view.label}
                </span>
                <span className="text-xs font-semibold tabular-nums text-[var(--app-ink)]">得分 {item.score}</span>
              </div>
              <GsgfSummaryText gsgf={item.gsgf} />
            </div>
          );
        },
      },
      {
        title: "板块",
        width: 170,
        render: (_, item) => <IndustrySummary item={item} />,
      },
      {
        title: "风险",
        width: 220,
        render: (_, item) => {
          const riskSummary = primaryRiskSummary(item);
          return <p className={`line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>{riskSummary.text}</p>;
        },
      },
      {
        title: "操作",
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
                href={buildStockDetailHref(item.symbol, { from: "screener" })}
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
    <Card className="mt-4 min-w-0 overflow-hidden rounded-md border-[var(--app-border)] bg-[var(--app-raised)]" styles={{ body: { padding: 0 } }}>
      <div className="flex flex-col gap-3 border-b border-[var(--app-border)] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-black text-[var(--app-ink)]">选股结果</h2>
            <span className="rounded-md border border-[var(--app-border)] px-2 py-0.5 text-xs font-bold text-[var(--app-muted)]">{items.length}</span>
          </div>
          <p className="mt-1 text-xs font-medium text-[var(--app-muted)]">
            {generatedAt ? new Date(generatedAt).toLocaleString("zh-CN") : "暂无运行结果"}
          </p>
        </div>
        <span className="text-xs font-medium text-[var(--app-muted)]">
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
              <span className={`shrink-0 rounded-md px-2 py-1 text-xs font-semibold ring-1 ${view.tone}`}>
                {view.label}
              </span>
            </div>
            <div className="candidate-decision mt-3">
              <span className="text-xs font-semibold tabular-nums text-[var(--app-ink)]">得分 {item.score}</span>
              <GsgfSummaryText gsgf={item.gsgf} />
            </div>
            <div className="mt-3"><IndustrySummary item={item} /></div>
            <p className={`mt-3 line-clamp-2 text-xs leading-5 ${riskSummary.tone}`}>{riskSummary.text}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <a
                className="inline-flex min-h-[36px] items-center justify-center rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200"
                href={buildStockDetailHref(item.symbol, { from: "screener" })}
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
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <div className="candidate-filter-scroll flex-1">
            <Segmented
              onChange={(value) => onStatusFilterChange(value as CandidateStatusFilter)}
              options={candidateStatusFilters.map((filter) => ({
                label: `${filter.label} ${statusCounts[filter.value]}`,
                value: filter.value,
              }))}
              size="small"
              value={candidateStatusFilter}
            />
          </div>
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
        <div className="candidate-filter-scroll">
          <Segmented
            onChange={(value) => onGsgfSignalFilterChange(value as GsgfSignalFilter)}
            options={gsgfSignalFilterOptions}
            size="small"
            value={gsgfSignalFilter}
          />
        </div>
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

function GsgfSummaryText({ gsgf }: { gsgf: GsgfAnalysis | null }) {
  if (!gsgf) {
    return null;
  }
  const diagnostics = Object.entries(gsgf.diagnostics)
    .filter(([, item]) => item.flags.length > 0 || item.score !== null)
    .map(([name]) => gsgfLabel(name))
    .slice(0, 2);
  const detail = [
    gsgf.setup_type ? `形态 ${gsgfLabel(gsgf.setup_type)}` : null,
    gsgf.confirm_type ? `确认 ${gsgfLabel(gsgf.confirm_type)}` : null,
    gsgf.evidence_refs.length > 0 ? `证据链 ${gsgf.evidence_refs.length}` : null,
    diagnostics.length > 0 ? `诊断 ${diagnostics.join("/")}` : null,
  ]
    .filter((value): value is string => Boolean(value))
    .join(" · ");
  const tone = gsgf.action === "avoid" || gsgf.zone === "c_zone" ? "text-[var(--market-warning-text)]" : "text-[var(--app-muted)]";

  return (
    <div className={`candidate-decision-meta ${tone}`}>
      <div>股是股非 {gsgf.total_score} · {gsgf.final_status} · {gsgfLabel(gsgf.zone)} · {gsgfLabel(gsgf.action)}</div>
      {detail ? <div className="candidate-decision-meta__detail" title={detail}>{detail}</div> : null}
    </div>
  );
}

function IndustrySummary({ item }: { item: StrongStockScreeningItem }) {
  const strength = item.industry_strength ? industryStrengthCopy[item.industry_strength].label : null;
  const score = item.industry_score > 0 ? ` +${item.industry_score}` : item.industry_score < 0 ? ` ${item.industry_score}` : "";
  return (
    <div className="candidate-industry-summary">
      <div className="truncate text-sm font-semibold text-[var(--app-ink)]" title={item.industry ?? "未标注"}>{item.industry ?? "未标注"}</div>
      <div className="mt-1 text-xs text-[var(--app-muted)]">{strength ? `板块强度 ${strength}${score}` : "板块强度待数据"}</div>
    </div>
  );
}
