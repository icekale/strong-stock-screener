<script setup lang="ts">
import type { ECharts, EChartsOption } from 'echarts';
import * as echarts from 'echarts';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { runEChartLifecycle } from '@/utils/charts/klineOverlayOption';

defineOptions({ name: 'EChart' });

const props = withDefaults(
  defineProps<{
    option: EChartsOption;
    height?: number | string;
    loading?: boolean;
  }>(),
  { height: 280, loading: false }
);

const emit = defineEmits<{
  select: [params: unknown];
  hover: [params: unknown];
}>();

const root = ref<HTMLElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

function render() {
  if (!root.value) return;
  if (!chart) {
    chart = echarts.init(root.value);
    chart.on('click', params => emit('select', params));
    chart.on('mouseover', params => emit('hover', params));
  }
  runEChartLifecycle(chart, { type: 'setOption', option: props.option });
  if (props.loading) chart.showLoading('default', { color: '#1677ff', maskColor: 'rgba(255,255,255,0.62)' });
  else chart.hideLoading();
}

function resize() {
  if (chart) runEChartLifecycle(chart, { type: 'resize' });
}

function restore() {
  if (chart) runEChartLifecycle(chart, { type: 'restore' });
}

defineExpose({ resize, restore });

onMounted(async () => {
  await nextTick();
  if (root.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(root.value);
  }
  render();
});

watch(() => props.option, render, { deep: true });
watch(() => props.loading, render);

onBeforeUnmount(() => {
  if (chart) runEChartLifecycle(chart, { type: 'dispose', resizeObserver });
  resizeObserver = null;
  chart = null;
});
</script>

<template>
  <div ref="root" class="w-full" :style="{ height: typeof height === 'number' ? `${height}px` : height }" />
</template>
