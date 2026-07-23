// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SystemView from './SystemView.vue';

const api = vi.hoisted(() => ({
  clearSystemCache: vi.fn(),
  generateModelMaintenancePacket: vi.fn(),
  getAuctionTop3TrainingPerformance: vi.fn(),
  getAuctionTop3TrainingSummary: vi.fn(),
  getDataSourceStatus: vi.fn(),
  getLatestModelMaintenancePacket: vi.fn(),
  getLatestModelMaintenanceReport: vi.fn(),
  getRuntimeSettings: vi.fn(),
  getSystemCache: vi.fn(),
  getSystemStatus: vi.fn(),
  saveRuntimeSettings: vi.fn()
}));

vi.mock('@/service/product-api', () => api);

const PlainStub = defineComponent({
  props: ['title', 'items'],
  template: '<section><h2 v-if="title">{{ title }}</h2><slot /><div v-for="item in items" :key="item.key">{{ item.label }} {{ item.value }}</div></section>'
});

const ButtonStub = defineComponent({
  props: ['loading'],
  emits: ['click'],
  template: '<button @click="$emit(\'click\')"><slot /></button>'
});

const InputStub = defineComponent({
  props: ['value', 'placeholder'],
  emits: ['update:value'],
  template: '<input :value="value" :placeholder="placeholder" @input="$emit(\'update:value\', $event.target.value)" />'
});

const PasswordStub = defineComponent({
  props: ['value', 'placeholder'],
  emits: ['update:value'],
  template: '<input type="password" :value="value" :placeholder="placeholder" @input="$emit(\'update:value\', $event.target.value)" />'
});

const SelectStub = defineComponent({
  props: ['value', 'options'],
  emits: ['update:value'],
  template: '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>'
});

const SwitchStub = defineComponent({
  props: ['checked'],
  emits: ['update:checked'],
  template: '<input type="checkbox" :checked="checked" @change="$emit(\'update:checked\', $event.target.checked)" />'
});

const settingsResponse = {
  config: {
    candidate_provider: 'recent_limit_up',
    kline_provider: 'tickflow',
    quote_provider: 'tickflow',
    tickflow_api_key_configured: false,
    tickflow_api_key_preview: '',
    tickflow_api_key_source: 'none',
    tickflow_base_url: 'https://tickflow.example.test',
    ifind_api_key_configured: false,
    ifind_api_key_preview: '',
    ifind_api_key_source: 'none',
    ifind_base_url: 'https://ifind.example.test',
    ifind_service_id: 'hexin-ifind-ds-stock-mcp',
    tdx_api_key_configured: false,
    tdx_api_key_preview: '',
    tdx_api_key_source: 'none',
    tdx_base_url: 'https://tdx.example.test',
    provider_timeout_seconds: 12,
    runtime_config_path: './data/runtime_config.json',
    notifications: { channels: [] },
    sentiment_monitor: { enabled: false },
    gsgf_auto_review: { auto_snapshot_enabled: false },
    ai_analysis: {
      enabled: false,
      provider: 'openai_compatible',
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4.1-mini',
      api_key_configured: false,
      api_key_preview: '',
      api_key_source: 'none',
      run_after_daily_review: false,
      run_after_weekly_calibration: false
    },
    auction_top3_training: { record_signal_samples: true }
  },
  saved: {
    candidate_provider: 'recent_limit_up',
    kline_provider: 'tickflow',
    quote_provider: 'tickflow',
    tickflow_base_url: 'https://tickflow.example.test',
    ifind_base_url: 'https://ifind.example.test',
    ifind_service_id: 'hexin-ifind-ds-stock-mcp',
    tdx_base_url: 'https://tdx.example.test',
    provider_timeout_seconds: 12,
    notification_channels: [],
    sentiment_monitor: { enabled: false },
    gsgf_auto_review: { auto_snapshot_enabled: false },
    auction_top3_training: { record_signal_samples: true }
  }
};

function mountView() {
  return mount(SystemView, {
    global: {
      stubs: {
        AAlert: { props: ['title'], template: '<div role="alert">{{ title }}</div>' },
        AButton: ButtonStub,
        AInput: InputStub,
        AInputPassword: PasswordStub,
        ASelect: SelectStub,
        ASwitch: SwitchStub,
        DataList: PlainStub,
        MetricStrip: PlainStub,
        PageHeader: PlainStub,
        SectionHeader: PlainStub,
        StatusTag: true
      }
    }
  });
}

beforeEach(() => {
  api.getRuntimeSettings.mockResolvedValue(settingsResponse);
  api.getSystemStatus.mockResolvedValue({ status: 'ok', generated_at: '2026-07-23T15:00:00+08:00', jobs: [], confidence: 'fresh' });
  api.getSystemCache.mockResolvedValue({ total: 0, items: [] });
  api.getDataSourceStatus.mockResolvedValue({ items: [] });
  api.getAuctionTop3TrainingSummary.mockResolvedValue({ signal_sample_count: 0, simulated_trade_sample_count: 0, manual_trade_sample_count: 0, quality_notes: [] });
  api.getAuctionTop3TrainingPerformance.mockResolvedValue({ points: [], generated_at: '2026-07-23T15:00:00+08:00' });
  api.getLatestModelMaintenancePacket.mockResolvedValue(null);
  api.getLatestModelMaintenanceReport.mockResolvedValue(null);
  api.saveRuntimeSettings.mockResolvedValue(settingsResponse);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('SystemView AI settings', () => {
  it('shows editable AI settings on the deployed system page', async () => {
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.get('[data-testid="ai-analysis-settings"]').text()).toContain('AI 分析服务');
    expect((wrapper.get('[data-testid="ai-analysis-model"]').element as HTMLInputElement).value).toBe('gpt-4.1-mini');
  });

  it('saves the AI settings without dropping existing runtime settings', async () => {
    const wrapper = mountView();
    await flushPromises();
    await wrapper.get('[data-testid="ai-analysis-model"]').setValue('deepseek-reasoner');
    await wrapper.get('[data-testid="ai-analysis-save"]').trigger('click');
    await flushPromises();

    expect(api.saveRuntimeSettings).toHaveBeenCalledWith(expect.objectContaining({
      candidate_provider: 'recent_limit_up',
      tickflow_base_url: 'https://tickflow.example.test',
      ai_analysis: expect.objectContaining({
        enabled: false,
        model: 'deepseek-reasoner',
        api_key: undefined
      })
    }));
  });
});
