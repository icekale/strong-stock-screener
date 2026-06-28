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
  Tag,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { checkRuntimeSettingsHealth, getRuntimeSettings, saveRuntimeSettings } from "../../lib/api";
import type { RuntimeSettingsConfig, RuntimeSettingsHealthProbe } from "../../lib/types";

type SettingsDraft = {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow";
  quote_provider: "tickflow";
  tickflow_api_key: string;
  tickflow_base_url: string;
  ifind_api_key: string;
  ifind_base_url: string;
  ifind_service_id: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp";
  provider_timeout_seconds: number;
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
  provider_timeout_seconds: 12,
};

export default function SettingsPage() {
  const [form] = Form.useForm<SettingsDraft>();
  const [draft, setDraft] = useState<SettingsDraft>(DEFAULT_DRAFT);
  const [config, setConfig] = useState<RuntimeSettingsConfig | null>(null);
  const [probes, setProbes] = useState<RuntimeSettingsHealthProbe[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningHealth, setRunningHealth] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadSettings();
  }, []);

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
        provider_timeout_seconds: response.config.provider_timeout_seconds,
      });
      setMessage("已读取当前设置");
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取设置失败");
    } finally {
      setLoading(false);
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
        provider_timeout_seconds: draft.provider_timeout_seconds,
      });
      setConfig(response.config);
      applyDraft({
        ...draft,
        tickflow_api_key: "",
        tickflow_base_url: response.config.tickflow_base_url,
        ifind_api_key: "",
        ifind_base_url: response.config.ifind_base_url,
        ifind_service_id: response.config.ifind_service_id,
        provider_timeout_seconds: response.config.provider_timeout_seconds,
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
    form.setFieldsValue(nextDraft);
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
                  <Descriptions.Item label="超时">{config ? `${config.provider_timeout_seconds}s` : "未读取"}</Descriptions.Item>
                </Descriptions>
              </Card>

              <Card className="workbench-panel" title="行情与候选源">
                <Form form={form} layout="vertical" onValuesChange={(_, values) => updateDraft(values)}>
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
                </Form>
              </Card>

              <Card className="workbench-panel" title="iFinD 研究增强">
                <Alert
                  className="mb-4"
                  showIcon
                  title="iFinD 用于行业板块、公告新闻、财务估值和风险事件，不替代 TickFlow 行情。"
                  type="info"
                />
                <Form form={form} layout="vertical" onValuesChange={(_, values) => updateDraft(values)}>
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
                </Form>
              </Card>
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
