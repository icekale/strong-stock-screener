<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  approveChanlunPaperOrder,
  createChanlunPaperOrderDraft,
  fillChanlunPaperOrder,
  getChanlunAnalysis,
  getChanlunPaperAccount,
  getChanlunWorkspace
} from '@/service/product-api';
import type { ChanlunAnalysisResponse, ChanlunLayerKey, ChanlunPaperAccount, ChanlunPaperOrder, ChanlunPeriod, ChanlunWorkspaceResponse } from '@/service/types';
import StockKlineChart from '@/components/charts/StockKlineChart.vue';
import { KLINE_SUB_INDICATOR_OPTIONS, type KlineMovingAverage, type KlineSubIndicator } from '@/utils/charts/klineIndicatorLayout';

defineOptions({ name: 'ChanlunView' });

const route = useRoute();
const router = useRouter();
const symbol = ref(String(route.query.symbol || '600000.SH'));
const symbolInput = ref(symbol.value);
const name = computed(() => String(route.query.name || symbol.value));
const period = ref<ChanlunPeriod>('1d');
const workspace = ref<ChanlunWorkspaceResponse | null>(null);
const analysis = ref<ChanlunAnalysisResponse | null>(null);
const account = ref<ChanlunPaperAccount | null>(null);
const order = ref<ChanlunPaperOrder | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const paperError = ref<string | null>(null);
const layers = reactive<Partial<Record<ChanlunLayerKey, boolean>>>({ zones: true, strokes: true, segments: true, divergences: true, signals: true, fractals: false });
const showMovingAverages = ref(false);
const movingAverages = ref<KlineMovingAverage[]>([]);
const subIndicators = ref<KlineSubIndicator[]>(['volume']);
const paperQuantity = ref(100);

const periods = [
  { label: '日线', value: '1d' },
  { label: '60 分钟', value: '60m' },
  { label: '30 分钟', value: '30m' },
  { label: '5 分钟', value: '5m' }
];
const layerLabels: Record<ChanlunLayerKey, string> = { zones: '中枢', strokes: '笔', segments: '线段', divergences: '背驰', signals: '买卖点', fractals: '分型' };

const chartBars = computed(() => analysis.value?.bars ?? workspace.value?.analysis.bars ?? []);
const availablePeriods = computed(() => workspace.value?.periods ?? []);

async function loadWorkspace() {
  loading.value = true;
  error.value = null;
  try {
    workspace.value = await getChanlunWorkspace(symbol.value);
    analysis.value = workspace.value.analysis;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取缠论工作台失败';
  } finally {
    loading.value = false;
  }
}

async function changePeriod(value: ChanlunPeriod) {
  period.value = value;
  if (!symbol.value) return;
  loading.value = true;
  try {
    analysis.value = await getChanlunAnalysis(symbol.value, { period: value, lookback: 220, includeObserving: true });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取缠论周期分析失败';
  } finally {
    loading.value = false;
  }
}

function applySymbol() {
  const next = symbolInput.value.trim().toUpperCase();
  if (!next) return;
  symbol.value = next;
  void router.replace({ query: { ...route.query, symbol: next } });
  void loadWorkspace();
}

async function loadAccount() {
  try { account.value = await getChanlunPaperAccount(); } catch (cause) { paperError.value = cause instanceof Error ? cause.message : '读取模拟账户失败'; }
}

async function createDraft() {
  paperError.value = null;
  try { order.value = await createChanlunPaperOrderDraft(symbol.value, { quantity: paperQuantity.value, lookback: 220 }); await loadAccount(); } catch (cause) { paperError.value = cause instanceof Error ? cause.message : '创建模拟订单失败'; }
}

async function approveOrder() {
  if (!order.value) return;
  try { order.value = await approveChanlunPaperOrder(order.value.id); await loadAccount(); } catch (cause) { paperError.value = cause instanceof Error ? cause.message : '确认模拟订单失败'; }
}

async function fillOrder() {
  if (!order.value) return;
  try { order.value = await fillChanlunPaperOrder(order.value.id); await loadAccount(); } catch (cause) { paperError.value = cause instanceof Error ? cause.message : '模拟成交失败'; }
}

function toggleAverage(value: KlineMovingAverage) {
  movingAverages.value = movingAverages.value.includes(value) ? movingAverages.value.filter(item => item !== value) : [...movingAverages.value, value];
}

onMounted(() => { void loadWorkspace(); void loadAccount(); });
watch(() => route.query.symbol, value => { if (value && value !== symbol.value) { symbol.value = String(value); symbolInput.value = symbol.value; void loadWorkspace(); } });
</script>

<template>
  <div class="space-y-16px">
    <div class="flex flex-wrap items-center justify-between gap-12px"><div><div class="text-22px font-700 text-text-primary">缠论工作台</div><div class="mt-4px text-13px text-text-secondary">结构、背驰、买卖点与人工确认模拟盘</div></div><a-space><a-input v-model:value="symbolInput" style="width: 150px" placeholder="输入股票代码" @press-enter="applySymbol" /><a-button type="primary" @click="applySymbol">加载</a-button></a-space></div>
    <a-alert v-if="error" :message="error" show-icon type="warning" />
    <a-card size="small"><template #title><a-space><span>{{ name }} · {{ symbol }}</span><a-segmented :value="period" size="small" :options="periods" @change="value => changePeriod(value as ChanlunPeriod)" /></a-space></template><template #extra><a-space wrap><a-switch v-model:checked="showMovingAverages" size="small" /><span class="text-12px">均线</span><a-button v-for="item in [{ label: 'MA5', value: 'ma5' }, { label: 'MA20', value: 'ma20' }, { label: 'MA60', value: 'ma60' }]" :key="item.value" size="small" :type="movingAverages.includes(item.value as KlineMovingAverage) ? 'primary' : 'default'" @click="toggleAverage(item.value as KlineMovingAverage)">{{ item.label }}</a-button><a-select v-model:value="subIndicators[0]" size="small" style="width: 100px" :options="KLINE_SUB_INDICATOR_OPTIONS" /><a-checkbox v-for="key in Object.keys(layerLabels) as ChanlunLayerKey[]" :key="key" v-model:checked="layers[key]">{{ layerLabels[key] }}</a-checkbox></a-space></template><StockKlineChart :bars="chartBars" :chanlun="analysis" :chanlun-layers="layers" :height="720" :loading="loading" :moving-averages="showMovingAverages ? movingAverages : []" :sub-indicators="subIndicators" /></a-card>

    <a-row :gutter="12"><a-col :xs="24" :xl="14"><a-card size="small" title="结构信号"><a-row :gutter="12"><a-col :xs="12" :sm="6"><a-statistic title="可用性" :value="analysis?.availability ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="中枢" :value="analysis?.zones.length ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="背驰" :value="analysis?.divergences.length ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="信号" :value="analysis?.signals.length ?? '--'" /></a-col></a-row><a-divider /><a-list :data-source="[...(analysis?.signals ?? [])].reverse().slice(0, 8)" size="small"><template #renderItem="{ item }"><a-list-item><a-list-item-meta :title="item.type" :description="`${item.occurred_at} · ${item.status} · ${item.rule_version}`" /><template #extra><span>{{ item.price.toFixed(2) }}</span></template></a-list-item></template></a-list><a-empty v-if="!analysis?.signals.length" description="暂无买卖点" /></a-card></a-col><a-col :xs="24" :xl="10"><a-card size="small" title="人工确认模拟盘"><a-alert v-if="paperError" :message="paperError" show-icon type="warning" /><a-descriptions v-if="account" :column="2" size="small"><a-descriptions-item label="可用资金">{{ account.available_cash.toFixed(2) }}</a-descriptions-item><a-descriptions-item label="总权益">{{ account.total_equity.toFixed(2) }}</a-descriptions-item></a-descriptions><a-space wrap class="mt-12px"><a-input-number v-model:value="paperQuantity" :min="100" :step="100" addon-before="数量" /><a-button :loading="loading" @click="createDraft">生成草案</a-button></a-space><a-alert v-if="order" class="mt-12px" :message="`订单 ${order.id} · ${order.status}`" :description="order.reasons.join('；') || '等待人工确认'" show-icon type="info" /><a-space v-if="order" class="mt-8px"><a-button :disabled="order.status !== 'awaiting_confirmation'" type="primary" @click="approveOrder">人工确认</a-button><a-button :disabled="order.status !== 'simulated_open'" @click="fillOrder">模拟成交</a-button></a-space></a-card></a-col></a-row>

    <a-card size="small" title="周期状态"><a-list :data-source="availablePeriods" size="small"><template #renderItem="{ item }"><a-list-item><span>{{ item.period }}</span><a-space><a-tag>{{ item.availability }}</a-tag><span class="text-12px text-text-secondary">{{ item.latest_signal_type || '无信号' }} · {{ item.latest_divergence_type || '无背驰' }}</span></a-space></a-list-item></template></a-list><a-empty v-if="!availablePeriods.length" description="周期状态待确认" /></a-card>
  </div>
</template>
