"use client";

import { CopyOutlined, FileTextOutlined, ReloadOutlined, RobotOutlined } from "@ant-design/icons";
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
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";
import {
  analyzeModelMaintenance,
  generateAuctionTop3TrainingSamples,
  generateModelMaintenancePacket,
  getAuctionTop3TrainingPerformance,
  getAuctionTop3TrainingSummary,
  getLatestModelMaintenancePacket,
  getLatestModelMaintenanceReport,
  updateModelMaintenanceSuggestion,
} from "../../lib/api";
import type {
  AuctionTop3PerformanceResponse,
  AuctionTop3TrainingSummary,
  ModelMaintenanceHealthStatus,
  ModelMaintenancePacket,
  ModelMaintenanceReport,
  ModelMaintenanceSuggestion,
  ModelMaintenanceSuggestionStatus,
} from "../../lib/types";

type ModelMaintenanceContentProps = {
  renderPage?: (content: ReactNode, actions?: ReactNode) => ReactNode;
};

export function ModelMaintenanceWorkspace() {
  return (
    <ModelMaintenanceContent
      renderPage={(content, actions) => (
        <PageFrame
          actions={actions}
          context="把筛选结果、复盘样本、竞价 Top3 训练和数据源状态整理成维护包，再交给 Codex / DeepSeek 分析。"
          title="AI 模型维护"
        >
          {content}
        </PageFrame>
      )}
    />
  );
}

export function ModelMaintenanceContent({ renderPage }: ModelMaintenanceContentProps) {
  const { message } = App.useApp();
  const [packet, setPacket] = useState<ModelMaintenancePacket | null>(null);
  const [report, setReport] = useState<ModelMaintenanceReport | null>(null);
  const [trainingSummary, setTrainingSummary] = useState<AuctionTop3TrainingSummary | null>(null);
  const [performance, setPerformance] = useState<AuctionTop3PerformanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [generatingPacket, setGeneratingPacket] = useState(false);
  const [generatingTraining, setGeneratingTraining] = useState(false);
  const [updatingSuggestionId, setUpdatingSuggestionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void loadMaintenanceState(() => active);
    return () => {
      active = false;
    };
  }, []);

  const pendingSuggestions = useMemo(
    () => report?.suggestions.filter((suggestion) => suggestion.status === "pending") ?? [],
    [report],
  );
  const packetLink = useMemo(() => buildPacketLink(packet), [packet]);

  async function loadMaintenanceState(canCommit: () => boolean = () => true) {
    setLoading(true);
    setError(null);
    try {
      const [nextPacket, nextReport, nextTrainingSummary, nextPerformance] = await Promise.all([
        getLatestModelMaintenancePacket(),
        getLatestModelMaintenanceReport(),
        getAuctionTop3TrainingSummary(),
        getAuctionTop3TrainingPerformance(),
      ]);
      if (!canCommit()) {
        return;
      }
      setPacket(nextPacket);
      setReport(nextReport);
      setTrainingSummary(nextTrainingSummary);
      setPerformance(nextPerformance);
    } catch (err) {
      if (canCommit()) {
        setError(err instanceof Error ? err.message : "读取模型维护状态失败");
      }
    } finally {
      if (canCommit()) {
        setLoading(false);
      }
    }
  }

  async function handleGeneratePacket() {
    setGeneratingPacket(true);
    setError(null);
    try {
      const nextPacket = await generateModelMaintenancePacket();
      setPacket(nextPacket);
      void message.success("模型维护数据包已生成");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "生成模型维护数据包失败";
      setError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setGeneratingPacket(false);
    }
  }

  async function handleGenerateTrainingSamples() {
    setGeneratingTraining(true);
    setError(null);
    try {
      const result = await generateAuctionTop3TrainingSamples();
      setPerformance(result.performance);
      setTrainingSummary(await getAuctionTop3TrainingSummary());
      void message.success(`已生成 ${result.saved_count} 条模拟交易样本`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "生成竞价 Top3 训练样本失败";
      setError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setGeneratingTraining(false);
    }
  }

  async function handleAnalyze() {
    if (!packet) {
      void message.warning("请先生成模型维护数据包");
      return;
    }
    setAnalyzing(true);
    setError(null);
    try {
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

  async function handleCopy(text: string, label: string) {
    if (!navigator.clipboard) {
      void message.error("当前浏览器不支持自动复制");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      void message.success(`${label}已复制`);
    } catch {
      void message.error("复制失败，请手动复制链接");
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

  const actions = (
    <Space wrap>
      <Button
        disabled={loading || analyzing || generatingPacket}
        icon={<ReloadOutlined />}
        onClick={() => void loadMaintenanceState()}
      >
        重新读取
      </Button>
      <Button icon={<FileTextOutlined />} loading={generatingPacket} onClick={() => void handleGeneratePacket()}>
        生成数据包
      </Button>
      <Button
        disabled={!packet}
        icon={<RobotOutlined />}
        loading={analyzing}
        onClick={() => void handleAnalyze()}
        type="primary"
      >
        提交 AI 分析
      </Button>
    </Space>
  );
  const content = (
    <>
      {error && <Alert className="mb-4" showIcon title={error} type="error" />}

      {loading ? (
        <Card className="app-panel">
          <Skeleton active paragraph={{ rows: 10 }} />
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.8fr)]">
          <Space className="min-w-0" orientation="vertical" size={16}>
            <Card className="app-panel" title="维护流程">
              <div className="grid gap-3 md:grid-cols-3">
                <WorkflowStep
                  active={Boolean(packet)}
                  description={packet ? `已生成 ${packet.generated_at}` : "整理筛选、GSGF、竞价 Top3 和训练摘要。"}
                  title="1. 生成数据包"
                />
                <WorkflowStep
                  active={Boolean(packetLink)}
                  description={packetLink ? "复制给 Codex 或打开可读详情页。" : "生成数据包后出现可复制链接。"}
                  title="2. 复制给 Codex"
                />
                <WorkflowStep
                  active={Boolean(report)}
                  description={report ? `报告 ${report.report_id}` : "由 DeepSeek / OpenAI-compatible 节点生成建议。"}
                  title="3. 提交 AI 分析"
                />
              </div>
            </Card>

            {report ? (
              <Card className="app-panel" title="维护结论">
                <Space className="mb-4" wrap>
                  <HealthTag status={report.health_status} />
                  <Tag>{report.provider}</Tag>
                  <Tag>{report.model}</Tag>
                  <Tag>{report.generated_at}</Tag>
                </Space>
                <Typography.Paragraph className="app-ink !mb-0 text-base">{report.summary}</Typography.Paragraph>
              </Card>
            ) : (
              <Card className="app-panel">
                <Empty
                  description="还没有模型维护报告。先生成数据包，再提交 AI 分析；也可以把链接复制给 Codex 单独分析。"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                >
                  <Space wrap>
                    <Button loading={generatingPacket} onClick={() => void handleGeneratePacket()}>
                      生成数据包
                    </Button>
                    <Button disabled={!packet} loading={analyzing} onClick={() => void handleAnalyze()} type="primary">
                      提交 AI 分析
                    </Button>
                  </Space>
                </Empty>
              </Card>
            )}

            <Card className="app-panel" title="关键发现">
              {report?.key_findings.length ? (
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

            <Card className="app-panel" title="规则诊断">
              {report?.rule_diagnostics.length ? (
                <List
                  dataSource={report.rule_diagnostics}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta
                        description={item.evidence.length ? item.evidence.join(" / ") : "暂无证据，继续积累样本。"}
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

          <Space className="min-w-0" orientation="vertical" size={16}>
            <Card
              className="app-panel"
              extra={
                packetLink ? (
                  <Button
                    icon={<CopyOutlined />}
                    onClick={() => void handleCopy(packetLink, "数据包链接")}
                    size="small"
                  >
                    复制给 Codex
                  </Button>
                ) : null
              }
              title="维护包信息"
            >
              {packet ? (
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="数据包 ID">{packet.packet_id}</Descriptions.Item>
                  <Descriptions.Item label="交易日">{packet.trade_date ?? "--"}</Descriptions.Item>
                  <Descriptions.Item label="生成时间">{packet.generated_at}</Descriptions.Item>
                  <Descriptions.Item label="数据质量">{packet.data_quality_notes.length ? "有提示" : "未见异常"}</Descriptions.Item>
                  <Descriptions.Item label="链接">
                    {packetLink ? <Typography.Link href={packetLink}>{packetLink}</Typography.Link> : "--"}
                  </Descriptions.Item>
                </Descriptions>
              ) : (
                <Empty description="暂无数据包" image={Empty.PRESENTED_IMAGE_SIMPLE}>
                  <Button loading={generatingPacket} onClick={() => void handleGeneratePacket()} type="primary">
                    生成数据包
                  </Button>
                </Empty>
              )}
            </Card>

            <Card
              className="app-panel"
              extra={
                <Button loading={generatingTraining} onClick={() => void handleGenerateTrainingSamples()} size="small">
                  生成模拟样本
                </Button>
              }
              title="竞价 Top3 训练"
            >
              <Descriptions column={1} size="small">
                <Descriptions.Item label="信号样本">{trainingSummary?.signal_sample_count ?? 0}</Descriptions.Item>
                <Descriptions.Item label="模拟交易">{trainingSummary?.simulated_trade_sample_count ?? 0}</Descriptions.Item>
                <Descriptions.Item label="人工样本">{trainingSummary?.manual_trade_sample_count ?? 0}</Descriptions.Item>
                <Descriptions.Item label="训练窗口">
                  {trainingSummary ? `${trainingSummary.training_window_days} 天` : "--"}
                </Descriptions.Item>
                <Descriptions.Item label="模拟收益">
                  {formatPercent(numberFromRecord(performance?.summary, "cumulative_return_pct"))}
                </Descriptions.Item>
                <Descriptions.Item label="最新权益">
                  {formatCurrency(numberFromRecord(performance?.summary, "latest_equity"))}
                </Descriptions.Item>
              </Descriptions>
              <Alert
                className="mt-3"
                showIcon
                title="模拟收益只用于模型维护和规则回测，不代表真实账户收益。"
                type="info"
              />
            </Card>

            <Card className="app-panel" title="待确认建议">
              <Descriptions className="mb-3" column={1} size="small">
                <Descriptions.Item label="报告 ID">{report?.report_id ?? "--"}</Descriptions.Item>
                <Descriptions.Item label="数据包 ID">{report?.packet_id ?? packet?.packet_id ?? "--"}</Descriptions.Item>
                <Descriptions.Item label="待确认建议">
                  <Badge count={pendingSuggestions.length} overflowCount={99} showZero />
                </Descriptions.Item>
              </Descriptions>
              {report?.suggestions.length ? (
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
                          <Typography.Paragraph className="app-ink !mb-0">
                            {suggestion.reason}
                          </Typography.Paragraph>
                          <Typography.Paragraph className="!mb-0 app-muted">
                            建议动作：{suggestion.suggested_action}
                          </Typography.Paragraph>
                          <Typography.Paragraph className="!mb-0 app-muted">
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

            {report && <Alert showIcon title={report.disclaimer} type="info" />}
          </Space>
        </div>
      )}
    </>
  );

  return renderPage ? renderPage(content, actions) : content;
}

function WorkflowStep({
  active,
  description,
  title,
}: {
  active: boolean;
  description: string;
  title: string;
}) {
  return (
    <div className="app-panel rounded-lg border p-3">
      <Space className="mb-1" wrap>
        <Badge status={active ? "success" : "default"} />
        <Typography.Text strong>{title}</Typography.Text>
      </Space>
      <Typography.Text className="app-muted block text-xs">{description}</Typography.Text>
    </div>
  );
}

function buildPacketLink(packet: ModelMaintenancePacket | null): string | null {
  if (!packet) {
    return null;
  }
  if (typeof window === "undefined") {
    return packet.packet_url;
  }
  return `${window.location.origin}/model-maintenance/packets/${packet.packet_id}`;
}

function numberFromRecord(record: Record<string, unknown> | undefined, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" ? value : null;
}

function formatPercent(value: number | null): string {
  return value === null ? "--" : `${value.toFixed(2)}%`;
}

function formatCurrency(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
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
