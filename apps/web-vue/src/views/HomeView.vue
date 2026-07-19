<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue';
import dayjs from 'dayjs';
import type { EChartsOption } from 'echarts';
import type { SectorRadarItem } from '@/service/types';
import { useHomeDashboard } from '@/composables/useHomeDashboard';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';
import type { WorkbenchMetric } from '@/components/common/workbench/workbench';
import {
  directionTone,
  formatDirectionalCny,
  formatDirectionalPercent,
  formatPlainCny,
  stageLabel
} from '@/utils/domain/capitalSignals';

defineOptions({ name: 'HomeView' });

const SectorRadarChart = defineAsyncComponent(() => import('@/components/charts/SectorRadarChart.vue'));

const { overview, sectorFlow, capital, busy, loadInitial, refreshAll } = useHomeDashboard();

const overviewData = computed(() => overview.data.value);
const overviewError = computed(() => overview.error.value);
const overviewIsStale = computed(() => overview.isStale.value);
const overviewLoading = computed(() => overview.loading.value);
const sectorFlowData = computed(() => sectorFlow.data.value);
const sectorFlowError = computed(() => sectorFlow.error.value);
const sectorFlowIsStale = computed(() => sectorFlow.isStale.value);
const sectorFlowLoading = computed(() => sectorFlow.loading.value);
const capitalData = computed(() => capital.data.value);
const capitalError = computed(() => capital.error.value);
const capitalIsStale = computed(() => capital.isStale.value);
const capitalLoading = computed(() => capital.loading.value);

const chartsReady = ref(false);
let chartFrame: number | null = null;
const staleDataTitle = '刷新失败，当前显示上次数据';

const breadth = computed(() => overviewData.value?.advance_decline);
const turnover = computed(() => overviewData.value?.turnover);
const indices = computed(() => overviewData.value?.indices.slice(0, 4) ?? []);

const displayTradeDate = computed(() =>
  [overviewData.value?.trade_date, sectorFlowData.value?.trade_date, capitalData.value?.trade_date]
    .find(value => Boolean(value)) || '交易日待确认'
);

const latestUpdate = computed(() => {
  const latest = [
    overviewData.value?.generated_at,
    sectorFlowData.value?.generated_at,
    capitalData.value?.generated_at
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

const sectorFlowRows = computed(() => {
  const withFlow = (item: SectorRadarItem): item is SectorRadarItem & { net_flow_cny: number } =>
    typeof item.net_flow_cny === 'number' && Number.isFinite(item.net_flow_cny);
  const inflow = (sectorFlowData.value?.inflow ?? []).filter(withFlow).slice(0, 6);
  const outflow = (sectorFlowData.value?.outflow ?? []).filter(withFlow).slice(0, 6);
  return [...inflow, ...outflow].sort((left, right) => left.net_flow_cny - right.net_flow_cny);
});

const sectorFlowOption = computed<EChartsOption>(() => {
  const rows = sectorFlowRows.value;
  if (!rows.length) return emptyChartOption('暂无板块资金流');

  return {
    aria: {
      enabled: true,
      description: '板块资金流图，红色表示净流入，绿色表示净流出。'
    },
    animationDuration: 160,
    grid: { left: 8, right: 18, top: 12, bottom: 22, containLabel: true },
    tooltip: {
      trigger: 'axis',
      confine: true,
      axisPointer: { type: 'shadow' },
      valueFormatter: value => formatDirectionalCny(typeof value === 'number' ? value : null)
    },
    xAxis: {
      type: 'value',
      splitNumber: 4,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#697991', fontSize: 11, formatter: formatMoney, hideOverlap: true },
      splitLine: { lineStyle: { color: '#d9e2ed' } }
    },
    yAxis: {
      type: 'category',
      data: rows.map(item => item.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#182336', fontSize: 11, width: 84, overflow: 'truncate' }
    },
    series: [
      {
        name: '净流入 / 净流出',
        type: 'bar',
        barMaxWidth: 16,
        data: rows.map(item => ({
          value: item.net_flow_cny,
          itemStyle: { color: item.net_flow_cny >= 0 ? '#d9363e' : '#07845e' }
        }))
      }
    ]
  } as EChartsOption;
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
  return toneClass(directionTone(value ?? null));
}

function toneClass(tone: 'fall' | 'neutral' | 'rise'): string {
  if (tone === 'rise') return 'home-positive';
  if (tone === 'fall') return 'home-negative';
  return '';
}

const etfActivityStatus = computed<'success' | 'partial'>(() => {
  const data = capitalData.value;
  if (!data) return 'partial';

  const activity = data.etf_radar.activity;
  const coverageComplete = activity.available_core_count === activity.core_count;
  const sourceDegraded = data.source_status.some(source => source.status === 'stale' || source.status === 'failed');
  return coverageComplete && !capitalIsStale.value && !sourceDegraded ? 'success' : 'partial';
});

function resourceError(error: Error | undefined, fallback: string): string | null {
  return error ? fallback : null;
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
    <PageHeader title="市场总览" description="全 A 盘面、资金流与资本信号">
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

    <div class="home-main-grid">
      <section class="home-panel home-flow-panel">
        <SectionHeader title="板块资金流" :updated-at="formatGeneratedAt(sectorFlowData?.generated_at)">
          <div class="home-section-actions">
            <span
              v-if="sectorFlowIsStale"
              class="home-stale-indicator"
              :aria-label="staleDataTitle"
              :title="staleDataTitle"
            >
              旧数据
            </span>
            <RouterLink class="home-detail-link" to="/market?view=sectors">查看板块</RouterLink>
          </div>
        </SectionHeader>
        <div class="home-chart">
          <template v-if="chartsReady">
            <div
              v-if="sectorFlowError && !sectorFlowData"
              class="home-chart-state home-chart-state--error"
              role="alert"
            >
              板块资金流读取失败
            </div>
            <SectorRadarChart
              v-else
              :height="360"
              :loading="sectorFlowLoading && !sectorFlowData"
              :option="sectorFlowOption"
            />
          </template>
          <div v-else class="home-chart-state">图表准备中</div>
        </div>
      </section>

      <div class="home-capital-stack">
        <template v-if="capitalData">
          <section class="home-panel home-capital-panel">
            <SectionHeader title="两融余额" :updated-at="formatGeneratedAt(capitalData.generated_at)">
              <div class="home-section-actions">
                <span
                  v-if="capitalIsStale"
                  class="home-stale-indicator"
                  :aria-label="staleDataTitle"
                  :title="staleDataTitle"
                >
                  旧数据
                </span>
                <StatusTag
                  :status="capitalData.margin.available_markets === capitalData.margin.expected_markets ? 'success' : 'partial'"
                  :text="capitalData.margin.available_markets === capitalData.margin.expected_markets ? '完整' : '部分'"
                />
              </div>
            </SectionHeader>
            <p class="home-capital-context">
              {{ capitalData.trade_date }} · 沪深 {{ capitalData.margin.available_markets }}/{{ capitalData.margin.expected_markets }}
            </p>
            <div class="home-capital-primary">
              <span>融资融券余额</span>
              <strong>{{ formatPlainCny(capitalData.margin.balance_cny) }}</strong>
            </div>
            <div class="home-capital-change">
              <span>较上一交易日</span>
              <strong :class="toneClass(directionTone(capitalData.margin.change_cny))">
                {{ formatDirectionalCny(capitalData.margin.change_cny) }}
              </strong>
              <small :class="toneClass(directionTone(capitalData.margin.change_pct))">
                {{ formatDirectionalPercent(capitalData.margin.change_pct) }}
              </small>
            </div>
            <div class="home-capital-metrics">
              <div><span>融资余额</span><strong>{{ formatPlainCny(capitalData.margin.financing_balance_cny) }}</strong></div>
              <div><span>当日融资买入</span><strong>{{ formatPlainCny(capitalData.margin.financing_buy_cny) }}</strong></div>
            </div>
          </section>

          <section class="home-panel home-capital-panel">
            <SectionHeader title="汇金 ETF 活动">
              <div class="home-section-actions">
                <span
                  v-if="capitalIsStale"
                  class="home-stale-indicator"
                  :aria-label="staleDataTitle"
                  :title="staleDataTitle"
                >
                  旧数据
                </span>
                <StatusTag :status="etfActivityStatus" />
                <RouterLink class="home-detail-link" to="/etf-radar">查看详情</RouterLink>
              </div>
            </SectionHeader>
            <p class="home-capital-context home-etf-context">
              数据日 {{ capitalData.trade_date }} · {{ stageLabel(capitalData.signal_stage) }} · {{ capitalData.model_version }}
            </p>
            <div class="home-etf-count-strip">
              <div>
                <strong class="home-positive" data-testid="tenfold-increase">
                  十倍量增加 {{ capitalData.etf_radar.activity.tenfold_increase_count }}
                </strong>
              </div>
              <div>
                <strong class="home-negative" data-testid="tenfold-decrease">
                  十倍量减少 {{ capitalData.etf_radar.activity.tenfold_decrease_count }}
                </strong>
              </div>
            </div>
            <div class="home-etf-facts">
              <div>
                <strong class="home-positive">确认增加 {{ capitalData.etf_radar.activity.confirmed_increase_group_count }}组</strong>
              </div>
              <div>
                <strong class="home-negative">确认减少 {{ capitalData.etf_radar.activity.confirmed_decrease_group_count }}组</strong>
              </div>
              <div>
                <strong data-testid="divergent-groups">方向分歧 {{ capitalData.etf_radar.activity.divergent_group_count }}组</strong>
              </div>
              <div>
                <strong>数据不全 {{ capitalData.etf_radar.activity.incomplete_group_count }}组</strong>
              </div>
            </div>
            <div class="home-etf-strongest" data-testid="strongest-core-etf">
              <span>最强核心 ETF 活动代理</span>
              <div>
                <strong>{{ capitalData.etf_radar.activity.strongest_symbol || '待确认' }}</strong>
                <small :class="toneClass(directionTone(capitalData.etf_radar.activity.strongest_baseline_change_pct))">
                  {{ capitalData.etf_radar.activity.strongest_symbol ? formatDirectionalPercent(capitalData.etf_radar.activity.strongest_baseline_change_pct) : '--' }}
                </small>
              </div>
              <small>覆盖 {{ capitalData.etf_radar.activity.available_core_count }}/{{ capitalData.etf_radar.activity.core_count }}</small>
            </div>
          </section>
        </template>

        <template v-else>
          <section class="home-panel home-capital-panel">
            <SectionHeader title="两融余额" />
            <div class="home-capital-state" :aria-busy="capitalLoading" :role="capitalError ? 'alert' : undefined">
              {{ capitalError ? '资金信号读取失败' : '资金信号加载中' }}
            </div>
          </section>
          <section class="home-panel home-capital-panel">
            <SectionHeader title="汇金 ETF 活动" />
            <div class="home-capital-state" :aria-busy="capitalLoading">
              {{ capitalError ? '等待服务恢复' : '等待 ETF 活动数据' }}
            </div>
          </section>
        </template>
      </div>
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

.home-header-meta,
.home-section-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 6px 12px;
}

.home-stale-indicator {
  color: var(--wb-warning);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.home-detail-link {
  color: var(--wb-primary);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}

.home-detail-link:hover {
  text-decoration: underline;
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

.home-index-cell,
.home-panel {
  min-width: 0;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.home-index-cell {
  padding: 10px 12px;
}

.home-index-name,
.home-index-empty,
.home-capital-context,
.home-capital-state {
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

.home-index-empty,
.home-capital-state {
  padding: 28px 0 16px;
  text-align: center;
}

.home-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.85fr);
  gap: 12px;
  min-width: 0;
}

.home-panel {
  padding: 12px;
}

.home-chart,
.home-chart-state {
  width: 100%;
  height: 360px;
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

.home-capital-stack {
  display: grid;
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.home-capital-panel {
  overflow: hidden;
}

.home-capital-context {
  margin: 2px 0 12px;
}

.home-capital-primary,
.home-capital-change,
.home-capital-metrics > div {
  display: grid;
  gap: 3px;
}

.home-capital-primary span,
.home-capital-change span,
.home-capital-metrics span {
  color: var(--wb-muted);
  font-size: 11px;
}

.home-capital-primary strong {
  color: var(--wb-ink);
  font-size: 20px;
  font-variant-numeric: tabular-nums;
}

.home-capital-change {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: baseline;
  margin-top: 10px;
  font-variant-numeric: tabular-nums;
}

.home-capital-change span {
  grid-column: 1 / -1;
}

.home-capital-change strong {
  font-size: 15px;
}

.home-capital-change small {
  color: var(--wb-muted);
  font-size: 11px;
}

.home-capital-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--wb-border);
}

.home-capital-metrics strong {
  color: var(--wb-ink);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.home-etf-context {
  margin-bottom: 8px;
}

.home-etf-count-strip,
.home-etf-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}

.home-etf-count-strip {
  padding: 8px 0;
  border-top: 1px solid var(--wb-border);
  border-bottom: 1px solid var(--wb-border);
}

.home-etf-count-strip > div,
.home-etf-facts > div,
.home-etf-strongest {
  display: grid;
  gap: 2px;
}

.home-etf-strongest > span,
.home-etf-strongest small {
  color: var(--wb-muted);
  font-size: 11px;
}

.home-etf-count-strip strong {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.home-etf-facts {
  margin-top: 9px;
}

.home-etf-facts strong {
  color: var(--wb-ink);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.home-etf-facts .home-positive,
.home-etf-strongest .home-positive {
  color: var(--wb-positive);
}

.home-etf-facts .home-negative,
.home-etf-strongest .home-negative {
  color: var(--wb-negative);
}

.home-etf-strongest {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: baseline;
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px solid var(--wb-border);
}

.home-etf-strongest > span {
  grid-column: 1 / -1;
}

.home-etf-strongest > div {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}

.home-etf-strongest strong {
  color: var(--wb-ink);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.home-etf-strongest small {
  font-variant-numeric: tabular-nums;
}

.home-positive {
  color: var(--wb-positive);
}

.home-negative {
  color: var(--wb-negative);
}

@media (max-width: 1023px) {
  .home-main-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .home-capital-stack {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: auto;
  }
}

@media (max-width: 639px) {
  .home-panel {
    padding: 10px;
  }

  .home-index-grid,
  .home-capital-stack {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .home-index-quote {
    align-items: flex-start;
    flex-direction: column;
  }

  .home-capital-stack {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
