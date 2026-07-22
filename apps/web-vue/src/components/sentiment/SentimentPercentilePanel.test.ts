// @vitest-environment jsdom

import process from 'node:process';
import { readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';
import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  SentimentAnalysisStatus,
  SentimentPercentileAnalysisResponse,
  SentimentPercentilePoint,
  SentimentPercentileResponse
} from '@/service/types';
import SentimentPercentilePanel from './SentimentPercentilePanel.vue';

const api = vi.hoisted(() => ({
  generateMarketSentimentAnalysis: vi.fn(),
  getMarketSentimentAnalysis: vi.fn(),
  getMarketSentimentPercentile: vi.fn()
}));

type Deferred<T> = {
  promise: Promise<T>;
  reject: (reason?: unknown) => void;
  resolve: (value: T) => void;
};

const source = readFileSync(
  resolvePath(process.cwd(), 'src/components/sentiment/SentimentPercentilePanel.vue'),
  'utf8'
);

vi.mock('@/service/product-api', () => api);

const EChartStub = defineComponent({
  name: 'EChart',
  props: ['option', 'height', 'loading'],
  emits: ['select'],
  template: '<button data-testid="percentile-chart" @click="$emit(\'select\', { dataIndex: 0 })">chart</button>'
});

const SelectStub = defineComponent({
  name: 'ASelect',
  props: ['value', 'options', 'ariaLabel'],
  emits: ['change', 'update:value'],
  template: `
    <select :value="value" :aria-label="ariaLabel" @change="$emit('change', $event.target.value)">
      <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
  `
});

const ButtonStub = defineComponent({
  name: 'AButton',
  props: ['loading'],
  emits: ['click'],
  template: '<button @click="$emit(\'click\')"><slot /></button>'
});

const RouterLinkStub = defineComponent({
  name: 'RouterLink',
  props: ['to'],
  template: '<a :href="to"><slot /></a>'
});

function point(index: number, tradeDate = `2025-${String(index + 1).padStart(3, '0')}`): SentimentPercentilePoint {
  const score = index % 100;
  return {
    trade_date: tradeDate,
    score,
    level: levelForScore(score),
    factors: {
      volume: { score: 72.4, raw_value: 1_230_000_000_000, raw_unit: 'CNY' },
      index_move_5d: { score: 61.2, raw_value: 3.12, raw_unit: '%' },
      price_position: { score: 55.6, raw_value: 64.5, raw_unit: '%' },
      amplitude_5d: { score: 48.8, raw_value: -6.78, raw_unit: '%' },
      volume_trend: { score: 68.2, raw_value: 12.3, raw_unit: '%' }
    }
  };
}

function levelForScore(score: number): SentimentPercentilePoint['level'] {
  if (score >= 80) return '过热';
  if (score >= 60) return '偏热';
  if (score >= 40) return '中性';
  if (score >= 20) return '偏冷';
  return '冰点';
}

function percentileFixture(): SentimentPercentileResponse {
  const history = Array.from({ length: 499 }, (_, index) => point(index));
  const selected = { ...point(61, '2026-07-22'), score: 62.4, level: '偏热' as const };
  return {
    model_version: 'market-sentiment-percentile-v1',
    benchmark_symbol: '000985.SH',
    benchmark_name: '中证全指',
    window_size: 500,
    weights: { volume: 0.2, index_move_5d: 0.2, price_position: 0.2, amplitude_5d: 0.2, volume_trend: 0.2 },
    latest_complete_trade_date: '2026-07-22',
    selected_trade_date: '2026-07-22',
    selected,
    history: [...history, selected],
    cache_status: 'fresh',
    source_status: [],
    generated_at: '2026-07-22T15:15:00+08:00',
    notes: []
  };
}

function analysisFixture(
  status: SentimentAnalysisStatus,
  overrides: Partial<SentimentPercentileAnalysisResponse> = {}
): SentimentPercentileAnalysisResponse {
  return {
    trade_date: '2026-07-22',
    status,
    model_version: 'market-sentiment-percentile-v1',
    provider: status === 'ready' ? 'openai-compatible' : null,
    llm_model: status === 'ready' ? 'gpt-5-mini' : null,
    input_hash: status === 'ready' ? 'hash' : null,
    attempts: status === 'failed' ? 3 : 1,
    requested_at: '2026-07-22T15:16:00+08:00',
    completed_at: status === 'ready' ? '2026-07-22T15:17:00+08:00' : null,
    retry_after: status === 'failed' ? '2026-07-22T15:47:00+08:00' : null,
    error: status === 'failed' ? '上游模型暂时不可用' : null,
    result:
      status === 'ready'
        ? {
            market_conclusion: '综合分 62.4，市场处于偏热区间但结构分化。',
            key_drivers: ['量能分 72.4，高于中性线。', '5日指数涨幅 3.12%，趋势偏强。'],
            factor_divergence: '价格位置 55.6 与量能分 72.4 存在背离。',
            historical_context: '近 500 个交易日位于第 62.4 百分位。',
            risk_posture: 'balanced',
            next_session_watch: ['若综合分升破 80，关注过热风险。', '若量能趋势回落至 0% 以下，确认降温。'],
            risk_note: '该模型描述市场温度，不构成买卖建议。'
          }
        : null,
    ...overrides
  };
}

function mountPanel() {
  return mount(SentimentPercentilePanel, {
    props: { asOf: '2026-07-22', refreshToken: 0 },
    global: {
      stubs: {
        AButton: ButtonStub,
        ASelect: SelectStub,
        EChart: EChartStub,
        RouterLink: RouterLinkStub
      }
    }
  });
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function readyAnalysis(tradeDate: string, conclusion: string) {
  const response = analysisFixture('ready');
  return {
    ...response,
    trade_date: tradeDate,
    result: { ...response.result!, market_conclusion: conclusion }
  };
}

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: true }))
  );
  api.getMarketSentimentPercentile.mockResolvedValue(percentileFixture());
  api.getMarketSentimentAnalysis.mockResolvedValue(analysisFixture('ready'));
  api.generateMarketSentimentAnalysis.mockResolvedValue(analysisFixture('ready'));
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('SentimentPercentilePanel', () => {
  it('renders a stable initial loading state before statistics arrive', async () => {
    const request = deferred<SentimentPercentileResponse>();
    api.getMarketSentimentPercentile.mockReturnValueOnce(request.promise);
    const wrapper = mountPanel();

    expect(wrapper.text()).toContain('正在读取市场情绪百分位');
    expect(wrapper.findComponent(EChartStub).exists()).toBe(false);

    request.resolve(percentileFixture());
    await flushPromises();
    expect(wrapper.findComponent(EChartStub).exists()).toBe(true);
  });

  it('renders 500-point statistics, five factor scales, raw values, and ready AI metadata', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.get('[data-testid="current-score"]').text()).toContain('62.4');
    expect(wrapper.get('[data-testid="current-level"]').text()).toContain('偏热');
    expect(wrapper.findAll('[data-testid="factor-row"]')).toHaveLength(5);
    expect(wrapper.text()).toContain('1.23万亿');
    expect(wrapper.text()).toContain('+3.12%');
    expect(wrapper.find('[aria-label="查看日期"]').exists()).toBe(true);

    const option = wrapper.getComponent(EChartStub).props('option') as { xAxis: { data: string[] } };
    expect(option.xAxis.data).toHaveLength(500);
    expect(wrapper.get('[data-testid="ai-ready"]').text()).toContain('综合分 62.4');
    expect(wrapper.get('[data-testid="ai-ready"]').text()).toContain('平衡');
    expect(wrapper.text()).toContain('gpt-5-mini');
    expect(wrapper.text()).toContain('15:17');
    expect(wrapper.text()).toContain('不构成买卖建议');
  });

  it('supports equivalent chart and keyboard date selection without generating historical analysis', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.get('[data-testid="percentile-chart"]').trigger('click');
    await flushPromises();
    const firstDate = percentileFixture().history[0]!.trade_date;
    expect(api.getMarketSentimentAnalysis).toHaveBeenLastCalledWith(firstDate);

    await wrapper.get('[aria-label="查看日期"]').setValue('2026-07-22');
    await flushPromises();
    expect(api.getMarketSentimentAnalysis).toHaveBeenLastCalledWith('2026-07-22');
    expect(api.generateMarketSentimentAnalysis).not.toHaveBeenCalled();
  });

  it.each([
    ['not_generated', '今日 AI 分析待生成'],
    ['unconfigured', 'AI 分析未配置'],
    ['pending', 'AI 解读生成中']
  ] as const)('renders the %s analysis state', async (status, copy) => {
    api.getMarketSentimentAnalysis.mockResolvedValueOnce(analysisFixture(status));
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain(copy);
    if (status === 'unconfigured') expect(wrapper.get('a[href="/system"]').text()).toContain('前往设置');
    if (status === 'pending') expect(wrapper.get('[data-testid="ai-pending"]').attributes('aria-busy')).toBe('true');
  });

  it('maps failed analysis to safe date-neutral copy and force-retries the selected analysis', async () => {
    api.getMarketSentimentAnalysis.mockResolvedValueOnce(analysisFixture('failed'));
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.get('[data-testid="ai-failed"]').text()).toContain('所选日期 AI 分析失败');
    expect(wrapper.get('[data-testid="ai-failed"]').text()).toContain('AI 解读服务暂时不可用，请稍后重试');
    await wrapper.get('[data-testid="analysis-retry"]').trigger('click');
    await flushPromises();

    expect(api.generateMarketSentimentAnalysis).toHaveBeenCalledWith('2026-07-22', true);
    expect(wrapper.get('[data-testid="ai-ready"]').text()).toContain('综合分 62.4');
  });

  it('does not expose provider URLs, secrets, or stack details from failed analysis', async () => {
    const unsafeError =
      'POST https://llm.internal.example/v1 failed: Bearer sk-live-secret\n    at request (/srv/app/client.ts:42:7)';
    api.getMarketSentimentAnalysis.mockResolvedValueOnce(analysisFixture('failed', { error: unsafeError }));
    const wrapper = mountPanel();
    await flushPromises();

    const failure = wrapper.get('[data-testid="ai-failed"]').text();
    expect(failure).toContain('AI 解读暂时不可用，请稍后重试');
    expect(failure).not.toContain('https://');
    expect(failure).not.toContain('sk-live-secret');
    expect(failure).not.toContain('/srv/app');
  });

  it('ignores a late retry success after selection moves to another date', async () => {
    const retry = deferred<SentimentPercentileAnalysisResponse>();
    const firstDate = percentileFixture().history[0]!.trade_date;
    api.getMarketSentimentAnalysis.mockResolvedValueOnce(analysisFixture('failed'));
    api.generateMarketSentimentAnalysis.mockReturnValueOnce(retry.promise);
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.get('[data-testid="analysis-retry"]').trigger('click');
    api.getMarketSentimentAnalysis.mockResolvedValueOnce(readyAnalysis(firstDate, 'B 日期分析保持可见。'));
    await wrapper.get('[data-testid="percentile-chart"]').trigger('click');
    await flushPromises();
    retry.resolve(readyAnalysis('2026-07-22', '迟到的 A 日期分析。'));
    await flushPromises();

    expect(wrapper.get('[data-testid="ai-ready"]').text()).toContain('B 日期分析保持可见。');
    expect(wrapper.text()).not.toContain('迟到的 A 日期分析。');
  });

  it('ignores a late retry failure after selection moves to another date', async () => {
    const retry = deferred<SentimentPercentileAnalysisResponse>();
    const firstDate = percentileFixture().history[0]!.trade_date;
    api.getMarketSentimentAnalysis.mockResolvedValueOnce(analysisFixture('failed'));
    api.generateMarketSentimentAnalysis.mockReturnValueOnce(retry.promise);
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.get('[data-testid="analysis-retry"]').trigger('click');
    api.getMarketSentimentAnalysis.mockResolvedValueOnce(readyAnalysis(firstDate, 'B 日期分析保持可见。'));
    await wrapper.get('[data-testid="percentile-chart"]').trigger('click');
    await flushPromises();
    retry.reject(new Error('late A failure'));
    await flushPromises();

    expect(wrapper.get('[data-testid="ai-ready"]').text()).toContain('B 日期分析保持可见。');
    expect(wrapper.find('[data-testid="ai-failed"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('AI 分析重试失败');
  });

  it('constrains direct layout children and wraps generated analysis text on narrow screens', () => {
    expect(source).toContain('.sentiment-percentile__body > *');
    expect(source).toContain('.sentiment-percentile__analysis-grid > *');
    expect(source).toContain('overflow-wrap: anywhere;');
    expect(source).toContain('word-break: break-word;');
  });

  it('keeps the last successful statistic visible while an explicit refresh fails', async () => {
    const wrapper = mountPanel();
    await flushPromises();
    api.getMarketSentimentPercentile.mockRejectedValueOnce(new Error('provider timeout'));

    await wrapper.setProps({ refreshToken: 1 });
    await flushPromises();

    expect(wrapper.get('[data-testid="current-score"]').text()).toContain('62.4');
    expect(wrapper.get('[data-testid="percentile-error"]').text()).toContain('市场情绪百分位更新失败');
    expect(api.getMarketSentimentPercentile).toHaveBeenLastCalledWith('2026-07-22', true);
  });
});
