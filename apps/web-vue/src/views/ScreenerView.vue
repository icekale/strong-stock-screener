<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import dayjs from 'dayjs';
import { useRouter } from 'vue-router';
import { createScreenRunJob, getLatestScreenRun, getScreenRunJob } from '@/service/product-api';
import type { ScreenRunFilters, ScreenRunJobState, ScreenStrategy, StrongStockScreeningResponse } from '@/service/types';
import { useTradeDate } from '@/composables/useTradeDate';

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

async function loadLatest() {
  loading.value = true;
  try {
    result.value = await getLatestScreenRun();
    if (result.value.trade_date) setTradeDate(result.value.trade_date);
  } catch {
    result.value = null;
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
    result.value = current.result;
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

onMounted(() => void loadLatest());
</script>

<template>
  <div class="space-y-16px">
    <div class="flex flex-wrap items-center justify-between gap-12px">
      <div><div class="text-22px font-700 text-text-primary">强势选股</div><div class="mt-4px text-13px text-text-secondary">规则筛选、缠论共振和风险过滤</div></div>
      <div class="flex flex-wrap items-center gap-8px">
        <a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => setTradeDate(String(value))" />
        <a-button :loading="loading" @click="loadLatest">读取最近结果</a-button>
      </div>
    </div>
    <a-alert v-if="error" :message="error" show-icon type="error" />
    <a-card size="small">
      <a-row :gutter="12" align="middle">
        <a-col :xs="24" :md="8"><a-segmented v-model:value="strategy" block :options="[{ label: '综合', value: 'combined' }, { label: '强势', value: 'strong_stock' }, { label: '股是股非', value: 'gsgf' }]" /></a-col>
        <a-col :xs="24" :md="5"><a-input-number v-model:value="scanLimit" :min="30" :max="500" addon-before="扫描" /></a-col>
        <a-col :xs="24" :md="5"><a-input-number v-model:value="minMarketCap" :min="0" addon-before="市值亿" /></a-col>
        <a-col :xs="24" :md="4"><a-input-number v-model:value="kdjJMax" :min="0" addon-before="KDJ J" /></a-col>
        <a-col :xs="24" :md="2"><a-button block type="primary" :loading="running" @click="runScreen">运行</a-button></a-col>
      </a-row>
      <a-progress v-if="running" class="mt-12px" :percent="job ? Math.round((job.progress_current / Math.max(job.progress_total, 1)) * 100) : 5" :status="job?.status === 'failed' ? 'exception' : 'active'" />
    </a-card>

    <a-row :gutter="12">
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="候选" :value="result?.items.length ?? '--'" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="可用" :value="result?.items.filter(item => item.data_status === 'complete').length ?? '--'" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="高分" :value="result?.items.filter(item => item.score >= 70).length ?? '--'" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="交易日" :value="result?.trade_date ?? tradeDate" /></a-card></a-col>
    </a-row>

    <a-card size="small" title="筛选结果">
      <a-list :data-source="result?.items ?? []" item-layout="horizontal">
        <template #renderItem="{ item }">
          <a-list-item class="cursor-pointer" @click="openStock(item.symbol, item.name, item.industry)">
            <a-list-item-meta :title="`${item.name} · ${item.symbol}`" :description="`${item.industry || '行业待补'} · ${item.status} · ${item.rule_hits.slice(0, 3).join(' / ') || '规则待确认'}`" />
            <template #extra><div class="text-right"><div :class="['text-18px font-700', scoreColor(item.score)]">{{ item.score.toFixed(1) }}</div><div class="text-12px text-text-secondary">{{ item.chanlun_summary?.confluence_score ?? '--' }} 共振</div></div></template>
          </a-list-item>
        </template>
      </a-list>
      <a-empty v-if="!result?.items.length" description="暂无筛选结果" />
    </a-card>
  </div>
</template>
