<script setup lang="ts">
import type { EChartsOption } from 'echarts';
import dayjs from 'dayjs';
import { computed, onMounted, reactive, ref } from 'vue';
import EChart from '@/components/charts/EChart.vue';
import PageHeader from '@/components/common/workbench/page-header.vue';
import SectionHeader from '@/components/common/workbench/section-header.vue';
import StatusTag from '@/components/common/workbench/status-tag.vue';
import {
  getEtfRadarHistory,
  getEtfRadarHolders,
  getEtfRadarMethodology,
  getEtfRadarOverview
} from '@/service/product-api';
import type {
  CapitalSignalMetadata,
  EtfHolderPosition,
  EtfRadarHistoryPoint,
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarItem,
  EtfRadarMethodologyResponse,
  EtfRadarOverviewResponse,
  SourceStatusValue
} from '@/service/types';
import { createMemoryRequestCache } from '@/utils/requestCache';
import {
  directionTone,
  formatDirectionalCny,
  formatDirectionalPercent,
  formatDirectionalShares,
  formatEvidenceStrength,
  formatPlainCny,
  formatPlainShares,
  stageLabel
} from '@/utils/domain/capitalSignals';

defineOptions({ name: 'EtfRadarView' });

type EtfTab = 'overview' | 'history' | 'holders' | 'methodology';
type EtfResponse =
  | EtfRadarOverviewResponse
  | EtfRadarHistoryResponse
  | EtfRadarHoldersResponse
  | EtfRadarMethodologyResponse;

const activeTab = ref<EtfTab>('overview');
const overview = ref<EtfRadarOverviewResponse | null>(null);
const history = ref<EtfRadarHistoryResponse | null>(null);
const holders = ref<EtfRadarHoldersResponse | null>(null);
const methodology = ref<EtfRadarMethodologyResponse | null>(null);
const loading = reactive<Record<EtfTab, boolean>>({ overview: false, history: false, holders: false, methodology: false });
const errors = reactive<Record<EtfTab, string | null>>({ overview: null, history: null, holders: null, methodology: null });
const loaded = reactive<Record<EtfTab, boolean>>({ overview: false, history: false, holders: false, methodology: false });
const requestCache = createMemoryRequestCache({ ttlMs: 15_000 });

const overviewColumns = [
  { title: 'ETF', dataIndex: 'name', key: 'name' },
  { title: '指数', dataIndex: 'index_name', key: 'index_name' },
  { title: '证据强度', dataIndex: 'evidence_strength', key: 'evidence_strength' },
  { title: '份额变化', dataIndex: 'share_change', key: 'share_change' },
  { title: '估算申购', dataIndex: 'estimated_subscription_cny', key: 'estimated_subscription_cny' },
  { title: '稳健分', dataIndex: 'robust_score', key: 'robust_score' },
  { title: '同时间成交', dataIndex: 'same_time_turnover_ratio', key: 'same_time_turnover_ratio' },
  { title: '相对指数', dataIndex: 'relative_index_return_pct', key: 'relative_index_return_pct' }
];

const historyColumns = [
  { title: '交易日', dataIndex: 'trade_date', key: 'trade_date' },
  { title: 'ETF', dataIndex: 'name', key: 'name' },
  { title: '份额', dataIndex: 'total_shares', key: 'total_shares' },
  { title: '份额变化', dataIndex: 'share_change', key: 'share_change' },
  { title: '估算申购', dataIndex: 'estimated_subscription_cny', key: 'estimated_subscription_cny' },
  { title: '稳健分', dataIndex: 'robust_score', key: 'robust_score' }
];

const holderColumns = [
  { title: 'ETF', dataIndex: 'name', key: 'name' },
  { title: '报告期', dataIndex: 'report_period', key: 'report_period' },
  { title: '披露实体', dataIndex: 'entity_name', key: 'entity_name' },
  { title: '持仓份额', dataIndex: 'shares', key: 'shares' },
  { title: '持仓比例', dataIndex: 'holding_pct', key: 'holding_pct' },
  { title: '份额变化', dataIndex: 'change_shares', key: 'change_shares' },
  { title: '来源', dataIndex: 'source', key: 'source' }
];

const activeData = computed<EtfResponse | null>(() => {
  if (activeTab.value === 'overview') return overview.value;
  if (activeTab.value === 'history') return history.value;
  if (activeTab.value === 'holders') return holders.value;
  return methodology.value;
});

const activeMetadata = computed<CapitalSignalMetadata | null>(() => activeData.value);

const historyDaily = computed(() => {
  const totals = new Map<string, number>();
  for (const point of history.value?.points ?? []) {
    if (point.estimated_subscription_cny == null) continue;
    totals.set(point.trade_date, (totals.get(point.trade_date) ?? 0) + point.estimated_subscription_cny);
  }
  return [...totals.entries()].sort(([left], [right]) => left.localeCompare(right));
});

const historyOption = computed<EChartsOption>(() => ({
  aria: {
    enabled: true,
    description: '按交易日汇总ETF估算申购金额，红色表示正向估算申购，绿色表示负向估算申购。'
  },
  animation: false,
  grid: { left: 54, right: 24, top: 24, bottom: 34 },
  tooltip: { trigger: 'axis', valueFormatter: value => formatDirectionalCny(Number(value)) },
  xAxis: { type: 'category', data: historyDaily.value.map(([date]) => date) },
  yAxis: { type: 'value', axisLabel: { formatter: (value: number) => formatPlainCny(value) } },
  series: [{
    type: 'bar',
    barMaxWidth: 24,
    data: historyDaily.value.map(([, value]) => ({
      value,
      itemStyle: { color: value >= 0 ? '#d9363e' : '#07845e' }
    }))
  }]
}));

const overviewMetrics = computed(() => [
  { label: '证据强度', value: formatEvidenceStrength(overview.value?.evidence_strength ?? null), helper: overview.value?.evidence_level || '待确认' },
  { label: '方向性估算申购', value: formatDirectionalCny(overview.value?.estimated_subscription_cny ?? null), tone: directionTone(overview.value?.estimated_subscription_cny ?? null) },
  { label: '有效ETF', value: overview.value ? `${overview.value.valid_etf_count}/${overview.value.expected_etf_count}` : '--', helper: '核心池覆盖' },
  { label: '模型版本', value: overview.value?.model_version || '--', helper: overview.value ? stageLabel(overview.value.signal_stage) : '待确认' }
]);

function sourceStatusTone(status: SourceStatusValue) {
  return status === 'success' ? 'success' : status === 'stale' ? 'warning' : status === 'failed' ? 'failed' : 'unknown';
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

function overviewCell(key: string, item: unknown) {
  const etf = item as EtfRadarItem;
  if (key === 'evidence_strength') return formatEvidenceStrength(etf.evidence_strength);
  if (key === 'share_change') return formatDirectionalShares(etf.share_change);
  if (key === 'estimated_subscription_cny') return formatDirectionalCny(etf.estimated_subscription_cny);
  if (key === 'robust_score') return etf.robust_score == null ? '--' : etf.robust_score.toFixed(1);
  if (key === 'same_time_turnover_ratio') return etf.same_time_turnover_ratio == null ? '--' : `${etf.same_time_turnover_ratio.toFixed(2)}x`;
  if (key === 'relative_index_return_pct') return formatDirectionalPercent(etf.relative_index_return_pct);
  return String(etf[key as keyof EtfRadarItem] ?? '--');
}

function historyCell(key: string, point: unknown) {
  const historyPoint = point as EtfRadarHistoryPoint;
  if (key === 'total_shares') return formatPlainShares(historyPoint.total_shares);
  if (key === 'share_change') return formatDirectionalShares(historyPoint.share_change);
  if (key === 'estimated_subscription_cny') return formatDirectionalCny(historyPoint.estimated_subscription_cny);
  if (key === 'robust_score') return historyPoint.robust_score == null ? '--' : historyPoint.robust_score.toFixed(1);
  return String(historyPoint[key as keyof EtfRadarHistoryPoint] ?? '--');
}

function holderCell(key: string, position: unknown) {
  const holder = position as EtfHolderPosition;
  if (key === 'shares' || key === 'change_shares') return key === 'shares' ? formatPlainShares(holder.shares) : formatDirectionalShares(holder.change_shares);
  if (key === 'holding_pct') return holder.holding_pct == null ? '--' : `${holder.holding_pct.toFixed(2)}%`;
  return String(holder[key as keyof EtfHolderPosition] ?? '--');
}

function columnKey(key: unknown) {
  return typeof key === 'string' ? key : '';
}

function recordNumber(record: unknown, key: unknown) {
  if (record === null || typeof record !== 'object' || typeof key !== 'string') return null;
  const value = (record as Record<string, unknown>)[key];
  return typeof value === 'number' ? value : null;
}

async function loadTab(tab: EtfTab, force = false) {
  if (!force && loaded[tab]) return;
  loading[tab] = true;
  errors[tab] = null;
  try {
    if (tab === 'overview') overview.value = await requestCache.get('etf-radar-overview', getEtfRadarOverview, { force });
    if (tab === 'history') history.value = await requestCache.get('etf-radar-history', () => getEtfRadarHistory(120), { force });
    if (tab === 'holders') holders.value = await requestCache.get('etf-radar-holders', getEtfRadarHolders, { force });
    if (tab === 'methodology') methodology.value = await requestCache.get('etf-radar-methodology', getEtfRadarMethodology, { force });
    loaded[tab] = true;
  } catch (error) {
    errors[tab] = errorMessage(error, '读取ETF资金雷达失败');
  } finally {
    loading[tab] = false;
  }
}

function changeTab(tab: unknown) {
  if (typeof tab !== 'string') return;
  if (tab === 'overview' || tab === 'history' || tab === 'holders' || tab === 'methodology') void loadTab(tab);
}

function activeError() {
  return errors[activeTab.value];
}

function activeLoading() {
  return loading[activeTab.value];
}

function activeSources() {
  return activeMetadata.value?.source_status ?? [];
}

onMounted(() => void loadTab('overview'));
</script>

<template>
  <div class="etf-radar-page">
    <PageHeader title="ETF资金雷达" description="交易所份额、行情与披露证据的资金观察工作区">
      <template #meta>
        <div class="etf-header-meta">
          <span>交易日 {{ activeMetadata?.trade_date || '--' }}</span>
          <span>{{ activeMetadata ? stageLabel(activeMetadata.signal_stage) : '待确认' }}</span>
          <span>as_of {{ formatAsOf(activeMetadata?.as_of) }}</span>
        </div>
      </template>
      <a-button data-testid="etf-refresh" :loading="activeLoading()" @click="void loadTab(activeTab, true)">刷新当前视图</a-button>
    </PageHeader>

    <a-tabs v-model:active-key="activeTab" class="etf-tabs" @change="changeTab">
      <a-tab-pane key="overview" tab="盘中雷达" />
      <a-tab-pane key="history" tab="份额变化" />
      <a-tab-pane key="holders" tab="持有人披露" />
      <a-tab-pane key="methodology" tab="方法与验证" />
    </a-tabs>

    <section v-if="activeTab === 'overview'" class="etf-panel">
      <SectionHeader title="盘中资金信号" source="ETF份额与行情快照" :updated-at="formatAsOf(overview?.as_of)">
        <StatusTag :status="activeLoading() ? 'running' : activeError() ? 'failed' : overview ? 'success' : 'unknown'" />
      </SectionHeader>
      <div v-if="activeLoading() && !overview" data-testid="etf-local-loading" class="etf-state">正在读取盘中雷达...</div>
      <a-alert v-else-if="activeError() && !overview" type="warning" :message="activeError()" show-icon />
      <div v-else-if="overview" class="etf-panel-content">
        <div class="etf-metrics">
          <div v-for="metric in overviewMetrics" :key="metric.label" class="etf-metric">
            <span class="etf-metric__label">{{ metric.label }}</span>
            <strong :class="valueTone(typeof metric.value === 'number' ? metric.value : null)">{{ metric.value }}</strong>
            <small>{{ metric.helper }}</small>
          </div>
        </div>
        <div class="etf-evidence-block">
          <strong>证据摘要</strong>
          <ul>
            <li v-for="line in overview.evidence.slice(0, 3)" :key="line">{{ line }}</li>
            <li v-if="overview.evidence.length === 0">暂无证据摘要</li>
          </ul>
        </div>
        <div class="etf-source-statuses">
          <span v-for="source in activeSources()" :key="source.source" class="etf-source-status">
            {{ source.source }} <StatusTag :status="sourceStatusTone(source.status)" />
          </span>
        </div>
        <div class="etf-table-scroll">
          <a-table :columns="overviewColumns" :data-source="overview.items" :pagination="false" :scroll="{ x: 1280 }" row-key="symbol">
            <template #bodyCell="{ column, record }">
              <span :class="valueTone(['share_change', 'estimated_subscription_cny', 'relative_index_return_pct'].includes(columnKey(column.key)) ? recordNumber(record, column.key) : null)">
                {{ overviewCell(columnKey(column.key), record) }}
              </span>
            </template>
          </a-table>
        </div>
      </div>
      <div v-else data-testid="etf-empty" class="etf-state">暂无盘中雷达数据</div>
    </section>

    <section v-else-if="activeTab === 'history'" class="etf-panel">
      <SectionHeader title="份额变化" source="交易所ETF份额历史" :updated-at="formatAsOf(history?.as_of)">
        <StatusTag :status="activeLoading() ? 'running' : activeError() ? 'failed' : history ? 'success' : 'unknown'" />
      </SectionHeader>
      <div v-if="activeLoading() && !history" data-testid="etf-local-loading" class="etf-state">正在读取份额变化...</div>
      <a-alert v-else-if="activeError() && !history" type="warning" :message="activeError()" show-icon />
      <div v-else-if="history" class="etf-panel-content">
        <EChart :height="280" :loading="activeLoading()" :option="historyOption" />
        <div class="etf-source-statuses">
          <span v-for="source in activeSources()" :key="source.source" class="etf-source-status">
            {{ source.source }} <StatusTag :status="sourceStatusTone(source.status)" />
          </span>
        </div>
        <div v-if="history.points.length === 0" data-testid="etf-empty" class="etf-state">暂无份额历史</div>
        <div v-else class="etf-table-scroll">
          <a-table :columns="historyColumns" :data-source="history.points" :pagination="false" :scroll="{ x: 980 }" row-key="trade_date">
            <template #bodyCell="{ column, record }">
              <span :class="valueTone(['share_change', 'estimated_subscription_cny'].includes(columnKey(column.key)) ? recordNumber(record, column.key) : null)">
                {{ historyCell(columnKey(column.key), record) }}
              </span>
            </template>
          </a-table>
        </div>
      </div>
      <div v-else data-testid="etf-empty" class="etf-state">暂无份额历史</div>
    </section>

    <section v-else-if="activeTab === 'holders'" class="etf-panel">
      <SectionHeader title="国家队持仓披露" source="基金定期报告" :updated-at="formatAsOf(holders?.as_of)">
        <StatusTag :status="activeLoading() ? 'running' : activeError() ? 'failed' : holders ? 'success' : 'unknown'" />
      </SectionHeader>
      <div v-if="activeLoading() && !holders" data-testid="etf-local-loading" class="etf-state">正在读取持有人披露...</div>
      <a-alert v-else-if="activeError() && !holders" type="warning" :message="activeError()" show-icon />
      <div v-else-if="holders" class="etf-panel-content">
        <p class="etf-disclosure-note">持有人披露为报告期数据，不代表实时资金流向。</p>
        <div class="etf-source-statuses">
          <span v-for="source in activeSources()" :key="source.source" class="etf-source-status">
            {{ source.source }} <StatusTag :status="sourceStatusTone(source.status)" />
          </span>
        </div>
        <div v-if="holders.positions.length === 0" data-testid="etf-empty" class="etf-state">暂无持有人披露</div>
        <div v-else class="etf-table-scroll">
          <a-table :columns="holderColumns" :data-source="holders.positions" :pagination="false" :scroll="{ x: 1120 }" row-key="entity_name">
            <template #bodyCell="{ column, record }">
              <span :class="valueTone(columnKey(column.key) === 'change_shares' ? recordNumber(record, 'change_shares') : null)">{{ holderCell(columnKey(column.key), record) }}</span>
            </template>
          </a-table>
        </div>
      </div>
      <div v-else data-testid="etf-empty" class="etf-state">暂无持有人披露</div>
    </section>

    <section v-else class="etf-panel">
      <SectionHeader title="方法与验证" source="模型说明与限制" :updated-at="formatAsOf(methodology?.as_of)">
        <StatusTag :status="activeLoading() ? 'running' : activeError() ? 'failed' : methodology ? 'success' : 'unknown'" />
      </SectionHeader>
      <div v-if="activeLoading() && !methodology" data-testid="etf-local-loading" class="etf-state">正在读取方法说明...</div>
      <a-alert v-else-if="activeError() && !methodology" type="warning" :message="activeError()" show-icon />
      <div v-else-if="methodology" class="etf-panel-content etf-methodology">
        <div class="etf-source-statuses">
          <span v-for="source in activeSources()" :key="source.source" class="etf-source-status">
            {{ source.source }} <StatusTag :status="sourceStatusTone(source.status)" />
          </span>
        </div>
        <div class="etf-methodology-grid">
          <div>
            <h3>因子定义</h3>
            <dl>
              <template v-for="factor in methodology.factors" :key="factor.key">
                <dt>{{ factor.name }}</dt>
                <dd>{{ factor.description }} · {{ factor.availability }}</dd>
              </template>
            </dl>
          </div>
          <div>
            <h3>阈值与池版本</h3>
            <p>核心池 {{ methodology.pool_version }}</p>
            <p v-for="(value, key) in methodology.thresholds" :key="key">{{ key }}：{{ value }}</p>
            <p>样本池：{{ methodology.core_pool.join('、') }}</p>
          </div>
        </div>
        <div>
          <h3>限制</h3>
          <ul><li v-for="limitation in methodology.limitations" :key="limitation">{{ limitation }}</li></ul>
        </div>
      </div>
      <div v-else data-testid="etf-empty" class="etf-state">暂无方法说明</div>
    </section>
  </div>
</template>

<style scoped>
.etf-radar-page {
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  color: var(--text-color);
}

.etf-header-meta,
.etf-source-statuses {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
  color: var(--text-color-3);
  font-size: 12px;
}

.etf-tabs {
  margin: 0 0 12px;
}

.etf-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--container-bg-color);
}

.etf-panel-content {
  min-width: 0;
  padding: 0 16px 16px;
}

.etf-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}

.etf-metric {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--hover-color);
}

.etf-metric__label,
.etf-metric small {
  display: block;
  color: var(--text-color-3);
  font-size: 12px;
}

.etf-metric strong {
  display: block;
  margin: 5px 0;
  overflow: hidden;
  font-size: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.etf-evidence-block {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-left: 3px solid #1677ff;
  background: var(--hover-color);
}

.etf-evidence-block ul,
.etf-methodology ul {
  margin: 6px 0 0;
  padding-left: 18px;
  color: var(--text-color-2);
}

.etf-source-statuses {
  margin-bottom: 12px;
}

.etf-source-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.etf-table-scroll {
  min-width: 0;
  overflow-x: auto;
}

.etf-table-scroll :deep(.ant-table-wrapper) {
  min-width: 980px;
}

.etf-value--positive {
  color: #d9363e;
}

.etf-value--negative {
  color: #07845e;
}

.etf-state {
  padding: 44px 16px;
  color: var(--text-color-3);
  text-align: center;
}

.etf-disclosure-note {
  margin: 0 0 14px;
  color: var(--text-color-2);
}

.etf-methodology {
  color: var(--text-color-2);
}

.etf-methodology-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(240px, 1fr);
  gap: 24px;
}

.etf-methodology h3 {
  margin: 0 0 8px;
  color: var(--text-color);
  font-size: 14px;
}

.etf-methodology dl {
  display: grid;
  grid-template-columns: minmax(90px, 0.35fr) minmax(0, 1fr);
  gap: 8px 12px;
  margin: 0;
}

.etf-methodology dt {
  color: var(--text-color);
  font-weight: 600;
}

.etf-methodology dd {
  margin: 0;
}

@media (max-width: 720px) {
  .etf-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .etf-methodology-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }
}
</style>
