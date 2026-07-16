<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import dayjs from 'dayjs';
import { useRouter } from 'vue-router';
import {
  addWatchlistPoolItem,
  createAuctionModelTop3Job,
  createAuctionSnapshotJob,
  getAuctionLatest,
  getAuctionModelTop3,
  getAuctionModelTop3Job,
  getAuctionSnapshotJob
} from '@/service/product-api';
import type { AuctionModelTop3Response, AuctionSnapshotItem, AuctionSnapshotResponse } from '@/service/types';
import { useJobPolling } from '@/composables/useJobPolling';
import { useTradeDate } from '@/composables/useTradeDate';
import { auctionModelBucketLabel, auctionModelCacheStatusLabel } from '@/utils/domain/auctionModel';
import { AUCTION_SORT_OPTIONS, getAuctionLiquidityWarning, getAuctionSortDescription, sortAuctionItems, type AuctionSortMode } from '@/utils/domain/auctionSort';

defineOptions({ name: 'AuctionView' });

const router = useRouter();
const { tradeDate, setTradeDate } = useTradeDate();
const data = ref<AuctionSnapshotResponse | null>(null);
const model = ref<AuctionModelTop3Response | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const modelError = ref<string | null>(null);
const tier = ref<'all' | AuctionSnapshotItem['tier']>('all');
const sortMode = ref<AuctionSortMode>('score');
const industry = ref('all');

const snapshotPolling = useJobPolling<AuctionSnapshotResponse>(createAuctionSnapshotJob, async jobId => {
  const state = await getAuctionSnapshotJob(jobId);
  return state;
}, { intervalMs: 1000 });
const modelPolling = useJobPolling<AuctionModelTop3Response>(
  () => createAuctionModelTop3Job(tradeDate.value),
  jobId => getAuctionModelTop3Job(jobId),
  { intervalMs: 1000 }
);

const industries = computed(() => ['all', ...new Set((data.value?.items ?? []).map(item => item.industry || '未标注'))]);
const items = computed(() => sortAuctionItems(
  (data.value?.items ?? []).filter(item => (tier.value === 'all' || item.tier === tier.value) && (industry.value === 'all' || (item.industry || '未标注') === industry.value)),
  sortMode.value
));
const selectedModelItems = computed(() => (model.value?.items ?? []).filter(item => item.bucket === 'selected').slice(0, 3));

async function loadLatest() {
  loading.value = true;
  try {
    data.value = await getAuctionLatest(100);
    error.value = null;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取竞价雷达失败';
  } finally {
    loading.value = false;
  }
}

async function refreshSnapshot() {
  error.value = null;
  try {
    await snapshotPolling.run();
    await loadLatest();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '刷新竞价雷达失败';
  }
}

async function loadModelCache() {
  modelError.value = null;
  try {
    model.value = await getAuctionModelTop3(tradeDate.value, { cacheOnly: true });
  } catch (cause) {
    model.value = null;
    modelError.value = cause instanceof Error ? cause.message : '暂无竞价模型缓存';
  }
}

async function runModel() {
  modelError.value = null;
  try {
    await modelPolling.run();
    model.value = await getAuctionModelTop3(tradeDate.value, { cacheOnly: true });
  } catch (cause) {
    modelError.value = cause instanceof Error ? cause.message : '竞价模型生成失败';
  }
}

async function addToWatchlist(item: AuctionSnapshotItem) {
  try {
    await addWatchlistPoolItem({ symbol: item.symbol, name: item.name, industry: item.industry, group: '竞价观察', tags: ['auction'] });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '加入自选失败';
  }
}

function openStock(symbol: string, name: string | null, itemIndustry: string | null, from: 'auction' | 'auction-model' = 'auction') {
  void router.push({ path: `/stock/${encodeURIComponent(symbol)}`, query: { from, name: name || undefined, industry: itemIndustry || undefined } });
}

function formatMoney(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  if (Math.abs(value) >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}亿`;
  if (Math.abs(value) >= 10_000) return `${(value / 10_000).toFixed(2)}万`;
  return value.toFixed(0);
}

function formatPct(value: number | null | undefined) {
  return typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(2)}%` : '--';
}

function tierLabel(value: AuctionSnapshotItem['tier']) {
  return { strong_high_open: '强势高开', volume_leader: '放量活跃', risk_overheat: '高开过热', weak_low_open: '低开偏弱', reversal_watch: '低开观察', neutral: '中性' }[value];
}

onMounted(async () => {
  await Promise.all([loadLatest(), loadModelCache()]);
});
</script>

<template>
  <div class="space-y-16px">
    <div class="flex flex-wrap items-center justify-between gap-12px">
      <div><div class="text-22px font-700 text-text-primary">竞价雷达</div><div class="mt-4px text-13px text-text-secondary">9:25 后快速确认高开、放量与行业聚集</div></div>
      <div class="flex flex-wrap items-center gap-8px"><a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => { setTradeDate(String(value)); void loadModelCache(); }" /><a-button :loading="snapshotPolling.polling.value" @click="refreshSnapshot">刷新快照</a-button></div>
    </div>
    <a-alert v-if="error" :message="error" show-icon type="warning" />
    <a-row :gutter="12">
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="候选数" :value="data?.metrics.candidate_count ?? '--'" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="强势高开" :value="data?.metrics.strong_high_open_count ?? '--'" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="高风险" :value="data?.metrics.high_risk_count ?? '--'" /></a-card></a-col>
      <a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="竞价成交额" :value="formatMoney(data?.metrics.total_turnover_cny)" /></a-card></a-col>
    </a-row>

    <a-card size="small" title="模型 Top3 试运行">
      <template #extra><a-space><a-tag v-if="model">{{ auctionModelCacheStatusLabel(model.cache_status) }}</a-tag><a-button size="small" :loading="modelPolling.polling.value" type="primary" @click="runModel">运行模型</a-button></a-space></template>
      <a-alert v-if="modelError" :message="modelError" show-icon type="info" />
      <a-progress v-if="modelPolling.polling.value" class="mb-8px" :percent="modelPolling.progress.value" />
      <a-row v-if="selectedModelItems.length" :gutter="12"><a-col v-for="item in selectedModelItems" :key="item.symbol" :xs="24" :md="8"><div class="cursor-pointer border border-border rounded-6px p-12px" @click="openStock(item.symbol, item.name, null, 'auction-model')"><div class="flex items-center justify-between"><span class="font-700">{{ item.rank ?? '--' }} · {{ item.name }}</span><a-tag color="red">{{ auctionModelBucketLabel(item.bucket) }}</a-tag></div><div class="mt-8px text-20px font-700 text-error">{{ (item.prob_3pct * 100).toFixed(1) }}%</div><div class="mt-4px text-12px text-text-secondary">{{ item.strategy_note || '策略说明待确认' }}</div></div></a-col></a-row>
      <a-empty v-else description="暂无缓存结果，请运行模型" />
    </a-card>

    <a-card size="small" title="竞价强度榜">
      <template #extra><a-space wrap><a-select v-model:value="tier" style="width: 120px" :options="[{ label: '全部分层', value: 'all' }, ...['strong_high_open','volume_leader','risk_overheat','reversal_watch','weak_low_open','neutral'].map(value => ({ label: tierLabel(value as AuctionSnapshotItem['tier']), value }))]" /><a-select v-model:value="industry" style="width: 130px" :options="industries.map(value => ({ label: value === 'all' ? '全部行业' : value, value }))" /><a-select v-model:value="sortMode" style="width: 130px" :options="AUCTION_SORT_OPTIONS" /></a-space></template>
      <div class="mb-8px text-12px text-text-secondary">{{ getAuctionSortDescription(sortMode) }}</div>
      <a-list :loading="loading" :data-source="items" item-layout="horizontal">
        <template #renderItem="{ item }"><a-list-item><a-list-item-meta :title="`${item.name || '未命名'} · ${item.symbol}`" :description="`${item.industry || '未标注'} · ${tierLabel(item.tier)} · ${item.signals.slice(0, 2).join(' / ') || '暂无信号'}`" /><template #extra><div class="flex items-center gap-12px"><div class="text-right"><div :class="item.open_gap_pct != null && item.open_gap_pct >= 0 ? 'text-error' : 'text-success'" class="font-700">{{ formatPct(item.open_gap_pct) }}</div><div class="text-12px text-text-secondary">额 {{ formatMoney(item.turnover_cny) }}</div><div v-if="getAuctionLiquidityWarning(item)" class="text-12px text-warning">{{ getAuctionLiquidityWarning(item) }}</div></div><a-button size="small" @click="addToWatchlist(item)">加入自选</a-button></div></template></a-list-item></template>
      </a-list>
      <a-empty v-if="!items.length" description="暂无竞价数据" />
    </a-card>
  </div>
</template>
