<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue';
import type { EChartsOption } from 'echarts';
import type { EtfExcessFlowResponse } from '@/service/types';
import { buildExcessFlowSeries, formatExcessFlowCny } from '@/utils/domain/etfExcessFlow';

defineOptions({ name: 'EtfExcessFlowPanel' });

const EChart = defineAsyncComponent(() => import('@/components/charts/EChart.vue'));

const props = defineProps<{
  response: EtfExcessFlowResponse | null;
  loading: boolean;
  error: string | null;
}>();

const panelElement = ref<HTMLElement | null>(null);
const chartColors = ref({
  primary: '#2563eb',
  negative: '#b91c1c',
  positive: '#15803d',
  warning: '#a16207'
});

function resolveChartColor(token: string, fallback: string) {
  if (typeof window === 'undefined') return fallback;
  const color = window.getComputedStyle(panelElement.value ?? document.documentElement).getPropertyValue(token).trim();
  return color && !color.includes('var(') ? color : fallback;
}

onMounted(() => {
  chartColors.value = {
    primary: resolveChartColor('--wb-primary', chartColors.value.primary),
    negative: resolveChartColor('--wb-negative', chartColors.value.negative),
    positive: resolveChartColor('--wb-positive', chartColors.value.positive),
    warning: resolveChartColor('--wb-warning', chartColors.value.warning)
  };
});

const seriesData = computed(() => (props.response ? buildExcessFlowSeries(props.response) : null));
const latestPoint = computed(() => props.response?.points.at(-1) ?? null);
const hasPoints = computed(() =>
  Boolean(
    props.response?.points.some(
      point => point.net_excess_flow_cny !== null || point.excess_inflow_cny !== null || point.excess_outflow_cny !== null
    )
  )
);
const chartOption = computed<EChartsOption>(() => {
  const data = seriesData.value;
  if (!data) return { animation: false, series: [] };
  const pointByDate = new Map((props.response?.points ?? []).map(point => [point.trade_date, point]));
  return {
    animation: false,
    aria: { enabled: true, description: '全部监控 ETF 合计超量资金趋势' },
    color: [chartColors.value.primary, chartColors.value.negative, chartColors.value.positive, chartColors.value.warning],
    grid: { left: 66, right: 18, top: 34, bottom: 34 },
    legend: { data: data.series.map(item => item.name), top: 0 },
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        const first = Array.isArray(params) ? params[0] : params;
        const date = String((first as { axisValue?: unknown } | undefined)?.axisValue ?? '');
        const point = pointByDate.get(date);
        if (!point) return date;
        const eventText = point.trigger_symbols.length ? `<br/>十倍量：${point.trigger_symbols.join('、')}` : '';
        return [
          date,
          `覆盖：${point.coverage_count} / ${point.expected_count}`,
          `净超量：${formatExcessFlowCny(point.net_excess_flow_cny)}`,
          `申购：${formatExcessFlowCny(point.excess_inflow_cny)}`,
          `赎回：${formatExcessFlowCny(point.excess_outflow_cny)}`
        ].join('<br/>') + eventText;
      }
    },
    xAxis: { type: 'category', boundaryGap: false, data: data.dates },
    yAxis: { type: 'value', axisLabel: { formatter: (value: number) => formatExcessFlowCny(value) } },
    series: [
      ...data.series,
      {
        name: '十倍量事件',
        type: 'scatter',
        data: data.events.map(event => ({
          value: [event.date, pointByDate.get(event.date)?.net_excess_flow_cny ?? 0],
          symbols: event.symbols.join('、')
        })),
        symbolSize: 10,
        tooltip: { formatter: params => `十倍量：${(params.data as { symbols?: string } | undefined)?.symbols ?? '--'}` }
      }
    ]
  } as EChartsOption;
});

function formatCoverage(point = latestPoint.value) {
  return point ? `${point.coverage_count} / ${point.expected_count}` : '--';
}
</script>

<template>
  <section ref="panelElement" data-testid="etf-excess-flow-panel" class="etf-excess-flow">
    <div class="etf-excess-flow__header">
      <div>
        <h3>市场合计超量资金趋势</h3>
        <p>全部监控 ETF 汇总，净值为超出各自 20 日平均份额变化基线的金额代理。</p>
      </div>
      <span class="etf-excess-flow__coverage">覆盖 {{ formatCoverage() }}</span>
    </div>

    <a-alert v-if="error" data-testid="excess-flow-error" type="warning" :message="error" show-icon />
    <div v-if="loading && !response" data-testid="etf-excess-flow-loading" class="etf-excess-flow__state" role="status">
      正在读取超量资金趋势
    </div>
    <div v-else-if="!hasPoints" data-testid="etf-excess-flow-empty" class="etf-excess-flow__state">
      暂无可用趋势数据
    </div>
    <template v-else>
      <div class="etf-excess-flow__metrics" aria-label="超量资金趋势摘要">
        <div>
          <span>最新净超量</span>
          <strong>{{ formatExcessFlowCny(latestPoint?.net_excess_flow_cny) }}</strong>
        </div>
        <div>
          <span>申购超量</span>
          <strong class="etf-excess-flow__inflow">{{ formatExcessFlowCny(latestPoint?.excess_inflow_cny) }}</strong>
        </div>
        <div>
          <span>赎回超量</span>
          <strong class="etf-excess-flow__outflow">{{ formatExcessFlowCny(latestPoint?.excess_outflow_cny) }}</strong>
        </div>
        <div>
          <span>十倍量事件</span>
          <strong>{{ (latestPoint?.tenfold_increase_count ?? 0) + (latestPoint?.tenfold_decrease_count ?? 0) }} 只</strong>
        </div>
      </div>
      <EChart :option="chartOption" :height="300" :loading="loading" />
      <div v-if="latestPoint?.trigger_symbols.length" class="etf-excess-flow__events" role="status">
        {{ latestPoint.trade_date }} 十倍量：{{ latestPoint.trigger_symbols.join('、') }}
      </div>
    </template>
  </section>
</template>

<style scoped>
.etf-excess-flow {
  margin: 0 0 16px;
  padding: 14px 16px 12px;
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
  background: var(--wb-surface-muted);
}

.etf-excess-flow__header,
.etf-excess-flow__metrics {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.etf-excess-flow__header {
  justify-content: space-between;
  margin-bottom: 10px;
}

.etf-excess-flow h3 {
  margin: 0;
  color: var(--wb-ink);
  font-size: 15px;
  line-height: 22px;
}

.etf-excess-flow p,
.etf-excess-flow__coverage,
.etf-excess-flow__events {
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 18px;
}

.etf-excess-flow p {
  margin: 2px 0 0;
}

.etf-excess-flow__coverage {
  flex: none;
  padding-top: 2px;
}

.etf-excess-flow__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 4px;
  border-top: 1px solid var(--wb-border);
}

.etf-excess-flow__metrics > div {
  min-width: 0;
  padding: 8px 12px 4px 0;
  border-inline-end: 1px solid var(--wb-border);
}

.etf-excess-flow__metrics > div:not(:first-child) {
  padding-inline-start: 12px;
}

.etf-excess-flow__metrics > div:last-child {
  border-inline-end: 0;
}

.etf-excess-flow__metrics span {
  display: block;
  color: var(--wb-muted);
  font-size: 11px;
}

.etf-excess-flow__metrics strong {
  display: block;
  margin-top: 2px;
  color: var(--wb-ink);
  font-size: 16px;
  line-height: 22px;
}

.etf-excess-flow__inflow {
  color: var(--wb-negative, #b91c1c) !important;
}

.etf-excess-flow__outflow {
  color: var(--wb-positive, #15803d) !important;
}

.etf-excess-flow__state {
  padding: 32px 0;
  color: var(--wb-muted);
  text-align: center;
}

.etf-excess-flow__events {
  padding-top: 4px;
  border-top: 1px solid var(--wb-border);
}

@media (max-width: 720px) {
  .etf-excess-flow__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .etf-excess-flow__metrics > div:nth-child(2) {
    border-inline-end: 0;
  }
}
</style>
