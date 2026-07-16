<script setup lang="ts">
import type { EChartsOption } from 'echarts';
import EChart from './EChart.vue';

defineOptions({ name: 'SectorRadarChart' });

withDefaults(
  defineProps<{
    option: EChartsOption;
    height?: number | string;
    loading?: boolean;
  }>(),
  { height: 320, loading: false }
);
</script>

<template>
  <EChart :height="height" :loading="loading" :option="option" />
</template>
