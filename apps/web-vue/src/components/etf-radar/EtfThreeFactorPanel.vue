<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue';
import type { EChartsOption } from 'echarts';
import type { EtfFactorEvidence, EtfThreeFactorHistoryResponse, EtfThreeFactorItem, EtfThreeFactorResponse } from '@/service/types';
import { closeChangeTone, factorStatusLabel, formatVolumeRatio, signalLevelLabel } from '@/utils/domain/etfThreeFactor';

defineOptions({ name: 'EtfThreeFactorPanel' });

const EChart = defineAsyncComponent(() => import('@/components/charts/EChart.vue'));

const props = defineProps<{
  snapshot: EtfThreeFactorResponse;
  history: EtfThreeFactorHistoryResponse | null;
  selectedSymbol: string;
  historyLoading: boolean;
  historyError: string | null;
}>();

const emit = defineEmits<{
  select: [symbol: string];
}>();

type SortKey = 'signal_score' | 'close_change_pct' | 'volume_ratio' | 'share_change_pct';

const sortKey = ref<SortKey>('signal_score');
const sortDirection = ref<'asc' | 'desc'>('desc');
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
const sortedItems = computed(() =>
  [...props.snapshot.items].sort((left, right) => {
    const leftValue = left[sortKey.value] ?? Number.NEGATIVE_INFINITY;
    const rightValue = right[sortKey.value] ?? Number.NEGATIVE_INFINITY;
    return sortDirection.value === 'desc' ? rightValue - leftValue : leftValue - rightValue;
  })
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
  if (value == null) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatScore(value: number | null | undefined) {
  return value == null ? '--' : value.toFixed(0);
}

function formatFactorValue(factor: EtfFactorEvidence) {
  if (factor.status === 'pending') return '待盘后';
  if (factor.value == null) return '--';
  return factor.value.toFixed(2);
}

function valueClass(value: number | null | undefined) {
  const tone = closeChangeTone(value ?? null);
  return tone === 'rise' ? 'etf-three-factor__value--rise' : tone === 'fall' ? 'etf-three-factor__value--fall' : '';
}

function levelClass(level: EtfThreeFactorItem['level']) {
  return `etf-three-factor__level--${level}`;
}

function sortBy(key: SortKey) {
  if (sortKey.value === key) sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc';
  else {
    sortKey.value = key;
    sortDirection.value = 'desc';
  }
}

function sortLabel(key: SortKey) {
  return sortKey.value === key ? (sortDirection.value === 'desc' ? '降序' : '升序') : '可排序';
}
</script>

<template>
  <section ref="panelElement" data-testid="etf-three-factor-panel" class="etf-three-factor">
    <div data-testid="three-factor-summary" class="etf-three-factor__summary">
      <div>
        <span>综合信号强度</span>
        <strong :class="levelClass(snapshot.summary.level)">{{ formatScore(snapshot.summary.signal_score) }}</strong>
        <small>{{ signalLevelLabel(snapshot.summary.level) }} · 疑似活动</small>
      </div>
      <div>
        <span>高确信</span>
        <strong>{{ snapshot.summary.high_count }}</strong>
        <small>7只核心ETF</small>
      </div>
      <div>
        <span>中确信</span>
        <strong>{{ snapshot.summary.medium_count }}</strong>
        <small>可用 {{ snapshot.summary.valid_count }} 只</small>
      </div>
      <div>
        <span>市场状态</span>
        <strong>{{ snapshot.summary.market_state.toUpperCase() }}</strong>
        <small>{{ snapshot.trade_date }}</small>
      </div>
    </div>

    <div class="etf-three-factor__dragons" role="region" aria-label="核心ETF状态条">
      <button
        v-for="item in snapshot.items"
        :key="item.symbol"
        data-testid="dragon-status"
        type="button"
        class="etf-three-factor__dragon"
        :class="[{ 'etf-three-factor__dragon--selected': item.symbol === selectedItem?.symbol }, levelClass(item.level)]"
        :aria-pressed="item.symbol === selectedItem?.symbol"
        @click="emit('select', item.symbol)"
      >
        <strong>{{ item.name }}</strong>
        <span>{{ item.symbol }}</span>
        <b>{{ item.level.toUpperCase() }}</b>
      </button>
    </div>

    <div class="etf-three-factor__monitor">
      <span>活动监测 {{ snapshot.monitor_running ? '运行中' : '待启动' }}</span>
      <span>最近扫描 {{ snapshot.last_scan_at || '--' }}</span>
      <span>高确信信号 {{ snapshot.summary.high_count }} 项</span>
      <span>提示：三因子同向仅表示疑似活动</span>
    </div>

    <div class="etf-three-factor__table-scroll" tabindex="0" role="region" aria-label="ETF三因子信号表">
      <table data-testid="three-factor-table" class="etf-three-factor__table">
        <thead>
          <tr>
            <th>ETF</th>
            <th><button type="button" :aria-label="`信号强度 ${sortLabel('signal_score')}`" @click="sortBy('signal_score')">信号强度</button></th>
            <th><button type="button" :aria-label="`收盘涨跌 ${sortLabel('close_change_pct')}`" @click="sortBy('close_change_pct')">收盘涨跌</button></th>
            <th><button type="button" :aria-label="`量能比 ${sortLabel('volume_ratio')}`" @click="sortBy('volume_ratio')">量能比</button></th>
            <th>20日均量</th>
            <th><button type="button" :aria-label="`份额日变化 ${sortLabel('share_change_pct')}`" @click="sortBy('share_change_pct')">份额日变化</button></th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in sortedItems" :key="item.symbol" :class="{ 'etf-three-factor__row--selected': item.symbol === selectedItem?.symbol }">
            <td><button type="button" @click="emit('select', item.symbol)"><strong>{{ item.name }}</strong><span>{{ item.symbol }}</span></button></td>
            <td>{{ formatScore(item.signal_score) }}</td>
            <td :class="valueClass(item.close_change_pct)">{{ formatPercent(item.close_change_pct) }}</td>
            <td>{{ formatVolumeRatio(item.volume_ratio) }}</td>
            <td>{{ item.average_volume_20d == null ? '--' : compactNumber(item.average_volume_20d) }}</td>
            <td :class="valueClass(item.share_change_pct)">{{ formatPercent(item.share_change_pct) }}</td>
            <td><span :class="levelClass(item.level)">{{ item.level.toUpperCase() }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div data-testid="factor-detail" class="etf-three-factor__detail">
      <div class="etf-three-factor__detail-heading">
        <span>选中ETF</span>
        <strong>{{ selectedItem?.name || '--' }}</strong>
        <small>{{ selectedItem?.symbol || '--' }} · {{ selectedItem?.index_name || '--' }}</small>
      </div>
      <dl>
        <div>
          <dt>量能因子</dt>
          <dd>{{ formatFactorValue(selectedItem?.volume_factor || { status: 'missing' } as EtfFactorEvidence) }}</dd>
          <small>{{ selectedItem ? factorStatusLabel(selectedItem.volume_factor.status) : '--' }} · {{ selectedItem?.volume_factor.detail || '--' }}</small>
        </div>
        <div>
          <dt>方向因子</dt>
          <dd>{{ formatFactorValue(selectedItem?.direction_factor || { status: 'missing' } as EtfFactorEvidence) }}</dd>
          <small>{{ selectedItem ? factorStatusLabel(selectedItem.direction_factor.status) : '--' }} · {{ selectedItem?.direction_factor.detail || '--' }}</small>
        </div>
        <div>
          <dt>份额因子</dt>
          <dd>{{ formatFactorValue(selectedItem?.share_factor || { status: 'missing' } as EtfFactorEvidence) }}</dd>
          <small>{{ selectedItem ? factorStatusLabel(selectedItem.share_factor.status) : '--' }} · {{ selectedItem?.share_factor.detail || '--' }}</small>
        </div>
      </dl>
      <p v-if="historyError && hasUsableHistory" class="etf-three-factor__history-error" role="status" aria-live="polite">{{ historyError }}</p>
      <div v-if="hasUsableHistory" class="etf-three-factor__charts">
        <EChart :option="volumeOption" :height="236" :loading="historyLoading" />
        <EChart :option="shareOption" :height="236" :loading="historyLoading" />
        <EChart :option="comparisonOption" :height="236" :loading="historyLoading" />
      </div>
      <p v-else-if="historyLoading" data-testid="three-factor-history-loading" class="etf-three-factor__history-state" role="status" aria-live="polite">正在读取历史信号</p>
      <p v-else-if="historyError" data-testid="three-factor-history-error" class="etf-three-factor__history-state etf-three-factor__history-error" role="status" aria-live="polite">{{ historyError }}</p>
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

.etf-three-factor__summary,
.etf-three-factor__detail > dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.etf-three-factor__summary > div,
.etf-three-factor__detail > dl > div {
  min-width: 0;
  padding: 12px;
  border-inline-end: 1px solid var(--wb-border);
}

.etf-three-factor__summary > div:last-child,
.etf-three-factor__detail > dl > div:last-child {
  border-inline-end: 0;
}

.etf-three-factor__summary span,
.etf-three-factor__summary small,
.etf-three-factor__detail small,
.etf-three-factor__dragon span,
.etf-three-factor__detail-heading span,
.etf-three-factor__detail-heading small {
  display: block;
  overflow-wrap: anywhere;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.4;
}

.etf-three-factor__summary strong {
  display: block;
  margin: 3px 0;
  font-size: 20px;
  line-height: 1.2;
}

.etf-three-factor__dragons {
  display: flex;
  min-width: 0;
  overflow-x: auto;
  border-top: 1px solid var(--wb-border);
  border-bottom: 1px solid var(--wb-border);
}

.etf-three-factor__dragon {
  flex: 0 0 154px;
  min-width: 0;
  padding: 9px 10px;
  color: var(--wb-ink);
  text-align: left;
  background: var(--wb-surface);
  border: 0;
  border-inline-end: 1px solid var(--wb-border);
  cursor: pointer;
}

.etf-three-factor__dragon strong {
  display: block;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.etf-three-factor__dragon b {
  display: inline-block;
  margin-top: 4px;
  font-size: 11px;
}

.etf-three-factor__dragon--selected,
.etf-three-factor__row--selected {
  background: var(--wb-primary-soft);
}

.etf-three-factor__monitor {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  padding: 9px 12px;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.4;
  border-bottom: 1px solid var(--wb-border);
}

.etf-three-factor__table-scroll {
  min-width: 0;
  overflow-x: auto;
  border-bottom: 1px solid var(--wb-border);
}

.etf-three-factor__table {
  width: 100%;
  min-width: 910px;
  border-collapse: collapse;
  font-size: 12px;
}

.etf-three-factor__table th,
.etf-three-factor__table td {
  padding: 9px 10px;
  text-align: right;
  border-bottom: 1px solid var(--wb-border);
}

.etf-three-factor__table th:first-child,
.etf-three-factor__table td:first-child {
  width: 220px;
  text-align: left;
}

.etf-three-factor__table th button,
.etf-three-factor__table td button {
  padding: 0;
  color: inherit;
  font: inherit;
  text-align: inherit;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.etf-three-factor__table td button strong,
.etf-three-factor__table td button span {
  display: block;
}

.etf-three-factor__table td button span {
  color: var(--wb-muted);
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

.etf-three-factor__value--rise,
.etf-three-factor__level--high {
  color: var(--wb-positive);
}

.etf-three-factor__value--fall {
  color: var(--wb-negative);
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
  .etf-three-factor__summary,
  .etf-three-factor__detail > dl {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .etf-three-factor__summary > div:nth-child(2),
  .etf-three-factor__detail > dl > div:nth-child(2) {
    border-inline-end: 0;
  }

  .etf-three-factor__summary > div:nth-child(-n + 2),
  .etf-three-factor__detail > dl > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--wb-border);
  }
}
</style>
