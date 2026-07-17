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
  MarketOverviewResponse,
  MarketRankingsResponse,
  SectorRadarResponse
} from '@/service/types';
import { useTradeDate } from '@/composables/useTradeDate';
import { buildMarketEmotionChartOption, buildMarketEmotionTrend } from '@/utils/domain/marketOverviewTrend';
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
  return typeof value === 'number' && Number.isFinite(value) ? `${value > 0 ? '+' : ''}${value.toFixed(2)}%` : '--';
}

onMounted(() => void refresh());
</script>

<template>
  <div class="space-y-16px">
    <div class="flex flex-wrap items-center justify-between gap-12px">
      <div>
        <div class="text-22px font-700 text-text-primary">市场总览</div>
        <div class="mt-4px text-13px text-text-secondary">全 A 盘面、资金流和情绪状态</div>
      </div>
      <div class="flex flex-wrap items-center gap-8px">
        <a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => handleDateChange(String(value))" />
        <a-button :loading="loading" type="primary" @click="refresh">刷新数据</a-button>
      </div>
    </div>

    <a-alert v-if="error" :message="error" show-icon type="warning" />

    <a-card size="small" title="主要指数">
      <a-row :gutter="12"><a-col v-for="index in indices" :key="index.symbol" :xs="12" :sm="8" :lg="4"><div class="border border-border rounded-6px p-10px"><div class="text-12px text-text-secondary">{{ index.name }}</div><div class="mt-4px text-16px font-700">{{ index.last_price ?? '--' }}</div><div :class="(index.change_pct ?? 0) >= 0 ? 'text-error' : 'text-success'">{{ formatPct(index.change_pct) }}</div></div></a-col></a-row>
    </a-card>

    <a-row :gutter="12">
      <a-col :xs="24" :xl="14">
        <a-card size="small" title="板块资金流"><SectorRadarChart :height="300" :loading="loading && !sectors" :option="sectorOption" /></a-card>
      </a-col>
      <a-col :xs="24" :xl="10">
        <a-card size="small" title="盘中情绪走势"><MarketTrendChart :height="300" :loading="loading && !emotion" :option="emotionOption" /></a-card>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small"><a-statistic title="总成交额" :value="turnover?.total_cny == null ? '--' : formatMoney(turnover.total_cny)" /><div class="mt-4px text-12px text-text-secondary">昨日对比 {{ formatPct(turnover?.change_pct) }}</div></a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small"><a-statistic title="上涨家数" :value="breadth?.advance_count ?? '--'" /><div class="mt-4px text-12px text-text-secondary">下跌 {{ breadth?.decline_count ?? '--' }} · 平盘 {{ breadth?.unchanged_count ?? '--' }}</div></a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small"><a-statistic title="涨停 / 跌停" :value="`${breadth?.limit_up_count ?? '--'} / ${breadth?.limit_down_count ?? '--'}`" /><div class="mt-4px text-12px text-text-secondary">全市场统计口径</div></a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small"><a-statistic title="盘面状态" :value="emotion?.metrics.emotion_level ?? '待确认'" /><div class="mt-4px text-12px text-text-secondary">情绪分 {{ emotion?.metrics.emotion_score ?? '--' }}</div></a-card>
      </a-col>
    </a-row>

    <a-row :gutter="12">
      <a-col :xs="24" :xl="12">
        <a-card size="small" title="竞价 Top3">
          <template #extra><span class="text-12px text-text-secondary">{{ top3Message || '缓存优先' }}</span></template>
          <a-list v-if="top3?.items.length" :data-source="top3.items.filter(item => item.bucket === 'selected').slice(0, 3)" size="small">
            <template #renderItem="{ item }"><a-list-item><div class="flex w-full items-center justify-between gap-8px"><span class="font-600">{{ item.rank ?? '--' }} · {{ item.name }}</span><span class="text-primary">{{ (item.prob_3pct * 100).toFixed(1) }}%</span></div></a-list-item></template>
          </a-list>
          <a-empty v-else :description="top3Message || '暂无缓存结果'" />
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="12">
        <a-card size="small" title="市场关注榜">
          <a-list :data-source="rankings?.pct_change_rank ?? []" size="small">
            <template #renderItem="{ item }"><a-list-item><div class="flex w-full items-center justify-between gap-8px"><span>{{ item.name || item.symbol }}</span><span :class="item.pct_change >= 0 ? 'text-error' : 'text-success'">{{ formatPct(item.pct_change) }}</span></div></a-list-item></template>
          </a-list>
          <a-empty v-if="!rankings?.pct_change_rank?.length" description="暂无排行榜" />
        </a-card>
      </a-col>
    </a-row>

    <div class="text-12px text-text-secondary">数据状态：{{ sourceItems.map(item => `${item.source} · ${item.status}`).join('  |  ') || '待确认' }}</div>
  </div>
</template>
