<script setup lang="ts">
import { computed } from 'vue';
import type { EChartsOption } from 'echarts';
import type { EtfRadarHistoryResponse, EtfRadarOverviewResponse } from '@/service/types';
import {
  formatDirectionalPercent as formatDirectionalPercentValue,
  formatPlainShares as formatPlainSharesValue
} from '@/utils/domain/capitalSignals';
import { buildHuijinRanking, buildHuijinTrajectory, huijinActivityDataState } from '@/utils/domain/huijinTrajectory';
import EChart from '@/components/charts/EChart.vue';

defineOptions({ name: 'HuijinTrajectoryPanel' });

const props = defineProps<{
  overview: EtfRadarOverviewResponse;
  history: EtfRadarHistoryResponse | null;
  selectedSymbol: string;
  historyLoading: boolean;
  historyError: string | null;
}>();

const emit = defineEmits<{
  select: [symbol: string];
}>();

const ranking = computed(() => buildHuijinRanking(props.overview.core_items));
const selectedItem = computed(
  () => props.overview.core_items.find(item => item.symbol === props.selectedSymbol) ?? ranking.value[0] ?? null
);
const realDates = computed(() => [...new Set((props.history?.points ?? []).map(point => point.trade_date))].sort());
const trajectory = computed(() =>
  selectedItem.value
    ? buildHuijinTrajectory(selectedItem.value, props.history?.points ?? [], realDates.value)
    : { dates: [], values: [] }
);
const baselineDate = computed(
  () =>
    selectedItem.value?.report_period ??
    props.overview.core_items.find(item => item.report_period)?.report_period ??
    '--'
);
const availableCount = computed(() => props.overview.activity.available_core_count);
const expansionCount = computed(
  () => props.overview.core_items.filter(item => (item.cumulative_baseline_change_pct ?? 0) > 0).length
);
const contractionCount = computed(
  () => props.overview.core_items.filter(item => (item.cumulative_baseline_change_pct ?? 0) < 0).length
);
const hasTrajectory = computed(() => trajectory.value.values.some(value => value !== null));

const chartOption = computed<EChartsOption>(() => ({
  animation: false,
  aria: { enabled: true, description: `${selectedItem.value?.name ?? 'ETF'}相对报告基线的累计份额轨迹` },
  grid: { left: 58, right: 18, top: 20, bottom: 34 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', boundaryGap: false, data: trajectory.value.dates },
  yAxis: { type: 'value', axisLabel: { formatter: (value: number) => `${value.toFixed(0)}%` } },
  series: [
    {
      name: selectedItem.value?.name ?? '累计偏离',
      type: 'line',
      connectNulls: false,
      showSymbol: true,
      data: trajectory.value.values
    }
  ]
}));

function formatDirectionalPercent(value: number | null | undefined) {
  return formatDirectionalPercentValue(value ?? null);
}

function formatPlainShares(value: number | null | undefined) {
  return formatPlainSharesValue(value ?? null);
}

function formatHoldingPct(value: number | null | undefined) {
  return value === null || value === undefined ? '--' : `${value.toFixed(2)}%`;
}

function valueClass(value: number | null | undefined) {
  if (value === null || value === undefined || value === 0) return '';
  return value > 0 ? 'huijin-value--increase' : 'huijin-value--decrease';
}

function deviationDirection(value: number | null | undefined) {
  if (value === null || value === undefined) return '数据缺失';
  if (value > 0) return '扩张';
  if (value < 0) return '收缩';
  return '持平';
}
</script>

<template>
  <section data-testid="huijin-trajectory-panel" class="huijin-trajectory">
    <div class="huijin-trajectory__metrics" aria-label="汇金持仓轨迹摘要">
      <div data-testid="huijin-baseline-date">
        <span>确认报告基线</span>
        <strong>{{ baselineDate }}</strong>
      </div>
      <div>
        <span>最新份额日期</span>
        <strong>{{ overview.trade_date }}</strong>
      </div>
      <div>
        <span>核心 ETF 覆盖</span>
        <strong>{{ availableCount }} / {{ overview.activity.core_count }}</strong>
      </div>
      <div>
        <span>累计偏离方向</span>
        <strong>{{ expansionCount }} 只扩张 / {{ contractionCount }} 只收缩</strong>
      </div>
    </div>

    <div class="huijin-trajectory__sources" aria-label="数据来源状态">
      <span v-for="source in overview.source_status" :key="`${source.source}-${source.detail}`">
        {{ source.source }} · {{ source.status }} · {{ source.detail }}
      </span>
    </div>

    <div class="huijin-trajectory__main">
      <div class="huijin-ranking" role="list" aria-label="核心 ETF 累计偏离排行">
        <button
          v-for="item in ranking"
          :key="item.symbol"
          data-testid="huijin-ranking-row"
          type="button"
          :class="[
            valueClass(item.cumulative_baseline_change_pct),
            { 'huijin-ranking__row--selected': item.symbol === selectedItem?.symbol }
          ]"
          :aria-pressed="item.symbol === selectedItem?.symbol"
          @click="emit('select', item.symbol)"
        >
          <span class="huijin-ranking__identity">
            <strong>{{ item.name }}</strong>
            <small>{{ item.symbol }}</small>
          </span>
          <span class="huijin-ranking__value">
            {{ formatDirectionalPercent(item.cumulative_baseline_change_pct) }} ·
            {{ deviationDirection(item.cumulative_baseline_change_pct) }}
          </span>
        </button>
      </div>

      <div class="huijin-selected">
        <div class="huijin-selected__heading">
          <span>选中 ETF 累计轨迹</span>
          <strong data-testid="huijin-selected-symbol">{{ selectedItem?.symbol }}</strong>
        </div>
        <EChart v-if="history && hasTrajectory" :option="chartOption" :height="286" :loading="historyLoading" />
        <div v-else class="huijin-trajectory__empty">
          {{ historyError || (historyLoading ? '历史加载中' : '历史积累中') }}
        </div>
      </div>
    </div>

    <dl class="huijin-trajectory__details">
      <div>
        <dt>汇金确认持有份额</dt>
        <dd>{{ formatPlainShares(selectedItem?.confirmed_huijin_shares) }}</dd>
      </div>
      <div>
        <dt>报告期 ETF 总份额</dt>
        <dd>{{ formatPlainShares(selectedItem?.baseline_total_shares) }}</dd>
      </div>
      <div>
        <dt>最新 ETF 总份额</dt>
        <dd>{{ formatPlainShares(selectedItem?.total_shares) }}</dd>
      </div>
      <div>
        <dt>汇金确认持仓比例</dt>
        <dd>{{ formatHoldingPct(selectedItem?.confirmed_huijin_holding_pct) }}</dd>
      </div>
      <div>
        <dt>累计偏离</dt>
        <dd :class="valueClass(selectedItem?.cumulative_baseline_change_pct)">
          {{ formatDirectionalPercent(selectedItem?.cumulative_baseline_change_pct) }} ·
          {{ deviationDirection(selectedItem?.cumulative_baseline_change_pct) }}
        </dd>
      </div>
      <div>
        <dt>最近日变化</dt>
        <dd :class="valueClass(selectedItem?.daily_change_pct)">
          {{ formatDirectionalPercent(selectedItem?.daily_change_pct) }}
        </dd>
      </div>
    </dl>

    <p class="huijin-trajectory__note">累计份额变化不能直接证明汇金增减持，需由下一期基金报告确认。</p>

    <div class="huijin-trajectory__table" role="table" aria-label="汇金核心 ETF 持仓轨迹明细">
      <div class="huijin-trajectory__table-head" role="row">
        <span role="columnheader">ETF</span>
        <span role="columnheader">确认持仓比例</span>
        <span role="columnheader">累计偏离</span>
        <span role="columnheader">数据状态</span>
      </div>
      <button
        v-for="item in overview.core_items"
        :key="item.symbol"
        type="button"
        :class="{ 'huijin-trajectory__table-row--selected': item.symbol === selectedItem?.symbol }"
        @click="emit('select', item.symbol)"
      >
        <span class="huijin-trajectory__table-identity">
          <strong>{{ item.name }}</strong>
          <small>{{ item.symbol }}</small>
        </span>
        <span>{{ formatHoldingPct(item.confirmed_huijin_holding_pct) }}</span>
        <span :class="valueClass(item.cumulative_baseline_change_pct)">
          {{ formatDirectionalPercent(item.cumulative_baseline_change_pct) }} ·
          {{ deviationDirection(item.cumulative_baseline_change_pct) }}
        </span>
        <span>{{ huijinActivityDataState(item) }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.huijin-trajectory {
  max-width: 100%;
  min-width: 0;
  overflow-x: hidden;
  color: var(--wb-ink);
}

.huijin-trajectory__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  background: var(--wb-surface);
  border-block: 1px solid var(--wb-border);
}

.huijin-trajectory__metrics > div {
  min-width: 0;
  padding: 10px 14px;
  border-inline-end: 1px solid var(--wb-border);
}

.huijin-trajectory__metrics > div:last-child {
  border-inline-end: 0;
}

.huijin-trajectory__metrics span,
.huijin-selected__heading span {
  display: block;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.4;
}

.huijin-trajectory__metrics strong {
  display: block;
  margin-top: 3px;
  overflow-wrap: anywhere;
  color: var(--wb-ink);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
  line-height: 1.4;
}

.huijin-trajectory__sources {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 16px;
  min-width: 0;
  padding: 8px 0 12px;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.5;
}

.huijin-trajectory__sources span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.huijin-trajectory__main {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: var(--wb-gap);
  min-width: 0;
}

.huijin-ranking,
.huijin-selected {
  min-width: 0;
  background: var(--wb-surface);
  border-block: 1px solid var(--wb-border);
}

.huijin-ranking {
  display: flex;
  flex-direction: column;
}

.huijin-ranking button,
.huijin-trajectory__table button {
  width: 100%;
  min-width: 0;
  color: var(--wb-ink);
  font: inherit;
  text-align: start;
  background: var(--wb-surface);
  border: 0;
  border-bottom: 1px solid var(--wb-border);
  cursor: pointer;
}

.huijin-ranking button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  flex: 1 1 0;
  padding: 8px 12px;
}

.huijin-ranking button:last-child,
.huijin-trajectory__table button:last-child {
  border-bottom: 0;
}

.huijin-ranking button:hover,
.huijin-ranking__row--selected,
.huijin-trajectory__table button:hover,
.huijin-trajectory__table-row--selected {
  background: var(--wb-primary-soft);
}

.huijin-ranking__identity,
.huijin-trajectory__table-identity {
  min-width: 0;
}

.huijin-ranking__identity strong,
.huijin-ranking__identity small,
.huijin-trajectory__table-identity strong,
.huijin-trajectory__table-identity small {
  display: block;
  overflow-wrap: anywhere;
}

.huijin-ranking__identity small,
.huijin-trajectory__table-identity small {
  margin-top: 2px;
  color: var(--wb-muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.huijin-ranking__value {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  text-align: end;
}

.huijin-selected {
  padding: 10px 12px;
}

.huijin-selected__heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.huijin-selected__heading strong {
  color: var(--wb-ink);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.huijin-trajectory__empty {
  display: grid;
  min-height: 286px;
  place-items: center;
  color: var(--wb-muted);
  font-size: 13px;
}

.huijin-trajectory__details {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: var(--wb-gap) 0 0;
  background: var(--wb-surface);
  border-block: 1px solid var(--wb-border);
}

.huijin-trajectory__details > div {
  min-width: 0;
  padding: 10px 12px;
  border-bottom: 1px solid var(--wb-border);
  border-inline-end: 1px solid var(--wb-border);
}

.huijin-trajectory__details > div:nth-child(3n) {
  border-inline-end: 0;
}

.huijin-trajectory__details > div:nth-last-child(-n + 3) {
  border-bottom: 0;
}

.huijin-trajectory__details dt {
  color: var(--wb-muted);
  font-size: 12px;
}

.huijin-trajectory__details dd {
  margin: 3px 0 0;
  overflow-wrap: anywhere;
  color: var(--wb-ink);
  font-size: 14px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.huijin-trajectory__note {
  margin: 12px 0;
  padding: 8px 10px;
  color: var(--wb-warning);
  font-size: 12px;
  line-height: 1.5;
  background: var(--wb-status-warning-soft);
  border-inline-start: 2px solid var(--wb-warning);
}

.huijin-trajectory__table {
  min-width: 0;
  background: var(--wb-surface);
  border-block: 1px solid var(--wb-border);
}

.huijin-trajectory__table-head,
.huijin-trajectory__table button {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 0.7fr) minmax(0, 0.8fr) minmax(0, 0.75fr);
  gap: 12px;
  align-items: center;
}

.huijin-trajectory__table-head {
  padding: 7px 10px;
  color: var(--wb-muted);
  font-size: 11px;
  font-weight: 600;
  border-bottom: 1px solid var(--wb-border);
}

.huijin-trajectory__table button {
  padding: 8px 10px;
  font-size: 12px;
}

.huijin-trajectory__table button > span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.huijin-ranking button.huijin-value--increase .huijin-ranking__value,
.huijin-trajectory__details dd.huijin-value--increase,
.huijin-trajectory__table span.huijin-value--increase {
  color: var(--wb-positive);
}

.huijin-ranking button.huijin-value--decrease .huijin-ranking__value,
.huijin-trajectory__details dd.huijin-value--decrease,
.huijin-trajectory__table span.huijin-value--decrease {
  color: var(--wb-negative);
}

@media (max-width: 900px) {
  .huijin-trajectory__main {
    grid-template-columns: minmax(0, 1fr);
  }

  .huijin-trajectory__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .huijin-trajectory__metrics > div:nth-child(2) {
    border-inline-end: 0;
  }

  .huijin-trajectory__metrics > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--wb-border);
  }
}

@media (max-width: 640px) {
  .huijin-ranking button {
    grid-template-columns: minmax(0, 1fr);
    gap: 4px;
  }

  .huijin-ranking__value {
    text-align: start;
  }

  .huijin-trajectory__details {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .huijin-trajectory__details > div,
  .huijin-trajectory__details > div:nth-child(3n),
  .huijin-trajectory__details > div:nth-last-child(-n + 3) {
    border-bottom: 1px solid var(--wb-border);
    border-inline-end: 1px solid var(--wb-border);
  }

  .huijin-trajectory__details > div:nth-child(2n) {
    border-inline-end: 0;
  }

  .huijin-trajectory__details > div:nth-last-child(-n + 2) {
    border-bottom: 0;
  }

  .huijin-trajectory__table-head {
    display: none;
  }

  .huijin-trajectory__table button {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 6px 12px;
  }
}
</style>
