<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import dayjs from 'dayjs';
import type { EChartsOption } from 'echarts';
import { getSectorReplicaBoardStocks, getSectorReplicaRadar } from '@/service/product-api';
import type {
  SectorReplicaMode,
  SectorReplicaPlate,
  SectorReplicaRadarResponse,
  SectorReplicaStockRow,
  SectorReplicaStocksResponse
} from '@/service/types';
import SectorRadarChart from '@/components/charts/SectorRadarChart.vue';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';
import { buildSectorReplicaChartOption } from '@/utils/charts/sectorReplicaChartOption';

defineOptions({ name: 'MarketView' });

const mode = ref<SectorReplicaMode>('strength');
const loading = ref(false);
const error = ref<string | null>(null);
const radar = ref<SectorReplicaRadarResponse | null>(null);
const stocks = ref<SectorReplicaStocksResponse | null>(null);
const selectedBoard = ref<string | null>(null);

const sectorOption = computed<EChartsOption>(() => radar.value
  ? buildSectorReplicaChartOption({ axis: radar.value.axis, mode: mode.value, series: radar.value.series, compact: false }) as EChartsOption
  : { title: { text: '暂无板块曲线', left: 'center', top: 'middle' } });

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

function formatPct(value: number | null | undefined) {
  return formatWorkbenchNumber(value, 'percent');
}

function formatGeneratedAt(value: string | undefined) {
  return value ? dayjs(value).format('HH:mm:ss') : undefined;
}

function changeTone(value: number | null | undefined) {
  return value != null && value >= 0 ? 'text-error' : 'text-success';
}

function sectionStatus() {
  return loading.value ? 'running' : error.value ? 'failed' : radar.value ? 'success' : 'unknown';
}

async function loadSectors() {
  loading.value = true;
  error.value = null;
  try {
    radar.value = await getSectorReplicaRadar({ mode: mode.value, limit: 8, stockLimit: 80 });
    if (!radar.value.plates.some(plate => plate.code === selectedBoard.value)) {
      selectedBoard.value = radar.value.plates[0]?.code ?? null;
    }
    await loadBoardStocks();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取板块雷达失败';
  } finally {
    loading.value = false;
  }
}

async function loadBoardStocks() {
  if (!selectedBoard.value) {
    stocks.value = null;
    return;
  }
  const boardName = radar.value?.plates.find(plate => plate.code === selectedBoard.value)?.name;
  try {
    stocks.value = await getSectorReplicaBoardStocks(selectedBoard.value, { boardName, mode: mode.value, limit: 50 });
  } catch {
    stocks.value = null;
  }
}

function selectBoard(boardCode: string) {
  if (selectedBoard.value === boardCode) return;
  selectedBoard.value = boardCode;
  void loadBoardStocks();
}

function asPlate(value: unknown) {
  return value as SectorReplicaPlate;
}

function asStock(value: unknown) {
  return value as SectorReplicaStockRow;
}

watch(mode, () => void loadSectors());
onMounted(() => void loadSectors());
</script>

<template>
  <div class="space-y-16px">
    <PageHeader title="板块雷达" description="实时强度曲线、题材轮动与成分股观察">
      <template #meta>{{ latestTime || '等待采样' }}</template>
    </PageHeader>

    <a-alert v-if="error" :title="error" show-icon type="warning" />

    <section class="market-panel">
      <SectionHeader title="板块实时曲线" :source="mode === 'strength' ? '强度' : '主力流'" :updated-at="formatGeneratedAt(radar?.generated_at)">
        <div class="flex items-center gap-8px">
          <StatusTag :status="sectionStatus()" />
          <a-segmented v-model:value="mode" size="small" :options="[{ label: '强度', value: 'strength' }, { label: '主力流', value: 'main_flow' }]" />
        </div>
      </SectionHeader>
      <SectorRadarChart :height="440" :loading="loading && !radar" :option="sectorOption" />
    </section>

    <div class="grid grid-cols-1 gap-16px xl:grid-cols-[minmax(230px,0.8fr)_minmax(0,1.6fr)]">
      <section class="market-panel">
        <SectionHeader title="板块选择" source="按强度排序" />
        <DataList :items="radar?.plates ?? []" :loading="loading && !radar" empty-description="暂无板块数据">
          <template #list-item="{ item }">
            <button
              class="market-board-row"
              :class="asPlate(item).code === selectedBoard ? 'market-board-row--selected' : undefined"
              type="button"
              @click="selectBoard(asPlate(item).code)"
            >
              <span class="min-w-0 truncate">{{ asPlate(item).name }}</span>
              <span :class="changeTone(asPlate(item).val)" class="wb-tabular-nums">{{ asPlate(item).display_value || asPlate(item).val }}</span>
            </button>
          </template>
        </DataList>
      </section>

      <section class="market-panel">
        <SectionHeader :title="`${stocks?.board_code || '板块'} 成分股`" source="当前选中板块" />
        <DataList :items="stocks?.rows ?? []" empty-description="选择板块查看成分股">
          <template #list-item="{ item }">
            <div class="market-stock-row">
              <div class="min-w-0">
                <div class="font-600 truncate">{{ asStock(item).name || '--' }} <span class="text-12px text-text-secondary">{{ asStock(item).symbol }}</span></div>
                <div class="text-12px text-text-secondary truncate">{{ asStock(item).industry || '行业待补' }} · {{ asStock(item).themes.slice(0, 2).join(' / ') || '题材待补' }}</div>
              </div>
              <span :class="changeTone(asStock(item).pct_change)" class="wb-tabular-nums font-700">{{ formatPct(asStock(item).pct_change) }}</span>
            </div>
          </template>
        </DataList>
      </section>
    </div>
  </div>
</template>

<style scoped>
.market-panel {
  padding: 12px;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.market-board-row,
.market-stock-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

.market-board-row {
  padding: 8px 10px;
  color: var(--wb-ink);
  text-align: left;
  background: transparent;
  border: 0;
  border-inline-start: 2px solid transparent;
  cursor: pointer;
}

.market-board-row:hover,
.market-board-row--selected {
  background: var(--wb-primary-soft);
  border-inline-start-color: var(--wb-primary);
}

.market-stock-row {
  padding: 2px 0;
}

@media (max-width: 639px) {
  .market-panel {
    padding: 10px;
  }
}
</style>
