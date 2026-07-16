<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { EChartsOption } from 'echarts';
import { getHeatmapTreemap, getSectorReplicaBoardStocks, getSectorReplicaRadar } from '@/service/product-api';
import type { HeatmapTreemapResponse, SectorReplicaMode, SectorReplicaRadarResponse, SectorReplicaStocksResponse } from '@/service/types';
import SectorRadarChart from '@/components/charts/SectorRadarChart.vue';
import HeatmapTreemap from '@/components/charts/HeatmapTreemap.vue';
import { buildSectorReplicaChartOption } from '@/utils/charts/sectorReplicaChartOption';

defineOptions({ name: 'MarketView' });

const route = useRoute();
const router = useRouter();
const view = ref<'sectors' | 'heatmap'>(route.query.view === 'heatmap' ? 'heatmap' : 'sectors');
const mode = ref<SectorReplicaMode>('strength');
const loading = ref(false);
const error = ref<string | null>(null);
const radar = ref<SectorReplicaRadarResponse | null>(null);
const stocks = ref<SectorReplicaStocksResponse | null>(null);
const heatmap = ref<HeatmapTreemapResponse | null>(null);
const selectedBoard = ref<string | null>(null);

const sectorOption = computed<EChartsOption>(() => radar.value ? buildSectorReplicaChartOption({ axis: radar.value.axis, mode: mode.value, series: radar.value.series, compact: false }) as EChartsOption : { title: { text: '暂无板块曲线', left: 'center', top: 'middle' } });
const heatmapOption = computed<EChartsOption>(() => {
  const nodes = heatmap.value?.nodes ?? [];
  return {
    animationDuration: 180,
    tooltip: { formatter: (params: { name: string; value: number }) => `${params.name}<br/>规模 ${formatNumber(params.value)}` },
    series: [{
      type: 'treemap',
      roam: true,
      nodeClick: false,
      breadcrumb: { show: false },
      label: { show: true, formatter: '{b}', fontSize: 11 },
      upperLabel: { show: true, height: 22 },
      data: nodes.map(board => ({
        name: board.name,
        value: board.value,
        children: board.children.map(stock => ({
          name: `${stock.code} ${stock.name}`,
          value: stock.value,
          itemStyle: { color: stock.change_pct >= 0 ? '#d9363e' : '#07845e' }
        }))
      }))
    }]
  } as EChartsOption;
});

const latestTime = computed(() => {
  if (!radar.value) return null;
  let index = -1;
  radar.value.series.forEach(series => {
    for (let cursor = Math.min(series.data.length, radar.value!.axis.length) - 1; cursor >= 0; cursor -= 1) {
      if (typeof series.data[cursor] === 'number' && Number.isFinite(series.data[cursor])) {
        index = Math.max(index, cursor);
        break;
      }
    }
  });
  return index >= 0 ? radar.value.axis[index] : null;
});

async function loadSectors() {
  loading.value = true;
  error.value = null;
  try {
    radar.value = await getSectorReplicaRadar({ mode: mode.value, limit: 8, stockLimit: 80 });
    if (radar.value.plates[0] && !selectedBoard.value) selectedBoard.value = radar.value.plates[0].code;
    await loadBoardStocks();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取板块雷达失败';
  } finally {
    loading.value = false;
  }
}

async function loadBoardStocks() {
  if (!selectedBoard.value) return;
  try {
    stocks.value = await getSectorReplicaBoardStocks(selectedBoard.value, { mode: mode.value, limit: 50 });
  } catch {
    stocks.value = null;
  }
}

async function loadHeatmap() {
  loading.value = true;
  error.value = null;
  try {
    heatmap.value = await getHeatmapTreemap(new URLSearchParams({ market: 'all', period: 'day', size_mode: 'market_cap', trend: 'all', limit: '500' }));
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取市场热图失败';
  } finally {
    loading.value = false;
  }
}

function changeView(next: 'sectors' | 'heatmap') {
  view.value = next;
  void router.replace({ query: { ...route.query, view: next } });
  void (next === 'sectors' ? loadSectors() : loadHeatmap());
}

function formatNumber(value: number) {
  return value >= 100_000_000 ? `${(value / 100_000_000).toFixed(1)}亿` : value >= 10_000 ? `${(value / 10_000).toFixed(1)}万` : String(value);
}

function formatPct(value: number | null) {
  return value == null ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

watch(mode, () => { if (view.value === 'sectors') void loadSectors(); });
watch(selectedBoard, () => void loadBoardStocks());
watch(() => route.query.view, value => { if (value === 'heatmap' || value === 'sectors') view.value = value; });
onMounted(() => void (view.value === 'sectors' ? loadSectors() : loadHeatmap()));
</script>

<template>
  <div class="space-y-16px">
    <div class="flex flex-wrap items-center justify-between gap-12px"><div><div class="text-22px font-700 text-text-primary">板块与热图</div><div class="mt-4px text-13px text-text-secondary">实时强度曲线、题材轮动与全市场分布</div></div><a-segmented :value="view" :options="[{ label: '板块雷达', value: 'sectors' }, { label: '市场热图', value: 'heatmap' }]" @change="value => changeView(value as 'sectors' | 'heatmap')" /></div>
    <a-alert v-if="error" :message="error" show-icon type="warning" />
    <template v-if="view === 'sectors'">
      <a-card size="small"><template #title><span>板块实时曲线</span><span class="ml-12px text-12px text-text-secondary">最新采样 {{ latestTime || '--' }}</span></template><template #extra><a-segmented v-model:value="mode" size="small" :options="[{ label: '强度', value: 'strength' }, { label: '主力流', value: 'main_flow' }]" /></template><SectorRadarChart :height="420" :loading="loading && !radar" :option="sectorOption" /></a-card>
      <a-row :gutter="12"><a-col :xs="24" :lg="10"><a-card size="small" title="板块选择"><a-list :data-source="radar?.plates ?? []" size="small"><template #renderItem="{ item }"><a-list-item class="cursor-pointer" :class="item.code === selectedBoard ? 'bg-primary/5' : ''" @click="selectedBoard = item.code"><span>{{ item.name }}</span><span :class="item.val >= 0 ? 'text-error' : 'text-success'">{{ item.display_value || item.val }}</span></a-list-item></template></a-list><a-empty v-if="!radar?.plates.length" description="暂无板块数据" /></a-card></a-col><a-col :xs="24" :lg="14"><a-card size="small" :title="`${stocks?.board_code || '板块'} 成分股`"><a-list :data-source="stocks?.rows ?? []" size="small"><template #renderItem="{ item }"><a-list-item><a-list-item-meta :title="`${item.name || '--'} · ${item.symbol}`" :description="`${item.industry || '行业待补'} · ${item.themes.slice(0, 2).join(' / ')}`" /><template #extra><span :class="(item.pct_change ?? 0) >= 0 ? 'text-error' : 'text-success'">{{ formatPct(item.pct_change) }}</span></template></a-list-item></template></a-list><a-empty v-if="!stocks?.rows.length" description="选择板块查看成分股" /></a-card></a-col></a-row>
    </template>
    <template v-else>
      <a-card size="small" title="全市场热图"><template #extra><span class="text-12px text-text-secondary">{{ heatmap?.summary.stock_count ?? '--' }} 只股票 · {{ heatmap?.summary.board_count ?? '--' }} 个行业</span></template><HeatmapTreemap :height="560" :loading="loading && !heatmap" :option="heatmapOption" /></a-card>
      <a-row :gutter="12"><a-col :xs="12" :sm="6"><a-statistic title="上涨" :value="heatmap?.summary.advance_count ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="下跌" :value="heatmap?.summary.decline_count ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="成交额" :value="heatmap?.summary.turnover_cny == null ? '--' : formatNumber(heatmap.summary.turnover_cny)" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="涨跌比" :value="`${heatmap?.summary.advance_count ?? '--'} / ${heatmap?.summary.decline_count ?? '--'}`" /></a-col></a-row>
    </template>
  </div>
</template>
