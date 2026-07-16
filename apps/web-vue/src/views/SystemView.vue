<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  clearSystemCache,
  generateModelMaintenancePacket,
  getAuctionTop3TrainingPerformance,
  getAuctionTop3TrainingSummary,
  getDataSourceStatus,
  getLatestModelMaintenancePacket,
  getLatestModelMaintenanceReport,
  getSystemCache,
  getSystemStatus
} from '@/service/product-api';
import type { AuctionTop3PerformanceResponse, AuctionTop3TrainingSummary, DataSourceStatusResponse, ModelMaintenancePacket, ModelMaintenanceReport, SystemCacheSummary, SystemStatusResponse } from '@/service/types';

defineOptions({ name: 'SystemView' });

const status = ref<SystemStatusResponse | null>(null);
const cache = ref<SystemCacheSummary | null>(null);
const sources = ref<DataSourceStatusResponse | null>(null);
const training = ref<AuctionTop3TrainingSummary | null>(null);
const performance = ref<AuctionTop3PerformanceResponse | null>(null);
const packet = ref<ModelMaintenancePacket | null>(null);
const report = ref<ModelMaintenanceReport | null>(null);
const cumulativeReturn = computed(() => performance.value?.points.at(-1)?.cumulative_return_pct ?? null);
const loading = ref(false);
const clearing = ref<string | null>(null);
const error = ref<string | null>(null);

async function load() {
  loading.value = true;
  error.value = null;
  const results = await Promise.allSettled([getSystemStatus(), getSystemCache(), getDataSourceStatus(), getAuctionTop3TrainingSummary(), getAuctionTop3TrainingPerformance(), getLatestModelMaintenancePacket(), getLatestModelMaintenanceReport()]);
  if (results[0].status === 'fulfilled') status.value = results[0].value;
  if (results[1].status === 'fulfilled') cache.value = results[1].value;
  if (results[2].status === 'fulfilled') sources.value = results[2].value;
  if (results[3].status === 'fulfilled') training.value = results[3].value;
  if (results[4].status === 'fulfilled') performance.value = results[4].value;
  if (results[5].status === 'fulfilled') packet.value = results[5].value;
  if (results[6].status === 'fulfilled') report.value = results[6].value;
  if (results.every(result => result.status === 'rejected')) error.value = '系统状态暂时不可用';
  loading.value = false;
}

async function clear(group: string) {
  clearing.value = group;
  try { await clearSystemCache(group); await load(); } catch (cause) { error.value = cause instanceof Error ? cause.message : '清理缓存失败'; } finally { clearing.value = null; }
}

async function generatePacket() {
  try { packet.value = await generateModelMaintenancePacket(); } catch (cause) { error.value = cause instanceof Error ? cause.message : '生成维护包失败'; }
}

onMounted(() => void load());
</script>

<template>
  <div class="space-y-16px"><div class="flex flex-wrap items-center justify-between gap-12px"><div><div class="text-22px font-700 text-text-primary">模型与数据源</div><div class="mt-4px text-13px text-text-secondary">运行状态、缓存和训练维护</div></div><a-button :loading="loading" @click="load">刷新状态</a-button></div><a-alert v-if="error" :message="error" show-icon type="warning" /><a-row :gutter="12"><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="系统状态" :value="status?.status ?? '--'" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="运行任务" :value="status?.jobs.filter(job => job.running).length ?? '--'" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="缓存条目" :value="cache?.total ?? '--'" /></a-card></a-col><a-col :xs="12" :sm="6"><a-card size="small"><a-statistic title="置信度" :value="status?.confidence ?? '--'" /></a-card></a-col></a-row><a-row :gutter="12"><a-col :xs="24" :lg="12"><a-card size="small" title="数据源"><a-list :data-source="sources?.items ?? []" size="small"><template #renderItem="{ item }"><a-list-item><a-list-item-meta :title="item.source" :description="item.detail" /><template #extra><a-tag :color="item.status === 'success' ? 'green' : item.status === 'failed' ? 'red' : 'orange'">{{ item.status }}</a-tag></template></a-list-item></template></a-list><a-empty v-if="!sources?.items.length" description="暂无数据源状态" /></a-card></a-col><a-col :xs="24" :lg="12"><a-card size="small" title="后台任务"><a-list :data-source="status?.jobs ?? []" size="small"><template #renderItem="{ item }"><a-list-item><span>{{ item.name }}</span><a-space><a-tag>{{ item.enabled ? '启用' : '停用' }}</a-tag><span class="text-12px text-text-secondary">{{ item.detail }}</span></a-space></a-list-item></template></a-list></a-card></a-col></a-row><a-card size="small" title="缓存维护"><a-list :data-source="cache?.items ?? []" size="small"><template #renderItem="{ item }"><a-list-item><a-list-item-meta :title="item.name" :description="`${item.group} · 命中 ${item.hits} · 未命中 ${item.misses}`" /><template #extra><a-button size="small" :loading="clearing === item.group" @click="clear(item.group)">清理</a-button></template></a-list-item></template></a-list><a-empty v-if="!cache?.items.length" description="暂无缓存" /></a-card><a-card size="small" title="竞价 Top3 训练"><a-row :gutter="12"><a-col :xs="12" :sm="6"><a-statistic title="信号样本" :value="training?.signal_sample_count ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="模拟样本" :value="training?.simulated_trade_sample_count ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="人工样本" :value="training?.manual_trade_sample_count ?? '--'" /></a-col><a-col :xs="12" :sm="6"><a-statistic title="累计收益" :value="cumulativeReturn == null ? '--' : `${cumulativeReturn.toFixed(2)}%`" /></a-col></a-row></a-card><a-card size="small" title="模型维护包"><template #extra><a-button size="small" type="primary" @click="generatePacket">生成维护包</a-button></template><a-descriptions v-if="packet" :column="2" size="small"><a-descriptions-item label="数据包 ID">{{ packet.packet_id }}</a-descriptions-item><a-descriptions-item label="交易日">{{ packet.trade_date }}</a-descriptions-item><a-descriptions-item label="生成时间">{{ packet.generated_at }}</a-descriptions-item><a-descriptions-item label="质量提示">{{ packet.data_quality_notes.length }} 条</a-descriptions-item></a-descriptions><a-empty v-else description="暂无维护包" /><a-alert v-if="report" class="mt-12px" :message="report.summary || '已有维护报告'" type="info" /></a-card></div>
</template>
