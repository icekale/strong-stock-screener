<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import dayjs from 'dayjs';
import {
  clearSystemCache,
  generateModelMaintenancePacket,
  getAuctionTop3TrainingPerformance,
  getAuctionTop3TrainingSummary,
  getDataSourceStatus,
  getLatestModelMaintenancePacket,
  getLatestModelMaintenanceReport,
  getRuntimeSettings,
  getSystemCache,
  getSystemStatus,
  saveRuntimeSettings
} from '@/service/product-api';
import type {
  AiAnalysisSettingsUpdate,
  AuctionTop3PerformanceResponse,
  AuctionTop3TrainingSummary,
  DataSourceStatusResponse,
  ModelMaintenancePacket,
  ModelMaintenanceReport,
  RuntimeSettingsConfig,
  RuntimeSettingsResponse,
  SourceStatusValue,
  SystemCacheItem,
  SystemCacheSummary,
  SystemConfidence,
  SystemJobStatus,
  SystemStatusResponse
} from '@/service/types';
import { formatWorkbenchNumber } from '@/components/common/workbench/workbench';
import type { WorkbenchMetric, WorkbenchMetricTone } from '@/components/common/workbench/workbench';

defineOptions({ name: 'SystemView' });

const status = ref<SystemStatusResponse | null>(null);
const cache = ref<SystemCacheSummary | null>(null);
const sources = ref<DataSourceStatusResponse | null>(null);
const training = ref<AuctionTop3TrainingSummary | null>(null);
const performance = ref<AuctionTop3PerformanceResponse | null>(null);
const packet = ref<ModelMaintenancePacket | null>(null);
const report = ref<ModelMaintenanceReport | null>(null);
const runtimeSettings = ref<RuntimeSettingsResponse | null>(null);
const aiSettingsSaving = ref(false);
const aiSettingsError = ref<string | null>(null);
const aiSettingsMessage = ref<string | null>(null);
const aiDraft = ref<AiAnalysisDraft>(defaultAiDraft());
const loading = ref(false);
const clearing = ref<string | null>(null);
const error = ref<string | null>(null);

const cumulativeReturn = computed(() => performance.value?.points.at(-1)?.cumulative_return_pct ?? null);
const runningJobs = computed(() => status.value?.jobs.filter(job => job.running).length ?? '--');
const systemMetrics = computed<WorkbenchMetric[]>(() => [
  { key: 'system-status', label: '系统状态', value: systemStatusLabel(status.value?.status), tone: systemStatusTone(status.value?.status), helper: status.value?.generated_at ? `更新 ${formatGeneratedAt(status.value.generated_at)}` : '等待状态' },
  { key: 'running-jobs', label: '运行任务', value: runningJobs.value, tone: Number(runningJobs.value) > 0 ? 'info' as const : 'neutral' as const, helper: `${status.value?.jobs.length ?? '--'} 个任务` },
  { key: 'cache-items', label: '缓存条目', value: cache.value?.total ?? '--', helper: '可按分组清理' },
  { key: 'confidence', label: '数据置信度', value: confidenceLabel(status.value?.confidence), tone: confidenceTone(status.value?.confidence), helper: status.value?.confidence || '等待状态' }
]);
const trainingMetrics = computed<WorkbenchMetric[]>(() => [
  { key: 'signal-samples', label: '信号样本', value: training.value?.signal_sample_count ?? '--', helper: '竞价 Top3' },
  { key: 'simulated-samples', label: '模拟样本', value: training.value?.simulated_trade_sample_count ?? '--', helper: '模拟交易' },
  { key: 'manual-samples', label: '人工样本', value: training.value?.manual_trade_sample_count ?? '--', helper: '人工确认' },
  { key: 'cumulative-return', label: '累计收益', value: formatPct(cumulativeReturn.value), tone: cumulativeReturn.value == null ? 'neutral' : cumulativeReturn.value >= 0 ? 'positive' : 'negative', helper: performance.value ? `更新 ${formatGeneratedAt(performance.value.generated_at)}` : '等待回测数据' }
]);

async function load() {
  loading.value = true;
  error.value = null;
  const results = await Promise.allSettled([getSystemStatus(), getSystemCache(), getDataSourceStatus(), getAuctionTop3TrainingSummary(), getAuctionTop3TrainingPerformance(), getLatestModelMaintenancePacket(), getLatestModelMaintenanceReport(), getRuntimeSettings()]);
  if (results[0].status === 'fulfilled') status.value = results[0].value;
  if (results[1].status === 'fulfilled') cache.value = results[1].value;
  if (results[2].status === 'fulfilled') sources.value = results[2].value;
  if (results[3].status === 'fulfilled') training.value = results[3].value;
  if (results[4].status === 'fulfilled') performance.value = results[4].value;
  if (results[5].status === 'fulfilled') packet.value = results[5].value;
  if (results[6].status === 'fulfilled') report.value = results[6].value;
  if (results[7].status === 'fulfilled') {
    runtimeSettings.value = results[7].value;
    applyAiDraft(results[7].value.config);
    aiSettingsError.value = null;
  } else {
    aiSettingsError.value = '读取 AI 配置失败，请检查后端服务';
  }
  if (results.every(result => result.status === 'rejected')) error.value = '系统状态暂时不可用';
  loading.value = false;
}

async function saveAiSettings() {
  const current = runtimeSettings.value;
  if (!current) return;

  aiSettingsSaving.value = true;
  aiSettingsError.value = null;
  aiSettingsMessage.value = null;
  try {
    const response = await saveRuntimeSettings(buildRuntimeSettingsPayload(current, aiDraft.value));
    runtimeSettings.value = response;
    applyAiDraft(response.config);
    aiSettingsMessage.value = 'AI 配置已保存';
  } catch (cause) {
    aiSettingsError.value = cause instanceof Error ? cause.message : '保存 AI 配置失败';
  } finally {
    aiSettingsSaving.value = false;
  }
}

async function clear(group: string) {
  clearing.value = group;
  try {
    await clearSystemCache(group);
    await load();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '清理缓存失败';
  } finally {
    clearing.value = null;
  }
}

async function generatePacket() {
  try {
    packet.value = await generateModelMaintenancePacket();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '生成维护包失败';
  }
}

function formatPct(value: number | null | undefined) {
  return formatWorkbenchNumber(value, 'percent');
}

function formatGeneratedAt(value: string | undefined) {
  return value ? dayjs(value).format('HH:mm:ss') : '--';
}

function systemStatusLabel(value: SystemStatusResponse['status'] | undefined) {
  if (value === 'ok') return '正常';
  if (value === 'degraded') return '降级';
  return '--';
}

function systemStatusTone(value: SystemStatusResponse['status'] | undefined): WorkbenchMetricTone {
  if (value === 'ok') return 'success';
  if (value === 'degraded') return 'warning';
  return 'neutral';
}

function confidenceLabel(value: SystemConfidence | undefined) {
  const labels: Record<SystemConfidence, string> = { fresh: '新鲜', stale: '陈旧', partial: '部分', degraded: '降级', unavailable: '不可用' };
  return value ? labels[value] : '--';
}

function confidenceTone(value: SystemConfidence | undefined): WorkbenchMetricTone {
  if (value === 'fresh') return 'success';
  if (value === 'stale' || value === 'partial') return 'warning';
  if (value === 'degraded' || value === 'unavailable') return 'error';
  return 'neutral';
}

function sourceStatusLabel(value: SourceStatusValue) {
  const labels: Record<SourceStatusValue, string> = { success: '成功', failed: '失败', disabled: '停用', missing_key: '缺少密钥', stale: '陈旧' };
  return labels[value];
}

function sourceStatusTone(value: SourceStatusValue) {
  if (value === 'success') return 'success';
  if (value === 'failed') return 'error';
  if (value === 'stale') return 'warning';
  return 'neutral';
}

function jobStatusTone(job: SystemJobStatus) {
  if (job.running) return 'running';
  return job.enabled ? 'success' : 'neutral';
}

function cacheStatusTone(item: SystemCacheItem) {
  if (item.last_error) return 'failed';
  if (item.refreshing_count > 0) return 'running';
  return 'success';
}

function reportStatusTone(value: ModelMaintenanceReport['health_status']) {
  if (value === 'normal') return 'success';
  if (value === 'watch' || value === 'insufficient_sample') return 'warning';
  return 'error';
}

function asSource(value: unknown) {
  return value as DataSourceStatusResponse['items'][number];
}

function asJob(value: unknown) {
  return value as SystemJobStatus;
}

function asCacheItem(value: unknown) {
  return value as SystemCacheItem;
}

type AiAnalysisDraft = AiAnalysisSettingsUpdate & { api_key: string };

function defaultAiDraft(): AiAnalysisDraft {
  return {
    enabled: false,
    provider: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4.1-mini',
    api_key: '',
    run_after_daily_review: false,
    run_after_weekly_calibration: false
  };
}

function applyAiDraft(config: RuntimeSettingsConfig) {
  const value = config.ai_analysis;
  aiDraft.value = {
    enabled: value.enabled,
    provider: value.provider,
    base_url: value.base_url,
    model: value.model,
    api_key: '',
    run_after_daily_review: value.run_after_daily_review,
    run_after_weekly_calibration: value.run_after_weekly_calibration
  };
}

function buildRuntimeSettingsPayload(current: RuntimeSettingsResponse, draft: AiAnalysisDraft) {
  const { config, saved } = current;
  return {
    candidate_provider: saved.candidate_provider ?? config.candidate_provider,
    kline_provider: saved.kline_provider ?? config.kline_provider,
    quote_provider: saved.quote_provider ?? config.quote_provider,
    tickflow_base_url: saved.tickflow_base_url ?? config.tickflow_base_url,
    ifind_base_url: saved.ifind_base_url ?? config.ifind_base_url,
    ifind_service_id: saved.ifind_service_id ?? config.ifind_service_id,
    tdx_base_url: saved.tdx_base_url ?? config.tdx_base_url,
    provider_timeout_seconds: saved.provider_timeout_seconds ?? config.provider_timeout_seconds,
    notification_channels: saved.notification_channels ?? [],
    sentiment_monitor: saved.sentiment_monitor ?? config.sentiment_monitor,
    gsgf_auto_review: saved.gsgf_auto_review ?? config.gsgf_auto_review,
    auction_top3_training: saved.auction_top3_training ?? config.auction_top3_training,
    ai_analysis: {
      enabled: draft.enabled,
      provider: draft.provider,
      base_url: draft.base_url.trim(),
      model: draft.model.trim(),
      api_key: draft.api_key.trim() || undefined,
      run_after_daily_review: draft.run_after_daily_review,
      run_after_weekly_calibration: draft.run_after_weekly_calibration
    }
  };
}

onMounted(() => void load());
</script>

<template>
  <div class="space-y-16px">
    <PageHeader title="模型与数据源" description="数据源健康、缓存维护和竞价模型训练">
      <template #meta>{{ status?.generated_at ? formatGeneratedAt(status.generated_at) : '等待状态' }}</template>
      <a-button :loading="loading" type="primary" @click="load">刷新状态</a-button>
    </PageHeader>

    <a-alert v-if="error" :title="error" show-icon type="warning" />
    <MetricStrip :items="systemMetrics" />

    <section class="system-panel" data-testid="ai-analysis-settings">
      <SectionHeader title="AI 分析服务" source="情绪盘后解读与模型维护">
        <a-button data-testid="ai-analysis-save" :loading="aiSettingsSaving" type="primary" @click="saveAiSettings">保存 AI 配置</a-button>
      </SectionHeader>
      <a-alert v-if="aiSettingsError" :title="aiSettingsError" show-icon type="warning" />
      <a-alert v-if="aiSettingsMessage" :title="aiSettingsMessage" show-icon type="success" />
      <div v-if="runtimeSettings" class="ai-settings-grid">
        <label class="ai-settings-field ai-settings-field--switch">
          <span>启用 AI 分析</span>
          <a-switch v-model:checked="aiDraft.enabled" />
        </label>
        <label class="ai-settings-field">
          <span>Provider</span>
          <a-select
            v-model:value="aiDraft.provider"
            data-testid="ai-analysis-provider"
            :options="[
              { label: 'OpenAI / Codex', value: 'openai' },
              { label: 'DeepSeek', value: 'deepseek' },
              { label: 'OpenAI Compatible', value: 'openai_compatible' }
            ]"
          />
        </label>
        <label class="ai-settings-field">
          <span>Base URL</span>
          <a-input v-model:value="aiDraft.base_url" data-testid="ai-analysis-base-url" />
        </label>
        <label class="ai-settings-field">
          <span>模型名称</span>
          <a-input v-model:value="aiDraft.model" data-testid="ai-analysis-model" placeholder="deepseek-reasoner / gpt-4.1-mini" />
        </label>
        <label class="ai-settings-field">
          <span>API Key</span>
          <a-input-password
            v-model:value="aiDraft.api_key"
            data-testid="ai-analysis-api-key"
            :placeholder="runtimeSettings.config.ai_analysis.api_key_configured ? '留空表示沿用已保存 Key' : '请输入 AI API Key'"
          />
        </label>
        <label class="ai-settings-field ai-settings-field--switch">
          <span>每日复盘后自动生成建议</span>
          <a-switch v-model:checked="aiDraft.run_after_daily_review" />
        </label>
        <label class="ai-settings-field ai-settings-field--switch">
          <span>每周校准后自动生成建议</span>
          <a-switch v-model:checked="aiDraft.run_after_weekly_calibration" />
        </label>
      </div>
      <div v-else class="system-empty">正在读取 AI 配置</div>
      <div v-if="runtimeSettings" class="system-detail ai-settings-hint">
        当前状态：{{ runtimeSettings.config.ai_analysis.enabled && runtimeSettings.config.ai_analysis.api_key_configured ? '已启用' : '未配置' }} · API Key 只显示配置状态，不会回显完整内容。留空保存时会沿用已有 Key。
      </div>
    </section>

    <div class="grid grid-cols-1 gap-16px xl:grid-cols-2">
      <section class="system-panel">
        <SectionHeader title="数据源健康" source="运行时检查" />
        <DataList :items="sources?.items ?? []" :loading="loading && !sources" empty-description="暂无数据源状态">
          <template #list-item="{ item }">
            <div class="system-source-row">
              <div class="min-w-0">
                <div class="font-600 truncate">{{ asSource(item).source }}</div>
                <div class="system-detail">{{ asSource(item).detail || '暂无补充详情' }}</div>
              </div>
              <div class="system-status-column">
                <StatusTag :status="sourceStatusTone(asSource(item).status)" />
                <span class="text-12px text-text-secondary">{{ sourceStatusLabel(asSource(item).status) }}</span>
              </div>
            </div>
          </template>
        </DataList>
      </section>

      <section class="system-panel">
        <SectionHeader title="后台任务" source="调度状态" />
        <DataList :items="status?.jobs ?? []" :loading="loading && !status" empty-description="暂无后台任务">
          <template #list-item="{ item }">
            <div class="system-job-row">
              <div class="min-w-0">
                <div class="font-600 truncate">{{ asJob(item).name }}</div>
                <div class="system-detail">{{ asJob(item).detail || '暂无任务详情' }}</div>
              </div>
              <div class="system-status-column">
                <StatusTag :status="jobStatusTone(asJob(item))" />
                <span class="text-12px text-text-secondary">{{ asJob(item).running ? '运行中' : asJob(item).enabled ? '启用' : '停用' }}</span>
              </div>
            </div>
          </template>
        </DataList>
      </section>
    </div>

    <section class="system-panel">
      <SectionHeader title="缓存维护" source="运行时缓存">
        <StatusTag :status="cache ? 'success' : loading ? 'running' : 'unknown'" />
      </SectionHeader>
      <DataList :items="cache?.items ?? []" :loading="loading && !cache" empty-description="暂无缓存条目">
        <template #list-item="{ item }">
          <div class="system-cache-row">
            <div class="min-w-0">
              <div class="font-600 truncate">{{ asCacheItem(item).name }}</div>
              <div class="system-detail">{{ asCacheItem(item).group }} · 命中 {{ asCacheItem(item).hits }} · 未命中 {{ asCacheItem(item).misses }} · 条目 {{ asCacheItem(item).size }}</div>
              <div v-if="asCacheItem(item).last_error" class="system-detail system-detail--error">{{ asCacheItem(item).last_error }}</div>
            </div>
            <div class="system-cache-actions">
              <StatusTag :status="cacheStatusTone(asCacheItem(item))" />
              <a-button size="small" :loading="clearing === asCacheItem(item).group" @click="clear(asCacheItem(item).group)">清理</a-button>
            </div>
          </div>
        </template>
      </DataList>
    </section>

    <section class="system-panel">
      <SectionHeader title="竞价 Top3 训练" source="训练与模拟表现" :updated-at="formatGeneratedAt(training?.latest_generated_at || undefined)" />
      <MetricStrip :items="trainingMetrics" />
      <div v-if="training?.quality_notes.length" class="system-notes">
        <span class="system-notes__label">质量提示</span>
        <span v-for="note in training.quality_notes" :key="note">{{ note }}</span>
      </div>
    </section>

    <section class="system-panel">
      <SectionHeader title="模型维护包" source="模型维护服务" :updated-at="formatGeneratedAt(packet?.generated_at)">
        <a-button size="small" type="primary" @click="generatePacket">生成维护包</a-button>
      </SectionHeader>
      <div v-if="packet" class="system-packet-grid">
        <div><span>数据包 ID</span><strong>{{ packet.packet_id }}</strong></div>
        <div><span>交易日</span><strong>{{ packet.trade_date || '--' }}</strong></div>
        <div><span>模型</span><strong>{{ packet.model_name }} · {{ packet.model_version || '--' }}</strong></div>
        <div><span>质量提示</span><strong>{{ packet.data_quality_notes.length }} 条</strong></div>
      </div>
      <div v-else class="system-empty">暂无维护包</div>
      <div v-if="report" class="system-report">
        <div class="system-report__header">
          <div>
            <div class="font-600">维护报告</div>
            <div class="text-12px text-text-secondary">{{ report.provider }} · {{ report.model }} · {{ formatGeneratedAt(report.generated_at) }}</div>
          </div>
          <div class="system-status-column">
            <StatusTag :status="reportStatusTone(report.health_status)" />
            <span class="text-12px text-text-secondary">{{ report.health_status }}</span>
          </div>
        </div>
        <div class="system-report__summary">{{ report.summary || '已有维护报告' }}</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.system-panel {
  padding: 12px;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
}

.system-source-row,
.system-job-row,
.system-cache-row,
.system-report__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.system-detail {
  margin-top: 3px;
  overflow-wrap: anywhere;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.45;
}

.system-detail--error {
  color: var(--wb-positive);
}

.ai-settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
  padding-top: 14px;
}

.ai-settings-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
  color: var(--wb-muted);
  font-size: 12px;
}

.ai-settings-field--switch {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  padding: 0 2px;
}

.ai-settings-hint {
  margin-top: 12px;
}

.system-status-column,
.system-cache-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.system-cache-row {
  align-items: center;
}

.system-packet-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding-top: 14px;
}

.system-packet-grid div {
  min-width: 0;
  padding: 10px;
  background: var(--wb-primary-soft);
  border-radius: 4px;
}

.system-packet-grid span,
.system-packet-grid strong {
  display: block;
  overflow-wrap: anywhere;
}

.system-packet-grid span {
  color: var(--wb-muted);
  font-size: 12px;
}

.system-packet-grid strong {
  margin-top: 5px;
  color: var(--wb-ink);
  font-size: 13px;
}

.system-report {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--wb-border);
}

.system-report__summary {
  margin-top: 10px;
  color: var(--wb-ink);
  font-size: 13px;
  line-height: 1.6;
}

.system-notes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.5;
}

.system-notes__label {
  color: var(--wb-warning);
  font-weight: 600;
}

.system-empty {
  padding: 20px 0 6px;
  color: var(--wb-muted);
  font-size: 13px;
  text-align: center;
}

@media (max-width: 767px) {
  .system-panel {
    padding: 10px;
  }

  .system-packet-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ai-settings-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 639px) {
  .system-source-row,
  .system-job-row,
  .system-cache-row,
  .system-report__header {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .system-status-column,
  .system-cache-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
