<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getChanlunAnalysis, getStockKline, getStockQuote } from '@/service/product-api';
import type { ChanlunAnalysisResponse, ChanlunPeriod, KlineBar, StockQuoteResponse } from '@/service/types';
import StockKlineChart from '@/components/charts/StockKlineChart.vue';
import { KLINE_SUB_INDICATOR_OPTIONS, type KlineMovingAverage, type KlineSubIndicator } from '@/utils/charts/klineIndicatorLayout';

defineOptions({ name: 'StockView' });

const route = useRoute();
const router = useRouter();
const symbol = computed(() => String(route.params.symbol || '')); 
const name = computed(() => String(route.query.name || symbol.value));
const industry = computed(() => String(route.query.industry || '行业待补'));
const period = ref<ChanlunPeriod>('1d');
const bars = ref<KlineBar[]>([]);
const quote = ref<StockQuoteResponse | null>(null);
const chanlun = ref<ChanlunAnalysisResponse | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const movingAverages = ref<KlineMovingAverage[]>([]);
const subIndicators = ref<KlineSubIndicator[]>(['volume']);

const periodOptions = [
  { label: '日线', value: '1d' },
  { label: '60 分钟', value: '60m' },
  { label: '30 分钟', value: '30m' },
  { label: '5 分钟', value: '5m' }
];

async function load() {
  if (!symbol.value) return;
  loading.value = true;
  error.value = null;
  const [klineResult, quoteResult, chanlunResult] = await Promise.allSettled([
    getStockKline(symbol.value, 220),
    getStockQuote(symbol.value),
    getChanlunAnalysis(symbol.value, { period: period.value, lookback: 220, includeObserving: true })
  ]);
  if (klineResult.status === 'fulfilled') bars.value = klineResult.value.bars;
  if (quoteResult.status === 'fulfilled') quote.value = quoteResult.value;
  if (chanlunResult.status === 'fulfilled') chanlun.value = chanlunResult.value;
  const failures = [klineResult, quoteResult, chanlunResult].filter(result => result.status === 'rejected');
  if (failures.length === 3) error.value = '个股数据暂时不可用，请检查数据源状态';
  loading.value = false;
}

function toggleAverage(value: KlineMovingAverage) {
  movingAverages.value = movingAverages.value.includes(value) ? movingAverages.value.filter(item => item !== value) : [...movingAverages.value, value];
}

function setPeriod(value: ChanlunPeriod) {
  period.value = value;
  void load();
}

function openChanlun() {
  void router.push({ path: '/chanlun', query: { symbol: symbol.value, name: name.value, industry: industry.value } });
}

function formatPct(value: number | null | undefined) {
  return typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(2)}%` : '--';
}

onMounted(() => void load());
watch(symbol, () => void load());
</script>

<template>
  <div class="space-y-16px">
    <div class="flex flex-wrap items-center justify-between gap-12px"><div><div class="text-22px font-700 text-text-primary">{{ name }}</div><div class="mt-4px text-13px text-text-secondary">{{ symbol }} · {{ industry }}</div></div><a-space><a-button @click="openChanlun">打开缠论工作台</a-button><a-button @click="router.back">返回</a-button></a-space></div>
    <a-alert v-if="error" :message="error" show-icon type="warning" />
    <a-row :gutter="12"><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="最新价" :value="quote?.last_price ?? '--'" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="涨跌幅" :value="formatPct(quote?.pct_change)" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="成交额" :value="quote?.turnover_cny == null ? '--' : `${(quote.turnover_cny / 100000000).toFixed(2)}亿`" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="换手率" :value="quote?.turnover_rate == null ? '--' : `${quote.turnover_rate.toFixed(2)}%`" /></a-card></a-col></a-row>
    <a-card size="small"><template #title><a-space><span>K 线与结构</span><a-segmented :value="period" size="small" :options="periodOptions" @change="value => setPeriod(value as ChanlunPeriod)" /></a-space></template><template #extra><a-space wrap><a-button v-for="item in [{ label: 'MA5', value: 'ma5' }, { label: 'MA10', value: 'ma10' }, { label: 'MA20', value: 'ma20' }, { label: 'MA60', value: 'ma60' }]" :key="item.value" size="small" :type="movingAverages.includes(item.value as KlineMovingAverage) ? 'primary' : 'default'" @click="toggleAverage(item.value as KlineMovingAverage)">{{ item.label }}</a-button><a-select v-model:value="subIndicators[0]" size="small" style="width: 110px" :options="KLINE_SUB_INDICATOR_OPTIONS" /></a-space></template><StockKlineChart :bars="bars" :chanlun="chanlun" :height="680" :loading="loading" :moving-averages="movingAverages" :sub-indicators="subIndicators" /></a-card>
    <a-card size="small" title="当前结构"><a-descriptions :column="{ xs: 1, sm: 2, md: 4 }" bordered size="small"><a-descriptions-item label="状态">{{ chanlun?.availability || '待确认' }}</a-descriptions-item><a-descriptions-item label="方向">{{ chanlun?.strokes.at(-1)?.direction || '--' }}</a-descriptions-item><a-descriptions-item label="最新信号">{{ chanlun?.signals.at(-1)?.type || '--' }}</a-descriptions-item><a-descriptions-item label="背驰">{{ chanlun?.divergences.at(-1)?.type || '--' }}</a-descriptions-item></a-descriptions></a-card>
  </div>
</template>
