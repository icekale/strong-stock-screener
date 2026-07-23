<script setup lang="ts">
import { computed, ref } from 'vue';
import type { UnifiedEtfActivityRow } from '@/utils/domain/etfThreeFactor';
import { closeChangeTone, signalLevelLabel } from '@/utils/domain/etfThreeFactor';
import { shareChangeEventLabel } from '@/utils/domain/etfExcessFlow';

defineOptions({ name: 'EtfActivityTable' });

const props = defineProps<{
  rows: UnifiedEtfActivityRow[];
  selectedSymbol: string;
}>();

const emit = defineEmits<{
  select: [symbol: string];
}>();

type SortKey = 'closeChangePct' | 'dailyChangePct' | 'baselineChangePct' | 'volumeRatio' | 'signalScore';

const sortKey = ref<SortKey>('signalScore');
const sortDirection = ref<'asc' | 'desc'>('desc');

const sortedRows = computed(() =>
  [...props.rows].sort((left, right) => {
    const leftValue = left[sortKey.value];
    const rightValue = right[sortKey.value];
    if (leftValue === null && rightValue === null) return 0;
    if (leftValue === null) return 1;
    if (rightValue === null) return -1;
    return sortDirection.value === 'desc' ? rightValue - leftValue : leftValue - rightValue;
  })
);

function selectRow(symbol: string) {
  emit('select', symbol);
}

function sortBy(key: SortKey) {
  if (sortKey.value === key) sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc';
  else {
    sortKey.value = key;
    sortDirection.value = 'desc';
  }
}

function sortLabel(key: SortKey) {
  if (sortKey.value !== key) return '可排序';
  return sortDirection.value === 'desc' ? '降序' : '升序';
}

function formatPercent(value: number | null) {
  return value === null ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatScore(value: number | null) {
  return value === null ? '--' : value.toFixed(0);
}

function formatVolumeRatio(value: number | null) {
  return value === null ? '--' : `${value.toFixed(2)}倍`;
}

function valueClass(value: number | null) {
  const tone = closeChangeTone(value);
  if (tone === 'rise') return 'etf-activity-table__value--rise';
  if (tone === 'fall') return 'etf-activity-table__value--fall';
  return '';
}

function statusText(row: UnifiedEtfActivityRow) {
  const level = signalLevelLabel(row.signalLevel);
  if (!row.activity) return level;
  const event = shareChangeEventLabel(row.activity);
  if (row.activity.direction === 'increase') return `${level} · +增加（申购代理）${event ? ` · ${event}` : ''}`;
  if (row.activity.direction === 'decrease') return `${level} · -减少（赎回代理）${event ? ` · ${event}` : ''}`;
  if (row.activity.direction === 'flat') return `${level} · 持平`;
  return `${level} · 待确认`;
}
</script>

<template>
  <div data-testid="etf-activity-table" class="etf-activity-table">
    <div class="etf-activity-table__scroll" role="region" aria-label="ETF活动统一表" tabindex="0">
      <table class="etf-activity-table__table">
        <colgroup>
          <col class="etf-activity-table__col--identity" />
          <col class="etf-activity-table__col--numeric" />
          <col class="etf-activity-table__col--numeric" />
          <col class="etf-activity-table__col--numeric" />
          <col class="etf-activity-table__col--numeric" />
          <col class="etf-activity-table__col--numeric" />
          <col class="etf-activity-table__col--status" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" class="etf-activity-table__cell--identity">ETF / 指数</th>
            <th scope="col" class="etf-activity-table__cell--numeric">
              <button
                type="button"
                :aria-label="`收盘涨跌 ${sortLabel('closeChangePct')}`"
                @click="sortBy('closeChangePct')"
              >
                收盘涨跌
              </button>
            </th>
            <th scope="col" class="etf-activity-table__cell--numeric">
              <button
                type="button"
                :aria-label="`份额日变化 ${sortLabel('dailyChangePct')}`"
                @click="sortBy('dailyChangePct')"
              >
                份额日变化
              </button>
            </th>
            <th scope="col" class="etf-activity-table__cell--numeric">
              <button
                type="button"
                :aria-label="`报告基线偏离 ${sortLabel('baselineChangePct')}`"
                @click="sortBy('baselineChangePct')"
              >
                报告基线偏离
              </button>
            </th>
            <th scope="col" class="etf-activity-table__cell--numeric">
              <button type="button" :aria-label="`20日量比 ${sortLabel('volumeRatio')}`" @click="sortBy('volumeRatio')">
                20日量比
              </button>
            </th>
            <th scope="col" class="etf-activity-table__cell--numeric">
              <button
                type="button"
                :aria-label="`三因子评分 ${sortLabel('signalScore')}`"
                @click="sortBy('signalScore')"
              >
                三因子评分
              </button>
            </th>
            <th scope="col" class="etf-activity-table__cell--status">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sortedRows"
            :key="row.symbol"
            data-testid="activity-etf-row"
            :data-symbol="row.symbol"
            :class="{ 'etf-activity-table__row--selected': row.symbol === selectedSymbol }"
            @click="selectRow(row.symbol)"
          >
            <th scope="row" class="etf-activity-table__cell--identity">
              <button
                data-testid="activity-etf-select"
                type="button"
                :aria-label="`选择 ${row.name} ${row.symbol}`"
                :aria-pressed="row.symbol === selectedSymbol"
                @click.stop="selectRow(row.symbol)"
              >
                <strong :title="row.name">{{ row.name }}</strong>
                <span :title="`${row.symbol} · ${row.indexName}`">{{ row.symbol }} · {{ row.indexName }}</span>
              </button>
            </th>
            <td class="etf-activity-table__cell--numeric" :class="valueClass(row.closeChangePct)">
              {{ formatPercent(row.closeChangePct) }}
            </td>
            <td class="etf-activity-table__cell--numeric" :class="valueClass(row.dailyChangePct)">
              <div class="etf-activity-table__share-change">
                <span>{{ formatPercent(row.dailyChangePct) }}</span>
                <span
                  v-if="row.activity && shareChangeEventLabel(row.activity)"
                  data-testid="tenfold-share-change"
                  class="etf-activity-table__event"
                  :class="
                    row.activity.direction === 'increase'
                      ? 'etf-activity-table__event--increase'
                      : 'etf-activity-table__event--decrease'
                  "
                >
                  {{ shareChangeEventLabel(row.activity) }}
                </span>
                <small
                  v-if="
                    row.activity?.share_change_20d_multiple !== null &&
                    row.activity?.share_change_20d_multiple !== undefined
                  "
                >
                  {{ row.activity.share_change_20d_multiple.toFixed(1) }}倍
                </small>
              </div>
            </td>
            <td class="etf-activity-table__cell--numeric" :class="valueClass(row.baselineChangePct)">
              {{ formatPercent(row.baselineChangePct) }}
            </td>
            <td class="etf-activity-table__cell--numeric">{{ formatVolumeRatio(row.volumeRatio) }}</td>
            <td class="etf-activity-table__cell--numeric">{{ formatScore(row.signalScore) }}</td>
            <td class="etf-activity-table__cell--status etf-activity-table__status">{{ statusText(row) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.etf-activity-table {
  min-width: 0;
  max-width: 100%;
}

.etf-activity-table__scroll {
  max-width: 100%;
  overflow-x: auto;
  overscroll-behavior-inline: contain;
}

.etf-activity-table__table {
  width: 100%;
  min-width: 1010px;
  border-collapse: collapse;
  table-layout: fixed;
}

.etf-activity-table__col--identity {
  width: 230px;
}

.etf-activity-table__col--numeric {
  width: 130px;
}

.etf-activity-table__col--status {
  width: 120px;
}

th,
td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--wb-border, #e2e8f0);
  text-align: right;
  white-space: nowrap;
}

.etf-activity-table__cell--identity {
  text-align: left;
}

.etf-activity-table__cell--numeric {
  text-align: right;
}

.etf-activity-table__cell--status {
  text-align: left;
}

thead th {
  color: var(--wb-muted, #64748b);
  font-size: 12px;
  font-weight: 600;
}

thead button {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  color: inherit;
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: inherit;
}

tbody tr {
  cursor: pointer;
}

tbody tr:not(.etf-activity-table__row--selected):hover {
  background: var(--wb-surface-muted, #f8fafc);
}

.etf-activity-table__row--selected {
  background: color-mix(in srgb, var(--wb-primary, #2563eb) 8%, transparent);
}

tbody th strong,
tbody th span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

tbody th button {
  display: block;
  width: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  color: inherit;
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

tbody th button:focus-visible {
  outline: 2px solid var(--wb-primary, #2563eb);
  outline-offset: 2px;
}

tbody th span {
  margin-top: 3px;
  color: var(--wb-muted, #64748b);
  font-size: 12px;
  font-weight: 400;
}

.etf-activity-table__value--rise {
  color: var(--wb-positive, #15803d);
  font-weight: 700;
}

.etf-activity-table__value--fall {
  color: var(--wb-negative, #b91c1c);
  font-weight: 700;
}

.etf-activity-table__share-change {
  display: inline-flex;
  min-height: 42px;
  flex-direction: column;
  justify-content: center;
  align-items: flex-end;
  gap: 2px;
}

.etf-activity-table__share-change small {
  color: var(--wb-muted, #64748b);
  font-size: 11px;
  font-weight: 400;
}

.etf-activity-table__event {
  display: inline-flex;
  min-height: 18px;
  align-items: center;
  padding: 0 5px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
}

.etf-activity-table__event--increase {
  color: var(--wb-negative, #b91c1c);
  background: color-mix(in srgb, var(--wb-negative, #b91c1c) 10%, transparent);
}

.etf-activity-table__event--decrease {
  color: var(--wb-positive, #15803d);
  background: color-mix(in srgb, var(--wb-positive, #15803d) 10%, transparent);
}

.etf-activity-table__status {
  white-space: normal;
  line-height: 18px;
  overflow-wrap: anywhere;
}
</style>
