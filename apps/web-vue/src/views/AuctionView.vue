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
import type { AuctionModelPredictionItem, AuctionModelTop3Response, AuctionSnapshotItem, AuctionSnapshotResponse } from '@/service/types';
import { useJobPolling } from '@/composables/useJobPolling';
import { useTradeDate } from '@/composables/useTradeDate';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';
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
const auctionMetrics = computed(() => [
  { key: 'candidate-count', label: '候选数', value: data.value?.metrics.candidate_count ?? '--' },
  { key: 'strong-high-open', label: '强势高开', value: data.value?.metrics.strong_high_open_count ?? '--', tone: 'positive' as const },
  { key: 'high-risk', label: '高风险', value: data.value?.metrics.high_risk_count ?? '--', tone: 'negative' as const },
  { key: 'turnover', label: '竞价成交额', value: formatMoney(data.value?.metrics.total_turnover_cny) }
]);

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
  return formatWorkbenchNumber(value, 'money');
}

function formatPct(value: number | null | undefined) {
  return formatWorkbenchNumber(value, 'percent');
}

function changeTone(value: number | null | undefined) {
  return value != null && value >= 0 ? 'text-error' : 'text-success';
}

function tierLabel(value: AuctionSnapshotItem['tier']) {
  return { strong_high_open: '强势高开', volume_leader: '放量活跃', risk_overheat: '高开过热', weak_low_open: '低开偏弱', reversal_watch: '低开观察', neutral: '中性' }[value];
}

function snapshotStatusLabel(value: AuctionSnapshotResponse['snapshot_status'] | undefined) {
  return { fresh: '实时', cached: '缓存', stale: '过期', missing: '缺失' }[value ?? 'missing'];
}

function statusTagValue(value: string | undefined) {
  if (value === 'fresh' || value === 'cached' || value === 'success') return 'success';
  if (value === 'stale' || value === 'running') return 'partial';
  if (value === 'missing' || value === 'failed') return 'failed';
  return 'unknown';
}

function formatGeneratedAt(value: string | undefined) {
  return value ? dayjs(value).format('HH:mm:ss') : undefined;
}

function asModelItem(value: unknown) {
  return value as AuctionModelPredictionItem;
}

function asAuctionItem(value: unknown) {
  return value as AuctionSnapshotItem;
}

onMounted(async () => {
  await Promise.all([loadLatest(), loadModelCache()]);
});
</script>

<template>
  <div class="space-y-16px">
    <PageHeader title="竞价雷达" description="9:25 后快速确认高开、放量与行业聚集">
      <template #meta>
        <div class="flex items-center gap-6px">
          <span>{{ tradeDate }}</span>
          <StatusTag :status="statusTagValue(data?.snapshot_status)" />
          <span>{{ snapshotStatusLabel(data?.snapshot_status) }}</span>
        </div>
      </template>
      <a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => { setTradeDate(String(value)); void loadModelCache(); }" />
      <a-button :loading="snapshotPolling.polling.value" @click="refreshSnapshot">刷新快照</a-button>
    </PageHeader>

    <a-alert v-if="error" :message="error" show-icon type="warning" />
    <MetricStrip :items="auctionMetrics" />

    <section class="border border-border rounded-6px bg-container p-12px">
      <SectionHeader title="模型 Top3 试运行" :source="model?.model_version || '竞价模型'" :updated-at="formatGeneratedAt(model?.generated_at)">
        <div class="flex flex-wrap items-center justify-end gap-8px">
          <div class="flex items-center gap-6px text-12px text-text-secondary">
            <StatusTag :status="model ? 'success' : modelError ? 'failed' : 'unknown'" />
            <span>{{ model ? auctionModelCacheStatusLabel(model.cache_status) : modelError ? '读取失败' : '未运行' }}</span>
          </div>
          <a-button size="small" :loading="modelPolling.polling.value" type="primary" @click="runModel">运行模型</a-button>
        </div>
      </SectionHeader>
      <a-progress v-if="modelPolling.polling.value" class="mb-8px" :percent="modelPolling.progress.value" />
      <DataList :items="selectedModelItems" :error="modelError" empty-description="暂无缓存结果，请运行模型">
        <template #list-item="{ item }">
          <div
            class="model-row cursor-pointer"
            role="button"
            tabindex="0"
            @click="openStock(asModelItem(item).symbol, asModelItem(item).name, null, 'auction-model')"
            @keydown.enter="openStock(asModelItem(item).symbol, asModelItem(item).name, null, 'auction-model')"
          >
            <div class="model-row__rank font-700">{{ asModelItem(item).rank ?? '--' }}</div>
            <div class="model-row__identity">
              <div class="font-600">{{ asModelItem(item).name }} <span class="text-12px text-text-secondary">{{ asModelItem(item).symbol }}</span></div>
              <div class="text-12px text-text-secondary">{{ auctionModelBucketLabel(asModelItem(item).bucket) }}</div>
            </div>
            <div class="model-row__prob text-error">{{ (asModelItem(item).prob_3pct * 100).toFixed(1) }}%</div>
            <div class="model-row__note text-12px text-text-secondary">{{ asModelItem(item).strategy_note || '策略说明待确认' }}</div>
          </div>
        </template>
      </DataList>
    </section>

    <section class="border border-border rounded-6px bg-container p-12px">
      <SectionHeader title="竞价强度榜" source="竞价快照" :updated-at="formatGeneratedAt(data?.generated_at)">
        <div class="auction-filters">
          <a-select v-model:value="tier" style="width: 120px" :options="[{ label: '全部分层', value: 'all' }, ...['strong_high_open','volume_leader','risk_overheat','reversal_watch','weak_low_open','neutral'].map(value => ({ label: tierLabel(value as AuctionSnapshotItem['tier']), value }))]" />
          <a-select v-model:value="industry" style="width: 130px" :options="industries.map(value => ({ label: value === 'all' ? '全部行业' : value, value }))" />
          <a-select v-model:value="sortMode" style="width: 130px" :options="AUCTION_SORT_OPTIONS" />
        </div>
      </SectionHeader>
      <div class="mb-8px pt-8px text-12px text-text-secondary">{{ getAuctionSortDescription(sortMode) }}</div>
      <DataList :items="items" :loading="loading" :error="error" empty-description="暂无竞价数据，请刷新快照">
        <template #list-item="{ item }">
          <div class="auction-row auction-row--two-line" data-layout="two-row">
            <div class="auction-row__primary">
              <div class="auction-row__identity">
                <div class="font-600">{{ asAuctionItem(item).name || '未命名' }} <span class="text-12px text-text-secondary">{{ asAuctionItem(item).symbol }}</span></div>
                <div class="text-12px text-text-secondary">{{ asAuctionItem(item).industry || '未标注' }} · {{ tierLabel(asAuctionItem(item).tier) }}</div>
              </div>
              <a-button class="auction-row__action" size="small" @click="addToWatchlist(asAuctionItem(item))">加入自选</a-button>
            </div>
            <div class="auction-row__secondary">
              <div class="auction-row__numbers text-right">
                <div :class="changeTone(asAuctionItem(item).open_gap_pct)" class="font-700">高开 {{ formatPct(asAuctionItem(item).open_gap_pct) }}</div>
                <div class="text-12px text-text-secondary">额 {{ formatMoney(asAuctionItem(item).turnover_cny) }} · 换手 {{ formatPct(asAuctionItem(item).turnover_rate) }}</div>
                <div v-if="getAuctionLiquidityWarning(asAuctionItem(item))" class="text-12px text-warning">{{ getAuctionLiquidityWarning(asAuctionItem(item)) }}</div>
              </div>
              <div class="auction-row__signals text-12px text-text-secondary">
                <div>{{ asAuctionItem(item).signals.slice(0, 2).join(' / ') || '暂无信号' }}</div>
                <div v-if="asAuctionItem(item).risk_flags.length" class="text-warning">{{ asAuctionItem(item).risk_flags.slice(0, 2).join(' / ') }}</div>
              </div>
            </div>
          </div>
        </template>
      </DataList>
    </section>
  </div>
</template>

<style scoped>
.model-row {
  display: grid;
  grid-template-columns: 28px minmax(150px, 0.8fr) minmax(80px, 0.3fr) minmax(180px, 1.5fr);
  gap: 10px;
  align-items: center;
  min-width: 0;
  padding: 2px 0;
}

.model-row__prob {
  font-size: 18px;
  font-weight: 700;
  text-align: right;
}

.model-row__note {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.auction-filters {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.auction-row {
  display: grid;
  grid-template-columns: minmax(170px, 1.15fr) minmax(160px, 1fr) minmax(170px, 0.9fr) auto;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.auction-row__primary,
.auction-row__secondary {
  display: contents;
}

.auction-row__identity,
.auction-row__signals,
.auction-row__numbers,
.auction-row__action {
  min-width: 0;
}

.auction-row__identity {
  grid-column: 1;
  grid-row: 1;
}

.auction-row__numbers {
  grid-column: 2;
  grid-row: 1;
}

.auction-row__signals {
  grid-column: 3;
  grid-row: 1;
}

.auction-row__action {
  grid-column: 4;
  grid-row: 1;
}

.auction-row__signals > div,
.auction-row__numbers > div {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 639px) {
  .model-row {
    grid-template-columns: 24px minmax(0, 1fr) auto;
    align-items: start;
  }

  .model-row__prob {
    grid-column: 3;
    grid-row: 1 / span 2;
    font-size: 16px;
  }

  .model-row__note {
    grid-column: 2;
    white-space: normal;
  }

  .auction-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 6px 10px;
    align-items: start;
  }

  .auction-row__primary,
  .auction-row__secondary {
    display: grid;
    grid-column: 1;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px 10px;
    align-items: start;
  }

  .auction-row__primary {
    grid-row: 1;
  }

  .auction-row__secondary {
    grid-row: 2;
  }

  .auction-row__identity,
  .auction-row__numbers,
  .auction-row__signals,
  .auction-row__action {
    grid-column: auto;
    grid-row: auto;
  }

  .auction-row__numbers {
    text-align: left;
  }

  .auction-row__signals {
    grid-column: auto;
    line-height: 1.5;
  }

  .auction-row__action {
    justify-self: end;
  }

  .auction-row__signals > div,
  .auction-row__numbers > div {
    white-space: normal;
  }
}
</style>
