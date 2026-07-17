<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import dayjs from 'dayjs';
import type { EChartsOption } from 'echarts';
import {
  getAuctionModelTop3,
  getMarketEmotionSnapshot,
  getMarketOverview,
  getMarketRankings,
  getSectorRadar,
  isAuctionModelTop3CacheMiss
} from '@/service/product-api';
import type {
  AuctionModelTop3Response,
  MarketEmotionSnapshotResponse,
  AuctionModelPredictionItem,
  MarketOverviewResponse,
  MarketRankingItem,
  MarketRankingsResponse,
  SectorRadarResponse
} from '@/service/types';
import { useTradeDate } from '@/composables/useTradeDate';
import { buildMarketEmotionChartOption, buildMarketEmotionTrend } from '@/utils/domain/marketOverviewTrend';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';
import MarketTrendChart from '@/components/charts/MarketTrendChart.vue';
import SectorRadarChart from '@/components/charts/SectorRadarChart.vue';

defineOptions({ name: 'HomeView' });

const { tradeDate, setTradeDate } = useTradeDate();
const loading = ref(false);
const error = ref<string | null>(null);
const overview = ref<MarketOverviewResponse | null>(null);
const rankings = ref<MarketRankingsResponse | null>(null);
const sectors = ref<SectorRadarResponse | null>(null);
const emotion = ref<MarketEmotionSnapshotResponse | null>(null);
const top3 = ref<AuctionModelTop3Response | null>(null);
const top3Message = ref('');

const emotionOption = computed<EChartsOption>(() =>
  emotion.value
    ? buildMarketEmotionChartOption(buildMarketEmotionTrend(emotion.value))
    : { title: { text: '暂无情绪曲线', left: 'center', top: 'middle', textStyle: { fontSize: 13, fontWeight: 'normal' } } }
);

const sectorOption = computed<EChartsOption>(() => {
  const rows = (sectors.value?.inflow ?? []).filter(item => item.net_flow_cny !== null).slice(0, 8).reverse();
  return {
    animationDuration: 180,
    grid: { left: 68, right: 20, top: 12, bottom: 24, containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: '#697991', formatter: formatMoney } },
    yAxis: { type: 'category', data: rows.map(item => item.name), axisLabel: { color: '#182336' } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: formatMoney },
    series: [{
      name: '净流入',
      type: 'bar',
      barMaxWidth: 18,
      data: rows.map(item => ({ value: item.net_flow_cny, itemStyle: { color: '#d9363e' } }))
    }]
  };
});

const breadth = computed(() => overview.value?.advance_decline ?? null);
const turnover = computed(() => overview.value?.turnover ?? null);
const indices = computed(() => overview.value?.indices ?? []);
const sourceItems = computed(() => overview.value?.source_status ?? []);
const overviewMetrics = computed(() => [
  {
    key: 'turnover',
    label: '总成交额',
    value: turnover.value?.total_cny == null ? '--' : formatMoney(turnover.value.total_cny),
    helper: `昨日对比 ${formatPct(turnover.value?.change_pct)}`
  },
  {
    key: 'advance',
    label: '上涨家数',
    value: breadth.value?.advance_count ?? '--',
    helper: `下跌 ${breadth.value?.decline_count ?? '--'} · 平盘 ${breadth.value?.unchanged_count ?? '--'}`,
    tone: 'positive' as const
  },
  {
    key: 'limit',
    label: '涨停 / 跌停',
    value: `${breadth.value?.limit_up_count ?? '--'} / ${breadth.value?.limit_down_count ?? '--'}`,
    helper: '全市场统计口径'
  },
  {
    key: 'emotion',
    label: '盘面状态',
    value: emotion.value?.metrics.emotion_level ?? '待确认',
    helper: `情绪分 ${emotion.value?.metrics.emotion_score ?? '--'}`,
    tone: 'info' as const
  }
]);

function sourceStatusTone(status: string) {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'failed';
  if (status === 'stale') return 'partial';
  return 'unknown';
}

function formatGeneratedAt(value: string | undefined) {
  return value ? dayjs(value).format('HH:mm:ss') : undefined;
}

function asTop3Item(value: unknown) {
  return value as AuctionModelPredictionItem;
}

function asRankingItem(value: unknown) {
  return value as MarketRankingItem;
}

async function refresh() {
  loading.value = true;
  error.value = null;
  const results = await Promise.allSettled([
    getMarketOverview(),
    getMarketRankings(12),
    getSectorRadar(12),
    getMarketEmotionSnapshot(tradeDate.value, 80, true),
    getAuctionModelTop3(tradeDate.value, { cacheOnly: true })
  ]);
  const [overviewResult, rankingsResult, sectorsResult, emotionResult, top3Result] = results;
  if (overviewResult.status === 'fulfilled') overview.value = overviewResult.value;
  if (rankingsResult.status === 'fulfilled') rankings.value = rankingsResult.value;
  if (sectorsResult.status === 'fulfilled') sectors.value = sectorsResult.value;
  if (emotionResult.status === 'fulfilled') emotion.value = emotionResult.value;
  if (top3Result.status === 'fulfilled') {
    top3.value = top3Result.value;
    top3Message.value = '缓存结果';
  } else if (isAuctionModelTop3CacheMiss(top3Result.reason)) {
    top3.value = null;
    top3Message.value = '今日尚未生成';
  }
  const failed = results.filter(result => result.status === 'rejected');
  if (failed.length === results.length) error.value = '市场数据暂时不可用，请检查 API 服务与数据源状态';
  loading.value = false;
}

function handleDateChange(value: string) {
  setTradeDate(value);
  void refresh();
}

function formatMoney(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 100_000_000_000) return `${sign}${(abs / 100_000_000_000).toFixed(2)}万亿`;
  if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(2)}亿`;
  if (abs >= 10_000) return `${sign}${(abs / 10_000).toFixed(2)}万`;
  return value.toFixed(0);
}

function formatPct(value: number | null | undefined): string {
  return formatWorkbenchNumber(value, 'percent');
}

function changeTone(value: number | null | undefined) {
  return value != null && value >= 0 ? 'text-error' : 'text-success';
}

onMounted(() => void refresh());
</script>

<template>
  <div class="space-y-16px">
    <PageHeader title="市场总览" description="全 A 盘面、资金流和情绪状态">
      <template #meta>{{ tradeDate }}</template>
      <a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => handleDateChange(String(value))" />
      <a-button :loading="loading" type="primary" @click="refresh">刷新数据</a-button>
    </PageHeader>

    <section>
      <SectionHeader title="主要指数" :updated-at="formatGeneratedAt(overview?.generated_at)" />
      <div class="mt-12px grid grid-cols-2 gap-12px lg:grid-cols-4">
        <div v-for="index in indices" :key="index.symbol" class="border border-border rounded-6px p-10px">
          <div class="text-12px text-text-secondary">{{ index.name }}</div>
          <div class="mt-4px text-16px font-700">{{ index.last_price ?? '--' }}</div>
          <div :class="(index.change_pct ?? 0) >= 0 ? 'text-error' : 'text-success'">{{ formatPct(index.change_pct) }}</div>
        </div>
      </div>
      <div v-if="!indices.length" class="py-20px text-center text-13px text-text-secondary">主要指数待确认</div>
    </section>

    <a-alert v-if="error" :message="error" show-icon type="warning" />

    <div class="grid grid-cols-1 gap-12px xl:grid-cols-[1.4fr_1fr]">
      <section class="border border-border rounded-6px bg-container p-12px">
        <SectionHeader title="板块资金流" :updated-at="formatGeneratedAt(sectors?.generated_at)" />
        <SectorRadarChart :height="300" :loading="loading && !sectors" :option="sectorOption" />
      </section>
      <section class="border border-border rounded-6px bg-container p-12px">
        <SectionHeader title="盘中情绪走势" :updated-at="formatGeneratedAt(emotion?.generated_at)" />
        <MarketTrendChart :height="300" :loading="loading && !emotion" :option="emotionOption" />
      </section>
    </div>

    <MetricStrip :items="overviewMetrics" />

    <div class="grid grid-cols-1 gap-12px xl:grid-cols-2">
      <section class="border border-border rounded-6px bg-container p-12px">
        <SectionHeader title="竞价 Top3" :source="top3Message || '缓存优先'" :updated-at="formatGeneratedAt(top3?.generated_at)" />
        <DataList
          class="mt-2px"
          :items="top3?.items.filter(item => item.bucket === 'selected').slice(0, 3)"
          empty-description="暂无缓存结果"
        >
          <template #list-item="{ item }">
            <div class="flex items-center justify-between gap-8px">
              <span class="font-600">{{ asTop3Item(item).rank ?? '--' }} · {{ asTop3Item(item).name }}</span>
              <span class="wb-tabular-nums text-primary">{{ (asTop3Item(item).prob_3pct * 100).toFixed(1) }}%</span>
            </div>
          </template>
        </DataList>
      </section>

      <section class="border border-border rounded-6px bg-container p-12px">
        <SectionHeader title="市场关注榜" :updated-at="formatGeneratedAt(rankings?.generated_at)" />
        <DataList class="mt-2px" :items="rankings?.pct_change_rank ?? []" empty-description="暂无排行榜">
          <template #list-item="{ item }">
            <div class="flex items-center justify-between gap-8px">
              <span>{{ asRankingItem(item).name || asRankingItem(item).symbol }}</span>
              <span :class="changeTone(asRankingItem(item).pct_change)">{{ formatPct(asRankingItem(item).pct_change) }}</span>
            </div>
          </template>
        </DataList>
      </section>
    </div>

    <section class="border border-border rounded-6px bg-container px-12px py-10px">
      <SectionHeader title="数据状态" :updated-at="formatGeneratedAt(overview?.generated_at)">
        <span class="text-12px text-text-secondary">{{ sourceItems.length || '--' }} 个来源</span>
      </SectionHeader>
      <div class="flex flex-wrap items-center gap-x-12px gap-y-8px pt-10px">
        <div v-for="item in sourceItems" :key="item.source" class="flex items-center gap-6px text-12px text-text-secondary">
          <span>{{ item.source }}</span>
          <StatusTag :status="sourceStatusTone(item.status)" />
          <span>{{ item.status }}</span>
        </div>
        <span v-if="!sourceItems.length" class="text-12px text-text-secondary">待确认</span>
      </div>
    </section>
  </div>
</template>
