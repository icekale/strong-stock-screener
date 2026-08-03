<script setup lang="ts">
import { computed } from 'vue';
import type { MarketEmotionSnapshotResponse } from '@/service/types';
import { buildMarketEmotionChartOption, buildMarketEmotionTrend } from '@/utils/domain/marketOverviewTrend';
import EChart from '@/components/charts/EChart.vue';

defineOptions({ name: 'MarketEmotionDashboard' });

const props = defineProps<{
  snapshot: MarketEmotionSnapshotResponse;
}>();

const bands = [
  {
    label: '冰点',
    className: 'market-emotion-dashboard__band--cold',
    textClass: 'market-emotion-dashboard__band-text--cold'
  },
  {
    label: '一般',
    className: 'market-emotion-dashboard__band--neutral',
    textClass: 'market-emotion-dashboard__band-text--neutral'
  },
  {
    label: '良好',
    className: 'market-emotion-dashboard__band--warm',
    textClass: 'market-emotion-dashboard__band-text--warm'
  },
  {
    label: '火爆',
    className: 'market-emotion-dashboard__band--hot',
    textClass: 'market-emotion-dashboard__band-text--hot'
  }
];

const score = computed(() => props.snapshot.metrics.emotion_score);
const markerLeft = computed(() => `${Math.max(0, Math.min(score.value, 100))}%`);
const trend = computed(() => buildMarketEmotionTrend(props.snapshot));
const chartOption = computed(() => buildMarketEmotionChartOption(trend.value));

function levelTone(level: MarketEmotionSnapshotResponse['metrics']['emotion_level']) {
  if (level === '冰点') return 'error';
  if (level === '火爆') return 'success';
  if (level === '良好') return 'warning';
  return 'info';
}
</script>

<template>
  <section class="market-emotion-dashboard" data-testid="market-emotion-dashboard">
    <header class="market-emotion-dashboard__header">
      <div class="min-w-0">
        <h2>市场情绪仪表盘</h2>
        <p>盘中实时快照：涨停/炸板 + 全A涨跌家数 + 成交额变化</p>
      </div>
      <StatusTag :status="levelTone(snapshot.metrics.emotion_level)" />
    </header>

    <div class="market-emotion-dashboard__body">
      <div class="market-emotion-dashboard__score">
        <span class="market-emotion-dashboard__score-label">情绪指标</span>
        <strong class="wb-tabular-nums">{{ score.toFixed(1) }}</strong>
        <span class="market-emotion-dashboard__level">{{ snapshot.metrics.emotion_level }}</span>
        <span class="market-emotion-dashboard__scale">0 冰点 · 100 火爆</span>
      </div>

      <dl class="market-emotion-dashboard__metrics">
        <div>
          <dt>涨停</dt>
          <dd>{{ snapshot.metrics.limit_up_count ?? '--' }}</dd>
        </div>
        <div>
          <dt>跌停</dt>
          <dd>{{ snapshot.metrics.limit_down_count ?? '--' }}</dd>
        </div>
        <div>
          <dt>封板率</dt>
          <dd>
            {{ snapshot.metrics.seal_rate_pct === null ? '--' : `${snapshot.metrics.seal_rate_pct.toFixed(1)}%` }}
          </dd>
        </div>
        <div>
          <dt>连板高度</dt>
          <dd>{{ snapshot.metrics.max_consecutive_boards ?? '--' }}</dd>
        </div>
      </dl>

      <div class="market-emotion-dashboard__bands" role="img" aria-label="市场情绪冷热区间">
        <div v-for="band in bands" :key="band.label" class="market-emotion-dashboard__band" :class="band.className">
          <span :class="band.textClass">{{ band.label }}</span>
        </div>
        <span
          class="market-emotion-dashboard__marker"
          :style="{ left: markerLeft }"
          :aria-label="`情绪分 ${score.toFixed(1)}`"
        />
      </div>

      <div class="market-emotion-dashboard__chart">
        <div class="market-emotion-dashboard__chart-heading">
          <span>日内情绪落点</span>
          <span>{{ trend.times.length }} 点</span>
        </div>
        <EChart v-if="trend.times.length" :option="chartOption" :height="150" />
        <div v-else class="market-emotion-dashboard__empty">等待盘中采样</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.market-emotion-dashboard {
  display: grid;
  gap: 12px;
  padding: 12px;
  background: var(--wb-surface, #fff);
  border: 1px solid var(--wb-border, #d9e2ea);
  border-radius: var(--wb-radius, 6px);
}

.market-emotion-dashboard__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.market-emotion-dashboard__header h2 {
  margin: 0;
  color: var(--wb-ink, #182336);
  font-size: 16px;
  font-weight: 700;
}

.market-emotion-dashboard__header p {
  margin: 4px 0 0;
  color: var(--wb-muted, #697991);
  font-size: 12px;
}

.market-emotion-dashboard__body {
  display: grid;
  gap: 12px;
}

.market-emotion-dashboard__score {
  display: grid;
  grid-template-columns: auto auto;
  align-items: baseline;
  justify-content: start;
  gap: 8px 12px;
}

.market-emotion-dashboard__score-label {
  grid-column: 1 / -1;
  color: var(--wb-muted, #697991);
  font-size: 12px;
}

.market-emotion-dashboard__score strong {
  color: var(--wb-ink, #182336);
  font-size: 30px;
  line-height: 1;
}

.market-emotion-dashboard__level {
  color: var(--wb-primary, #1769e0);
  font-size: 16px;
  font-weight: 700;
}

.market-emotion-dashboard__scale {
  grid-column: 1 / -1;
  color: var(--wb-muted, #697991);
  font-size: 12px;
}

.market-emotion-dashboard__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.market-emotion-dashboard__metrics div {
  min-width: 0;
  padding: 8px;
  border: 1px solid var(--wb-border, #d9e2ea);
  border-radius: 6px;
}

.market-emotion-dashboard__metrics dt {
  color: var(--wb-muted, #697991);
  font-size: 12px;
}

.market-emotion-dashboard__metrics dd {
  margin: 4px 0 0;
  color: var(--wb-ink, #182336);
  font-size: 16px;
  font-weight: 700;
}

.market-emotion-dashboard__bands {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  height: 32px;
  overflow: hidden;
  border: 1px solid var(--wb-border, #d9e2ea);
  border-radius: 6px;
}

.market-emotion-dashboard__band {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 5px;
}

.market-emotion-dashboard__band--cold {
  background: #dbeafe;
}

.market-emotion-dashboard__band--neutral {
  background: #e5e7eb;
}

.market-emotion-dashboard__band--warm {
  background: #fef3c7;
}

.market-emotion-dashboard__band--hot {
  background: #fee2e2;
}

.market-emotion-dashboard__band-text--cold {
  color: #1d4ed8;
}

.market-emotion-dashboard__band-text--neutral {
  color: #4b5563;
}

.market-emotion-dashboard__band-text--warm {
  color: #92400e;
}

.market-emotion-dashboard__band-text--hot {
  color: #b91c1c;
}

.market-emotion-dashboard__band span {
  font-size: 11px;
  font-weight: 700;
}

.market-emotion-dashboard__marker {
  position: absolute;
  top: 2px;
  bottom: 2px;
  width: 2px;
  background: #182336;
  border-radius: 2px;
  pointer-events: none;
  transform: translateX(-1px);
}

.market-emotion-dashboard__chart {
  min-width: 0;
}

.market-emotion-dashboard__chart-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  color: var(--wb-muted, #697991);
  font-size: 12px;
}

.market-emotion-dashboard__empty {
  display: grid;
  min-height: 96px;
  place-items: center;
  color: var(--wb-muted, #697991);
  font-size: 12px;
  border: 1px dashed var(--wb-border, #d9e2ea);
  border-radius: 6px;
}

@media (max-width: 639px) {
  .market-emotion-dashboard__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
