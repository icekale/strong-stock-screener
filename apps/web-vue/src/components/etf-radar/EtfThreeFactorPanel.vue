<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue';
import type { EChartsOption } from 'echarts';
import type {
  EtfFactorEvidence,
  EtfThreeFactorHistoryResponse,
  EtfThreeFactorItem,
  EtfThreeFactorResponse
} from '@/service/types';
import { factorStatusLabel, signalLevelLabel } from '@/utils/domain/etfThreeFactor';

defineOptions({ name: 'EtfThreeFactorPanel' });

const EChart = defineAsyncComponent(() => import('@/components/charts/EChart.vue'));

const props = defineProps<{
  snapshot: EtfThreeFactorResponse;
  history: EtfThreeFactorHistoryResponse | null;
  selectedSymbol: string;
  historyLoading: boolean;
  historyError: string | null;
}>();

const panelElement = ref<HTMLElement | null>(null);
const chartColors = ref({
  primary: '#2563eb',
  warning: '#a16207',
  negative: '#b91c1c',
  positive: '#15803d',
  muted: '#64748b'
});
const selectedItem = computed(() =>
  props.snapshot.items.find(item => item.symbol === props.selectedSymbol) ?? props.snapshot.items[0] ?? null
);
const selectedHistory = computed(() =>
  props.history?.symbol === props.selectedSymbol ? props.history : null
);
const hasUsableHistory = computed(() => (selectedHistory.value?.points.length ?? 0) > 0);
const historyDates = computed(() => selectedHistory.value?.points.map(point => point.trade_date) ?? []);
const timelinePoints = computed(() => [...(selectedHistory.value?.points ?? [])].reverse());

function resolveChartColor(token: string, fallback: string) {
  if (typeof window === 'undefined') return fallback;
  const color = window.getComputedStyle(panelElement.value ?? document.documentElement).getPropertyValue(token).trim();
  return color && !color.includes('var(') ? color : fallback;
}

function resolveChartColors() {
  chartColors.value = {
    primary: resolveChartColor('--wb-primary', chartColors.value.primary),
    warning: resolveChartColor('--wb-warning', chartColors.value.warning),
    negative: resolveChartColor('--wb-negative', chartColors.value.negative),
    positive: resolveChartColor('--wb-positive', chartColors.value.positive),
    muted: resolveChartColor('--wb-muted', chartColors.value.muted)
  };
}

onMounted(resolveChartColors);

const volumeOption = computed<EChartsOption>(() => ({
  animation: false,
  aria: { enabled: true, description: `${selectedItem.value?.name ?? 'ETF'}成交量与20日均量` },
  color: [chartColors.value.primary, chartColors.value.warning],
  grid: { left: 54, right: 18, top: 32, bottom: 32 },
  legend: { data: ['成交量', '20日均量'], top: 2 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: historyDates.value },
  yAxis: { type: 'value', axisLabel: { formatter: compactNumber } },
  series: [
    { name: '成交量', type: 'bar', data: selectedHistory.value?.points.map(point => point.volume) ?? [] },
    { name: '20日均量', type: 'line', connectNulls: false, data: selectedHistory.value?.points.map(point => point.average_volume_20d) ?? [] }
  ]
}));

const shareOption = computed<EChartsOption>(() => ({
  animation: false,
  aria: { enabled: true, description: `${selectedItem.value?.name ?? 'ETF'}份额与日变化` },
  color: [chartColors.value.primary, chartColors.value.negative],
  grid: { left: 54, right: 54, top: 32, bottom: 32 },
  legend: { data: ['ETF份额', '份额日变化'], top: 2 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: historyDates.value },
  yAxis: [
    { type: 'value', axisLabel: { formatter: compactNumber } },
    { type: 'value', axisLabel: { formatter: (value: number) => `${value.toFixed(1)}%` } }
  ],
  series: [
    { name: 'ETF份额', type: 'line', connectNulls: false, data: selectedHistory.value?.points.map(point => point.total_shares) ?? [] },
    { name: '份额日变化', type: 'line', yAxisIndex: 1, connectNulls: false, data: selectedHistory.value?.points.map(point => point.share_change_pct) ?? [] }
  ]
}));

const comparisonOption = computed<EChartsOption>(() => {
  const points = selectedHistory.value?.points ?? [];
  const latestDate = points.at(-1)?.trade_date;
  return {
    animation: false,
    aria: { enabled: true, description: `${selectedItem.value?.name ?? 'ETF'}收盘涨跌与指数最新涨跌对照` },
    color: [chartColors.value.positive, chartColors.value.muted],
    grid: { left: 48, right: 18, top: 32, bottom: 32 },
    legend: { data: ['ETF收盘涨跌', '指数涨跌（最新）'], top: 2 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: historyDates.value },
    yAxis: { type: 'value', axisLabel: { formatter: (value: number) => `${value.toFixed(1)}%` } },
    series: [
      { name: 'ETF收盘涨跌', type: 'line', connectNulls: false, data: points.map(point => point.close_change_pct) },
      {
        name: '指数涨跌（最新）',
        type: 'line',
        connectNulls: false,
        data: points.map(point => point.trade_date === latestDate ? selectedItem.value?.index_change_pct ?? null : null)
      }
    ]
  };
});

function compactNumber(value: number) {
  if (Math.abs(value) >= 100_000_000) return `${(value / 100_000_000).toFixed(0)}亿`;
  if (Math.abs(value) >= 10_000) return `${(value / 10_000).toFixed(0)}万`;
  return String(value);
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatScore(value: number | null | undefined) {
  return value === null || value === undefined ? '--' : value.toFixed(0);
}

function formatFactorValue(factor: EtfFactorEvidence) {
  if (factor.status === 'pending') return '待盘后';
  if (factor.value === null || factor.value === undefined) return '--';
  return factor.value.toFixed(2);
}

function levelClass(level: EtfThreeFactorItem['level']) {
  return `etf-three-factor__level--${level}`;
}
</script>

<template>
  <section ref="panelElement" data-testid="etf-three-factor-panel" class="etf-three-factor">
    <div data-testid="factor-detail" class="etf-three-factor__detail">
      <div class="etf-three-factor__detail-heading">
        <span>ETF 活动证据</span>
        <strong>{{ selectedItem?.name || '--' }}</strong>
        <small>
          {{ selectedItem?.symbol || '--' }} · {{ selectedItem?.index_name || '--' }} · 信号
          {{ formatScore(selectedItem?.signal_score) }} ·
          {{ selectedItem ? signalLevelLabel(selectedItem.level) : '--' }}
        </small>
      </div>
      <dl>
        <div>
          <dt>量能因子</dt>
          <dd>{{ formatFactorValue(selectedItem?.volume_factor || ({ status: 'missing' } as EtfFactorEvidence)) }}</dd>
          <small>
            {{ selectedItem?.volume_factor.source || '--' }} ·
            {{ selectedItem ? factorStatusLabel(selectedItem.volume_factor.status) : '--' }} ·
            {{ selectedItem?.volume_factor.detail || '--' }}
          </small>
        </div>
        <div>
          <dt>方向因子</dt>
          <dd>
            {{ formatFactorValue(selectedItem?.direction_factor || ({ status: 'missing' } as EtfFactorEvidence)) }}
          </dd>
          <small>
            {{ selectedItem?.direction_factor.source || '--' }} ·
            {{ selectedItem ? factorStatusLabel(selectedItem.direction_factor.status) : '--' }} ·
            {{ selectedItem?.direction_factor.detail || '--' }}
          </small>
        </div>
        <div>
          <dt>份额因子</dt>
          <dd>{{ formatFactorValue(selectedItem?.share_factor || ({ status: 'missing' } as EtfFactorEvidence)) }}</dd>
          <small>
            {{ selectedItem?.share_factor.source || '--' }} ·
            {{ selectedItem ? factorStatusLabel(selectedItem.share_factor.status) : '--' }} ·
            {{ selectedItem?.share_factor.detail || '--' }}
          </small>
        </div>
      </dl>
      <p class="etf-three-factor__disclaimer">三因子同向仅表示疑似活动</p>
      <p
        v-if="historyError && hasUsableHistory"
        class="etf-three-factor__history-error"
        role="status"
        aria-live="polite"
      >
        {{ historyError }}
      </p>
      <div v-if="hasUsableHistory" class="etf-three-factor__charts">
        <EChart :option="volumeOption" :height="236" :loading="historyLoading" />
        <EChart :option="shareOption" :height="236" :loading="historyLoading" />
        <EChart :option="comparisonOption" :height="236" :loading="historyLoading" />
      </div>
      <p
        v-else-if="historyLoading"
        data-testid="three-factor-history-loading"
        class="etf-three-factor__history-state"
        role="status"
        aria-live="polite"
      >
        正在读取历史信号
      </p>
      <p
        v-else-if="historyError"
        data-testid="three-factor-history-error"
        class="etf-three-factor__history-state etf-three-factor__history-error"
        role="status"
        aria-live="polite"
      >
        {{ historyError }}
      </p>
      <p v-else data-testid="three-factor-history-empty" class="etf-three-factor__history-state">暂无可用历史信号</p>
    </div>

    <div data-testid="signal-timeline" class="etf-three-factor__timeline" aria-label="三因子信号时间线">
      <div v-for="point in timelinePoints" :key="point.trade_date" class="etf-three-factor__timeline-item">
        <time>{{ point.trade_date }}</time>
        <strong :class="levelClass(point.level)">{{ point.level.toUpperCase() }}</strong>
        <span>评分 {{ formatScore(point.signal_score) }} · 收盘 {{ formatPercent(point.close_change_pct) }}</span>
      </div>
      <p v-if="timelinePoints.length === 0">暂无历史信号</p>
    </div>
  </section>
</template>

<style scoped>
.etf-three-factor {
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  border-block: 1px solid var(--wb-border);
  color: var(--wb-ink);
  font-variant-numeric: tabular-nums;
}

.etf-three-factor__detail > dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.etf-three-factor__detail > dl > div {
  min-width: 0;
  padding: 12px;
  border-inline-end: 1px solid var(--wb-border);
}

.etf-three-factor__detail > dl > div:last-child {
  border-inline-end: 0;
}

.etf-three-factor__detail small,
.etf-three-factor__detail-heading span,
.etf-three-factor__detail-heading small {
  display: block;
  overflow-wrap: anywhere;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.4;
}

.etf-three-factor__detail {
  border-bottom: 1px solid var(--wb-border);
}

.etf-three-factor__detail-heading {
  padding: 12px;
  border-bottom: 1px solid var(--wb-border);
}

.etf-three-factor__detail-heading strong {
  margin-inline: 8px;
}

.etf-three-factor__detail-heading small {
  display: inline;
}

.etf-three-factor__detail > dl {
  margin: 0;
}

.etf-three-factor__detail dt {
  color: var(--wb-muted);
  font-size: 12px;
}

.etf-three-factor__detail dd {
  margin: 4px 0;
  font-size: 16px;
  font-weight: 700;
}

.etf-three-factor__disclaimer {
  margin: 0;
  padding: 8px 12px;
  color: var(--wb-muted);
  font-size: 12px;
  border-top: 1px solid var(--wb-border);
}

.etf-three-factor__history-error {
  margin: 0;
  padding: 8px 12px;
  color: var(--wb-warning);
  background: var(--wb-status-warning-soft);
}

.etf-three-factor__history-state {
  margin: 0;
  padding: 12px;
  color: var(--wb-muted);
  border-top: 1px solid var(--wb-border);
}

.etf-three-factor__charts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid var(--wb-border);
}

.etf-three-factor__charts > :deep(*) {
  min-width: 0;
  padding: 8px;
  border-inline-end: 1px solid var(--wb-border);
}

.etf-three-factor__charts > :deep(*:last-child) {
  border-inline-end: 0;
}

.etf-three-factor__timeline {
  display: flex;
  min-width: 0;
  overflow-x: auto;
  padding: 10px 12px;
}

.etf-three-factor__timeline-item {
  display: grid;
  flex: 0 0 168px;
  gap: 3px;
  padding: 0 12px;
  border-inline-end: 1px solid var(--wb-border);
  font-size: 12px;
}

.etf-three-factor__timeline-item span,
.etf-three-factor__timeline-item time {
  color: var(--wb-muted);
}

.etf-three-factor__timeline p {
  margin: 0;
  color: var(--wb-muted);
}

.etf-three-factor__level--high {
  color: var(--wb-positive);
}

.etf-three-factor__level--medium {
  color: var(--wb-warning);
}

.etf-three-factor__level--low {
  color: var(--wb-primary);
}

.etf-three-factor__level--incomplete {
  color: var(--wb-muted);
}

@media (max-width: 900px) {
  .etf-three-factor__charts {
    grid-template-columns: minmax(0, 1fr);
  }

  .etf-three-factor__charts > :deep(*) {
    border-inline-end: 0;
    border-bottom: 1px solid var(--wb-border);
  }

  .etf-three-factor__charts > :deep(*:last-child) {
    border-bottom: 0;
  }
}

@media (max-width: 640px) {
  .etf-three-factor__detail > dl {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .etf-three-factor__detail > dl > div:nth-child(2) {
    border-inline-end: 0;
  }

  .etf-three-factor__detail > dl > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--wb-border);
  }
}
</style>
