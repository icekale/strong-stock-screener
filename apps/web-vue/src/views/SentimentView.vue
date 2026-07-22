<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import dayjs from 'dayjs';
import { getSentimentDecision, getSentimentSummary, getShortTermIntradaySentiment } from '@/service/product-api';
import type { SentimentDecisionResponse, SentimentSummaryResponse, ShortTermIntradaySentimentItem, ShortTermIntradaySentimentResponse } from '@/service/types';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';
import type { WorkbenchMetric } from '@/components/common/workbench/workbench';
import SentimentPercentilePanel from '@/components/sentiment/SentimentPercentilePanel.vue';
import { useTradeDate } from '@/composables/useTradeDate';

defineOptions({ name: 'SentimentView' });

const { tradeDate, setTradeDate } = useTradeDate();
const summary = ref<SentimentSummaryResponse | null>(null);
const decision = ref<SentimentDecisionResponse | null>(null);
const intraday = ref<ShortTermIntradaySentimentResponse | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const percentileRefreshToken = ref(0);

const sentimentMetrics = computed<WorkbenchMetric[]>(() => {
  const metrics = summary.value?.metrics;
  return [
    { key: 'emotion-score', label: '情绪分', value: metrics?.emotion_score ?? '--', helper: metrics?.emotion_level || '待确认', tone: 'info' },
    { key: 'limit-up', label: '涨停家数', value: metrics?.limit_up_count ?? '--', helper: metrics?.seal_rate_pct == null ? '封板率待确认' : `封板率 ${formatPct(metrics.seal_rate_pct)}`, tone: 'positive' },
    { key: 'break-board', label: '炸板家数', value: metrics?.break_board_count ?? '--', helper: '关注接力风险', tone: 'warning' },
    { key: 'consecutive', label: '连板高度', value: metrics?.max_consecutive_boards ?? '--', helper: `上涨 ${metrics?.advance_count ?? '--'} · 下跌 ${metrics?.decline_count ?? '--'}`, tone: 'positive' }
  ];
});

async function load() {
  loading.value = true;
  error.value = null;
  const results = await Promise.allSettled([getSentimentSummary(tradeDate.value), getSentimentDecision(tradeDate.value), getShortTermIntradaySentiment(tradeDate.value)]);
  if (results[0].status === 'fulfilled') summary.value = results[0].value;
  if (results[1].status === 'fulfilled') decision.value = results[1].value;
  if (results[2].status === 'fulfilled') intraday.value = results[2].value;
  if (results.every(result => result.status === 'rejected')) error.value = '情绪数据暂时不可用';
  loading.value = false;
}

function handleDateChange(value: string) {
  setTradeDate(value);
  void load();
}

function handleRefresh() {
  percentileRefreshToken.value += 1;
  void load();
}

function formatPct(value: number | null | undefined) {
  return formatWorkbenchNumber(value, 'percent');
}

function changeTone(value: number | null | undefined) {
  return value != null && value >= 0 ? 'text-error' : 'text-success';
}

function formatGeneratedAt(value: string | undefined) {
  return value ? dayjs(value).format('HH:mm:ss') : undefined;
}

function permissionTone(value: SentimentDecisionResponse['trade_permission'] | undefined) {
  if (value === '强势进攻') return 'success';
  if (value === '空仓等待' || value === '只卖不追') return 'error';
  return value ? 'warning' : 'unknown';
}

function riskTone(value: SentimentDecisionResponse['risk_level'] | undefined) {
  if (value === '高') return 'error';
  if (value === '中') return 'warning';
  return value ? 'success' : 'unknown';
}

function intradayActionLabel(value: ShortTermIntradaySentimentItem['action']) {
  const labels: Record<ShortTermIntradaySentimentItem['action'], string> = {
    watch: '观察',
    low_buy_watch: '低吸观察',
    reduce: '减仓',
    avoid_chase: '回避追高',
    data_incomplete: '数据不完整'
  };
  return labels[value];
}

function intradayActionTone(value: ShortTermIntradaySentimentItem['action']) {
  if (value === 'reduce' || value === 'avoid_chase') return 'error';
  if (value === 'data_incomplete') return 'neutral';
  if (value === 'low_buy_watch') return 'warning';
  return 'info';
}

function asMainSector(value: unknown) {
  return value as SentimentDecisionResponse['main_sectors'][number];
}

function asIntradayItem(value: unknown) {
  return value as ShortTermIntradaySentimentItem;
}

onMounted(() => void load());
</script>

<template>
  <div class="space-y-16px">
    <PageHeader title="情绪与复盘" description="短线情绪、交易许可和盘中提醒">
      <template #meta>{{ tradeDate }}</template>
      <a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => handleDateChange(String(value))" />
      <a-button data-testid="sentiment-refresh" :loading="loading" type="primary" @click="handleRefresh">刷新数据</a-button>
    </PageHeader>

    <a-alert v-if="error" :title="error" show-icon type="warning" />
    <SentimentPercentilePanel :as-of="tradeDate" :refresh-token="percentileRefreshToken" />
    <div data-testid="sentiment-metrics">
      <MetricStrip :items="sentimentMetrics" />
    </div>

    <section class="sentiment-panel sentiment-permission-panel">
      <SectionHeader title="交易许可" :source="decision ? '情绪决策模型' : '等待数据'" :updated-at="formatGeneratedAt(decision?.generated_at)">
        <StatusTag :status="permissionTone(decision?.trade_permission)" />
      </SectionHeader>
      <div v-if="decision" class="sentiment-permission">
        <div class="sentiment-permission__primary">
          <span class="sentiment-permission__label">当前许可</span>
          <strong>{{ decision.trade_permission }}</strong>
          <span class="text-13px text-text-secondary">{{ decision.market_state }}</span>
        </div>
        <dl class="sentiment-permission__facts">
          <div>
            <dt>风险等级</dt>
            <dd><StatusTag :status="riskTone(decision.risk_level)" /> <span>{{ decision.risk_level }}</span></dd>
          </div>
          <div>
            <dt>置信度</dt>
            <dd class="wb-tabular-nums">{{ (decision.confidence * 100).toFixed(0) }}%</dd>
          </div>
          <div>
            <dt>评分变化</dt>
            <dd :class="decision.score_change != null && decision.score_change >= 0 ? 'text-error' : 'text-success'">{{ formatPct(decision.score_change) }}</dd>
          </div>
        </dl>
      </div>
      <div v-else class="sentiment-empty">交易许可待确认</div>
    </section>

    <div class="grid grid-cols-1 gap-16px xl:grid-cols-2">
      <section class="sentiment-panel">
        <SectionHeader title="主线信号" source="情绪决策模型" />
        <DataList :items="decision?.main_sectors ?? []" empty-description="暂无主线信号">
          <template #list-item="{ item }">
            <div class="sentiment-list-row">
              <div class="min-w-0">
                <div class="font-600 truncate">{{ asMainSector(item).name }}</div>
                <div class="text-12px text-text-secondary truncate">领涨 {{ asMainSector(item).leader || '--' }} · 涨停 {{ asMainSector(item).limit_up_count }} · 最高 {{ asMainSector(item).max_consecutive_boards }} 板</div>
              </div>
              <span class="text-error wb-tabular-nums font-700">强度 {{ asMainSector(item).strength_score.toFixed(1) }}</span>
            </div>
          </template>
        </DataList>
      </section>

      <section class="sentiment-panel">
        <SectionHeader title="盘中提醒" source="TickFlow 观察池" :updated-at="formatGeneratedAt(intraday?.generated_at)" />
        <DataList :items="intraday?.items ?? []" empty-description="暂无盘中提醒">
          <template #list-item="{ item }">
            <div class="sentiment-list-row sentiment-list-row--intraday">
              <div class="min-w-0">
                <div class="font-600 truncate">{{ asIntradayItem(item).name }} <span class="text-12px text-text-secondary">{{ asIntradayItem(item).symbol }}</span></div>
                <div class="text-12px text-text-secondary truncate">{{ asIntradayItem(item).industry || '行业待补' }} · {{ asIntradayItem(item).signals.slice(0, 2).join('；') || '暂无信号' }}</div>
              </div>
              <div class="flex shrink-0 items-center gap-8px">
                <span :class="changeTone(asIntradayItem(item).pct_change)" class="wb-tabular-nums">{{ formatPct(asIntradayItem(item).pct_change) }}</span>
                <StatusTag :status="intradayActionTone(asIntradayItem(item).action)" />
                <span class="text-12px text-text-secondary">{{ intradayActionLabel(asIntradayItem(item).action) }}</span>
              </div>
            </div>
          </template>
        </DataList>
      </section>
    </div>
  </div>
</template>

<style scoped>
.sentiment-panel {
  padding: 12px;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.sentiment-permission {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 4px 4px;
}

.sentiment-permission__primary {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
  min-width: 0;
}

.sentiment-permission__label,
.sentiment-permission__facts dt {
  color: var(--wb-muted);
  font-size: 12px;
}

.sentiment-permission__primary strong {
  color: var(--wb-ink);
  font-size: 22px;
}

.sentiment-permission__facts {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin: 0;
}

.sentiment-permission__facts div {
  min-width: 72px;
}

.sentiment-permission__facts dd {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 4px 0 0;
  color: var(--wb-ink);
  font-size: 14px;
  font-weight: 600;
}

.sentiment-empty {
  padding: 24px 4px 8px;
  color: var(--wb-muted);
  font-size: 13px;
  text-align: center;
}

.sentiment-list-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.sentiment-list-row--intraday {
  align-items: flex-start;
}

@media (max-width: 639px) {
  .sentiment-panel {
    padding: 10px;
  }

  .sentiment-permission {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }

  .sentiment-permission__facts {
    width: 100%;
    justify-content: space-between;
    gap: 12px;
  }

  .sentiment-list-row--intraday {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
