<script setup lang="ts">
import type { ECharts, EChartsOption } from 'echarts';
import * as echarts from 'echarts';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { createEChartLifecycle } from '@/utils/charts/klineOverlayOption';

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
let lifecycle: ReturnType<typeof createEChartLifecycle> | null = null;

function render() {
  if (!root.value) return;
  if (!chart) {
    chart = echarts.init(root.value);
    lifecycle = createEChartLifecycle(chart, resizeObserver);
    chart.on('click', params => emit('select', params));
    chart.on('mouseover', params => emit('hover', params));
  }
  lifecycle?.setOption(props.option);
  if (props.loading) chart.showLoading('default', { color: '#1677ff', maskColor: 'rgba(255,255,255,0.62)' });
  else chart.hideLoading();
}

function resize() {
  lifecycle?.resize();
}

function restore() {
  lifecycle?.restore();
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
  lifecycle?.dispose();
  lifecycle = null;
  resizeObserver = null;
  chart = null;
});
</script>

<template>
  <div ref="root" class="w-full" :style="{ height: typeof height === 'number' ? `${height}px` : height }" />
</template>
