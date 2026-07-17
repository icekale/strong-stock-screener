<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  getChanlunAnalysis,
  getLatestScreenRun,
  getStockKline,
  getStockQuote,
  getStockResearch
} from '@/service/product-api';
import type {
  ChanlunAnalysisResponse,
  ChanlunLayerKey,
  GsgfChartAnnotation,
  KlineBar,
  StockKlinePeriod,
  StockKlineResponse,
  StockQuoteResponse,
  StockResearchResponse,
  StrongStockScreeningItem
} from '@/service/types';
import StockKlineChart from '@/components/charts/StockKlineChart.vue';
import {
  KLINE_SUB_INDICATOR_OPTIONS,
  updateKlineSubIndicator,
  updateKlineSubPaneCount,
  type KlineIndicatorState,
  type KlineMovingAverage,
  type KlineSubIndicator,
  type KlineSubPaneCount
} from '@/utils/charts/klineIndicatorLayout';
import { aggregateWeeklyBars } from '@/utils/charts/klinePeriod';
import { getVisibleGsgfAnnotations } from '@/utils/charts/klineOverlayOption';
import {
  buildStockKlineQuery,
  buildStockViewDefaults,
  calculateCompleteMovingAverage,
  isLatestStockRequest,
  KLINE_INDICATOR_STORAGE_KEY,
  nextStockRequestId,
  parseIndicatorState,
  serializeIndicatorState
} from '@/utils/domain/stockViewState';

defineOptions({ name: 'StockView' });

type StockViewPeriod = StockKlinePeriod | 'weekly';
type StockContentTab = 'chart' | 'info' | 'strategy' | 'concept';

const route = useRoute();
const router = useRouter();
const symbol = computed(() => String(route.params.symbol || ''));
const name = computed(() => String(route.query.name || symbol.value));
const industry = computed(() => String(route.query.industry || '行业待补'));
const displayName = computed(() => quote.value?.name || name.value);
const displayIndustry = computed(() => quote.value?.industry || industry.value);

const period = ref<StockViewPeriod>('1d');
const activeTab = ref<StockContentTab>('chart');
const kline = ref<StockKlineResponse | null>(null);
const quote = ref<StockQuoteResponse | null>(null);
const chanlun = ref<ChanlunAnalysisResponse | null>(null);
const research = ref<StockResearchResponse | null>(null);
const screenItems = ref<StrongStockScreeningItem[]>([]);

const klineLoading = ref(false);
const quoteLoading = ref(false);
const chanlunLoading = ref(false);
const researchLoading = ref(false);
const screenLoading = ref(false);
const klineError = ref<string | null>(null);
const quoteError = ref<string | null>(null);
const chanlunError = ref<string | null>(null);
const researchError = ref<string | null>(null);
const screenError = ref<string | null>(null);

const defaults = buildStockViewDefaults();
const movingAverages = ref<KlineMovingAverage[]>([...defaults.visibleMovingAverages]);
const indicatorState = ref<KlineIndicatorState>(parseIndicatorState(null));
const indicatorStateLoaded = ref(false);
const showGsgf = ref(true);
const showChanlun = ref(true);
const researchRequested = ref(false);
const screenRequested = ref(false);

const periodOptions: Array<{ label: string; value: StockViewPeriod }> = [
  { label: '日线', value: '1d' },
  { label: '周线', value: 'weekly' },
  { label: '60 分钟', value: '60m' },
  { label: '30 分钟', value: '30m' },
  { label: '5 分钟', value: '5m' }
];
const contentTabs: Array<{ key: StockContentTab; label: string }> = [
  { key: 'chart', label: 'K 线' },
  { key: 'info', label: '信息' },
  { key: 'strategy', label: '战法' },
  { key: 'concept', label: '概念' }
];
const movingAverageOptions: Array<{ label: string; value: KlineMovingAverage }> = [
  { label: 'MA5', value: 'ma5' },
  { label: 'MA10', value: 'ma10' },
  { label: 'MA20', value: 'ma20' },
  { label: 'MA60', value: 'ma60' }
];
const gsgfModelConditions = [
  '20日内有涨停，优先强势板块和高辨识度个股。',
  '趋势优先，股价在关键均线上方，尤其关注200日新高。',
  'K线红肥绿瘦，上涨放量饱满，缩量回踩不破趋势。',
  '放量上涨继续跟踪，放量滞涨或实体阴线降低评级。',
  '买绿不买红，卖红不卖绿；不冲高不卖，不跳水不买。',
  '5日线拐头向下、跌破均线、断板未修复时触发空仓纪律。'
];
const chanlunLayers: Partial<Record<ChanlunLayerKey, boolean>> = {
  fractals: false,
  segments: true,
  strokes: false,
  zones: true,
  divergences: true,
  signals: true
};

const requestPeriod = computed<StockKlinePeriod>(() => (period.value === 'weekly' ? '1d' : period.value));
const chartBars = computed(() => {
  const sourceBars = kline.value?.bars ?? [];
  const displayedBars = period.value === 'weekly' ? aggregateWeeklyBars(sourceBars) : sourceBars;
  return period.value === 'weekly' ? displayedBars : withMovingAverages(displayedBars);
});
const latestBar = computed(() => chartBars.value.at(-1) ?? null);
const currentCandidate = computed(() => screenItems.value.find(item => item.symbol === symbol.value) ?? null);
const gsgfAnnotations = computed(() => kline.value?.gsgf_annotations ?? []);
const gsgfSupported = computed(() => period.value === '1d' && gsgfAnnotations.value.length > 0);
const chartGsgfAnnotations = computed(() => getVisibleGsgfAnnotations(requestPeriod.value, period.value === '1d' && showGsgf.value, gsgfAnnotations.value));
const chanlunForPeriod = computed(() => {
  if (period.value === 'weekly' || chanlun.value?.period !== requestPeriod.value) return null;
  return chanlun.value;
});
const chanlunSupported = computed(() => chanlunForPeriod.value != null && chanlunForPeriod.value.availability !== 'unavailable');
const chartChanlun = computed(() => (showChanlun.value ? chanlunForPeriod.value : null));
const chanlunStatus = computed(() => {
  if (chanlunLoading.value) return '读取中';
  if (chanlunError.value) return '暂不可用';
  if (chanlunSupported.value) return chanlunForPeriod.value?.availability || '可用';
  return '结构待确认';
});

let stockRequestId = 0;
let researchRequestId = 0;
let screenRequestId = 0;

function loadStockData() {
  const currentSymbol = symbol.value;
  if (!currentSymbol) return;

  const currentPeriod = period.value;
  const requestId = nextStockRequestId(stockRequestId);
  stockRequestId = requestId;
  const query = buildStockKlineQuery({ period: requestPeriod.value, count: 220 });

  klineLoading.value = true;
  quoteLoading.value = true;
  chanlunLoading.value = true;
  klineError.value = null;
  quoteError.value = null;
  chanlunError.value = null;

  void getStockKline(currentSymbol, query.kline)
    .then(response => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) kline.value = response;
    })
    .catch(cause => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) klineError.value = toErrorMessage(cause, `${periodLabel(currentPeriod)} K线读取失败`);
    })
    .finally(() => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) klineLoading.value = false;
    });

  void getStockQuote(currentSymbol)
    .then(response => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) quote.value = response;
    })
    .catch(cause => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) quoteError.value = toErrorMessage(cause, '实时行情读取失败');
    })
    .finally(() => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) quoteLoading.value = false;
    });

  void getChanlunAnalysis(currentSymbol, query.chanlun)
    .then(response => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) chanlun.value = response;
    })
    .catch(cause => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) chanlunError.value = toErrorMessage(cause, `${periodLabel(currentPeriod)} 缠论分析读取失败`);
    })
    .finally(() => {
      if (isCurrentStockRequest(requestId, currentSymbol, currentPeriod)) chanlunLoading.value = false;
    });
}

function isCurrentStockRequest(requestId: number, currentSymbol: string, currentPeriod: StockViewPeriod) {
  return isLatestStockRequest(requestId, stockRequestId) && currentSymbol === symbol.value && currentPeriod === period.value;
}

async function loadResearch() {
  const currentSymbol = symbol.value;
  if (!currentSymbol || researchRequested.value || researchLoading.value) return;
  const requestId = nextStockRequestId(researchRequestId);
  researchRequestId = requestId;
  researchLoading.value = true;
  researchError.value = null;
  try {
    const response = await getStockResearch(currentSymbol);
    if (isLatestStockRequest(requestId, researchRequestId) && currentSymbol === symbol.value) {
      research.value = response;
      researchRequested.value = true;
    }
  } catch (cause) {
    if (isLatestStockRequest(requestId, researchRequestId) && currentSymbol === symbol.value) {
      researchError.value = toErrorMessage(cause, '个股研究读取失败');
    }
  } finally {
    if (isLatestStockRequest(requestId, researchRequestId) && currentSymbol === symbol.value) researchLoading.value = false;
  }
}

async function loadScreenRun() {
  const currentSymbol = symbol.value;
  if (!currentSymbol || screenRequested.value || screenLoading.value) return;
  const requestId = nextStockRequestId(screenRequestId);
  screenRequestId = requestId;
  screenLoading.value = true;
  screenError.value = null;
  try {
    const response = await getLatestScreenRun();
    if (isLatestStockRequest(requestId, screenRequestId) && currentSymbol === symbol.value) {
      screenItems.value = response.items;
      screenRequested.value = true;
    }
  } catch (cause) {
    if (isLatestStockRequest(requestId, screenRequestId) && currentSymbol === symbol.value) {
      screenError.value = toErrorMessage(cause, '选股结果读取失败');
    }
  } finally {
    if (isLatestStockRequest(requestId, screenRequestId) && currentSymbol === symbol.value) screenLoading.value = false;
  }
}

function ensureContentData(tab: StockContentTab) {
  if (tab !== 'chart') void loadResearch();
  if (tab === 'strategy' || tab === 'concept') void loadScreenRun();
}

function resetSymbolState() {
  stockRequestId = nextStockRequestId(stockRequestId);
  researchRequestId = nextStockRequestId(researchRequestId);
  screenRequestId = nextStockRequestId(screenRequestId);
  kline.value = null;
  quote.value = null;
  chanlun.value = null;
  research.value = null;
  screenItems.value = [];
  researchRequested.value = false;
  screenRequested.value = false;
  klineError.value = null;
  quoteError.value = null;
  chanlunError.value = null;
  researchError.value = null;
  screenError.value = null;
  klineLoading.value = false;
  quoteLoading.value = false;
  chanlunLoading.value = false;
  researchLoading.value = false;
  screenLoading.value = false;
  showGsgf.value = true;
  showChanlun.value = true;
}

function setPeriod(value: StockViewPeriod) {
  if (value !== period.value) period.value = value;
}

function toggleAverage(value: KlineMovingAverage) {
  movingAverages.value = movingAverages.value.includes(value)
    ? movingAverages.value.filter(item => item !== value)
    : [...movingAverages.value, value];
}

function changeSubPaneCount(paneCount: KlineSubPaneCount) {
  indicatorState.value = updateKlineSubPaneCount(indicatorState.value, paneCount);
}

function changeSubIndicator(index: number, indicator: KlineSubIndicator) {
  indicatorState.value = updateKlineSubIndicator(indicatorState.value, index, indicator);
}

function openChanlun() {
  void router.push({ path: '/chanlun', query: { symbol: symbol.value, name: name.value, industry: industry.value } });
}

function formatPct(value: number | null | undefined) {
  return typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(2)}%` : '--';
}

function formatPrice(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '--';
}

function formatAmount(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return value >= 100_000_000 ? `${(value / 100_000_000).toFixed(2)}亿` : value.toLocaleString('zh-CN');
}

function formatMarketCap(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return `${(value / 100_000_000).toFixed(2)}亿`;
}

function formatResearchValue(value: unknown): string {
  if (value == null) return '--';
  if (typeof value === 'string') return value || '--';
  if (typeof value === 'number') return Number.isFinite(value) ? value.toLocaleString('zh-CN') : '--';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (Array.isArray(value)) return value.map(formatResearchValue).filter(item => item !== '--').join(' / ') || '--';
  return '--';
}

function pickResearchValue(keys: string[]) {
  const payloads = [research.value?.valuation, research.value?.financials, research.value?.profile];
  for (const payload of payloads) {
    if (!payload) continue;
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(payload, key)) {
        const value = formatResearchValue(payload[key]);
        if (value !== '--') return value;
      }
    }
  }
  return '--';
}

function comparePrice(price: number | null | undefined, target: number | null | undefined) {
  if (typeof price !== 'number' || typeof target !== 'number' || target === 0) return '--';
  const pct = ((price - target) / target) * 100;
  return `${pct >= 0 ? '上方' : '下方'} ${Math.abs(pct).toFixed(2)}%`;
}

function statusLabel(status: StrongStockScreeningItem['status'] | null | undefined) {
  if (status === 'focus') return '重点';
  if (status === 'wait_pullback') return '等回踩';
  if (status === 'reduce_risk') return '减仓';
  if (status === 'data_incomplete') return '缺数据';
  return '--';
}

function toErrorMessage(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback;
}

function periodLabel(value: StockViewPeriod) {
  return periodOptions.find(item => item.value === value)?.label || value;
}

function annotationColor(annotation: GsgfChartAnnotation) {
  if (annotation.severity === 'positive') return 'red';
  if (annotation.severity === 'warning') return 'orange';
  if (annotation.severity === 'danger') return 'green';
  return 'default';
}

function withMovingAverages(bars: KlineBar[]): KlineBar[] {
  const periods = [5, 10, 20, 60] as const;
  const averages = Object.fromEntries(periods.map(size => [`ma${size}`, calculateCompleteMovingAverage(bars.map(bar => bar.close), size)])) as Record<`ma${(typeof periods)[number]}`, Array<number | null>>;
  return bars.map((bar, index) => ({
    ...bar,
    ma5: index >= 4 ? bar.ma5 ?? averages.ma5[index] ?? null : null,
    ma10: index >= 9 ? bar.ma10 ?? averages.ma10[index] ?? null : null,
    ma20: index >= 19 ? bar.ma20 ?? averages.ma20[index] ?? null : null,
    ma60: index >= 59 ? bar.ma60 ?? averages.ma60[index] ?? null : null
  }));
}

watch(
  [symbol, period],
  ([nextSymbol], previousValue) => {
    const previousSymbol = previousValue?.[0];
    if (nextSymbol !== previousSymbol) resetSymbolState();
    void loadStockData();
    if (nextSymbol !== previousSymbol) ensureContentData(activeTab.value);
  },
  { immediate: true }
);
watch(activeTab, value => ensureContentData(value));
function persistIndicatorState() {
  if (indicatorStateLoaded.value && typeof window !== 'undefined') {
    window.localStorage.setItem(KLINE_INDICATOR_STORAGE_KEY, serializeIndicatorState({
      visibleMovingAverages: movingAverages.value,
      paneCount: indicatorState.value.paneCount,
      subIndicators: indicatorState.value.subIndicators
    }));
  }
}

watch(movingAverages, persistIndicatorState, { deep: true });
watch(indicatorState, persistIndicatorState, { deep: true });

onMounted(() => {
  if (typeof window !== 'undefined') {
    const storedState = parseIndicatorState(window.localStorage.getItem(KLINE_INDICATOR_STORAGE_KEY));
    movingAverages.value = [...storedState.visibleMovingAverages];
    indicatorState.value = { paneCount: storedState.paneCount, subIndicators: [...storedState.subIndicators] };
  }
  indicatorStateLoaded.value = true;
});
</script>

<template>
  <div class="space-y-16px pb-24px">
    <div class="flex flex-wrap items-center justify-between gap-12px">
      <div>
        <div class="text-22px font-700 text-text-primary">{{ displayName }}</div>
        <div class="mt-4px text-13px text-text-secondary">{{ symbol }} · {{ displayIndustry }}</div>
      </div>
      <a-space>
        <a-button @click="openChanlun">打开缠论工作台</a-button>
        <a-button @click="router.back">返回</a-button>
      </a-space>
    </div>

    <a-alert v-if="quoteError" :message="`行情摘要：${quoteError}`" show-icon type="warning" />
    <a-row :gutter="12">
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="最新价" :value="quote?.last_price ?? '--'" :loading="quoteLoading" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="涨跌幅" :value="formatPct(quote?.pct_change)" :loading="quoteLoading" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="成交额" :value="formatAmount(quote?.turnover_cny)" :loading="quoteLoading" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="换手率" :value="quote?.turnover_rate == null ? '--' : `${quote.turnover_rate.toFixed(2)}%`" :loading="quoteLoading" /></a-card></a-col>
    </a-row>

    <a-card size="small">
      <template #title>
        <a-space wrap>
          <span>K 线与结构</span>
          <a-segmented :value="period" size="small" :options="periodOptions" @change="value => setPeriod(value as StockViewPeriod)" />
        </a-space>
      </template>
      <a-tabs v-model:activeKey="activeTab" size="small">
        <a-tab-pane v-for="tab in contentTabs" :key="tab.key" :tab="tab.label">
          <template v-if="tab.key === 'chart'">
            <div class="flex flex-wrap items-center justify-between gap-8px pb-12px">
              <a-space wrap>
                <a-button
                  v-for="item in movingAverageOptions"
                  :key="item.value"
                  size="small"
                  :type="movingAverages.includes(item.value) ? 'primary' : 'default'"
                  @click="toggleAverage(item.value)"
                >{{ item.label }}</a-button>
                <a-segmented :value="indicatorState.paneCount" size="small" :options="[1, 2, 3].map(value => ({ label: `${value}图`, value }))" @change="value => changeSubPaneCount(value as KlineSubPaneCount)" />
                <a-select
                  v-for="(indicator, index) in indicatorState.subIndicators"
                  :key="`${index}-${indicator}`"
                  size="small"
                  style="width: 112px"
                  :value="indicator"
                  :options="KLINE_SUB_INDICATOR_OPTIONS"
                  @change="value => changeSubIndicator(index, value as KlineSubIndicator)"
                />
              </a-space>
              <a-space wrap>
                <span class="text-12px text-text-secondary">GSGF</span>
                <a-switch v-model:checked="showGsgf" size="small" :disabled="!gsgfSupported" />
                <span class="text-12px text-text-secondary">缠论</span>
                <a-switch v-model:checked="showChanlun" size="small" :disabled="!chanlunSupported" />
                <span class="text-12px text-text-secondary">{{ chanlunStatus }}</span>
              </a-space>
            </div>
            <a-alert v-if="klineError" :message="`${periodLabel(period)} K线：${klineError}`" show-icon type="warning" />
            <a-alert v-if="chanlunError" class="mt-8px" :message="`${periodLabel(period)} 缠论：${chanlunError}`" show-icon type="warning" />
            <div v-if="gsgfSupported && showGsgf" class="mb-8px flex flex-wrap gap-6px">
              <a-tag v-for="(annotation, index) in gsgfAnnotations" :key="`${annotation.type}-${annotation.label}-${index}`" :color="annotationColor(annotation)">{{ annotation.label }}</a-tag>
            </div>
            <div class="min-h-720px overflow-hidden">
              <StockKlineChart
                :bars="chartBars"
                :chanlun="chartChanlun"
                :chanlun-layers="chanlunLayers"
                :gsgf-annotations="chartGsgfAnnotations"
                :height="720"
                :loading="klineLoading"
                :moving-averages="movingAverages"
                :period="requestPeriod"
                :sub-indicators="indicatorState.subIndicators"
                :symbol="symbol"
              />
            </div>
            <a-card class="mt-12px" size="small" title="当前结构">
              <a-descriptions :column="{ xs: 1, sm: 2, md: 4 }" bordered size="small">
                <a-descriptions-item label="状态">{{ chanlun?.availability || '待确认' }}</a-descriptions-item>
                <a-descriptions-item label="方向">{{ chanlun?.strokes.at(-1)?.direction || '--' }}</a-descriptions-item>
                <a-descriptions-item label="最新信号">{{ chanlun?.signals.at(-1)?.type || '--' }}</a-descriptions-item>
                <a-descriptions-item label="背驰">{{ chanlun?.divergences.at(-1)?.type || '--' }}</a-descriptions-item>
              </a-descriptions>
            </a-card>
          </template>

          <template v-else-if="tab.key === 'info'">
            <a-spin :spinning="researchLoading">
              <a-card size="small" title="个股信息">
                <a-alert v-if="researchError" :message="researchError" show-icon type="warning" />
                <a-descriptions class="mt-8px" :column="{ xs: 1, sm: 2, md: 3 }" bordered size="small">
                  <a-descriptions-item label="行业">{{ displayIndustry }}</a-descriptions-item>
                  <a-descriptions-item label="评分">{{ currentCandidate?.score?.toFixed(1) || '--' }}</a-descriptions-item>
                  <a-descriptions-item label="状态">{{ statusLabel(currentCandidate?.status) }}</a-descriptions-item>
                  <a-descriptions-item label="最新价">{{ formatPrice(quote?.last_price) }}</a-descriptions-item>
                  <a-descriptions-item label="成交量">{{ formatAmount(quote?.volume) }}</a-descriptions-item>
                  <a-descriptions-item label="总市值">{{ formatMarketCap(quote?.total_market_cap_cny) === '--' ? pickResearchValue(['总市值', '总市值(元)', '总市值（元）', 'market_cap', 'market_capitalization']) : formatMarketCap(quote?.total_market_cap_cny) }}</a-descriptions-item>
                  <a-descriptions-item label="动态市盈率">{{ formatPrice(quote?.pe_ttm) === '--' ? pickResearchValue(['动态市盈率', '市盈率动态', '市盈率TTM', 'PE TTM', 'pe_ttm']) : formatPrice(quote?.pe_ttm) }}</a-descriptions-item>
                  <a-descriptions-item label="静态市盈率">{{ formatPrice(quote?.pe_static) === '--' ? pickResearchValue(['静态市盈率', '市盈率静态', '市盈率', 'PE', 'pe']) : formatPrice(quote?.pe_static) }}</a-descriptions-item>
                </a-descriptions>
              </a-card>
            </a-spin>
          </template>

          <template v-else-if="tab.key === 'strategy'">
            <a-spin :spinning="researchLoading || screenLoading">
              <a-alert v-if="researchError" :message="researchError" show-icon type="warning" />
              <a-alert v-if="screenError" class="mt-8px" :message="screenError" show-icon type="warning" />
              <a-card size="small" title="战法判断">
                <a-descriptions :column="{ xs: 1, sm: 2, md: 4 }" bordered size="small">
                  <a-descriptions-item label="候选状态">{{ statusLabel(currentCandidate?.status) }}</a-descriptions-item>
                  <a-descriptions-item label="收盘 / MA5">{{ comparePrice(latestBar?.close, latestBar?.ma5) }}</a-descriptions-item>
                  <a-descriptions-item label="收盘 / MA20">{{ comparePrice(latestBar?.close, latestBar?.ma20) }}</a-descriptions-item>
                  <a-descriptions-item label="收盘 / MA60">{{ comparePrice(latestBar?.close, latestBar?.ma60) }}</a-descriptions-item>
                </a-descriptions>
              </a-card>
              <a-card class="mt-12px" size="small" title="股是股非模型选股条件">
                <a-space wrap>
                  <a-tag v-for="(condition, index) in gsgfModelConditions" :key="condition" color="blue">{{ index + 1 }}. {{ condition }}</a-tag>
                </a-space>
              </a-card>
              <a-card class="mt-12px" size="small" title="规则命中">
                <a-space v-if="currentCandidate?.rule_hits.length" wrap><a-tag v-for="item in currentCandidate.rule_hits" :key="item" color="red">{{ item }}</a-tag></a-space>
                <span v-else class="text-13px text-text-secondary">暂无命中规则</span>
              </a-card>
              <a-card class="mt-12px" size="small" title="风险提示">
                <a-space v-if="currentCandidate?.risk_flags.length" wrap><a-tag v-for="item in currentCandidate.risk_flags" :key="item" color="orange">{{ item }}</a-tag></a-space>
                <span v-else class="text-13px text-text-secondary">暂无风险提示</span>
              </a-card>
            </a-spin>
          </template>

          <template v-else>
            <a-spin :spinning="researchLoading || screenLoading">
              <a-alert v-if="researchError" :message="researchError" show-icon type="warning" />
              <a-alert v-if="screenError" class="mt-8px" :message="screenError" show-icon type="warning" />
              <a-card size="small" title="概念与板块">
                <a-descriptions :column="{ xs: 1, sm: 2, md: 3 }" bordered size="small">
                  <a-descriptions-item label="所属行业">{{ displayIndustry }}</a-descriptions-item>
                  <a-descriptions-item label="板块强度">{{ currentCandidate?.industry_strength || '--' }}</a-descriptions-item>
                  <a-descriptions-item label="行业得分">{{ currentCandidate?.industry_score ?? '--' }}</a-descriptions-item>
                  <a-descriptions-item label="行业排名">{{ currentCandidate?.industry_rank ?? '--' }}</a-descriptions-item>
                  <a-descriptions-item label="股票">{{ displayName }} · {{ symbol }}</a-descriptions-item>
                  <a-descriptions-item label="研究来源">{{ research?.source_status.map(item => item.source).join(' / ') || '--' }}</a-descriptions-item>
                </a-descriptions>
                <a-divider />
                <div class="mb-8px text-13px font-600 text-text-secondary">板块备注</div>
                <a-space v-if="currentCandidate?.industry_notes.length" wrap><a-tag v-for="item in currentCandidate.industry_notes" :key="item">{{ item }}</a-tag></a-space>
                <span v-else class="text-13px text-text-secondary">暂无板块备注</span>
              </a-card>
            </a-spin>
          </template>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>
