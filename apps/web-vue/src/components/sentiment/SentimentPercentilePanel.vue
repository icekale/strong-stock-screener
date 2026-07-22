<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Skeleton as ASkeleton } from 'ant-design-vue';
import dayjs from 'dayjs';
import type { EChartsOption } from 'echarts';
import {
  generateMarketSentimentAnalysis,
  getMarketSentimentAnalysis,
  getMarketSentimentPercentile
} from '@/service/product-api';
import type {
  SentimentPercentileAnalysisResponse,
  SentimentPercentileFactor,
  SentimentPercentileFactors,
  SentimentPercentilePoint,
  SentimentPercentileResponse,
  SentimentRiskPosture
} from '@/service/types';
import { buildSentimentPercentileChartOption } from '@/utils/charts/sentimentPercentileChart';
import EChart from '@/components/charts/EChart.vue';

defineOptions({ name: 'SentimentPercentilePanel' });

const props = defineProps<{
  asOf: string;
  refreshToken: number;
}>();

type FactorKey = keyof SentimentPercentileFactors;

const FACTORS: Array<{ key: FactorKey; label: string }> = [
  { key: 'volume', label: '量能百分位' },
  { key: 'index_move_5d', label: '5日指数涨跌' },
  { key: 'price_position', label: '500日价格位置' },
  { key: 'amplitude_5d', label: '5日方向振幅' },
  { key: 'volume_trend', label: '量能趋势' }
];

const percentile = ref<SentimentPercentileResponse | null>(null);
const selectedTradeDate = ref('');
const analysis = ref<SentimentPercentileAnalysisResponse | null>(null);
const percentileLoading = ref(false);
const analysisLoading = ref(false);
const analysisRetrying = ref(false);
const percentileError = ref<string | null>(null);
const analysisReadError = ref<string | null>(null);
let percentileRequestId = 0;
let analysisRequestId = 0;

const reducedMotion =
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const currentPoint = computed<SentimentPercentilePoint | null>(() => {
  const response = percentile.value;
  if (!response) return null;
  return response.history.find(point => point.trade_date === selectedTradeDate.value) ?? response.selected ?? null;
});

const dateOptions = computed(() =>
  [...(percentile.value?.history ?? [])].reverse().map(point => ({ label: point.trade_date, value: point.trade_date }))
);

const chartOption = computed<EChartsOption>(
  () =>
    buildSentimentPercentileChartOption(
      percentile.value?.history ?? [],
      selectedTradeDate.value,
      reducedMotion
    ) as EChartsOption
);

const cacheLabel = computed(() => {
  const status = percentile.value?.cache_status;
  if (status === 'fresh') return '数据已更新';
  if (status === 'cached') return '缓存数据';
  if (status === 'stale') return '缓存已过期';
  return '等待数据';
});

const notGeneratedCopy = computed(() =>
  selectedTradeDate.value === percentile.value?.latest_complete_trade_date ? '今日 AI 分析待生成' : '该日未生成 AI 解读'
);

async function loadPercentile(asOf: string, refresh: boolean) {
  percentileRequestId += 1;
  const requestId = percentileRequestId;
  percentileLoading.value = true;
  percentileError.value = null;
  try {
    const response = await getMarketSentimentPercentile(asOf, refresh);
    if (requestId !== percentileRequestId) return;
    percentile.value = response;
    selectedTradeDate.value =
      response.selected_trade_date ?? response.selected?.trade_date ?? response.history.at(-1)?.trade_date ?? '';
    if (selectedTradeDate.value) await loadAnalysis(selectedTradeDate.value);
    else analysis.value = null;
  } catch {
    if (requestId === percentileRequestId) percentileError.value = '市场情绪百分位更新失败，请稍后重试';
  } finally {
    if (requestId === percentileRequestId) percentileLoading.value = false;
  }
}

async function loadAnalysis(tradeDate: string) {
  analysisRequestId += 1;
  const requestId = analysisRequestId;
  analysisLoading.value = true;
  analysisReadError.value = null;
  try {
    const response = await getMarketSentimentAnalysis(tradeDate);
    if (requestId === analysisRequestId && selectedTradeDate.value === tradeDate) analysis.value = response;
  } catch {
    if (requestId === analysisRequestId) {
      analysis.value = null;
      analysisReadError.value = 'AI 解读读取失败，请稍后重试';
    }
  } finally {
    if (requestId === analysisRequestId) analysisLoading.value = false;
  }
}

function selectTradeDate(value: unknown) {
  const tradeDate = typeof value === 'string' ? value : '';
  if (!tradeDate || tradeDate === selectedTradeDate.value) return;
  selectedTradeDate.value = tradeDate;
  loadAnalysis(tradeDate);
}

function handleChartSelect(params: unknown) {
  const dataIndex =
    typeof params === 'object' && params !== null && 'dataIndex' in params
      ? Number((params as { dataIndex: unknown }).dataIndex)
      : Number.NaN;
  if (!Number.isInteger(dataIndex)) return;
  const point = percentile.value?.history[dataIndex];
  if (point) selectTradeDate(point.trade_date);
}

async function retryAnalysis() {
  if (!selectedTradeDate.value || analysisRetrying.value) return;
  analysisRetrying.value = true;
  analysisReadError.value = null;
  try {
    analysis.value = await generateMarketSentimentAnalysis(selectedTradeDate.value, true);
  } catch {
    analysis.value = analysis.value
      ? { ...analysis.value, status: 'failed', error: 'AI 分析重试失败，请稍后再试' }
      : null;
    analysisReadError.value = analysis.value ? null : 'AI 分析重试失败，请稍后再试';
  } finally {
    analysisRetrying.value = false;
  }
}

function factorFor(key: FactorKey): SentimentPercentileFactor | null {
  return currentPoint.value?.factors[key] ?? null;
}

function formatRawValue(key: FactorKey, factor: SentimentPercentileFactor | null) {
  if (!factor) return '--';
  if (factor.raw_unit === 'CNY') {
    if (Math.abs(factor.raw_value) >= 1_000_000_000_000)
      return `${(factor.raw_value / 1_000_000_000_000).toFixed(2)}万亿`;
    if (Math.abs(factor.raw_value) >= 100_000_000) return `${(factor.raw_value / 100_000_000).toFixed(2)}亿`;
  }
  const sign = key !== 'price_position' && factor.raw_value > 0 ? '+' : '';
  return `${sign}${factor.raw_value.toFixed(2)}${factor.raw_unit}`;
}

function boundedScore(value: number | undefined) {
  return Math.max(0, Math.min(100, value ?? 0));
}

function postureLabel(posture: SentimentRiskPosture) {
  const labels: Record<SentimentRiskPosture, string> = {
    attack: '进攻',
    balanced: '平衡',
    defensive: '防守',
    wait: '等待'
  };
  return labels[posture];
}

function formatCompletedAt(value: string | null) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '--';
}

watch(
  () => [props.asOf, props.refreshToken] as const,
  ([asOf, refreshToken], previous) => {
    const refresh = previous !== undefined && refreshToken !== previous[1];
    loadPercentile(asOf, refresh);
  },
  { immediate: true }
);
</script>

<template>
  <section class="sentiment-panel sentiment-percentile" data-testid="sentiment-percentile-panel">
    <header class="sentiment-percentile__header">
      <div class="min-w-0">
        <h2>市场情绪百分位</h2>
        <p>中证全指 · 收盘模型</p>
      </div>
      <div class="sentiment-percentile__header-meta">
        <span v-if="percentile">截至 {{ percentile.latest_complete_trade_date }}</span>
        <span :class="{ 'sentiment-percentile__cache--stale': percentile?.cache_status === 'stale' }">
          {{ cacheLabel }}
        </span>
      </div>
    </header>

    <div v-if="percentileError" class="sentiment-percentile__notice" data-testid="percentile-error" role="status">
      {{ percentileError }}
    </div>

    <div v-if="!percentile && percentileLoading" class="sentiment-percentile__initial" aria-busy="true">
      正在读取市场情绪百分位
    </div>

    <div v-else-if="percentile" class="sentiment-percentile__body">
      <div class="sentiment-percentile__chart">
        <EChart :option="chartOption" :height="360" :loading="percentileLoading" @select="handleChartSelect" />
      </div>

      <aside class="sentiment-percentile__current">
        <div class="sentiment-percentile__selector">
          <label for="sentiment-trade-date">查看日期</label>
          <ASelect
            id="sentiment-trade-date"
            aria-label="查看日期"
            :value="selectedTradeDate"
            :options="dateOptions"
            size="small"
            @change="selectTradeDate"
          />
        </div>

        <div v-if="currentPoint" class="sentiment-percentile__score-block">
          <div>
            <span>综合情绪</span>
            <strong data-testid="current-score" class="wb-tabular-nums">{{ currentPoint.score.toFixed(1) }}</strong>
          </div>
          <span
            data-testid="current-level"
            class="sentiment-percentile__level"
            :class="`sentiment-percentile__level--${currentPoint.level}`"
          >
            {{ currentPoint.level }}
          </span>
        </div>
        <div v-else class="sentiment-percentile__empty">该日期暂无完整情绪分</div>

        <div v-if="currentPoint" class="sentiment-percentile__factors">
          <div
            v-for="factor in FACTORS"
            :key="factor.key"
            class="sentiment-percentile__factor"
            data-testid="factor-row"
          >
            <div class="sentiment-percentile__factor-copy">
              <span>{{ factor.label }}</span>
              <span class="wb-tabular-nums">
                <strong>{{ factorFor(factor.key)?.score.toFixed(1) }}</strong>
                · {{ formatRawValue(factor.key, factorFor(factor.key)) }}
              </span>
            </div>
            <div
              class="sentiment-percentile__factor-track"
              role="progressbar"
              :aria-label="factor.label"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-valuenow="factorFor(factor.key)?.score"
            >
              <span :style="{ width: `${boundedScore(factorFor(factor.key)?.score)}%` }" />
            </div>
          </div>
        </div>
      </aside>
    </div>

    <section v-if="percentile" class="sentiment-percentile__analysis" aria-labelledby="sentiment-analysis-title">
      <div class="sentiment-percentile__analysis-heading">
        <h3 id="sentiment-analysis-title">AI 盘后解读</h3>
        <span>{{ selectedTradeDate }}</span>
      </div>

      <div
        v-if="analysisLoading || analysis?.status === 'pending'"
        class="sentiment-percentile__analysis-state"
        data-testid="ai-pending"
        aria-busy="true"
      >
        <ASkeleton active :paragraph="{ rows: 2 }" :title="{ width: '72%' }" />
        <p>{{ analysisLoading ? 'AI 解读加载中' : 'AI 解读生成中' }}</p>
      </div>
      <div v-else-if="analysisReadError" class="sentiment-percentile__analysis-state" role="status">
        {{ analysisReadError }}
      </div>
      <div v-else-if="analysis?.status === 'not_generated'" class="sentiment-percentile__analysis-state">
        {{ notGeneratedCopy }}
      </div>
      <div v-else-if="analysis?.status === 'unconfigured'" class="sentiment-percentile__analysis-state">
        <span>AI 分析未配置</span>
        <RouterLink to="/system">前往设置</RouterLink>
      </div>
      <div
        v-else-if="analysis?.status === 'failed'"
        class="sentiment-percentile__analysis-state"
        data-testid="ai-failed"
      >
        <div>
          <strong>今日 AI 分析失败</strong>
          <p>{{ analysis.error || '上游模型暂时不可用' }}</p>
        </div>
        <AButton data-testid="analysis-retry" size="small" :loading="analysisRetrying" @click="retryAnalysis">
          重试
        </AButton>
      </div>
      <div
        v-else-if="analysis?.status === 'ready' && analysis.result"
        class="sentiment-percentile__analysis-ready"
        data-testid="ai-ready"
      >
        <div class="sentiment-percentile__analysis-lead">
          <div>
            <span>市场结论</span>
            <p>{{ analysis.result.market_conclusion }}</p>
          </div>
          <div>
            <span>风险姿态</span>
            <strong>{{ postureLabel(analysis.result.risk_posture) }}</strong>
          </div>
        </div>
        <div class="sentiment-percentile__analysis-grid">
          <div>
            <h4>主要驱动</h4>
            <ul>
              <li v-for="item in analysis.result.key_drivers" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <h4>次日观察</h4>
            <ul>
              <li v-for="item in analysis.result.next_session_watch" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <h4>因子背离</h4>
            <p>{{ analysis.result.factor_divergence }}</p>
          </div>
          <div>
            <h4>历史位置</h4>
            <p>{{ analysis.result.historical_context }}</p>
          </div>
        </div>
        <footer class="sentiment-percentile__analysis-meta">
          <span>{{ analysis.provider || 'OpenAI 兼容接口' }} · {{ analysis.llm_model || '--' }}</span>
          <span>生成 {{ formatCompletedAt(analysis.completed_at) }}</span>
          <span>{{ analysis.result.risk_note }}</span>
        </footer>
      </div>
    </section>
  </section>
</template>

<style scoped>
.sentiment-panel {
  padding: 12px;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.sentiment-percentile,
.sentiment-percentile__body,
.sentiment-percentile__chart,
.sentiment-percentile__current,
.sentiment-percentile__analysis,
.sentiment-percentile__analysis-ready {
  min-width: 0;
}

.sentiment-percentile__header,
.sentiment-percentile__header-meta,
.sentiment-percentile__selector,
.sentiment-percentile__score-block,
.sentiment-percentile__factor-copy,
.sentiment-percentile__analysis-heading,
.sentiment-percentile__analysis-lead,
.sentiment-percentile__analysis-state,
.sentiment-percentile__analysis-meta {
  display: flex;
  align-items: center;
}

.sentiment-percentile__header {
  justify-content: space-between;
  gap: 16px;
  padding: 0 2px 10px;
  border-bottom: 1px solid var(--wb-border);
}

.sentiment-percentile__header h2,
.sentiment-percentile__analysis h3,
.sentiment-percentile__analysis h4,
.sentiment-percentile__header p,
.sentiment-percentile__analysis p,
.sentiment-percentile__analysis ul {
  margin: 0;
}

.sentiment-percentile__header h2 {
  color: var(--wb-ink);
  font-size: 15px;
  line-height: 1.4;
}

.sentiment-percentile__header p,
.sentiment-percentile__header-meta,
.sentiment-percentile__analysis-heading span,
.sentiment-percentile__analysis-meta {
  color: var(--wb-muted);
  font-size: 12px;
}

.sentiment-percentile__header p {
  margin-top: 2px;
}

.sentiment-percentile__header-meta {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px 12px;
}

.sentiment-percentile__cache--stale,
.sentiment-percentile__notice {
  color: var(--wb-warning);
}

.sentiment-percentile__notice {
  padding: 8px 2px 0;
  font-size: 12px;
}

.sentiment-percentile__initial {
  display: grid;
  min-height: 360px;
  place-items: center;
  color: var(--wb-muted);
  font-size: 13px;
}

.sentiment-percentile__body {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
  gap: 18px;
  padding-top: 12px;
}

.sentiment-percentile__chart {
  min-height: 360px;
}

.sentiment-percentile__current {
  padding: 2px 2px 0 0;
}

.sentiment-percentile__selector {
  justify-content: space-between;
  gap: 12px;
}

.sentiment-percentile__selector label {
  color: var(--wb-muted);
  font-size: 12px;
}

.sentiment-percentile__selector :deep(.ant-select) {
  width: 140px;
}

.sentiment-percentile__score-block {
  justify-content: space-between;
  gap: 12px;
  margin: 20px 0 18px;
}

.sentiment-percentile__score-block > div {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.sentiment-percentile__score-block span,
.sentiment-percentile__factor-copy {
  color: var(--wb-muted);
  font-size: 12px;
}

.sentiment-percentile__score-block strong {
  color: var(--wb-ink);
  font-size: 28px;
  line-height: 1;
}

.sentiment-percentile__level {
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.sentiment-percentile__level--冰点,
.sentiment-percentile__level--偏冷 {
  color: var(--wb-negative);
  background: var(--wb-status-success-soft);
}

.sentiment-percentile__level--偏热,
.sentiment-percentile__level--过热 {
  color: var(--wb-positive);
  background: var(--wb-status-error-soft);
}

.sentiment-percentile__level--中性 {
  color: var(--wb-muted);
  background: var(--wb-primary-soft);
}

.sentiment-percentile__factors {
  display: grid;
  gap: 13px;
}

.sentiment-percentile__factor-copy {
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
}

.sentiment-percentile__factor-copy strong {
  color: var(--wb-ink);
}

.sentiment-percentile__factor-track {
  height: 4px;
  overflow: hidden;
  background: var(--wb-primary-soft);
  border-radius: 2px;
}

.sentiment-percentile__factor-track span {
  display: block;
  height: 100%;
  background: var(--wb-primary);
  border-radius: inherit;
  transition: width 180ms ease-out;
}

.sentiment-percentile__empty {
  padding: 32px 0;
  color: var(--wb-muted);
  font-size: 13px;
  text-align: center;
}

.sentiment-percentile__analysis {
  margin-top: 14px;
  padding: 14px 2px 2px;
  border-top: 1px solid var(--wb-border);
}

.sentiment-percentile__analysis-heading {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.sentiment-percentile__analysis h3 {
  color: var(--wb-ink);
  font-size: 14px;
}

.sentiment-percentile__analysis-state {
  justify-content: space-between;
  gap: 12px;
  min-height: 96px;
  color: var(--wb-muted);
  font-size: 13px;
}

.sentiment-percentile__analysis-state > div p {
  margin-top: 4px;
}

.sentiment-percentile__analysis-state > div strong {
  color: var(--wb-ink);
}

.sentiment-percentile__analysis-state[aria-busy='true'] {
  align-items: flex-start;
  flex-direction: column;
  justify-content: center;
}

.sentiment-percentile__analysis-lead {
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 12px;
}

.sentiment-percentile__analysis-lead > div:first-child {
  max-width: 75ch;
}

.sentiment-percentile__analysis-lead span,
.sentiment-percentile__analysis h4 {
  color: var(--wb-muted);
  font-size: 12px;
  font-weight: 500;
}

.sentiment-percentile__analysis-lead p {
  margin-top: 4px;
  color: var(--wb-ink);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.65;
}

.sentiment-percentile__analysis-lead strong {
  display: block;
  margin-top: 4px;
  color: var(--wb-warning);
  font-size: 16px;
  white-space: nowrap;
}

.sentiment-percentile__analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 24px;
  padding: 12px 0;
  border-top: 1px solid var(--wb-border);
}

.sentiment-percentile__analysis-grid p,
.sentiment-percentile__analysis-grid li {
  color: var(--wb-ink);
  font-size: 12px;
  line-height: 1.7;
}

.sentiment-percentile__analysis-grid p,
.sentiment-percentile__analysis-grid ul {
  margin-top: 5px;
}

.sentiment-percentile__analysis-grid ul {
  padding-left: 18px;
}

.sentiment-percentile__analysis-meta {
  flex-wrap: wrap;
  gap: 6px 16px;
  padding-top: 10px;
  border-top: 1px solid var(--wb-border);
}

.sentiment-percentile__analysis-meta span:last-child {
  flex-basis: 100%;
}

@media (max-width: 767px) {
  .sentiment-percentile__body,
  .sentiment-percentile__analysis-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .sentiment-percentile__body {
    gap: 8px;
  }

  .sentiment-percentile__current {
    padding: 0 2px;
  }

  .sentiment-percentile__analysis-lead {
    flex-direction: column;
    gap: 10px;
  }
}

@media (max-width: 479px) {
  .sentiment-panel {
    padding: 10px;
  }

  .sentiment-percentile__header {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .sentiment-percentile__header-meta {
    justify-content: flex-start;
  }

  .sentiment-percentile__factor-copy {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .sentiment-percentile__factor-track span {
    transition: none;
  }
}
</style>
