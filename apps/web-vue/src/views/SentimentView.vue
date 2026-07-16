<script setup lang="ts">
import { onMounted, ref } from 'vue';
import dayjs from 'dayjs';
import { getSentimentDecision, getSentimentSummary, getShortTermIntradaySentiment } from '@/service/product-api';
import type { SentimentDecisionResponse, SentimentSummaryResponse, ShortTermIntradaySentimentResponse } from '@/service/types';
import { useTradeDate } from '@/composables/useTradeDate';

defineOptions({ name: 'SentimentView' });

const { tradeDate, setTradeDate } = useTradeDate();
const summary = ref<SentimentSummaryResponse | null>(null);
const decision = ref<SentimentDecisionResponse | null>(null);
const intraday = ref<ShortTermIntradaySentimentResponse | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

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

function formatPct(value: number | null) { return value == null ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`; }
onMounted(() => void load());
</script>

<template>
  <div class="space-y-16px"><div class="flex flex-wrap items-center justify-between gap-12px"><div><div class="text-22px font-700 text-text-primary">情绪与复盘</div><div class="mt-4px text-13px text-text-secondary">短线情绪、交易许可和盘中提醒</div></div><a-space><a-date-picker :value="dayjs(tradeDate)" value-format="YYYY-MM-DD" @change="(_, value) => { setTradeDate(String(value)); void load(); }" /><a-button :loading="loading" @click="load">刷新</a-button></a-space></div><a-alert v-if="error" :message="error" show-icon type="warning" /><a-row :gutter="12"><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="情绪分" :value="summary?.metrics.emotion_score ?? '--'" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="涨停" :value="summary?.metrics.limit_up_count ?? '--'" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="炸板" :value="summary?.metrics.break_board_count ?? '--'" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="连板高度" :value="summary?.metrics.max_consecutive_boards ?? '--'" /></a-card></a-col></a-row><a-card size="small" title="交易许可"><a-result v-if="decision" :status="decision.trade_permission === '强势进攻' ? 'success' : decision.risk_level === '高' ? 'warning' : 'info'" :title="decision.trade_permission" :sub-title="decision.market_state"><template #extra><a-tag>置信度 {{ (decision.confidence * 100).toFixed(0) }}%</a-tag></template></a-result><a-empty v-else description="许可待确认" /></a-card><a-row :gutter="12"><a-col :xs="24" :lg="12"><a-card size="small" title="主线信号"><a-list :data-source="decision?.main_sectors ?? []" size="small"><template #renderItem="{ item }"><a-list-item><a-list-item-meta :title="item.name" :description="`领涨 ${item.leader || '--'} · 涨停 ${item.limit_up_count} · 最高 ${item.max_consecutive_boards} 板`" /><template #extra><span class="text-error">强度 {{ item.strength_score.toFixed(1) }}</span></template></a-list-item></template></a-list><a-empty v-if="!decision?.main_sectors.length" description="暂无主线" /></a-card></a-col><a-col :xs="24" :lg="12"><a-card size="small" title="盘中提醒"><a-list :data-source="intraday?.items ?? []" size="small"><template #renderItem="{ item }"><a-list-item><a-list-item-meta :title="`${item.name} · ${item.symbol}`" :description="item.signals.slice(0, 2).join('；')" /><template #extra><a-tag>{{ item.action }}</a-tag></template></a-list-item></template></a-list><a-empty v-if="!intraday?.items.length" description="暂无盘中提醒" /></a-card></a-col></a-row></div>
</template>
