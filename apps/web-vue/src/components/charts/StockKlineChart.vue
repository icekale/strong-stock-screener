<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { ChanlunAnalysisResponse, ChanlunLayerKey, GsgfChartAnnotation, KlineBar, StockKlinePeriod } from '@/service/types';
import type { KlineZoomRange } from '@/utils/charts/klineOverlayOption';
import { buildKlineOverlayOption } from '@/utils/charts/klineOverlayOption';
import { resolveVisibleBarCount } from '@/utils/charts/chanlunOverlay';
import type { KlineMovingAverage, KlineSubIndicator } from '@/utils/charts/klineIndicatorLayout';
import EChart from './EChart.vue';

defineOptions({ name: 'StockKlineChart' });

const props = withDefaults(
  defineProps<{
    bars: KlineBar[];
    symbol?: string;
    period?: StockKlinePeriod;
    movingAverages?: KlineMovingAverage[];
    subIndicators?: KlineSubIndicator[];
    gsgfAnnotations?: GsgfChartAnnotation[];
    chanlun?: ChanlunAnalysisResponse | null;
    chanlunLayers?: Partial<Record<ChanlunLayerKey, boolean>>;
    height?: number | string;
    loading?: boolean;
  }>(),
  { movingAverages: () => [], subIndicators: () => ['volume'], gsgfAnnotations: () => [], height: 620, loading: false }
);

const chartKey = computed(() => [
  props.symbol ?? props.chanlun?.symbol ?? 'stock',
  props.period ?? props.chanlun?.period ?? '1d'
].join(':'));
const zoomRange = ref<KlineZoomRange>({ start: 0, end: 100 });
const visibleBarCount = computed(() => resolveVisibleBarCount(props.bars.length, zoomRange.value));

const option = computed(() =>
  buildKlineOverlayOption({
    bars: props.bars,
    movingAverages: props.movingAverages,
    subIndicators: props.subIndicators,
    gsgfAnnotations: props.gsgfAnnotations,
    chanlun: props.chanlun,
    chanlunLayers: props.chanlunLayers,
    visibleBarCount: visibleBarCount.value,
    zoomRange: zoomRange.value
  })
);

function handleDataZoom(range: KlineZoomRange) {
  if (zoomRange.value.start === range.start && zoomRange.value.end === range.end) return;
  zoomRange.value = range;
}

watch(chartKey, () => {
  zoomRange.value = { start: 0, end: 100 };
});
</script>

<template>
  <div v-if="bars.length === 0" class="flex min-h-80 items-center justify-center text-sm text-text-secondary">暂无 K 线数据</div>
  <EChart v-else :key="chartKey" :height="height" :loading="loading" :option="option" @datazoom="handleDataZoom" />
</template>
