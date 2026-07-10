"use client";

import {
  CameraOutlined,
  FullscreenOutlined,
  ReloadOutlined,
  UndoOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Select,
  Skeleton,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { getHeatmapTreemap } from "../../lib/api";
import {
  buildHeatmapQuery,
  formatHeatmapMoney,
  heatmapSourceStatusLabel,
  HEATMAP_MARKET_OPTIONS,
  HEATMAP_PERIOD_OPTIONS,
  HEATMAP_SIZE_MODE_OPTIONS,
  HEATMAP_TREND_OPTIONS,
  type HeatmapQueryState,
} from "../../lib/heatmap";
import { buildStockDetailHref } from "../../lib/stockNavigation";
import type { HeatmapStockNode, HeatmapTreemapResponse, StrongStockSourceStatus } from "../../lib/types";
import { HeatmapCanvas } from "./HeatmapCanvas";
import {
  buildHeatmapBoardOptions,
  heatmapSourceSummaryLabel,
  heatmapSourceSummaryTone,
  resolveHeatmapDisplayStock,
} from "./heatmapWorkspaceHelpers";

const DEFAULT_QUERY: HeatmapQueryState = {
  market: "all",
  period: "day",
  sizeMode: "market_cap",
  trend: "all",
  board: "全部",
  limit: 520,
};

export function HeatmapWorkspace() {
  return <HeatmapWorkspaceContent />;
}

export function HeatmapWorkspaceContent() {
  const [query, setQuery] = useState<HeatmapQueryState>(DEFAULT_QUERY);
  const [data, setData] = useState<HeatmapTreemapResponse | null>(null);
  const [boardNodes, setBoardNodes] = useState<HeatmapTreemapResponse["nodes"]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoverStock, setHoverStock] = useState<HeatmapStockNode | null>(null);
  const [selectedStock, setSelectedStock] = useState<HeatmapStockNode | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const canvasPanelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await getHeatmapTreemap(buildHeatmapQuery(query));
        if (!cancelled) {
          setData(response);
          if (query.board === "全部") {
            setBoardNodes(response.nodes);
          }
          setHoverStock(null);
          setSelectedStock(null);
          setResetKey((value) => value + 1);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "读取市场热图失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [query]);

  useEffect(() => {
    if (query.board === "全部") {
      return;
    }

    let cancelled = false;

    async function loadBoardOptions() {
      try {
        const response = await getHeatmapTreemap(buildHeatmapQuery({ ...query, board: "全部" }));
        if (!cancelled) {
          setBoardNodes(response.nodes);
        }
      } catch {
        // Keep the previous full-board option set instead of collapsing to the current filtered board.
      }
    }

    void loadBoardOptions();
    return () => {
      cancelled = true;
    };
  }, [query.board, query.limit, query.market, query.period, query.sizeMode, query.trend]);

  const boardOptions = useMemo(() => buildHeatmapBoardOptions(boardNodes), [boardNodes]);
  const displayStock = resolveHeatmapDisplayStock(selectedStock, hoverStock);
  const statusTone = heatmapSourceSummaryTone(data?.source_status ?? []);

  function updateQuery(next: Partial<HeatmapQueryState>) {
    setQuery((current) => ({ ...current, ...next }));
  }

  function resetView() {
    setSelectedStock(null);
    setHoverStock(null);
    setResetKey((value) => value + 1);
  }

  async function downloadScreenshot() {
    const canvas = canvasPanelRef.current?.querySelector("canvas");
    if (!canvas) {
      message.warning("热图尚未渲染完成");
      return;
    }

    const link = document.createElement("a");
    link.download = `stockmaster-heatmap-${data?.summary.trade_date ?? "snapshot"}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  }

  async function openFullscreen() {
    const panel = canvasPanelRef.current;
    if (!panel || !panel.requestFullscreen) {
      message.warning("当前浏览器不支持全屏查看");
      return;
    }

    await panel.requestFullscreen().catch(() => {
      message.warning("无法进入全屏模式");
    });
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
        <Typography.Text className="workbench-muted text-xs">
          更新：{formatDateTime(data?.summary.updated_at ?? data?.generated_at)}
        </Typography.Text>
        <Tag color={statusTone}>{data ? heatmapSourceSummaryLabel(data.source_status) : "读取中"}</Tag>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => updateQuery({ ...query })} type="primary">
          刷新
        </Button>
      </div>

      {error ? (
        <Alert className="mb-4" title={error} showIcon type="warning" />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[264px_minmax(0,1fr)_300px]">
        <ControlRail
          boardOptions={boardOptions}
          disabled={loading}
          query={query}
          onChange={updateQuery}
        />

        <Card
          ref={canvasPanelRef}
          className="workbench-panel min-h-[560px] min-w-0 overflow-hidden xl:min-h-[calc(100vh-146px)]"
          styles={{ body: { height: "100%", minHeight: 560, padding: 0 } }}
        >
          <div className="flex h-full min-h-[560px] flex-col">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#34302a] bg-[#171512] px-3 py-2 text-[#c8bda9]">
              <Space size={8} wrap>
                <Tag color="default">{marketLabel(query.market)}</Tag>
                <Tag color="default">{periodLabel(query.period)}</Tag>
                <Tag color="default">{query.sizeMode === "market_cap" ? "流通市值" : "成交额"}</Tag>
                {query.board !== "全部" ? <Tag color="volcano">{query.board}</Tag> : null}
              </Space>
              <Space size={6} wrap>
                <Button icon={<UndoOutlined />} onClick={resetView} size="small">
                  重置
                </Button>
                <Button icon={<CameraOutlined />} onClick={() => void downloadScreenshot()} size="small">
                  截图
                </Button>
                <Button icon={<FullscreenOutlined />} onClick={() => void openFullscreen()} size="small">
                  全屏
                </Button>
              </Space>
            </div>
            <div className="min-h-0 flex-1 bg-[#171512]">
              {loading && !data ? (
                <div className="p-4">
                  <Skeleton active paragraph={{ rows: 12 }} />
                </div>
              ) : data && data.nodes.length > 0 ? (
                <HeatmapCanvas
                  nodes={data.nodes}
                  resetKey={resetKey}
                  selectedStock={selectedStock}
                  onHoverStock={setHoverStock}
                  onOpenStock={(stock) => {
                    window.location.href = buildStockDetailHref(stock.symbol, {
                      from: "heatmap",
                      industry: stock.industry,
                      name: stock.name,
                    });
                  }}
                  onSelectStock={setSelectedStock}
                />
              ) : (
                <div className="flex h-full min-h-[480px] items-center justify-center">
                  <Empty description="暂无可渲染热图数据">
                    <Button onClick={() => updateQuery({ ...query })}>重试</Button>
                  </Empty>
                </div>
              )}
            </div>
          </div>
        </Card>

        <DetailRail
          data={data}
          displayStock={displayStock}
          loading={loading}
          selectedStock={selectedStock}
        />
      </section>
    </>
  );
}

function ControlRail({
  boardOptions,
  disabled,
  query,
  onChange,
}: {
  boardOptions: Array<{ label: string; value: string }>;
  disabled: boolean;
  query: HeatmapQueryState;
  onChange: (next: Partial<HeatmapQueryState>) => void;
}) {
  return (
    <Card className="workbench-panel" size="small" title="筛选">
      <div className="space-y-4">
        <FilterSelect label="市场范围">
          <Select
            disabled={disabled}
            options={HEATMAP_MARKET_OPTIONS}
            value={query.market}
            onChange={(market) => onChange({ market })}
          />
        </FilterSelect>
        <FilterSelect label="行业">
          <Select
            disabled={disabled}
            optionFilterProp="label"
            options={boardOptions}
            showSearch
            value={query.board}
            onChange={(board) => onChange({ board })}
          />
        </FilterSelect>
        <FilterSelect label="涨跌方向">
          <Select
            disabled={disabled}
            options={HEATMAP_TREND_OPTIONS}
            value={query.trend}
            onChange={(trend) => onChange({ trend })}
          />
        </FilterSelect>
        <FilterSelect label="面积口径">
          <Select
            disabled={disabled}
            options={HEATMAP_SIZE_MODE_OPTIONS}
            value={query.sizeMode}
            onChange={(sizeMode) => onChange({ sizeMode })}
          />
        </FilterSelect>
        <FilterSelect label="收益周期">
          <Select
            disabled={disabled}
            options={HEATMAP_PERIOD_OPTIONS}
            value={query.period}
            onChange={(period) => onChange({ period })}
          />
        </FilterSelect>
        <div className="rounded-md border border-[#ddd8d0] bg-[#eee9df] p-3 text-xs leading-5 text-[#7b756d]">
          鼠标悬停查看个股，点击固定右侧详情。画布支持拖拽、滚轮缩放和键盘平移。
        </div>
      </div>
    </Card>
  );
}

function FilterSelect({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-bold text-[#7b756d]">{label}</span>
      <div>{children}</div>
    </label>
  );
}

function DetailRail({
  data,
  displayStock,
  loading,
  selectedStock,
}: {
  data: HeatmapTreemapResponse | null;
  displayStock: HeatmapStockNode | null;
  loading: boolean;
  selectedStock: HeatmapStockNode | null;
}) {
  const summary = data?.summary;

  return (
    <div className="space-y-4">
      <Card className="workbench-panel" loading={loading && !data} size="small" title={selectedStock ? "已选个股" : "个股详情"}>
        {displayStock ? (
          <div className="space-y-3">
            <div>
              <Typography.Title className="m-0 text-[#11100e]" level={4}>
                {displayStock.name}
              </Typography.Title>
              <Typography.Text className="workbench-muted">
                {displayStock.symbol} · {displayStock.industry}
              </Typography.Text>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <SmallStat label="现价" value={formatPrice(displayStock.price)} />
              <SmallStat label="涨跌幅" value={formatPct(displayStock.change_pct)} valueClass={pctClass(displayStock.change_pct)} />
              <SmallStat label="成交额" value={formatHeatmapMoney(displayStock.turnover_cny)} />
              <SmallStat label="流通市值" value={formatHeatmapMoney(displayStock.circulating_market_cap_cny)} />
            </div>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="细分行业">{displayStock.sub_industry ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="总市值">{formatHeatmapMoney(displayStock.total_market_cap_cny)}</Descriptions.Item>
              <Descriptions.Item label="行情时间">{formatDateTime(displayStock.quote_time)}</Descriptions.Item>
            </Descriptions>
            <Button
              block
              href={buildStockDetailHref(displayStock.symbol, {
                from: "heatmap",
                industry: displayStock.industry,
                name: displayStock.name,
              })}
              type="primary"
            >
              查看K线
            </Button>
          </div>
        ) : (
          <Empty description="悬停或点击热图中的股票" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      <Card className="workbench-panel" loading={loading && !data} size="small" title="市场概览">
        {summary ? (
          <div className="grid grid-cols-2 gap-2">
            <SmallStat label="股票数" value={String(summary.stock_count)} />
            <SmallStat label="行业数" value={String(summary.board_count)} />
            <SmallStat label="上涨" value={String(summary.advance_count)} valueClass="text-[#d92d20]" />
            <SmallStat label="下跌" value={String(summary.decline_count)} valueClass="market-green-text" />
            <SmallStat label="成交额" value={formatHeatmapMoney(summary.turnover_cny)} />
            <SmallStat label="成交变化" value={formatPct(summary.turnover_change_pct)} valueClass={pctClass(summary.turnover_change_pct)} />
          </div>
        ) : (
          <Empty description="暂无概览" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      <Card className="workbench-panel" size="small" title="图例">
        <div className="grid grid-cols-3 gap-2 text-xs">
          <LegendItem color="#dc2626" label="上涨" />
          <LegendItem color="#4b5563" label="平盘" />
          <LegendItem color="#059669" label="下跌" />
        </div>
      </Card>

      <Card className="workbench-panel" size="small" title="数据源">
        <div className="space-y-2">
          {(data?.source_status ?? []).map((item) => (
            <div key={`${item.source}-${item.status}`} className="rounded-md border border-[#ddd8d0] bg-[#f5f3f0] p-2">
              <div className="flex items-center justify-between gap-2">
                <Typography.Text className="text-xs font-bold text-[#11100e]">{item.source}</Typography.Text>
                <Tag color={sourceStatusColor(item.status)}>{heatmapSourceStatusLabel(item)}</Tag>
              </div>
              <Typography.Text className="workbench-muted text-xs">{item.detail}</Typography.Text>
            </div>
          ))}
          {data?.source_status.length === 0 ? (
            <Typography.Text className="workbench-muted text-xs">暂无数据源状态</Typography.Text>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

function SmallStat({
  label,
  value,
  valueClass = "text-[#11100e]",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-md border border-[#ddd8d0] bg-[#f5f3f0] px-3 py-2">
      <Typography.Text className="workbench-muted block text-xs">{label}</Typography.Text>
      <Typography.Text className={`block text-sm font-black tabular-nums ${valueClass}`}>{value}</Typography.Text>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[#ddd8d0] bg-[#f5f3f0] px-2 py-1">
      <span className="size-3 rounded-sm" style={{ background: color }} />
      <span className="font-semibold text-[#11100e]">{label}</span>
    </div>
  );
}

function sourceStatusColor(status: StrongStockSourceStatus["status"]): string {
  if (status === "success") {
    return "green";
  }
  if (status === "stale") {
    return "orange";
  }
  if (status === "failed") {
    return "red";
  }
  return "default";
}

function marketLabel(value: string): string {
  return HEATMAP_MARKET_OPTIONS.find((item) => item.value === value)?.label ?? value;
}

function periodLabel(value: string): string {
  return HEATMAP_PERIOD_OPTIONS.find((item) => item.value === value)?.label ?? value;
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function pctClass(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value) || Math.abs(value) <= 0.1) {
    return "text-[#11100e]";
  }
  return value > 0 ? "text-[#d92d20]" : "market-green-text";
}

function formatPrice(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
