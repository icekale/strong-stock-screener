<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useThemeStore } from '@/store/modules/theme';
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
import type { WorkbenchMetric } from '@/components/common/workbench/workbench';

defineOptions({ name: 'ChanlunView' });

const route = useRoute();
const router = useRouter();
const themeStore = useThemeStore();
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
const latestZone = computed(() => analysis.value?.zones.at(-1) ?? null);
const latestDivergence = computed(() => analysis.value?.divergences.at(-1) ?? null);
const latestSignal = computed(() => analysis.value?.signals.at(-1) ?? null);
const chanlunMetrics = computed<WorkbenchMetric[]>(() => [
  {
    key: 'availability',
    label: '结构状态',
    value: availabilityLabel(analysis.value?.availability),
    tone: availabilityTone(analysis.value?.availability),
    helper: analysis.value?.last_closed_bar_at ? `收盘 ${analysis.value.last_closed_bar_at}` : '等待分析'
  },
  {
    key: 'zones',
    label: '中枢',
    value: analysis.value?.zones.length ?? '--',
    helper: latestZone.value ? `${formatPrice(latestZone.value.low)} - ${formatPrice(latestZone.value.high)}` : '暂无中枢'
  },
  {
    key: 'divergences',
    label: '背驰',
    value: analysis.value?.divergences.length ?? '--',
    helper: latestDivergence.value ? divergenceLabel(latestDivergence.value.type) : '暂无背驰'
  },
  {
    key: 'signals',
    label: '最新信号',
    value: latestSignal.value ? signalLabel(latestSignal.value.type) : '--',
    tone: latestSignal.value ? statusTone(latestSignal.value.status) : 'neutral',
    helper: latestSignal.value ? `${statusLabel(latestSignal.value.status)} · ${formatPrice(latestSignal.value.price)}` : '暂无买卖点'
  }
]);

const signalTypeLabels: Record<string, string> = {
  one_buy: '一买',
  one_sell: '一卖',
  two_buy: '二买',
  two_sell: '二卖',
  three_buy: '三买',
  three_sell: '三卖'
};
const divergenceTypeLabels: Record<string, string> = { top: '顶背驰', bottom: '底背驰', consolidation: '盘整背驰' };
const availabilityLabels: Record<string, string> = {
  ready: '可用',
  backfilling: '回补中',
  insufficient_bars: '数据不足',
  stale: '已过期',
  unavailable: '不可用'
};
const paperOrderStatusLabels: Record<string, string> = {
  draft: '草案',
  awaiting_confirmation: '待人工确认',
  simulated_open: '待模拟成交',
  filled: '已成交',
  rejected: '已拒绝',
  expired: '已过期',
  cancelled: '已取消'
};

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

function periodLabel(value: ChanlunPeriod) {
  return periods.find(item => item.value === value)?.label || value;
}

function formatPrice(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '--';
}

function availabilityLabel(value: string | null | undefined) {
  return value ? availabilityLabels[value] || value : '--';
}

function availabilityTone(value: string | null | undefined) {
  if (value === 'ready') return 'success';
  if (value === 'unavailable' || value === 'insufficient_bars') return 'error';
  if (value === 'backfilling' || value === 'stale') return 'warning';
  return 'neutral';
}

function availabilityTagTone(value: string | null | undefined) {
  if (value === 'ready') return 'success';
  if (value === 'unavailable' || value === 'insufficient_bars') return 'failed';
  if (value === 'backfilling' || value === 'stale') return 'partial';
  return 'neutral';
}

function signalLabel(value: string) {
  return signalTypeLabels[value] || value;
}

function divergenceLabel(value: string) {
  return divergenceTypeLabels[value] || value;
}

function statusLabel(value: string) {
  return { observing: '观察', provisional: '待确认', confirmed: '已确认', final: '最终' }[value] || value;
}

function statusTone(value: string) {
  if (value === 'confirmed' || value === 'final') return 'success';
  if (value === 'provisional') return 'warning';
  return 'neutral';
}

function statusTagTone(value: string) {
  if (value === 'confirmed' || value === 'final') return 'success';
  if (value === 'provisional') return 'partial';
  return 'neutral';
}

function paperOrderStatusLabel(value: string) {
  return paperOrderStatusLabels[value] || value;
}

function paperOrderStatusTone(value: string) {
  if (value === 'filled' || value === 'simulated_open') return 'success';
  if (value === 'awaiting_confirmation') return 'partial';
  if (value === 'rejected' || value === 'expired' || value === 'cancelled') return 'failed';
  return 'running';
}

onMounted(() => { void loadWorkspace(); void loadAccount(); });
watch(() => route.query.symbol, value => { if (value && value !== symbol.value) { symbol.value = String(value); symbolInput.value = symbol.value; void loadWorkspace(); } });
</script>

<template>
  <div class="space-y-16px pb-24px" :class="{ 'chanlun-view--footer-safe': themeStore.footer.fixed }">
    <PageHeader title="缠论工作台" :description="`${name} · ${symbol} · 结构、背驰与人工确认模拟盘`">
      <template #meta>{{ periodLabel(period) }} · {{ availabilityLabel(analysis?.availability) }}</template>
      <a-input v-model:value="symbolInput" class="chanlun-symbol-input" placeholder="输入股票代码" @press-enter="applySymbol" />
      <a-button type="primary" @click="applySymbol">
        <icon-ic-round-search />
        加载
      </a-button>
      <a-segmented :value="period" size="small" :options="periods" @change="value => changePeriod(value as ChanlunPeriod)" />
    </PageHeader>

    <a-alert v-if="error" :message="error" show-icon type="warning" />
    <MetricStrip :items="chanlunMetrics" />

    <section class="chanlun-chart-panel border border-border rounded-6px bg-container p-12px">
      <SectionHeader title="结构图" :source="analysis?.rule_version || '缠论引擎'" :updated-at="analysis?.calculated_at" />
      <div class="chanlun-control-strip">
        <div class="chanlun-control-group chanlun-control-group--layers">
          <span class="chanlun-control-label">层级</span>
          <a-checkbox v-for="key in Object.keys(layerLabels) as ChanlunLayerKey[]" :key="key" v-model:checked="layers[key]">{{ layerLabels[key] }}</a-checkbox>
        </div>
        <div class="chanlun-control-group">
          <span class="chanlun-control-label">均线</span>
          <a-switch v-model:checked="showMovingAverages" size="small" />
          <a-button v-for="item in [{ label: 'MA5', value: 'ma5' }, { label: 'MA20', value: 'ma20' }, { label: 'MA60', value: 'ma60' }]" :key="item.value" size="small" :type="movingAverages.includes(item.value as KlineMovingAverage) ? 'primary' : 'default'" @click="toggleAverage(item.value as KlineMovingAverage)">{{ item.label }}</a-button>
        </div>
        <div class="chanlun-control-group">
          <span class="chanlun-control-label">副图</span>
          <a-select v-model:value="subIndicators[0]" size="small" class="chanlun-indicator-select" :options="KLINE_SUB_INDICATOR_OPTIONS" />
        </div>
      </div>
      <div class="chanlun-chart-frame">
        <StockKlineChart :bars="chartBars" :chanlun="analysis" :chanlun-layers="layers" :height="720" :loading="loading" :moving-averages="showMovingAverages ? movingAverages : []" :period="period" :sub-indicators="subIndicators" :symbol="symbol" />
      </div>
    </section>

    <div class="chanlun-analysis-grid">
      <section class="chanlun-panel border border-border rounded-6px bg-container p-12px">
        <SectionHeader title="信号列表" :source="analysis?.rule_version || '结构信号'" />
        <a-list :data-source="[...(analysis?.signals ?? [])].reverse().slice(0, 8)" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div class="chanlun-signal-row">
                <div class="chanlun-signal-row__main">
                  <div class="flex flex-wrap items-center gap-8px">
                    <strong>{{ signalLabel(item.type) }}</strong>
                    <StatusTag :status="statusTagTone(item.status)" />
                    <span class="text-12px text-text-secondary">{{ statusLabel(item.status) }}</span>
                  </div>
                  <div class="mt-4px text-12px text-text-secondary">{{ item.occurred_at }} · 规则 {{ item.rule_version }}</div>
                </div>
                <div class="chanlun-signal-row__price">
                  <strong>{{ formatPrice(item.price) }}</strong>
                  <span v-if="item.divergence_id" class="text-12px text-text-secondary">关联背驰</span>
                </div>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-if="!analysis?.signals.length" description="暂无买卖点" />
      </section>

      <section class="chanlun-panel border border-border rounded-6px bg-container p-12px">
        <SectionHeader title="结构证据" :source="analysis?.adjustment_mode || '复权方式待确认'" />
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="最新中枢">
            {{ latestZone ? `${formatPrice(latestZone.low)} - ${formatPrice(latestZone.high)} · ${statusLabel(latestZone.status)}` : '暂无中枢' }}
          </a-descriptions-item>
          <a-descriptions-item label="最新背驰">
            {{ latestDivergence ? `${divergenceLabel(latestDivergence.type)} · ${statusLabel(latestDivergence.status)} · ${latestDivergence.occurred_at}` : '暂无背驰' }}
          </a-descriptions-item>
          <a-descriptions-item label="最新方向">{{ analysis?.strokes.at(-1)?.direction || '--' }}</a-descriptions-item>
          <a-descriptions-item label="最后闭合 K 线">{{ analysis?.last_closed_bar_at || '--' }}</a-descriptions-item>
        </a-descriptions>
      </section>

      <section class="chanlun-panel chanlun-paper-panel border border-border rounded-6px bg-container p-12px">
        <SectionHeader title="人工确认模拟盘" source="纸面账户">
          <StatusTag v-if="order" :status="paperOrderStatusTone(order.status)" />
        </SectionHeader>
        <a-alert v-if="paperError" class="mt-12px" :message="paperError" show-icon type="warning" />
        <div v-if="account" class="chanlun-account-grid mt-12px">
          <div><span>可用资金</span><strong>{{ account.available_cash.toFixed(2) }}</strong></div>
          <div><span>总权益</span><strong>{{ account.total_equity.toFixed(2) }}</strong></div>
        </div>
        <div class="chanlun-order-controls">
          <a-input-number v-model:value="paperQuantity" :min="100" :step="100" addon-before="数量" />
          <a-button :loading="loading" @click="createDraft">
            <icon-carbon-document-add />
            生成草案
          </a-button>
        </div>
        <div v-if="order" class="chanlun-order-status">
          <div class="flex flex-wrap items-start justify-between gap-8px">
            <div>
              <strong>{{ paperOrderStatusLabel(order.status) }}</strong>
              <div class="mt-4px text-12px text-text-secondary">订单 {{ order.id }} · {{ order.quantity }} 股 · 参考价 {{ formatPrice(order.reference_price) }}</div>
            </div>
            <StatusTag :status="paperOrderStatusTone(order.status)" />
          </div>
          <ul v-if="order.reasons.length" class="chanlun-order-reasons">
            <li v-for="reason in order.reasons" :key="reason">{{ reason }}</li>
          </ul>
          <div v-else class="mt-8px text-12px text-text-secondary">等待人工确认</div>
          <div class="chanlun-order-actions">
            <a-button :disabled="order.status !== 'awaiting_confirmation'" type="primary" @click="approveOrder">
              <icon-ic-round-check />
              人工确认
            </a-button>
            <a-button :disabled="order.status !== 'simulated_open'" @click="fillOrder">
              <icon-carbon-play />
              模拟成交
            </a-button>
          </div>
        </div>
      </section>
    </div>

    <section class="chanlun-panel border border-border rounded-6px bg-container p-12px">
      <SectionHeader title="周期状态" source="缠论工作区" />
      <a-list :data-source="availablePeriods" size="small">
        <template #renderItem="{ item }">
          <a-list-item>
            <div class="chanlun-period-row">
              <strong>{{ periodLabel(item.period) }}</strong>
              <div class="flex flex-wrap items-center gap-8px">
                <StatusTag :status="availabilityTagTone(item.availability)" />
                <span class="text-12px text-text-secondary">{{ availabilityLabel(item.availability) }} · {{ item.latest_signal_type ? signalLabel(item.latest_signal_type) : '无信号' }} · {{ item.latest_divergence_type ? divergenceLabel(item.latest_divergence_type) : '无背驰' }}</span>
              </div>
            </div>
          </a-list-item>
        </template>
      </a-list>
      <a-empty v-if="!availablePeriods.length" description="周期状态待确认" />
    </section>
  </div>
</template>

<style scoped>
.chanlun-symbol-input {
  width: 150px;
}

.chanlun-control-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  margin: 12px 0;
  padding: 10px;
  background: var(--wb-primary-soft);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.chanlun-control-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.chanlun-control-group--layers {
  flex: 1 1 360px;
}

.chanlun-control-label {
  color: var(--wb-muted);
  font-size: 12px;
  white-space: nowrap;
}

.chanlun-indicator-select {
  width: 112px;
}

.chanlun-chart-frame {
  min-height: 720px;
  overflow: hidden;
}

.chanlun-analysis-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(260px, 0.75fr);
  gap: 12px;
}

.chanlun-paper-panel {
  grid-column: 1 / -1;
}

.chanlun-signal-row,
.chanlun-period-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

.chanlun-signal-row__main,
.chanlun-signal-row__price {
  min-width: 0;
}

.chanlun-signal-row__price {
  flex: 0 0 auto;
  text-align: right;
}

.chanlun-signal-row__price span {
  display: block;
  margin-top: 4px;
}

.chanlun-account-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.chanlun-account-grid div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.chanlun-account-grid span {
  color: var(--wb-muted);
  font-size: 12px;
}

.chanlun-account-grid strong {
  font-variant-numeric: tabular-nums;
}

.chanlun-order-controls,
.chanlun-order-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.chanlun-order-status {
  margin-top: 12px;
  padding: 12px;
  background: var(--wb-primary-soft);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.chanlun-order-reasons {
  margin: 10px 0 0;
  padding-left: 18px;
  color: var(--wb-ink);
  font-size: 13px;
  line-height: 1.6;
}

.chanlun-view--footer-safe {
  padding-bottom: calc(var(--soy-footer-height, 48px) + 24px);
}

@media (max-width: 1199px) {
  .chanlun-analysis-grid {
    grid-template-columns: 1fr;
  }

  .chanlun-paper-panel {
    grid-column: auto;
  }
}

@media (max-width: 767px) {
  .chanlun-symbol-input {
    width: min(100%, 240px);
  }

  .chanlun-control-group,
  .chanlun-control-group--layers {
    flex: 1 1 100%;
  }

  .chanlun-chart-frame {
    min-height: 520px;
  }

  .chanlun-signal-row,
  .chanlun-period-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .chanlun-signal-row__price {
    text-align: left;
  }
}
</style>
