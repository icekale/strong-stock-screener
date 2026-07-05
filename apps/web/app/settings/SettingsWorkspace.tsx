"use client";

import { ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { SystemStatusPanel } from "../../components/system/SystemStatusPanel";
import { checkRuntimeSettingsHealth, getRuntimeSettings, getSystemStatus, saveRuntimeSettings } from "../../lib/api";
import type {
  GsgfAutoReviewConfig,
  RuntimeSettingsConfig,
  RuntimeSettingsHealthProbe,
  SystemStatusResponse,
} from "../../lib/types";

type SettingsDraft = {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow";
  quote_provider: "tickflow";
  tickflow_api_key: string;
  tickflow_base_url: string;
  ifind_api_key: string;
  ifind_base_url: string;
  ifind_service_id: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp";
  tdx_api_key: string;
  tdx_base_url: string;
  provider_timeout_seconds: number;
  notification_wechat_enabled: boolean;
  notification_wechat_webhook: string;
  notification_feishu_enabled: boolean;
  notification_feishu_webhook: string;
  notification_telegram_enabled: boolean;
  notification_telegram_bot_token: string;
  notification_telegram_chat_id: string;
  notification_email_enabled: boolean;
  notification_email_host: string;
  notification_email_port: number;
  notification_email_username: string;
  notification_email_password: string;
  notification_email_sender: string;
  notification_email_recipients: string;
  notification_email_tls: boolean;
  gsgf_auto_snapshot_enabled: boolean;
  gsgf_daily_review_enabled: boolean;
  gsgf_daily_review_time: string;
  gsgf_weekly_calibration_enabled: boolean;
  gsgf_weekly_calibration_weekday: number;
  gsgf_weekly_calibration_time: string;
  gsgf_weekly_calibration_trade_days: number;
  gsgf_weekly_calibration_scan_limit: number;
  gsgf_notify_on_success: boolean;
  gsgf_notify_on_degradation: boolean;
  ai_analysis_enabled: boolean;
  ai_analysis_provider: "openai" | "deepseek" | "openai_compatible";
  ai_analysis_base_url: string;
  ai_analysis_model: string;
  ai_analysis_api_key: string;
  ai_analysis_run_after_daily_review: boolean;
  ai_analysis_run_after_weekly_calibration: boolean;
  auction_top3_record_signal_samples: boolean;
  auction_top3_generate_simulated_trade_samples: boolean;
  auction_top3_include_manual_trade_samples_in_training: boolean;
  auction_top3_training_window_days: number;
  auction_top3_simulated_initial_capital: number;
  auction_top3_simulated_position_pct: number;
};

const DEFAULT_DRAFT: SettingsDraft = {
  candidate_provider: "recent_limit_up",
  kline_provider: "tickflow",
  quote_provider: "tickflow",
  tickflow_api_key: "",
  tickflow_base_url: "https://api.tickflow.org",
  ifind_api_key: "",
  ifind_base_url: "https://api-mcp.51ifind.com:8643",
  ifind_service_id: "hexin-ifind-ds-stock-mcp",
  tdx_api_key: "",
  tdx_base_url: "https://mcp.tdx.com.cn:3001/mcp",
  provider_timeout_seconds: 12,
  notification_wechat_enabled: false,
  notification_wechat_webhook: "",
  notification_feishu_enabled: false,
  notification_feishu_webhook: "",
  notification_telegram_enabled: false,
  notification_telegram_bot_token: "",
  notification_telegram_chat_id: "",
  notification_email_enabled: false,
  notification_email_host: "",
  notification_email_port: 587,
  notification_email_username: "",
  notification_email_password: "",
  notification_email_sender: "",
  notification_email_recipients: "",
  notification_email_tls: true,
  gsgf_auto_snapshot_enabled: true,
  gsgf_daily_review_enabled: true,
  gsgf_daily_review_time: "15:40",
  gsgf_weekly_calibration_enabled: true,
  gsgf_weekly_calibration_weekday: 5,
  gsgf_weekly_calibration_time: "16:10",
  gsgf_weekly_calibration_trade_days: 5,
  gsgf_weekly_calibration_scan_limit: 80,
  gsgf_notify_on_success: true,
  gsgf_notify_on_degradation: true,
  ai_analysis_enabled: false,
  ai_analysis_provider: "openai_compatible",
  ai_analysis_base_url: "https://api.openai.com/v1",
  ai_analysis_model: "gpt-4.1-mini",
  ai_analysis_api_key: "",
  ai_analysis_run_after_daily_review: false,
  ai_analysis_run_after_weekly_calibration: false,
  auction_top3_record_signal_samples: true,
  auction_top3_generate_simulated_trade_samples: false,
  auction_top3_include_manual_trade_samples_in_training: false,
  auction_top3_training_window_days: 60,
  auction_top3_simulated_initial_capital: 100000,
  auction_top3_simulated_position_pct: 0.33,
};

export function SettingsWorkspace() {
  const [form] = Form.useForm<SettingsDraft>();
  const [draft, setDraft] = useState<SettingsDraft>(DEFAULT_DRAFT);
  const [config, setConfig] = useState<RuntimeSettingsConfig | null>(null);
  const [probes, setProbes] = useState<RuntimeSettingsHealthProbe[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningHealth, setRunningHealth] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [systemStatusLoading, setSystemStatusLoading] = useState(false);
  const [systemStatusError, setSystemStatusError] = useState<string | null>(null);

  useEffect(() => {
    void loadSettings();
    void loadSystemStatus();
  }, []);

  useEffect(() => {
    if (!loading) {
      form.setFieldsValue(draft);
    }
  }, [draft, form, loading]);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const response = await getRuntimeSettings();
      setConfig(response.config);
      applyDraft({
        candidate_provider: response.config.candidate_provider,
        kline_provider: response.config.kline_provider,
        quote_provider: response.config.quote_provider,
        tickflow_api_key: "",
        tickflow_base_url: response.config.tickflow_base_url,
        ifind_api_key: "",
        ifind_base_url: response.config.ifind_base_url,
        ifind_service_id: response.config.ifind_service_id,
        tdx_api_key: "",
        tdx_base_url: response.config.tdx_base_url,
        provider_timeout_seconds: response.config.provider_timeout_seconds,
        ...gsgfDraftFromConfig(response.config),
        ...notificationDraftFromConfig(response.config),
        ...aiAnalysisDraftFromConfig(response.config),
        ...auctionTop3TrainingDraftFromConfig(response.config),
      });
      setMessage("已读取当前设置");
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取设置失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadSystemStatus() {
    setSystemStatusLoading(true);
    setSystemStatusError(null);
    try {
      setSystemStatus(await getSystemStatus());
    } catch (err) {
      setSystemStatusError(err instanceof Error ? err.message : "读取系统状态失败");
    } finally {
      setSystemStatusLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await saveRuntimeSettings({
        candidate_provider: draft.candidate_provider,
        kline_provider: draft.kline_provider,
        quote_provider: draft.quote_provider,
        tickflow_api_key: draft.tickflow_api_key.trim() || undefined,
        tickflow_base_url: draft.tickflow_base_url.trim(),
        ifind_api_key: draft.ifind_api_key.trim() || undefined,
        ifind_base_url: draft.ifind_base_url.trim(),
        ifind_service_id: draft.ifind_service_id,
        tdx_api_key: draft.tdx_api_key.trim() || undefined,
        tdx_base_url: draft.tdx_base_url.trim(),
        provider_timeout_seconds: draft.provider_timeout_seconds,
        notification_channels: buildNotificationChannels(draft),
        sentiment_monitor: config?.sentiment_monitor,
        gsgf_auto_review: buildGsgfAutoReviewConfig(draft, config?.gsgf_auto_review),
        ai_analysis: buildAiAnalysisConfig(draft),
        auction_top3_training: buildAuctionTop3TrainingConfig(draft),
      });
      setConfig(response.config);
      applyDraft({
        ...draft,
        tickflow_api_key: "",
        tickflow_base_url: response.config.tickflow_base_url,
        ifind_api_key: "",
        ifind_base_url: response.config.ifind_base_url,
        ifind_service_id: response.config.ifind_service_id,
        tdx_api_key: "",
        tdx_base_url: response.config.tdx_base_url,
        provider_timeout_seconds: response.config.provider_timeout_seconds,
        ...gsgfDraftFromConfig(response.config),
        ...notificationDraftFromConfig(response.config),
        ...aiAnalysisDraftFromConfig(response.config),
        ...auctionTop3TrainingDraftFromConfig(response.config),
      });
      setMessage("设置已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存设置失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleHealthCheck() {
    setRunningHealth(true);
    setError(null);
    setMessage(null);
    try {
      const response = await checkRuntimeSettingsHealth();
      setConfig(response.config);
      setProbes(response.probes);
      setMessage("健康检查完成");
    } catch (err) {
      setError(err instanceof Error ? err.message : "健康检查失败");
    } finally {
      setRunningHealth(false);
    }
  }

  function applyDraft(nextDraft: SettingsDraft) {
    setDraft(nextDraft);
  }

  function updateDraft(value: Partial<SettingsDraft>) {
    setDraft((current) => ({ ...current, ...value }));
  }

  const summary = useMemo(() => {
    if (!config) {
      return "未读取";
    }
    return `${config.candidate_provider} / ${config.kline_provider} / ${config.quote_provider}`;
  }, [config]);

  if (loading && !config) {
    return (
      <main className="workbench-page">
        <div className="mx-auto max-w-none space-y-4 px-5 py-4">
          <Card className="workbench-panel">
            <Typography.Text className="workbench-muted text-xs font-semibold uppercase">Settings</Typography.Text>
            <Typography.Title className="workbench-ink !mb-1 !mt-1 !text-2xl !font-black" level={1}>
              数据源配置
            </Typography.Title>
            <Typography.Text className="workbench-muted">
              正在读取独立选股工作台的数据源、模型和健康检查配置。
            </Typography.Text>
          </Card>
          <Card className="workbench-panel">
            <Skeleton active paragraph={{ rows: 8 }} title={false} />
          </Card>
        </div>
      </main>
    );
  }

  return (
    <main className="workbench-page">
      <div className="mx-auto max-w-none space-y-4 px-5 py-4">
        <Card className="workbench-panel">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <Typography.Text className="workbench-muted text-xs font-semibold uppercase">Settings</Typography.Text>
              <Typography.Title className="workbench-ink !mb-1 !mt-1 !text-2xl !font-black" level={1}>
                数据源配置
              </Typography.Title>
              <Typography.Text className="workbench-muted">
                独立选股工作台的行情源、候选源和 iFinD 研究增强配置。
              </Typography.Text>
            </div>
            <Space wrap>
              <Button disabled={loading || runningHealth} icon={<ReloadOutlined />} onClick={() => void loadSettings()}>
                重新读取
              </Button>
              <Button icon={<SaveOutlined />} loading={saving} onClick={() => void handleSave()} type="primary">
                保存设置
              </Button>
            </Space>
          </div>
        </Card>

        {error && <Alert showIcon title={error} type="error" />}
        {message && <Alert showIcon title={message} type="success" />}

        <SystemStatusPanel
          error={systemStatusError}
          loading={systemStatusLoading}
          onRefresh={() => void loadSystemStatus()}
          status={systemStatus}
        />

        <Row gutter={[16, 16]}>
          <Col lg={16} xs={24}>
            <Space className="w-full" orientation="vertical" size={16}>
              <Card className="workbench-panel" title="当前状态">
                <Descriptions bordered column={{ lg: 3, md: 2, xs: 1 }} size="small">
                  <Descriptions.Item label="状态摘要">{summary}</Descriptions.Item>
                  <Descriptions.Item label="候选源">{config?.candidate_provider ?? "未读取"}</Descriptions.Item>
                  <Descriptions.Item label="K线源">{config?.kline_provider ?? "未读取"}</Descriptions.Item>
                  <Descriptions.Item label="行情源">{config?.quote_provider ?? "未读取"}</Descriptions.Item>
                  <Descriptions.Item label="TickFlow Key">
                    <KeyStatus configured={Boolean(config?.tickflow_api_key_configured)} />
                  </Descriptions.Item>
                  <Descriptions.Item label="iFinD Key">
                    <KeyStatus configured={Boolean(config?.ifind_api_key_configured)} />
                  </Descriptions.Item>
                  <Descriptions.Item label="iFinD 服务">{config?.ifind_service_id ?? "未读取"}</Descriptions.Item>
                  <Descriptions.Item label="通达信 MCP Key">
                    <KeyStatus configured={Boolean(config?.tdx_api_key_configured)} />
                  </Descriptions.Item>
                  <Descriptions.Item label="通达信 MCP">{config?.tdx_api_key_source ?? "未读取"}</Descriptions.Item>
                  <Descriptions.Item label="AI 分析服务">
                    {config?.ai_analysis.enabled ? "已启用" : "未启用"}
                  </Descriptions.Item>
                  <Descriptions.Item label="AI Provider">{config?.ai_analysis.provider ?? "未读取"}</Descriptions.Item>
                  <Descriptions.Item label="AI Key">
                    <KeyStatus configured={Boolean(config?.ai_analysis.api_key_configured)} />
                  </Descriptions.Item>
                  <Descriptions.Item label="Top3 训练">
                    {config?.auction_top3_training.record_signal_samples ? "记录信号样本" : "未记录"}
                  </Descriptions.Item>
                  <Descriptions.Item label="超时">{config ? `${config.provider_timeout_seconds}s` : "未读取"}</Descriptions.Item>
                </Descriptions>
              </Card>

              <Form className="space-y-4" form={form} layout="vertical" onValuesChange={(_, values) => updateDraft(values)}>
                <Card className="workbench-panel" title="行情与候选源">
                  <Row gutter={12}>
                    <Col md={12} xs={24}>
                      <Form.Item label="候选源" name="candidate_provider">
                        <Select
                          options={[
                            { label: "recent_limit_up", value: "recent_limit_up" },
                            { label: "thsdk", value: "thsdk" },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="K线源" name="kline_provider">
                        <Input readOnly />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="行情源" name="quote_provider">
                        <Input readOnly />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="TickFlow Base URL" name="tickflow_base_url">
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="TickFlow API Key" name="tickflow_api_key">
                        <Input.Password
                          autoComplete="off"
                          placeholder={config?.tickflow_api_key_configured ? "留空表示沿用已保存 Key" : "请输入 TickFlow API Key"}
                        />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="请求超时（秒）" name="provider_timeout_seconds">
                        <InputNumber className="w-full" max={60} min={1} step={0.5} />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>

                <Card className="workbench-panel" title="iFinD 研究增强">
                <Alert
                  className="mb-4"
                  showIcon
                  title="iFinD 用于行业板块、公告新闻、财务估值和风险事件，不替代 TickFlow 行情。"
                  type="info"
                />
                  <Row gutter={12}>
                    <Col md={12} xs={24}>
                      <Form.Item label="iFinD Base URL" name="ifind_base_url">
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="默认 MCP 服务" name="ifind_service_id">
                        <Select
                          options={[
                            { label: "A股数据", value: "hexin-ifind-ds-stock-mcp" },
                            { label: "新闻公告", value: "hexin-ifind-ds-news-mcp" },
                            { label: "指数板块", value: "hexin-ifind-ds-index-mcp" },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="iFinD MCP Key" name="ifind_api_key">
                        <Input.Password
                          autoComplete="off"
                          placeholder={config?.ifind_api_key_configured ? "留空表示沿用已保存 Key" : "请输入 iFinD MCP Key"}
                        />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Descriptions bordered column={1} size="small">
                        <Descriptions.Item label="Key 来源">{config?.ifind_api_key_source ?? "未读取"}</Descriptions.Item>
                        <Descriptions.Item label="Key 摘要">{config?.ifind_api_key_preview || "未配置"}</Descriptions.Item>
                      </Descriptions>
                    </Col>
                  </Row>
                </Card>

                <Card className="workbench-panel" title="通达信 MCP 补充源">
                <Alert
                  className="mb-4"
                  showIcon
                  title="通达信 MCP 用于补充涨跌停、短线情绪和板块主线集中度；主行情仍优先使用 TickFlow。"
                  type="info"
                />
                  <Row gutter={12}>
                    <Col md={12} xs={24}>
                      <Form.Item label="通达信 MCP Base URL" name="tdx_base_url">
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="通达信 MCP Key" name="tdx_api_key">
                        <Input.Password
                          autoComplete="off"
                          placeholder={config?.tdx_api_key_configured ? "留空表示沿用已保存 Key" : "请输入通达信 MCP Key"}
                        />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Descriptions bordered column={1} size="small">
                        <Descriptions.Item label="Key 来源">{config?.tdx_api_key_source ?? "未读取"}</Descriptions.Item>
                        <Descriptions.Item label="Key 摘要">{config?.tdx_api_key_preview || "未配置"}</Descriptions.Item>
                      </Descriptions>
                    </Col>
                  </Row>
                </Card>

                <Card className="workbench-panel" title="AI 分析服务">
                <Alert
                  className="mb-4"
                  showIcon
                  title="AI 只用于模型维护复盘和建议生成；建议需要人工确认，不会自动改筛选策略。"
                  type="info"
                />
                  <Row gutter={12}>
                    <Col md={8} xs={24}>
                      <Form.Item label="启用 AI 分析" name="ai_analysis_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="Provider" name="ai_analysis_provider">
                        <Select
                          options={[
                            { label: "OpenAI / Codex", value: "openai" },
                            { label: "DeepSeek", value: "deepseek" },
                            { label: "OpenAI Compatible", value: "openai_compatible" },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="模型名称" name="ai_analysis_model">
                        <Input placeholder="deepseek-reasoner / gpt-4.1-mini" />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="Base URL" name="ai_analysis_base_url">
                        <Input placeholder="https://api.deepseek.com 或 OpenAI-compatible 节点" />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="API Key" name="ai_analysis_api_key">
                        <Input.Password
                          autoComplete="off"
                          placeholder={config?.ai_analysis.api_key_configured ? "留空表示沿用已保存 Key" : "请输入 AI API Key"}
                        />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item
                        label="每日复盘后自动生成 AI 建议"
                        name="ai_analysis_run_after_daily_review"
                        valuePropName="checked"
                      >
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item
                        label="每周校准后自动生成 AI 建议"
                        name="ai_analysis_run_after_weekly_calibration"
                        valuePropName="checked"
                      >
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>

                <Card className="workbench-panel" title="竞价 Top3 训练">
                <Alert
                  className="mb-4"
                  showIcon
                  title="记录竞价 Top3 模型输出、模拟交易和人工复盘样本，仅用于模型维护；不会真实下单，也不会自动调参。"
                  type="info"
                />
                  <Row gutter={12}>
                    <Col md={8} xs={24}>
                      <Form.Item label="记录 Top3 信号样本" name="auction_top3_record_signal_samples" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item
                        label="生成模拟交易样本"
                        name="auction_top3_generate_simulated_trade_samples"
                        valuePropName="checked"
                      >
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item
                        label="人工交易样本进入训练"
                        name="auction_top3_include_manual_trade_samples_in_training"
                        valuePropName="checked"
                      >
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="训练窗口（天）" name="auction_top3_training_window_days">
                        <InputNumber className="w-full" max={365} min={5} />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="模拟初始资金" name="auction_top3_simulated_initial_capital">
                        <InputNumber className="w-full" min={1} step={10000} />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="单票模拟仓位" name="auction_top3_simulated_position_pct">
                        <InputNumber className="w-full" max={1} min={0.01} step={0.01} />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>

                <Card className="workbench-panel" title="GSGF 自动复盘">
                <Alert
                  className="mb-4"
                  showIcon
                  title="自动复盘会在后台保存筛选信号、复查真实走势，并在信号退化时通过已启用通知渠道提醒。"
                  type="info"
                />
                  <Row gutter={12}>
                    <Col md={8} xs={24}>
                      <Form.Item label="筛选后自动保存快照" name="gsgf_auto_snapshot_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="每日复盘" name="gsgf_daily_review_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="每日复盘时间" name="gsgf_daily_review_time">
                        <Input placeholder="15:40" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="每周真实样本校准" name="gsgf_weekly_calibration_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="校准星期（1-7）" name="gsgf_weekly_calibration_weekday">
                        <InputNumber className="w-full" max={7} min={1} />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="校准时间" name="gsgf_weekly_calibration_time">
                        <Input placeholder="16:10" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="回看交易日数" name="gsgf_weekly_calibration_trade_days">
                        <InputNumber className="w-full" max={20} min={1} />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="校准扫描候选数" name="gsgf_weekly_calibration_scan_limit">
                        <InputNumber className="w-full" max={300} min={1} />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="校准完成通知" name="gsgf_notify_on_success" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                    <Col md={8} xs={24}>
                      <Form.Item label="信号退化通知" name="gsgf_notify_on_degradation" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>

                <Card className="workbench-panel" title="通知渠道">
                <Alert
                  className="mb-4"
                  showIcon
                  title="用于手动发送短线情绪提醒草稿；后台定时任务会在下一版接入。"
                  type="info"
                />
                  <Row gutter={12}>
                    <Col md={12} xs={24}>
                      <Form.Item label="企业微信启用" name="notification_wechat_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                      <Form.Item label="企业微信 Webhook" name="notification_wechat_webhook">
                        <Input.Password placeholder="留空表示沿用已保存 webhook" />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="飞书启用" name="notification_feishu_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                      <Form.Item label="飞书 Webhook" name="notification_feishu_webhook">
                        <Input.Password placeholder="留空表示沿用已保存 webhook" />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="Telegram 启用" name="notification_telegram_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                      <Form.Item label="Telegram Bot Token" name="notification_telegram_bot_token">
                        <Input.Password placeholder="留空表示沿用已保存 token" />
                      </Form.Item>
                      <Form.Item label="Telegram Chat ID" name="notification_telegram_chat_id">
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col md={12} xs={24}>
                      <Form.Item label="邮件启用" name="notification_email_enabled" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                      <Row gutter={8}>
                        <Col span={16}>
                          <Form.Item label="SMTP Host" name="notification_email_host">
                            <Input />
                          </Form.Item>
                        </Col>
                        <Col span={8}>
                          <Form.Item label="端口" name="notification_email_port">
                            <InputNumber className="w-full" min={1} />
                          </Form.Item>
                        </Col>
                      </Row>
                      <Form.Item label="SMTP 用户名" name="notification_email_username">
                        <Input />
                      </Form.Item>
                      <Form.Item label="SMTP 密码" name="notification_email_password">
                        <Input.Password placeholder="留空表示沿用已保存密码" />
                      </Form.Item>
                      <Form.Item label="发件人" name="notification_email_sender">
                        <Input />
                      </Form.Item>
                      <Form.Item label="收件人（逗号分隔）" name="notification_email_recipients">
                        <Input />
                      </Form.Item>
                      <Form.Item label="TLS" name="notification_email_tls" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>
              </Form>
            </Space>
          </Col>

          <Col lg={8} xs={24}>
            <Card
              className="workbench-panel"
              extra={
                <Button loading={runningHealth} onClick={() => void handleHealthCheck()} type="primary">
                  运行健康检查
                </Button>
              }
              title="手动健康检查"
            >
              <Typography.Paragraph className="workbench-muted">
                健康检查需要手动触发，避免设置页加载时自动消耗 TickFlow 或 iFinD 请求额度。
              </Typography.Paragraph>
              <Space className="w-full" orientation="vertical" size={10}>
                {probes.length === 0 ? (
                  <Alert showIcon title="暂无健康检查结果" type="info" />
                ) : (
                  probes.map((probe) => (
                    <Card className="workbench-panel" key={probe.name} size="small">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <Typography.Text strong>{probe.name}</Typography.Text>
                          <Typography.Text className="workbench-muted mt-1 block text-xs">
                            {probe.latency_ms} ms · {probe.detail}
                          </Typography.Text>
                        </div>
                        <ProbeStatus status={probe.status} />
                      </div>
                    </Card>
                  ))
                )}
              </Space>
            </Card>
          </Col>
        </Row>
      </div>
    </main>
  );
}

function KeyStatus({ configured }: { configured: boolean }) {
  return configured ? <Tag color="success">已配置</Tag> : <Tag color="warning">未配置</Tag>;
}

function ProbeStatus({ status }: { status: RuntimeSettingsHealthProbe["status"] }) {
  if (status === "success") {
    return <Tag color="success">success</Tag>;
  }
  if (status === "missing_key") {
    return <Tag color="warning">missing_key</Tag>;
  }
  return <Tag color="error">{status}</Tag>;
}

function gsgfDraftFromConfig(config: RuntimeSettingsConfig): Pick<
  SettingsDraft,
  | "gsgf_auto_snapshot_enabled"
  | "gsgf_daily_review_enabled"
  | "gsgf_daily_review_time"
  | "gsgf_weekly_calibration_enabled"
  | "gsgf_weekly_calibration_weekday"
  | "gsgf_weekly_calibration_time"
  | "gsgf_weekly_calibration_trade_days"
  | "gsgf_weekly_calibration_scan_limit"
  | "gsgf_notify_on_success"
  | "gsgf_notify_on_degradation"
> {
  const value = config.gsgf_auto_review;
  return {
    gsgf_auto_snapshot_enabled: value.auto_snapshot_enabled,
    gsgf_daily_review_enabled: value.daily_review_enabled,
    gsgf_daily_review_time: value.daily_review_time,
    gsgf_weekly_calibration_enabled: value.weekly_calibration_enabled,
    gsgf_weekly_calibration_weekday: value.weekly_calibration_weekday,
    gsgf_weekly_calibration_time: value.weekly_calibration_time,
    gsgf_weekly_calibration_trade_days: value.weekly_calibration_trade_days,
    gsgf_weekly_calibration_scan_limit: value.weekly_calibration_scan_limit,
    gsgf_notify_on_success: value.notify_on_success,
    gsgf_notify_on_degradation: value.notify_on_degradation,
  };
}

function buildGsgfAutoReviewConfig(
  draft: SettingsDraft,
  current: GsgfAutoReviewConfig | undefined,
): GsgfAutoReviewConfig {
  return {
    auto_snapshot_enabled: draft.gsgf_auto_snapshot_enabled,
    daily_review_enabled: draft.gsgf_daily_review_enabled,
    daily_review_time: draft.gsgf_daily_review_time.trim() || "15:40",
    weekly_calibration_enabled: draft.gsgf_weekly_calibration_enabled,
    weekly_calibration_weekday: draft.gsgf_weekly_calibration_weekday,
    weekly_calibration_time: draft.gsgf_weekly_calibration_time.trim() || "16:10",
    weekly_calibration_trade_days: draft.gsgf_weekly_calibration_trade_days,
    weekly_calibration_scan_limit: draft.gsgf_weekly_calibration_scan_limit,
    windows: current?.windows ?? [1, 3, 5, 10],
    kline_count: current?.kline_count ?? 260,
    notify_on_success: draft.gsgf_notify_on_success,
    notify_on_degradation: draft.gsgf_notify_on_degradation,
  };
}

function aiAnalysisDraftFromConfig(config: RuntimeSettingsConfig): Pick<
  SettingsDraft,
  | "ai_analysis_enabled"
  | "ai_analysis_provider"
  | "ai_analysis_base_url"
  | "ai_analysis_model"
  | "ai_analysis_api_key"
  | "ai_analysis_run_after_daily_review"
  | "ai_analysis_run_after_weekly_calibration"
> {
  const value = config.ai_analysis;
  return {
    ai_analysis_enabled: value.enabled,
    ai_analysis_provider: value.provider,
    ai_analysis_base_url: value.base_url,
    ai_analysis_model: value.model,
    ai_analysis_api_key: "",
    ai_analysis_run_after_daily_review: value.run_after_daily_review,
    ai_analysis_run_after_weekly_calibration: value.run_after_weekly_calibration,
  };
}

function buildAiAnalysisConfig(draft: SettingsDraft) {
  return {
    enabled: draft.ai_analysis_enabled,
    provider: draft.ai_analysis_provider,
    base_url: draft.ai_analysis_base_url.trim(),
    model: draft.ai_analysis_model.trim(),
    api_key: draft.ai_analysis_api_key.trim() || undefined,
    run_after_daily_review: draft.ai_analysis_run_after_daily_review,
    run_after_weekly_calibration: draft.ai_analysis_run_after_weekly_calibration,
  };
}

function auctionTop3TrainingDraftFromConfig(config: RuntimeSettingsConfig): Pick<
  SettingsDraft,
  | "auction_top3_record_signal_samples"
  | "auction_top3_generate_simulated_trade_samples"
  | "auction_top3_include_manual_trade_samples_in_training"
  | "auction_top3_training_window_days"
  | "auction_top3_simulated_initial_capital"
  | "auction_top3_simulated_position_pct"
> {
  const value = config.auction_top3_training;
  return {
    auction_top3_record_signal_samples: value.record_signal_samples,
    auction_top3_generate_simulated_trade_samples: value.generate_simulated_trade_samples,
    auction_top3_include_manual_trade_samples_in_training: value.include_manual_trade_samples_in_training,
    auction_top3_training_window_days: value.training_window_days,
    auction_top3_simulated_initial_capital: value.simulated_initial_capital,
    auction_top3_simulated_position_pct: value.simulated_position_pct,
  };
}

function buildAuctionTop3TrainingConfig(draft: SettingsDraft) {
  return {
    record_signal_samples: draft.auction_top3_record_signal_samples,
    generate_simulated_trade_samples: draft.auction_top3_generate_simulated_trade_samples,
    include_manual_trade_samples_in_training: draft.auction_top3_include_manual_trade_samples_in_training,
    training_window_days: draft.auction_top3_training_window_days,
    simulated_initial_capital: draft.auction_top3_simulated_initial_capital,
    simulated_position_pct: draft.auction_top3_simulated_position_pct,
  };
}

function notificationDraftFromConfig(config: RuntimeSettingsConfig): Pick<
  SettingsDraft,
  | "notification_wechat_enabled"
  | "notification_wechat_webhook"
  | "notification_feishu_enabled"
  | "notification_feishu_webhook"
  | "notification_telegram_enabled"
  | "notification_telegram_bot_token"
  | "notification_telegram_chat_id"
  | "notification_email_enabled"
  | "notification_email_host"
  | "notification_email_port"
  | "notification_email_username"
  | "notification_email_password"
  | "notification_email_sender"
  | "notification_email_recipients"
  | "notification_email_tls"
> {
  const channels = config.notifications?.channels ?? [];
  const wechat = channels.find((channel) => channel.id === "wechat-work");
  const feishu = channels.find((channel) => channel.id === "feishu");
  const telegram = channels.find((channel) => channel.id === "telegram");
  const email = channels.find((channel) => channel.id === "email");
  return {
    notification_wechat_enabled: Boolean(wechat?.enabled),
    notification_wechat_webhook: "",
    notification_feishu_enabled: Boolean(feishu?.enabled),
    notification_feishu_webhook: "",
    notification_telegram_enabled: Boolean(telegram?.enabled),
    notification_telegram_bot_token: "",
    notification_telegram_chat_id: telegram?.chat_id_configured ? "已配置" : "",
    notification_email_enabled: Boolean(email?.enabled),
    notification_email_host: email?.smtp_host ?? "",
    notification_email_port: email?.smtp_port ?? 587,
    notification_email_username: email?.smtp_username ?? "",
    notification_email_password: "",
    notification_email_sender: email?.smtp_sender ?? "",
    notification_email_recipients: (email?.smtp_recipients ?? []).join(","),
    notification_email_tls: email?.smtp_use_tls ?? true,
  };
}

function buildNotificationChannels(draft: SettingsDraft) {
  return [
    {
      id: "wechat-work",
      type: "wechat_work" as const,
      name: "企业微信",
      enabled: draft.notification_wechat_enabled,
      webhook_url: draft.notification_wechat_webhook.trim() || null,
    },
    {
      id: "feishu",
      type: "feishu" as const,
      name: "飞书",
      enabled: draft.notification_feishu_enabled,
      webhook_url: draft.notification_feishu_webhook.trim() || null,
    },
    {
      id: "telegram",
      type: "telegram" as const,
      name: "Telegram",
      enabled: draft.notification_telegram_enabled,
      bot_token: draft.notification_telegram_bot_token.trim() || null,
      chat_id: draft.notification_telegram_chat_id.trim() === "已配置" ? null : draft.notification_telegram_chat_id.trim() || null,
    },
    {
      id: "email",
      type: "email" as const,
      name: "邮件",
      enabled: draft.notification_email_enabled,
      smtp_host: draft.notification_email_host.trim() || null,
      smtp_port: draft.notification_email_port,
      smtp_username: draft.notification_email_username.trim() || null,
      smtp_password: draft.notification_email_password.trim() || null,
      smtp_sender: draft.notification_email_sender.trim() || null,
      smtp_recipients: splitRecipients(draft.notification_email_recipients),
      smtp_use_tls: draft.notification_email_tls,
    },
  ];
}

function splitRecipients(value: string): string[] {
  return value
    .split(/[,\n，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
