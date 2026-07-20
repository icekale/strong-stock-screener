<script setup lang="ts">
import { Skeleton as ASkeleton } from 'ant-design-vue';
import dayjs from 'dayjs';
import { computed, onMounted, reactive, ref } from 'vue';
import IconIcRoundRefresh from '~icons/ic/round-refresh';
import PageHeader from '@/components/common/workbench/page-header.vue';
import SectionHeader from '@/components/common/workbench/section-header.vue';
import StatusTag from '@/components/common/workbench/status-tag.vue';
import HuijinTrajectoryPanel from '@/components/etf-radar/HuijinTrajectoryPanel.vue';
import {
  getEtfRadarHistory,
  getEtfRadarHolders,
  getEtfRadarMethodology,
  getEtfRadarOverview
} from '@/service/product-api';
import type {
  CapitalSignalMetadata,
  EtfActivityDirection,
  EtfHolderPosition,
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarMethodologyResponse,
  EtfRadarOverviewResponse,
  EtfValidationState,
  HuijinEtfActivityItem,
  HuijinEtfBaseline,
  HuijinEtfValidationGroup,
  SourceStatusValue
} from '@/service/types';
import { createMemoryRequestCache } from '@/utils/requestCache';
import {
  activityDirectionLabel,
  directionTone,
  formatActivityMultiple,
  formatDirectionalPercent,
  formatDirectionalShares,
  formatPlainShares,
  stageLabel,
  validationStateLabel,
  validationStateTone
} from '@/utils/domain/capitalSignals';
import { huijinActivityDataState, pickDefaultHuijinSymbol } from '@/utils/domain/huijinTrajectory';

defineOptions({ name: 'EtfRadarView' });

type EtfTab = 'trajectory' | 'activity' | 'holders' | 'methodology';
type EtfDataKey = 'overview' | 'history' | 'holders' | 'methodology';
type EtfResponse =
  | EtfRadarOverviewResponse
  | EtfRadarHistoryResponse
  | EtfRadarHoldersResponse
  | EtfRadarMethodologyResponse;

const activeTab = ref<EtfTab>('trajectory');
const overview = ref<EtfRadarOverviewResponse | null>(null);
const history = ref<EtfRadarHistoryResponse | null>(null);
const holders = ref<EtfRadarHoldersResponse | null>(null);
const methodology = ref<EtfRadarMethodologyResponse | null>(null);
const selectedTrajectorySymbol = ref('');
const historyLoading = ref(false);
const loading = reactive<Record<EtfTab, boolean>>({ trajectory: false, activity: false, holders: false, methodology: false });
const errors = reactive<Record<EtfDataKey, string | null>>({ overview: null, history: null, holders: null, methodology: null });
const loaded = reactive({ holders: false, methodology: false });
const requestCache = createMemoryRequestCache({ ttlMs: 15_000 });

const coreColumns = [
  { title: 'ETF', dataIndex: 'symbol', key: 'etf', width: 188, fixed: 'left' as const },
  { title: '指数', dataIndex: 'index_name', key: 'index_name', width: 110 },
  { title: '份额变化', dataIndex: 'share_delta', key: 'share_delta', width: 130 },
  { title: '日变化', dataIndex: 'daily_change_pct', key: 'daily_change_pct', width: 112 },
  { title: '报告基线变化', dataIndex: 'baseline_change_pct', key: 'baseline_change_pct', width: 132 },
  { title: '倍数', dataIndex: 'multiple', key: 'multiple', width: 88 },
  { title: '方向', dataIndex: 'direction', key: 'direction', width: 136 },
  { title: '确认持仓', dataIndex: 'confirmed_huijin_holding_pct', key: 'holding', width: 178 },
  { title: '数据状态', dataIndex: 'data_state', key: 'data_state', width: 100, fixed: 'right' as const }
];

const baselineColumns = [
  { title: 'ETF', dataIndex: 'symbol', key: 'etf', width: 188 },
  { title: '指数', dataIndex: 'index_name', key: 'index_name', width: 110 },
  { title: '报告期', dataIndex: 'report_period', key: 'report_period', width: 154 },
  { title: '基线总份额', dataIndex: 'baseline_total_shares', key: 'baseline_total_shares', width: 138 },
  { title: '确认汇金份额', dataIndex: 'confirmed_huijin_shares', key: 'confirmed_huijin_shares', width: 138 },
  { title: '持仓比例', dataIndex: 'confirmed_huijin_holding_pct', key: 'confirmed_huijin_holding_pct', width: 108 },
  { title: '来源类型', dataIndex: 'source_kind', key: 'source_kind', width: 108 }
];

const holderColumns = [
  { title: 'ETF', dataIndex: 'symbol', key: 'etf', width: 188 },
  { title: '报告期', dataIndex: 'report_period', key: 'report_period', width: 154 },
  { title: '法律实体', dataIndex: 'entity_name', key: 'entity_name', width: 240 },
  { title: '持仓份额', dataIndex: 'shares', key: 'shares', width: 138 },
  { title: '持仓比例', dataIndex: 'holding_pct', key: 'holding_pct', width: 108 },
  { title: '较上期变化', dataIndex: 'change_shares', key: 'change_shares', width: 138 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 210 }
];

const activeData = computed<EtfResponse | null>(() => {
  if (activeTab.value === 'trajectory') return overview.value ?? history.value;
  if (activeTab.value === 'activity') return overview.value;
  if (activeTab.value === 'holders') return holders.value;
  return methodology.value;
});

const activeMetadata = computed<CapitalSignalMetadata | null>(() => activeData.value);

const overviewMetrics = computed(() => {
  const activity = overview.value?.activity;
  return [
    { label: '十倍量增加', value: activity?.tenfold_increase_count ?? '--', helper: '增加方向', className: 'etf-value--positive' },
    { label: '十倍量减少', value: activity?.tenfold_decrease_count ?? '--', helper: '减少方向', className: 'etf-value--negative' },
    {
      label: '配对一致',
      value: activity ? activity.confirmed_increase_group_count + activity.confirmed_decrease_group_count : '--',
      helper: activity ? `增加 ${activity.confirmed_increase_group_count} / 减少 ${activity.confirmed_decrease_group_count}` : '增加 -- / 减少 --',
      className: ''
    },
    { label: '方向分歧', value: activity?.divergent_group_count ?? '--', helper: '配对方向不一致', className: '' }
  ];
});

const validationItemsBySymbol = computed(() => {
  const items = [...(overview.value?.core_items ?? []), ...(overview.value?.validation_items ?? [])];
  return new Map(items.map(item => [item.symbol, item]));
});

const formulaFactors = computed(() =>
  (methodology.value?.factors ?? []).filter(factor => !factor.key.startsWith('validation_'))
);

const validationRuleFactors = computed(() =>
  (methodology.value?.factors ?? []).filter(factor => factor.key.startsWith('validation_'))
);

function sourceStatusTone(status: SourceStatusValue) {
  return status === 'success' ? 'success' : status === 'stale' ? 'partial' : status === 'failed' ? 'failed' : 'unknown';
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function formatAsOf(value: string | undefined) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '--';
}

function valueTone(value: number | null | undefined) {
  const tone = directionTone(value ?? null);
  return tone === 'rise' ? 'etf-value--positive' : tone === 'fall' ? 'etf-value--negative' : '';
}

function validationTone(state: EtfValidationState) {
  const tone = validationStateTone(state);
  return tone === 'rise' ? 'etf-value--positive' : tone === 'fall' ? 'etf-value--negative' : '';
}

function formatPercent(value: number | null | undefined) {
  return formatDirectionalPercent(value ?? null);
}

function formatHoldingPct(value: number | null | undefined) {
  return value == null ? '--' : `${value.toFixed(2)}%`;
}

function formatFingerprint(value: string | null | undefined) {
  if (!value) return '--';
  return value.length > 10 ? `${value.slice(0, 10)}...` : value;
}

function directionDisplay(direction: EtfActivityDirection) {
  if (direction === 'increase') return `增加（${activityDirectionLabel(direction)}代理）`;
  if (direction === 'decrease') return `减少（${activityDirectionLabel(direction)}代理）`;
  return activityDirectionLabel(direction);
}

function directionClass(direction: EtfActivityDirection) {
  return direction === 'increase' ? 'etf-value--positive' : direction === 'decrease' ? 'etf-value--negative' : '';
}

function coreCell(key: string, record: unknown) {
  const item = record as HuijinEtfActivityItem;
  if (key === 'share_delta') return formatDirectionalShares(item.share_delta);
  if (key === 'daily_change_pct') return formatPercent(item.daily_change_pct);
  if (key === 'baseline_change_pct') return formatPercent(item.baseline_change_pct);
  if (key === 'multiple') return formatActivityMultiple(item.multiple);
  if (key === 'direction') return directionDisplay(item.direction);
  if (key === 'data_state') return huijinActivityDataState(item);
  return String(item[key as keyof HuijinEtfActivityItem] ?? '--');
}

function baselineCell(key: string, record: unknown) {
  const baseline = record as HuijinEtfBaseline;
  if (key === 'baseline_total_shares') return formatPlainShares(baseline.baseline_total_shares);
  if (key === 'confirmed_huijin_shares') return formatPlainShares(baseline.confirmed_huijin_shares);
  if (key === 'confirmed_huijin_holding_pct') return formatHoldingPct(baseline.confirmed_huijin_holding_pct);
  if (key === 'source_kind') return baseline.source_kind === 'reported' ? '报告披露' : '数据推导';
  return String(baseline[key as keyof HuijinEtfBaseline] ?? '--');
}

function holderCell(key: string, record: unknown) {
  const position = record as EtfHolderPosition;
  if (key === 'shares') return formatPlainShares(position.shares);
  if (key === 'holding_pct') return formatHoldingPct(position.holding_pct);
  if (key === 'change_shares') return formatDirectionalShares(position.change_shares);
  return String(position[key as keyof EtfHolderPosition] ?? '--');
}

function validationItem(symbol: string) {
  return validationItemsBySymbol.value.get(symbol);
}

function validationBaseline(symbol: string) {
  return formatPercent(validationItem(symbol)?.baseline_change_pct);
}

function conservativeResult(group: HuijinEtfValidationGroup) {
  if (group.state === 'divergent' || group.state === 'incomplete') return '--';
  return formatPercent(group.conservative_baseline_change_pct);
}

function conservativeMultiple(group: HuijinEtfValidationGroup) {
  if (group.state === 'divergent' || group.state === 'incomplete') return '--';
  return formatActivityMultiple(group.conservative_multiple);
}

function thresholdLabel(key: string) {
  return key === 'tenfold_baseline_pct' ? '十倍阈值' : key;
}

function thresholdValue(key: string, value: number) {
  return key === 'tenfold_baseline_pct' ? `${value.toFixed(2)}%` : String(value);
}

function columnKey(key: unknown) {
  return typeof key === 'string' ? key : '';
}

function recordNumber(record: unknown, key: unknown) {
  if (record === null || typeof record !== 'object' || typeof key !== 'string') return null;
  const value = (record as Record<string, unknown>)[key];
  return typeof value === 'number' ? value : null;
}

function holderRowKey(position: EtfHolderPosition) {
  return `${position.report_period}-${position.symbol}-${position.entity_name}`;
}

function activeDataKey(): Exclude<EtfDataKey, 'history'> {
  if (activeTab.value === 'activity' || activeTab.value === 'trajectory') return 'overview';
  return activeTab.value;
}

function dataErrorMessage(key: EtfDataKey, data: EtfResponse | null) {
  const error = errors[key];
  if (!error) return '';
  return data ? `${error}；当前显示上次成功数据` : error;
}

function activeErrorMessage() {
  return dataErrorMessage(activeDataKey(), activeData.value);
}

function activeStatus() {
  if (loading[activeTab.value]) return 'running';
  const error = errors[activeDataKey()];
  if (error && activeData.value) return 'partial';
  if (error) return 'failed';
  if (activeData.value?.source_status.some(source => source.status === 'stale' || source.status === 'failed')) {
    return 'partial';
  }
  return activeData.value ? 'success' : 'unknown';
}

function activeSources() {
  return activeMetadata.value?.source_status ?? [];
}

async function loadOverview(force = false) {
  loading.activity = true;
  errors.overview = null;
  try {
    overview.value = await requestCache.get('etf-radar-overview', getEtfRadarOverview, { force });
  } catch (error) {
    errors.overview = errorMessage(error, '读取汇金持仓概览失败');
  } finally {
    loading.activity = false;
  }
}

async function loadHistory(force = false) {
  historyLoading.value = true;
  errors.history = null;
  try {
    history.value = await requestCache.get('etf-radar-history', () => getEtfRadarHistory(120), { force });
  } catch (error) {
    errors.history = errorMessage(error, '读取汇金持仓历史失败');
  } finally {
    historyLoading.value = false;
  }
}

async function loadTrajectory(force = false) {
  loading.trajectory = true;
  await Promise.allSettled([loadOverview(force), loadHistory(force)]);
  if (!selectedTrajectorySymbol.value && overview.value) {
    selectedTrajectorySymbol.value = pickDefaultHuijinSymbol(overview.value.core_items);
  }
  loading.trajectory = false;
}

async function loadLazyTab(tab: 'holders' | 'methodology', force = false) {
  if (!force && loaded[tab]) return;
  loading[tab] = true;
  errors[tab] = null;
  try {
    if (tab === 'holders') holders.value = await requestCache.get('etf-radar-holders', getEtfRadarHolders, { force });
    if (tab === 'methodology') methodology.value = await requestCache.get('etf-radar-methodology', getEtfRadarMethodology, { force });
    loaded[tab] = true;
  } catch (error) {
    errors[tab] = errorMessage(error, '读取汇金持仓追踪数据失败');
  } finally {
    loading[tab] = false;
  }
}

function loadTab(tab: EtfTab, force = false) {
  if (tab === 'trajectory') return loadTrajectory(force);
  if (tab === 'activity') return force ? loadOverview(true) : Promise.resolve();
  return loadLazyTab(tab, force);
}

function changeTab(tab: unknown) {
  if (tab === 'holders' || tab === 'methodology') void loadLazyTab(tab);
}

onMounted(() => void loadTrajectory());
</script>

<template>
  <div class="etf-radar-page">
    <PageHeader
      title="汇金持仓追踪"
      description="分开展示定期报告确认持仓与每日 ETF 份额活动代理，不将份额变化视为国家队确认交易。"
    >
      <template #meta>
        <div class="etf-header-meta">
          <span>交易日 {{ activeMetadata?.trade_date || '--' }}</span>
          <span>{{ activeMetadata ? stageLabel(activeMetadata.signal_stage) : '待确认' }}</span>
          <span>更新 {{ formatAsOf(activeMetadata?.as_of) }}</span>
        </div>
      </template>
      <a-button data-testid="etf-refresh" :loading="loading[activeTab]" @click="void loadTab(activeTab, true)">
        <icon-ic-round-refresh aria-hidden="true" />
        <span>刷新当前视图</span>
      </a-button>
    </PageHeader>

    <a-tabs v-model:active-key="activeTab" class="etf-tabs" @change="changeTab">
      <a-tab-pane key="trajectory" tab="持仓轨迹" />
      <a-tab-pane key="activity" tab="日度活动" />
      <a-tab-pane key="holders" tab="确认持仓" />
      <a-tab-pane key="methodology" tab="方法与数据" />
    </a-tabs>

    <section v-if="activeTab === 'trajectory'" class="etf-panel etf-panel--trajectory">
      <a-alert
        v-if="errors.overview"
        data-testid="etf-panel-error"
        type="warning"
        :message="dataErrorMessage('overview', overview)"
        show-icon
      />
      <div v-if="loading.trajectory && !overview" class="etf-loading" aria-label="正在读取持仓轨迹">
        <a-skeleton active :paragraph="{ rows: 8 }" />
      </div>
      <HuijinTrajectoryPanel
        v-else-if="overview"
        :overview="overview"
        :history="history"
        :selected-symbol="selectedTrajectorySymbol"
        :history-loading="historyLoading"
        :history-error="dataErrorMessage('history', history) || null"
        @select="selectedTrajectorySymbol = $event"
      />
      <div v-else-if="!errors.overview" class="etf-state">暂无持仓轨迹数据</div>
    </section>

    <section v-else-if="activeTab === 'activity'" class="etf-panel">
      <SectionHeader title="今日份额活动" source="交易所份额与报告基线" :updated-at="formatAsOf(overview?.as_of)">
        <StatusTag :status="activeStatus()" />
      </SectionHeader>
      <a-alert v-if="errors.overview" data-testid="etf-panel-error" type="warning" :message="activeErrorMessage()" show-icon />
      <div v-if="loading.activity && !overview" class="etf-loading" aria-label="正在读取今日活动">
        <a-skeleton active :paragraph="{ rows: 7 }" />
      </div>
      <div v-else-if="overview" class="etf-panel-content">
        <div class="etf-metrics" aria-label="今日活动摘要">
          <div v-for="metric in overviewMetrics" :key="metric.label" class="etf-metric">
            <span class="etf-metric__label">{{ metric.label }}</span>
            <strong :class="metric.className">{{ metric.value }}</strong>
            <small>{{ metric.helper }}</small>
          </div>
        </div>

        <div class="etf-compact-meta">
          <span>核心池 {{ overview.pool_version || '--' }}</span>
          <span>报告基线 {{ overview.baseline_version || '--' }}</span>
          <span
            data-testid="baseline-fingerprint"
            class="etf-fingerprint"
            :title="overview.baseline_fingerprint || undefined"
          >基线指纹 {{ formatFingerprint(overview.baseline_fingerprint) }}</span>
          <span>模型 {{ overview.model_version || '--' }}</span>
        </div>

        <div class="etf-source-statuses">
          <div v-for="source in activeSources()" :key="source.source" class="etf-source-status">
            <span class="etf-source-status__summary">
              {{ source.source }} <StatusTag :status="sourceStatusTone(source.status)" />
            </span>
            <span class="etf-source-status__detail">{{ source.detail || '--' }}</span>
          </div>
        </div>

        <div
          v-if="overview.core_items.length"
          class="etf-table-scroll"
          tabindex="0"
          role="region"
          aria-label="核心 ETF 今日活动表"
        >
          <a-table
            data-testid="core-table"
            :columns="coreColumns"
            :data-source="overview.core_items"
            :pagination="false"
            :scroll="{ x: 1184 }"
            row-key="symbol"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <div v-if="columnKey(column.key) === 'etf'" data-testid="core-etf-row" class="etf-name-cell">
                <strong :title="record.name">{{ record.name }}</strong>
                <span>{{ record.symbol }}</span>
              </div>
              <div v-else-if="columnKey(column.key) === 'holding'" class="etf-holding-cell">
                <span>{{ formatHoldingPct(record.confirmed_huijin_holding_pct) }}</span>
                <small>{{ record.report_period ? `报告期 ${record.report_period}` : '--' }}</small>
              </div>
              <span
                v-else
                :class="[
                  ['share_delta', 'daily_change_pct', 'baseline_change_pct'].includes(columnKey(column.key)) ? valueTone(recordNumber(record, column.key)) : '',
                  columnKey(column.key) === 'direction' ? directionClass(record.direction) : ''
                ]"
              >
                {{ coreCell(columnKey(column.key), record) }}
              </span>
            </template>
          </a-table>
        </div>
        <div v-else class="etf-state">暂无核心 ETF 活动数据</div>

        <div class="etf-divider" />
        <h3 class="etf-subheading">交叉验证</h3>
        <div
          v-if="overview.validation_groups.length"
          class="etf-validation-list"
          tabindex="0"
          role="region"
          aria-label="ETF 配对交叉验证"
        >
          <div v-for="group in overview.validation_groups" :key="group.index_name" data-testid="validation-row" class="etf-validation-row">
            <strong>{{ group.index_name }}</strong>
            <div class="etf-validation-pair">
              <span>{{ group.core_symbol }} <b :class="valueTone(validationItem(group.core_symbol)?.baseline_change_pct)">{{ validationBaseline(group.core_symbol) }}</b></span>
              <span>{{ group.validator_symbol }} <b :class="valueTone(validationItem(group.validator_symbol)?.baseline_change_pct)">{{ validationBaseline(group.validator_symbol) }}</b></span>
            </div>
            <span>保守结果 <b data-testid="validation-conservative" :class="validationTone(group.state)">{{ conservativeResult(group) }}</b></span>
            <span>保守倍数 <b>{{ conservativeMultiple(group) }}</b></span>
            <span class="etf-validation-state" :class="validationTone(group.state)">{{ validationStateLabel(group.state) }}</span>
          </div>
        </div>
        <div v-else class="etf-state etf-state--compact">暂无配对验证数据</div>
      </div>
      <div v-else-if="!errors.overview" class="etf-state">暂无今日活动数据</div>
    </section>

    <section v-else-if="activeTab === 'holders'" class="etf-panel">
      <SectionHeader title="确认持仓" source="基金定期报告" :updated-at="formatAsOf(holders?.as_of)">
        <StatusTag :status="activeStatus()" />
      </SectionHeader>
      <a-alert v-if="errors.holders" data-testid="etf-panel-error" type="warning" :message="activeErrorMessage()" show-icon />
      <div v-if="loading.holders && !holders" class="etf-loading" aria-label="正在读取确认持仓">
        <a-skeleton active :paragraph="{ rows: 8 }" />
      </div>
      <div v-else-if="holders" class="etf-panel-content">
        <p class="etf-disclosure-note">报告期确认的法律实体持仓，不是实时资金流。</p>
        <div class="etf-source-statuses">
          <div v-for="source in activeSources()" :key="source.source" class="etf-source-status">
            <span class="etf-source-status__summary">
              {{ source.source }} <StatusTag :status="sourceStatusTone(source.status)" />
            </span>
            <span class="etf-source-status__detail">{{ source.detail || '--' }}</span>
          </div>
        </div>

        <h3 class="etf-subheading">确认基线</h3>
        <div
          v-if="holders.baselines.length"
          class="etf-table-scroll"
          tabindex="0"
          role="region"
          aria-label="确认持仓基线表"
        >
          <a-table
            data-testid="holder-baseline-table"
            :columns="baselineColumns"
            :data-source="holders.baselines"
            :pagination="false"
            :scroll="{ x: 944 }"
            row-key="baseline_id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <div v-if="columnKey(column.key) === 'etf'" class="etf-name-cell">
                <strong :title="record.name">{{ record.name }}</strong><span>{{ record.symbol }}</span>
              </div>
              <span v-else-if="columnKey(column.key) === 'report_period'">报告期 {{ record.report_period }}</span>
              <span v-else>{{ baselineCell(columnKey(column.key), record) }}</span>
            </template>
          </a-table>
        </div>
        <div v-else class="etf-state etf-state--compact">暂无确认基线</div>

        <div class="etf-divider" />
        <h3 class="etf-subheading">精确实体持仓</h3>
        <div
          v-if="holders.positions.length"
          class="etf-table-scroll"
          tabindex="0"
          role="region"
          aria-label="精确实体持仓表"
        >
          <a-table
            data-testid="holder-position-table"
            :columns="holderColumns"
            :data-source="holders.positions"
            :pagination="false"
            :scroll="{ x: 1176 }"
            :row-key="holderRowKey"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <div v-if="columnKey(column.key) === 'etf'" class="etf-name-cell">
                <strong :title="record.name">{{ record.name }}</strong><span>{{ record.symbol }}</span>
              </div>
              <span v-else-if="columnKey(column.key) === 'report_period'">报告期 {{ record.report_period }}</span>
              <span v-else :class="columnKey(column.key) === 'change_shares' ? valueTone(record.change_shares) : ''">
                {{ holderCell(columnKey(column.key), record) }}
              </span>
            </template>
          </a-table>
        </div>
        <div v-else class="etf-state etf-state--compact">暂无精确实体持仓</div>
      </div>
      <div v-else-if="!errors.holders" class="etf-state">暂无确认持仓数据</div>
    </section>

    <section v-else class="etf-panel">
      <SectionHeader title="方法与数据" source="后端方法说明" :updated-at="formatAsOf(methodology?.as_of)">
        <StatusTag :status="activeStatus()" />
      </SectionHeader>
      <a-alert v-if="errors.methodology" data-testid="etf-panel-error" type="warning" :message="activeErrorMessage()" show-icon />
      <div v-if="loading.methodology && !methodology" class="etf-loading" aria-label="正在读取方法与数据">
        <a-skeleton active :paragraph="{ rows: 8 }" />
      </div>
      <div v-else-if="methodology" class="etf-panel-content etf-methodology">
        <div class="etf-source-statuses">
          <div v-for="source in activeSources()" :key="source.source" class="etf-source-status">
            <span class="etf-source-status__summary">
              {{ source.source }} <StatusTag :status="sourceStatusTone(source.status)" />
            </span>
            <span class="etf-source-status__detail">{{ source.detail || '--' }}</span>
          </div>
        </div>
        <div class="etf-compact-meta">
          <span>交易日 {{ methodology.trade_date || '--' }}</span>
          <span>模型 {{ methodology.model_version || '--' }}</span>
          <span>更新 {{ formatAsOf(methodology.as_of) }}</span>
        </div>

        <div class="etf-methodology-grid">
          <div>
            <h3 class="etf-subheading">公式与数据因子</h3>
            <dl class="etf-factor-list">
              <div v-for="factor in formulaFactors" :key="factor.key" data-testid="method-factor">
                <dt>{{ factor.name }}</dt>
                <dd>{{ factor.description }} · {{ factor.availability }}</dd>
              </div>
            </dl>
            <div v-if="formulaFactors.length === 0" class="etf-state etf-state--compact">暂无因子说明</div>
          </div>
          <div>
            <h3 class="etf-subheading">阈值与追踪池</h3>
            <dl class="etf-definition-list">
              <template v-for="(value, key) in methodology.thresholds" :key="key">
                <dt>{{ thresholdLabel(String(key)) }}</dt>
                <dd>{{ thresholdValue(String(key), value) }}</dd>
              </template>
              <dt>池版本</dt>
              <dd>{{ methodology.pool_version || '--' }}</dd>
              <dt>精确池</dt>
              <dd>{{ methodology.core_pool.length ? methodology.core_pool.join('、') : '--' }}</dd>
            </dl>
          </div>
        </div>

        <div class="etf-divider" />
        <h3 class="etf-subheading">配对验证规则</h3>
        <div v-if="validationRuleFactors.length" class="etf-rule-list">
          <p v-for="factor in validationRuleFactors" :key="factor.key" data-testid="validation-rule">
            <strong>{{ factor.name }}</strong>
            <span>{{ factor.description }} · {{ factor.availability }}</span>
          </p>
        </div>
        <div v-else class="etf-state etf-state--compact">暂无配对验证规则</div>

        <div class="etf-limitations">
          <h3 class="etf-subheading">限制</h3>
          <ul v-if="methodology.limitations.length">
            <li v-for="limitation in methodology.limitations" :key="limitation">{{ limitation }}</li>
          </ul>
          <div v-else class="etf-state etf-state--compact">后端未提供限制说明</div>
        </div>
      </div>
      <div v-else-if="!errors.methodology" class="etf-state">暂无方法与数据说明</div>
    </section>
  </div>
</template>

<style scoped>
.etf-radar-page {
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  color: var(--wb-ink);
}

.etf-header-meta,
.etf-source-statuses,
.etf-compact-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
  color: var(--wb-muted);
  font-size: 12px;
}

.etf-tabs {
  margin: 0 0 12px;
}

.etf-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
  background: var(--wb-surface);
}

.etf-panel :deep(.wb-section-header) {
  padding: 12px 16px;
}

.etf-panel > :deep(.ant-alert) {
  margin: 0 16px 12px;
}

.etf-panel-content {
  min-width: 0;
  padding: 0 16px 16px;
}

.etf-loading {
  padding: 8px 16px 20px;
}

.etf-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 12px;
  border-bottom: 1px solid var(--wb-border);
}

.etf-metric {
  min-width: 0;
  padding: 4px 12px 12px;
  border-inline-end: 1px solid var(--wb-border);
}

.etf-metric:last-child {
  border-inline-end: 0;
}

.etf-metric__label,
.etf-metric small,
.etf-name-cell span,
.etf-holding-cell small {
  display: block;
  color: var(--wb-muted);
  font-size: 12px;
}

.etf-metric strong {
  display: block;
  margin: 3px 0;
  font-size: 18px;
  line-height: 24px;
}

.etf-compact-meta,
.etf-source-statuses {
  margin-bottom: 10px;
}

.etf-source-status {
  display: flex;
  flex: 1 1 260px;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.etf-source-status__summary {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}

.etf-source-status__detail,
.etf-fingerprint {
  overflow-wrap: anywhere;
}

.etf-source-status__detail {
  color: var(--wb-muted);
  line-height: 1.4;
}

.etf-table-scroll {
  min-width: 0;
  overflow-x: auto;
}

.etf-name-cell,
.etf-holding-cell {
  min-width: 0;
  line-height: 1.35;
}

.etf-name-cell strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.etf-value--positive {
  color: var(--wb-positive);
}

.etf-value--negative {
  color: var(--wb-negative);
}

.etf-state,
.etf-chart-empty {
  padding: 40px 16px;
  color: var(--wb-muted);
  text-align: center;
}

.etf-state--compact {
  padding: 20px 12px;
}

.etf-chart-empty {
  display: grid;
  min-height: 304px;
  place-items: center;
  border-block: 1px solid var(--wb-border);
}

.etf-divider {
  height: 1px;
  margin: 16px 0 12px;
  background: var(--wb-border);
}

.etf-subheading {
  margin: 0 0 10px;
  color: var(--wb-ink);
  font-size: 14px;
  line-height: 20px;
}

.etf-validation-list {
  min-width: 0;
  overflow-x: auto;
  border-block: 1px solid var(--wb-border);
}

.etf-validation-row {
  display: grid;
  grid-template-columns: minmax(90px, 0.7fr) minmax(300px, 2fr) minmax(140px, 1fr) minmax(120px, 0.8fr) 88px;
  gap: 12px;
  align-items: center;
  min-width: 820px;
  padding: 9px 4px;
  border-bottom: 1px solid var(--wb-border);
  font-size: 12px;
}

.etf-validation-row:last-child {
  border-bottom: 0;
}

.etf-validation-pair {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}

.etf-validation-state {
  font-weight: 600;
}

.etf-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: center;
  margin-bottom: 10px;
  color: var(--wb-muted);
  font-size: 12px;
}

.etf-toolbar label {
  color: var(--wb-ink);
  font-weight: 600;
}

.etf-history-select {
  width: min(320px, 100%);
}

.etf-history-table {
  margin-top: 14px;
}

.etf-disclosure-note {
  margin: 0 0 10px;
  color: var(--wb-ink);
  font-weight: 600;
}

.etf-methodology-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 1fr);
  gap: 28px;
}

.etf-factor-list,
.etf-definition-list {
  margin: 0;
}

.etf-factor-list > div {
  display: grid;
  grid-template-columns: minmax(120px, 0.35fr) minmax(0, 1fr);
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--wb-border);
}

.etf-factor-list dt,
.etf-definition-list dt {
  color: var(--wb-ink);
  font-weight: 600;
}

.etf-factor-list dd,
.etf-definition-list dd {
  margin: 0;
  color: var(--wb-muted);
}

.etf-definition-list {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 8px 12px;
}

.etf-rule-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-block: 1px solid var(--wb-border);
}

.etf-rule-list p {
  margin: 0;
  padding: 10px 12px;
  border-inline-end: 1px solid var(--wb-border);
}

.etf-rule-list p:last-child {
  border-inline-end: 0;
}

.etf-rule-list strong,
.etf-rule-list span {
  display: block;
}

.etf-rule-list span {
  margin-top: 4px;
  color: var(--wb-muted);
  font-size: 12px;
}

.etf-limitations {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid var(--wb-warning);
  border-radius: var(--wb-radius);
  background: var(--wb-status-warning-soft);
}

.etf-limitations ul {
  margin: 0;
  padding-left: 18px;
}

@media (max-width: 760px) {
  .etf-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .etf-metric:nth-child(2) {
    border-inline-end: 0;
  }

  .etf-metric:nth-child(-n + 2) {
    border-bottom: 1px solid var(--wb-border);
  }

  .etf-methodology-grid,
  .etf-rule-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .etf-rule-list p {
    border-inline-end: 0;
    border-bottom: 1px solid var(--wb-border);
  }

  .etf-rule-list p:last-child {
    border-bottom: 0;
  }

  .etf-factor-list > div {
    grid-template-columns: minmax(0, 1fr);
    gap: 3px;
  }
}
</style>
