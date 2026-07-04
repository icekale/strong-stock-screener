"use client";

import {
  Alert,
  App,
  Badge,
  Button,
  Card,
  Descriptions,
  Empty,
  List,
  Skeleton,
  Space,
  Tag,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  analyzeModelMaintenance,
  generateModelMaintenancePacket,
  getLatestModelMaintenanceReport,
  updateModelMaintenanceSuggestion,
} from "../../lib/api";
import type {
  ModelMaintenanceHealthStatus,
  ModelMaintenanceReport,
  ModelMaintenanceSuggestion,
  ModelMaintenanceSuggestionStatus,
} from "../../lib/types";

export function ModelMaintenanceWorkspace() {
  const { message } = App.useApp();
  const [report, setReport] = useState<ModelMaintenanceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [updatingSuggestionId, setUpdatingSuggestionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadLatestReport();
  }, []);

  const pendingSuggestions = useMemo(
    () => report?.suggestions.filter((suggestion) => suggestion.status === "pending") ?? [],
    [report],
  );

  async function loadLatestReport() {
    setLoading(true);
    setError(null);
    try {
      const nextReport = await getLatestModelMaintenanceReport();
      setReport(nextReport);
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取模型维护报告失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    setError(null);
    try {
      await generateModelMaintenancePacket();
      const nextReport = await analyzeModelMaintenance();
      setReport(nextReport);
      void message.success("模型维护分析已生成");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "生成模型维护分析失败";
      setError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleSuggestionAction(
    suggestion: ModelMaintenanceSuggestion,
    action: "accept" | "ignore" | "snooze",
  ) {
    setUpdatingSuggestionId(suggestion.suggestion_id);
    setError(null);
    try {
      const updated = await updateModelMaintenanceSuggestion(suggestion.suggestion_id, action);
      setReport((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          suggestions: current.suggestions.map((item) =>
            item.suggestion_id === updated.suggestion_id ? updated : item,
          ),
        };
      });
      void message.success(`建议已${suggestionStatusText(updated.status)}`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "更新模型维护建议失败";
      setError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setUpdatingSuggestionId(null);
    }
  }

  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Typography.Text className="workbench-muted text-xs font-semibold uppercase">
            Model Maintenance
          </Typography.Text>
          <Typography.Title className="m-0 text-[#11100e]" level={3}>
            AI 模型维护
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            把筛选结果、复盘样本和数据源状态整理成维护包，由 Codex / DeepSeek 生成待确认建议。
          </Typography.Text>
        </div>
        <Space wrap>
          <Button disabled={loading || analyzing} onClick={() => void loadLatestReport()}>
            重新读取
          </Button>
          <Button loading={analyzing} onClick={() => void handleAnalyze()} type="primary">
            生成复盘包并分析
          </Button>
        </Space>
      </div>

      {error && <Alert className="mb-4" showIcon title={error} type="error" />}

      {loading ? (
        <Card className="workbench-panel">
          <Skeleton active paragraph={{ rows: 10 }} />
        </Card>
      ) : report ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.8fr)]">
          <Space className="min-w-0" direction="vertical" size={16}>
            <Card className="workbench-panel" title="维护结论">
              <Space className="mb-4" wrap>
                <HealthTag status={report.health_status} />
                <Tag>{report.provider}</Tag>
                <Tag>{report.model}</Tag>
                <Tag>{report.generated_at}</Tag>
              </Space>
              <Typography.Paragraph className="!mb-0 text-base text-[#34312d]">{report.summary}</Typography.Paragraph>
            </Card>

            <Card className="workbench-panel" title="关键发现">
              {report.key_findings.length ? (
                <List
                  dataSource={report.key_findings}
                  renderItem={(item) => (
                    <List.Item>
                      <Typography.Text>{item}</Typography.Text>
                    </List.Item>
                  )}
                />
              ) : (
                <Empty description="暂无关键发现" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>

            <Card className="workbench-panel" title="规则诊断">
              {report.rule_diagnostics.length ? (
                <List
                  dataSource={report.rule_diagnostics}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta
                        description={
                          item.evidence.length ? item.evidence.join(" / ") : "暂无证据，继续积累样本。"
                        }
                        title={
                          <Space wrap>
                            <Typography.Text strong>{item.rule_name}</Typography.Text>
                            <Tag>{item.status}</Tag>
                            <Tag>{Math.round(item.confidence * 100)}%</Tag>
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
              ) : (
                <Empty description="暂无分规则诊断" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </Space>

          <Space className="min-w-0" direction="vertical" size={16}>
            <Card className="workbench-panel" title="维护包信息">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="报告 ID">{report.report_id}</Descriptions.Item>
                <Descriptions.Item label="复盘包 ID">{report.packet_id}</Descriptions.Item>
                <Descriptions.Item label="待确认建议">
                  <Badge count={pendingSuggestions.length} overflowCount={99} showZero />
                </Descriptions.Item>
              </Descriptions>
            </Card>

            <Card className="workbench-panel" title="待确认建议">
              {report.suggestions.length ? (
                <List
                  dataSource={report.suggestions}
                  renderItem={(suggestion) => {
                    const disabled = suggestion.status !== "pending";
                    const loadingAction = updatingSuggestionId === suggestion.suggestion_id;
                    return (
                      <List.Item className="!items-start">
                        <div className="w-full space-y-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <Typography.Text className="text-base" strong>
                              {suggestion.title}
                            </Typography.Text>
                            <SuggestionStatusTag status={suggestion.status} />
                            <Tag>{suggestion.type}</Tag>
                            <Tag>{Math.round(suggestion.confidence * 100)}%</Tag>
                          </div>
                          <Typography.Paragraph className="!mb-0 text-[#4a4640]">
                            {suggestion.reason}
                          </Typography.Paragraph>
                          <Typography.Paragraph className="!mb-0 workbench-muted">
                            建议动作：{suggestion.suggested_action}
                          </Typography.Paragraph>
                          <Typography.Paragraph className="!mb-0 workbench-muted">
                            风险：{suggestion.risk}
                          </Typography.Paragraph>
                          <Space wrap>
                            <Button
                              disabled={disabled}
                              loading={loadingAction}
                              onClick={() => void handleSuggestionAction(suggestion, "accept")}
                              size="small"
                              type="primary"
                            >
                              确认
                            </Button>
                            <Button
                              disabled={disabled}
                              loading={loadingAction}
                              onClick={() => void handleSuggestionAction(suggestion, "snooze")}
                              size="small"
                            >
                              延后
                            </Button>
                            <Button
                              disabled={disabled}
                              loading={loadingAction}
                              onClick={() => void handleSuggestionAction(suggestion, "ignore")}
                              size="small"
                            >
                              忽略
                            </Button>
                          </Space>
                        </div>
                      </List.Item>
                    );
                  }}
                />
              ) : (
                <Empty description="暂无待确认建议" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>

            <Alert showIcon title={report.disclaimer} type="info" />
          </Space>
        </div>
      ) : (
        <Card className="workbench-panel">
          <Empty
            description="还没有模型维护报告。先生成复盘包，系统会把最近筛选、复盘样本和数据源状态整理给 AI 分析。"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button loading={analyzing} onClick={() => void handleAnalyze()} type="primary">
              生成复盘包并分析
            </Button>
          </Empty>
        </Card>
      )}
    </main>
  );
}

function HealthTag({ status }: { status: ModelMaintenanceHealthStatus }) {
  const colorByStatus: Record<ModelMaintenanceHealthStatus, string> = {
    normal: "green",
    watch: "blue",
    degraded: "orange",
    insufficient_sample: "default",
    data_unreliable: "red",
  };
  const labelByStatus: Record<ModelMaintenanceHealthStatus, string> = {
    normal: "正常",
    watch: "观察",
    degraded: "退化",
    insufficient_sample: "样本不足",
    data_unreliable: "数据不可靠",
  };
  return <Tag color={colorByStatus[status]}>{labelByStatus[status]}</Tag>;
}

function SuggestionStatusTag({ status }: { status: ModelMaintenanceSuggestionStatus }) {
  const colorByStatus: Record<ModelMaintenanceSuggestionStatus, string> = {
    pending: "gold",
    accepted: "green",
    ignored: "default",
    snoozed: "blue",
  };
  return <Tag color={colorByStatus[status]}>{suggestionStatusText(status)}</Tag>;
}

function suggestionStatusText(status: ModelMaintenanceSuggestionStatus): string {
  const labelByStatus: Record<ModelMaintenanceSuggestionStatus, string> = {
    pending: "待确认",
    accepted: "确认",
    ignored: "忽略",
    snoozed: "延后",
  };
  return labelByStatus[status];
}
