<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue';
import dayjs from 'dayjs';
import type { EChartsOption } from 'echarts';
import type {
  MarketRankingItem,
  SectorRadarItem,
  SectorReplicaMode,
  SourceStatusValue,
  StrongStockSourceStatus
} from '@/service/types';
import { useHomeDashboard } from '@/composables/useHomeDashboard';
import { buildSectorReplicaChartOption } from '@/utils/charts/sectorReplicaChartOption';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';
import type { WorkbenchMetric } from '@/components/common/workbench/workbench';

defineOptions({ name: 'HomeView' });

const SectorRadarChart = defineAsyncComponent(() => import('@/components/charts/SectorRadarChart.vue'));

const { overview, rankings, sectorFlow, sectorTrend, sectorMode, busy, loadInitial, refreshAll, setSectorMode } =
  useHomeDashboard();

const overviewData = computed(() => overview.data.value);
const overviewError = computed(() => overview.error.value);
const overviewIsStale = computed(() => overview.isStale.value);
const overviewLoading = computed(() => overview.loading.value);
const rankingsData = computed(() => rankings.data.value);
const rankingsError = computed(() => rankings.error.value);
const rankingsIsStale = computed(() => rankings.isStale.value);
const rankingsLoading = computed(() => rankings.loading.value);
const sectorFlowData = computed(() => sectorFlow.data.value);
const sectorFlowError = computed(() => sectorFlow.error.value);
const sectorFlowIsStale = computed(() => sectorFlow.isStale.value);
const sectorFlowLoading = computed(() => sectorFlow.loading.value);
const sectorTrendData = computed(() => sectorTrend.data.value);
const sectorTrendError = computed(() => sectorTrend.error.value);
const sectorTrendIsStale = computed(() => sectorTrend.isStale.value);
const sectorTrendLoading = computed(() => sectorTrend.loading.value);

const chartsReady = ref(false);
let chartFrame: number | null = null;
const staleDataTitle = '刷新失败，当前显示上次数据';

const breadth = computed(() => overviewData.value?.advance_decline);
const turnover = computed(() => overviewData.value?.turnover);
const indices = computed(() => overviewData.value?.indices.slice(0, 4) ?? []);
const rankingItems = computed(() => rankingsData.value?.pct_change_rank.slice(0, 8) ?? []);
const sectorModeOptions = [
  { label: '强度', value: 'strength' },
  { label: '主力流', value: 'main_flow' }
];

const displayTradeDate = computed(() => {
  const values = [
    overviewData.value?.trade_date,
    sectorFlowData.value?.trade_date,
    sectorTrendData.value?.trade_date,
    rankingsData.value?.trade_date
  ];
  return values.find(value => Boolean(value)) || '交易日待确认';
});

const latestUpdate = computed(() => {
  const latest = [
    overviewData.value?.generated_at,
    rankingsData.value?.generated_at,
    sectorFlowData.value?.generated_at,
    sectorTrendData.value?.generated_at
  ]
    .map(value => ({ value, timestamp: value ? dayjs(value).valueOf() : Number.NaN }))
    .filter(item => item.value && Number.isFinite(item.timestamp))
    .sort((left, right) => right.timestamp - left.timestamp)[0];

  return latest?.value ? dayjs(latest.value).format('HH:mm:ss') : '等待更新';
});

const marketStatus = computed(() => {
  const advance = breadth.value?.advance_count;
  const decline = breadth.value?.decline_count;
  if (typeof advance !== 'number' || typeof decline !== 'number' || advance + decline <= 0) {
    return { value: '待确认', helper: '上涨占比 --' };
  }

  const ratio = advance / (advance + decline);
  const helper = `上涨占比 ${(ratio * 100).toFixed(1)}%`;
  if (ratio >= 0.6) return { value: '偏强', helper, tone: 'positive' as const };
  if (ratio <= 0.4) return { value: '偏弱', helper, tone: 'negative' as const };
  return { value: '均衡', helper };
});

const overviewMetrics = computed<WorkbenchMetric[]>(() => [
  {
    key: 'turnover',
    label: '总成交额',
    value: formatMoney(turnover.value?.total_cny),
    helper: `较昨日 ${formatPercent(turnover.value?.change_pct)}`
  },
  {
    key: 'breadth',
    label: '上涨 / 下跌',
    value: `${breadth.value?.advance_count ?? '--'} / ${breadth.value?.decline_count ?? '--'}`,
    helper: `平盘 ${breadth.value?.unchanged_count ?? '--'}`
  },
  {
    key: 'limit',
    label: '涨停 / 跌停',
    value: `${breadth.value?.limit_up_count ?? '--'} / ${breadth.value?.limit_down_count ?? '--'}`,
    helper: '全市场统计口径'
  },
  {
    key: 'market-status',
    label: '盘面状态',
    value: marketStatus.value.value,
    helper: marketStatus.value.helper,
    tone: marketStatus.value.tone
  }
]);

const sectorFlowOption = computed<EChartsOption>(() => {
  const rows = (sectorFlowData.value?.inflow ?? [])
    .filter((item): item is SectorRadarItem & { net_flow_cny: number } => item.net_flow_cny !== null)
    .slice(0, 8)
    .reverse();

  if (!rows.length) return emptyChartOption('暂无板块资金流');

  return {
    animationDuration: 160,
    grid: { left: 8, right: 18, top: 12, bottom: 22, containLabel: true },
    tooltip: {
      trigger: 'axis',
      confine: true,
      axisPointer: { type: 'shadow' },
      valueFormatter: formatMoney
    },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#697991', fontSize: 11, formatter: formatMoney },
      splitLine: { lineStyle: { color: '#d9e2ed' } }
    },
    yAxis: {
      type: 'category',
      data: rows.map(item => item.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#182336', fontSize: 11, width: 76, overflow: 'truncate' }
    },
    series: [
      {
        name: '净流入',
        type: 'bar',
        barMaxWidth: 16,
        data: rows.map(item => item.net_flow_cny),
        itemStyle: { color: '#d9363e' }
      }
    ]
  } as EChartsOption;
});

const sectorTrendOption = computed<EChartsOption>(() => {
  const data = sectorTrendData.value;
  if (!data?.series.length) return emptyChartOption('等待板块采样');

  return buildSectorReplicaChartOption({
    axis: data.axis,
    series: data.series,
    mode: data.mode,
    compact: true
  }) as EChartsOption;
});

const sourceItems = computed(() => {
  const merged = new Map<string, StrongStockSourceStatus>();
  const groups = [
    overviewData.value?.source_status,
    rankingsData.value?.source_status,
    sectorFlowData.value?.source_status,
    sectorTrendData.value?.source_status
  ];

  groups.forEach(group => {
    group?.forEach(item => {
      const current = merged.get(item.source);
      if (!current || sourceSeverity(item.status) > sourceSeverity(current.status)) {
        merged.set(item.source, item);
      }
    });
  });

  return Array.from(merged.values());
});

function emptyChartOption(text: string): EChartsOption {
  return {
    title: {
      text,
      left: 'center',
      top: 'middle',
      textStyle: { color: '#697991', fontSize: 13, fontWeight: 'normal' }
    }
  };
}

function sourceSeverity(status: SourceStatusValue): number {
  if (status === 'failed') return 4;
  if (status === 'stale') return 3;
  if (status === 'missing_key') return 2;
  if (status === 'disabled') return 1;
  return 0;
}

function sourceStatusTone(status: SourceStatusValue) {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'failed';
  if (status === 'stale') return 'partial';
  return 'unknown';
}

function sourceStatusNote(status: SourceStatusValue): string | undefined {
  if (status === 'stale') return '延迟';
  if (status === 'missing_key') return '缺少密钥';
  if (status === 'disabled') return '未启用';
  return undefined;
}

function formatMoney(value: unknown): string {
  return formatWorkbenchNumber(typeof value === 'number' ? value : null, 'money');
}

function formatPercent(value: number | null | undefined): string {
  return formatWorkbenchNumber(value, 'percent');
}

function formatPrice(value: number | null | undefined): string {
  return formatWorkbenchNumber(value, 'price');
}

function formatGeneratedAt(value: string | undefined): string | undefined {
  return value && dayjs(value).isValid() ? dayjs(value).format('HH:mm:ss') : undefined;
}

function changeTone(value: number | null | undefined): string {
  return value !== null && value !== undefined && value >= 0 ? 'home-positive' : 'home-negative';
}

function asRankingItem(value: unknown): MarketRankingItem {
  return value as MarketRankingItem;
}

function resourceError(error: Error | undefined, fallback: string): string | null {
  return error ? error.message || fallback : null;
}

function handleSectorModeChange(value: string | number): void {
  if (value === 'strength' || value === 'main_flow') {
    setSectorMode(value as SectorReplicaMode).catch(() => undefined);
  }
}

onMounted(() => {
  loadInitial().catch(() => undefined);
  chartFrame = requestAnimationFrame(() => {
    chartsReady.value = true;
    chartFrame = null;
  });
});

onBeforeUnmount(() => {
  if (chartFrame !== null) cancelAnimationFrame(chartFrame);
});
</script>

<template>
  <div class="home-dashboard">
    <PageHeader title="市场总览" description="全 A 盘面、资金流与板块轮动">
      <template #meta>
        <div class="home-header-meta">
          <span>交易日 {{ displayTradeDate }}</span>
          <span>更新 {{ latestUpdate }}</span>
          <span
            v-if="overviewIsStale"
            class="home-stale-indicator"
            :aria-label="staleDataTitle"
            :title="staleDataTitle"
          >
            旧数据
          </span>
        </div>
      </template>
      <AButton :loading="busy" type="primary" @click="refreshAll">刷新数据</AButton>
    </PageHeader>

    <AAlert
      v-if="overviewError && !overviewData"
      :title="resourceError(overviewError, '市场总览暂时不可用')"
      show-icon
      type="warning"
    />

    <section class="home-index-section">
      <SectionHeader title="主要指数" :updated-at="formatGeneratedAt(overviewData?.generated_at)" />
      <div v-if="indices.length" class="home-index-grid">
        <div v-for="index in indices" :key="index.symbol" class="home-index-cell">
          <div class="home-index-name">{{ index.name }}</div>
          <div class="home-index-quote">
            <strong>{{ formatPrice(index.last_price) }}</strong>
            <span :class="changeTone(index.change_pct)">{{ formatPercent(index.change_pct) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="home-index-empty" :aria-busy="overviewLoading">主要指数待确认</div>
    </section>

    <MetricStrip :items="overviewMetrics" />

    <div class="home-chart-grid">
      <section class="home-panel">
        <SectionHeader title="板块资金流" :updated-at="formatGeneratedAt(sectorFlowData?.generated_at)">
          <span
            v-if="sectorFlowIsStale"
            class="home-stale-indicator"
            :aria-label="staleDataTitle"
            :title="staleDataTitle"
          >
            旧数据
          </span>
        </SectionHeader>
        <div class="home-chart">
          <template v-if="chartsReady">
            <div
              v-if="sectorFlowError && !sectorFlowData"
              class="home-chart-state home-chart-state--error"
              role="alert"
            >
              {{ resourceError(sectorFlowError, '板块资金流读取失败') }}
            </div>
            <SectorRadarChart
              v-else
              :height="280"
              :loading="sectorFlowLoading && !sectorFlowData"
              :option="sectorFlowOption"
            />
          </template>
          <div v-else class="home-chart-state">图表准备中</div>
        </div>
      </section>

      <section class="home-panel">
        <SectionHeader title="板块实时曲线" :updated-at="formatGeneratedAt(sectorTrendData?.generated_at)">
          <div class="home-section-actions">
            <span
              v-if="sectorTrendIsStale"
              class="home-stale-indicator"
              :aria-label="staleDataTitle"
              :title="staleDataTitle"
            >
              旧数据
            </span>
            <ASegmented
              :options="sectorModeOptions"
              :value="sectorMode"
              size="small"
              @change="handleSectorModeChange"
            />
          </div>
        </SectionHeader>
        <div class="home-chart">
          <template v-if="chartsReady">
            <div
              v-if="sectorTrendError && !sectorTrendData"
              class="home-chart-state home-chart-state--error"
              role="alert"
            >
              {{ resourceError(sectorTrendError, '板块曲线读取失败') }}
            </div>
            <SectorRadarChart
              v-else
              :height="280"
              :loading="sectorTrendLoading && !sectorTrendData"
              :option="sectorTrendOption"
            />
          </template>
          <div v-else class="home-chart-state">图表准备中</div>
        </div>
      </section>
    </div>

    <div class="home-bottom-grid">
      <section class="home-panel">
        <SectionHeader title="市场关注榜" :updated-at="formatGeneratedAt(rankingsData?.generated_at)">
          <span
            v-if="rankingsIsStale"
            class="home-stale-indicator"
            :aria-label="staleDataTitle"
            :title="staleDataTitle"
          >
            旧数据
          </span>
        </SectionHeader>
        <DataList
          :error="rankingsData ? null : resourceError(rankingsError, '市场关注榜读取失败')"
          :items="rankingItems"
          :loading="rankingsLoading && !rankingsData"
          empty-description="暂无排行榜"
        >
          <template #list-item="{ item, index }">
            <div class="home-ranking-row">
              <span class="home-ranking-position">{{ Number(index) + 1 }}</span>
              <div class="home-ranking-name">
                <strong>{{ asRankingItem(item).name || asRankingItem(item).symbol }}</strong>
                <span>{{ asRankingItem(item).symbol }}</span>
              </div>
              <div class="home-ranking-quote">
                <span>{{ formatPrice(asRankingItem(item).last_price) }}</span>
                <strong :class="changeTone(asRankingItem(item).pct_change)">
                  {{ formatPercent(asRankingItem(item).pct_change) }}
                </strong>
              </div>
            </div>
          </template>
        </DataList>
      </section>

      <section class="home-panel">
        <SectionHeader title="数据状态" :updated-at="latestUpdate === '等待更新' ? undefined : latestUpdate">
          <span class="home-source-count">{{ sourceItems.length }} 个来源</span>
        </SectionHeader>
        <div v-if="sourceItems.length" class="home-source-list">
          <div v-for="item in sourceItems" :key="item.source" class="home-source-row">
            <strong class="home-source-name">{{ item.source }}</strong>
            <span class="home-source-detail" :title="item.detail">{{ item.detail }}</span>
            <span class="home-source-status">
              <StatusTag :status="sourceStatusTone(item.status)" />
              <span v-if="sourceStatusNote(item.status)" class="home-source-status-note">
                {{ sourceStatusNote(item.status) }}
              </span>
            </span>
          </div>
        </div>
        <div v-else class="home-source-empty">数据来源待确认</div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.home-dashboard {
  display: grid;
  gap: 12px;
}

.home-dashboard :deep(.wb-page-header),
.home-dashboard :deep(.wb-metric-strip) {
  margin: 0;
}

.home-header-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 12px;
}

.home-section-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.home-stale-indicator {
  color: var(--wb-warning);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.home-index-section {
  min-width: 0;
}

.home-index-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding-top: 10px;
}

.home-index-cell {
  min-width: 0;
  padding: 10px 12px;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.home-index-name,
.home-index-empty,
.home-source-count,
.home-source-empty {
  color: var(--wb-muted);
  font-size: 12px;
}

.home-index-quote {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}

.home-index-quote strong {
  overflow-wrap: anywhere;
  color: var(--wb-ink);
  font-size: 17px;
  line-height: 1.35;
}

.home-index-quote span {
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 600;
}

.home-index-empty {
  padding: 28px 0 16px;
  text-align: center;
}

.home-chart-grid,
.home-bottom-grid {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.home-chart-grid {
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 1fr);
}

.home-bottom-grid {
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
}

.home-panel {
  min-width: 0;
  padding: 12px;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.home-chart,
.home-chart-state {
  width: 100%;
  height: 280px;
}

.home-chart {
  overflow: hidden;
}

.home-chart-state {
  display: grid;
  place-items: center;
  padding: 16px;
  color: var(--wb-muted);
  font-size: 13px;
  text-align: center;
}

.home-chart-state--error {
  color: var(--wb-positive);
}

.home-ranking-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.home-ranking-position {
  color: var(--wb-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.home-ranking-name {
  min-width: 0;
}

.home-ranking-name strong,
.home-ranking-name span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-ranking-name strong {
  color: var(--wb-ink);
  font-size: 13px;
}

.home-ranking-name span {
  margin-top: 2px;
  color: var(--wb-muted);
  font-size: 11px;
}

.home-ranking-quote {
  display: grid;
  grid-template-columns: minmax(56px, auto) minmax(58px, auto);
  gap: 10px;
  color: var(--wb-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.home-source-list {
  display: grid;
}

.home-source-row {
  display: grid;
  grid-template-columns: minmax(76px, 0.45fr) minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 9px 0;
  border-bottom: 1px solid var(--wb-border);
}

.home-source-row:last-child {
  border-bottom: 0;
}

.home-source-name,
.home-source-detail {
  min-width: 0;
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-source-name {
  color: var(--wb-ink);
}

.home-source-detail {
  color: var(--wb-muted);
}

.home-source-status {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.home-source-status-note {
  color: var(--wb-muted);
  font-size: 11px;
  white-space: nowrap;
}

.home-source-empty {
  padding: 28px 0 16px;
  text-align: center;
}

.home-positive {
  color: var(--wb-positive);
}

.home-negative {
  color: var(--wb-negative);
}

@media (max-width: 1023px) {
  .home-chart-grid,
  .home-bottom-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 639px) {
  .home-panel {
    padding: 10px;
  }

  .home-index-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .home-index-quote {
    align-items: flex-start;
    flex-direction: column;
  }

  .home-ranking-quote {
    grid-template-columns: minmax(52px, auto);
    gap: 2px;
  }

  .home-source-row {
    grid-template-columns: minmax(68px, 0.45fr) minmax(0, 1fr) auto;
    gap: 6px;
  }
}
</style>
