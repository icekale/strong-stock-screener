<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import dayjs from 'dayjs';
import { useRouter } from 'vue-router';
import { createScreenRunJob, getLatestScreenRun, getScreenRunJob } from '@/service/product-api';
import type { ScreenRunFilters, ScreenRunJobState, ScreenStrategy, StrongStockScreeningItem, StrongStockScreeningResponse } from '@/service/types';
import { useTradeDate } from '@/composables/useTradeDate';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';

defineOptions({ name: 'ScreenerView' });

const router = useRouter();
const { tradeDate, setTradeDate } = useTradeDate();
const strategy = ref<ScreenStrategy>('combined');
const scanLimit = ref(160);
const running = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);
const result = ref<StrongStockScreeningResponse | null>(null);
const job = ref<ScreenRunJobState | null>(null);
const filters = reactive<ScreenRunFilters>({ min_market_cap_billion: 30, kdj_j_max: 120 });
const minMarketCap = ref(30);
const kdjJMax = ref(120);
const screenerMetrics = computed(() => [
  { key: 'candidate-count', label: '候选', value: result.value?.items.length ?? '--' },
  { key: 'complete-count', label: '可用', value: result.value?.items.filter(item => item.data_status === 'complete').length ?? '--', tone: 'success' as const },
  { key: 'high-score-count', label: '高分', value: result.value?.items.filter(item => item.score >= 70).length ?? '--', tone: 'positive' as const },
  { key: 'trade-date', label: '交易日', value: result.value?.trade_date ?? tradeDate.value }
]);

async function loadLatest() {
  loading.value = true;
  error.value = null;
  try {
    const latest = await getLatestScreenRun();
    result.value = latest;
    strategy.value = latest.strategy;
    if (latest.trade_date) setTradeDate(latest.trade_date);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取最近结果失败';
  } finally {
    loading.value = false;
  }
}

async function runScreen() {
  if (running.value) return;
  running.value = true;
  error.value = null;
  try {
    const nextFilters: ScreenRunFilters = { ...filters, min_market_cap_billion: minMarketCap.value, kdj_j_max: kdjJMax.value };
    let current = await createScreenRunJob(tradeDate.value, 30, scanLimit.value, nextFilters, { strategy: strategy.value });
    job.value = current;
    while (current.status === 'pending' || current.status === 'running') {
      await new Promise(resolve => setTimeout(resolve, 1200));
      current = await getScreenRunJob(current.job_id);
      job.value = current;
    }
    if (current.status !== 'success') throw new Error(current.error || current.message || '筛选任务失败');
    const completedResult = current.result;
    if (!completedResult) throw new Error('筛选任务未返回结果');
    result.value = completedResult;
    strategy.value = completedResult.strategy;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '运行筛选失败';
  } finally {
    running.value = false;
  }
}

function openStock(symbol: string, name: string, industry: string | null) {
  void router.push({ path: `/stock/${encodeURIComponent(symbol)}`, query: { from: 'screener', name, industry: industry || undefined } });
}

function scoreColor(score: number) {
  return score >= 70 ? 'text-error' : score >= 50 ? 'text-warning' : 'text-text-secondary';
}

function strategyLabel(value: ScreenStrategy) {
  return { combined: '综合', strong_stock: '强势', gsgf: '股是股非' }[value];
}

function screenStatusLabel(value: StrongStockScreeningItem['status']) {
  return { focus: '重点', wait_pullback: '等回踩', reduce_risk: '降风险', data_incomplete: '数据不完整' }[value];
}

function screenStatusTone(value: StrongStockScreeningItem['status']) {
  if (value === 'focus') return 'success';
  if (value === 'wait_pullback') return 'warning';
  if (value === 'reduce_risk') return 'failed';
  return 'partial';
}

function riskReasons(item: StrongStockScreeningItem) {
  return [...item.risk_flags, ...item.negative_news_flags].slice(0, 3).join(' / ') || '未发现风险标记';
}

function formatGeneratedAt(value: string | undefined) {
  return value ? dayjs(value).format('HH:mm:ss') : undefined;
}

function formatConfluence(value: number | null | undefined) {
  return formatWorkbenchNumber(value, 'price');
}

function asScreeningItem(value: unknown) {
  return value as StrongStockScreeningItem;
}

onMounted(() => void loadLatest());
</script>

<template>
  <div class="space-y-16px">
    <PageHeader title="强势选股" description="规则筛选、缠论共振和风险过滤">
      <template #meta>{{ tradeDate }}</template>
      <a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => setTradeDate(String(value))" />
      <a-button :loading="loading" @click="loadLatest">读取最近结果</a-button>
    </PageHeader>
    <a-alert v-if="error && (result?.items.length ?? 0)" :message="error" show-icon type="error" />
    <section class="border border-border rounded-6px bg-container p-12px">
      <SectionHeader title="筛选参数" source="当前运行设置" />
      <div class="screener-filter-toolbar mt-12px">
        <a-segmented v-model:value="strategy" block :options="[{ label: '综合', value: 'combined' }, { label: '强势', value: 'strong_stock' }, { label: '股是股非', value: 'gsgf' }]" />
        <a-input-number v-model:value="scanLimit" :min="30" :max="500" addon-before="扫描" />
        <a-input-number v-model:value="minMarketCap" :min="0" addon-before="市值亿" />
        <a-input-number v-model:value="kdjJMax" :min="0" addon-before="KDJ J" />
        <a-button type="primary" :loading="running" @click="runScreen">运行</a-button>
      </div>
      <a-progress v-if="running" class="mt-12px" :percent="job ? Math.round((job.progress_current / Math.max(job.progress_total, 1)) * 100) : 5" :status="job?.status === 'failed' ? 'exception' : 'active'" />
    </section>

    <MetricStrip :items="screenerMetrics" />

    <details class="border border-border rounded-6px bg-container px-12px py-10px" open>
      <summary class="cursor-pointer text-13px font-600">模型与筛选说明</summary>
      <div class="screener-explanation mt-10px text-12px text-text-secondary">
        <span>当前运行策略 {{ strategyLabel(strategy) }}</span>
        <span>结果策略 {{ result ? strategyLabel(result.strategy) : '暂无结果' }}</span>
        <span>强势模型 {{ result?.strong_model_version ?? '运行后显示' }}</span>
        <span>GSGF 模型 {{ result?.gsgf_model_version ?? '未启用或待确认' }}</span>
        <span>排序 {{ result?.sort_version ?? '运行后显示' }}</span>
        <span>扫描 {{ scanLimit }} · 市值 ≥ {{ minMarketCap }} 亿 · KDJ J ≤ {{ kdjJMax }}</span>
      </div>
    </details>

    <section class="border border-border rounded-6px bg-container p-12px">
      <SectionHeader title="筛选结果" :source="result ? strategyLabel(result.strategy) : '等待结果'" :updated-at="formatGeneratedAt(result?.generated_at)">
        <StatusTag :status="running ? 'running' : error ? 'failed' : result ? 'success' : 'unknown'" />
      </SectionHeader>
      <DataList :items="result?.items ?? []" :loading="loading || running" :error="error && !(result?.items.length ?? 0) ? error : null" empty-description="暂无筛选结果，请读取最近结果或运行筛选">
        <template #list-item="{ item }">
          <div class="screener-row cursor-pointer" role="button" tabindex="0" @click="openStock(asScreeningItem(item).symbol, asScreeningItem(item).name, asScreeningItem(item).industry)" @keydown.enter="openStock(asScreeningItem(item).symbol, asScreeningItem(item).name, asScreeningItem(item).industry)" @keydown.space.prevent="openStock(asScreeningItem(item).symbol, asScreeningItem(item).name, asScreeningItem(item).industry)">
            <div class="screener-row__identity">
              <div class="font-600">{{ asScreeningItem(item).name }} <span class="text-12px text-text-secondary">{{ asScreeningItem(item).symbol }}</span></div>
              <div class="text-12px text-text-secondary">{{ asScreeningItem(item).industry || '行业待补' }} · {{ asScreeningItem(item).rule_hits.slice(0, 3).join(' / ') || '规则待确认' }}</div>
            </div>
            <div class="screener-row__score" :class="scoreColor(asScreeningItem(item).score)">
              <div class="text-18px font-700">{{ asScreeningItem(item).score.toFixed(1) }}</div>
              <div class="text-12px">评分</div>
            </div>
            <div class="screener-row__chanlun">
              <div class="font-600">{{ formatConfluence(asScreeningItem(item).chanlun_summary?.confluence_score) }}</div>
              <div class="text-12px text-text-secondary">缠论共振</div>
            </div>
            <div class="screener-row__status">
              <div class="flex items-center gap-6px">
                <StatusTag :status="screenStatusTone(asScreeningItem(item).status)" />
                <span class="text-12px text-text-secondary">{{ screenStatusLabel(asScreeningItem(item).status) }}</span>
              </div>
              <div class="mt-4px text-12px text-text-secondary">数据 {{ asScreeningItem(item).data_status === 'complete' ? '完整' : '不完整' }} · {{ riskReasons(asScreeningItem(item)) }}</div>
            </div>
            <a-button class="screener-row__action" size="small" @click.stop="openStock(asScreeningItem(item).symbol, asScreeningItem(item).name, asScreeningItem(item).industry)">查看</a-button>
          </div>
        </template>
      </DataList>
    </section>
  </div>
</template>

<style scoped>
.screener-filter-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) repeat(3, minmax(120px, 0.65fr)) auto;
  gap: 8px;
  align-items: center;
}

.screener-explanation {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
}

.screener-row {
  display: grid;
  grid-template-columns: minmax(190px, 1.3fr) 72px 92px minmax(240px, 1.5fr) auto;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.screener-row__identity,
.screener-row__status {
  min-width: 0;
}

.screener-row__score,
.screener-row__chanlun {
  text-align: right;
}

.screener-row__status > div:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 767px) {
  .screener-filter-toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .screener-filter-toolbar > :first-child,
  .screener-filter-toolbar > :last-child {
    grid-column: 1 / -1;
  }

  .screener-row {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px 10px;
    align-items: start;
  }

  .screener-row__score,
  .screener-row__chanlun {
    text-align: right;
  }

  .screener-row__status {
    grid-column: 1 / -1;
  }

  .screener-row__status > div:last-child {
    white-space: normal;
  }

  .screener-row__action {
    grid-column: 2;
    grid-row: 1;
  }
}
</style>
