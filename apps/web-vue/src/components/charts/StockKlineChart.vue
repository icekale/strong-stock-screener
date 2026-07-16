<script setup lang="ts">
import { computed } from 'vue';
import type { ChanlunAnalysisResponse, ChanlunLayerKey, KlineBar } from '@/service/types';
import { buildKlineOverlayOption } from '@/utils/charts/klineOverlayOption';
import type { KlineMovingAverage, KlineSubIndicator } from '@/utils/charts/klineIndicatorLayout';
import EChart from './EChart.vue';

defineOptions({ name: 'StockKlineChart' });

const props = withDefaults(
  defineProps<{
    bars: KlineBar[];
    movingAverages?: KlineMovingAverage[];
    subIndicators?: KlineSubIndicator[];
    chanlun?: ChanlunAnalysisResponse | null;
    chanlunLayers?: Partial<Record<ChanlunLayerKey, boolean>>;
    height?: number | string;
    loading?: boolean;
  }>(),
  { movingAverages: () => [], subIndicators: () => ['volume'], height: 620, loading: false }
);

const option = computed(() =>
  buildKlineOverlayOption({
    bars: props.bars,
    movingAverages: props.movingAverages,
    subIndicators: props.subIndicators,
    chanlun: props.chanlun,
    chanlunLayers: props.chanlunLayers
  })
);
</script>

<template>
  <div v-if="bars.length === 0" class="flex min-h-80 items-center justify-center text-sm text-text-secondary">暂无 K 线数据</div>
  <EChart v-else :height="height" :loading="loading" :option="option" />
</template>
