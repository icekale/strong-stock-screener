"use client";

import { Alert, Button, Card, Descriptions, Skeleton, Space, Tag, Typography } from "antd";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getModelMaintenancePacket } from "../../../../lib/api";
import type { ModelMaintenancePacket } from "../../../../lib/types";

export default function ModelMaintenancePacketPage() {
  const params = useParams<{ packetId: string }>();
  const packetId = params.packetId;
  const [packet, setPacket] = useState<ModelMaintenancePacket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadPacket() {
      setLoading(true);
      setError(null);
      try {
        setPacket(await getModelMaintenancePacket(packetId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "读取模型维护数据包失败");
      } finally {
        setLoading(false);
      }
    }
    void loadPacket();
  }, [packetId]);

  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Typography.Text className="workbench-muted text-xs font-semibold uppercase">
            Model Maintenance Packet
          </Typography.Text>
          <Typography.Title className="m-0 text-[#11100e]" level={3}>
            模型维护数据包
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            复制本页链接给 Codex，可直接分析 GSGF、竞价 Top3、训练样本和数据源状态。
          </Typography.Text>
        </div>
        <Space wrap>
          <Button href="/model-maintenance">返回模型维护</Button>
          <Button href={`/api/model-maintenance/packets/${encodeURIComponent(packetId)}`} target="_blank">
            打开原始 JSON
          </Button>
        </Space>
      </div>

      {error && <Alert className="mb-4" showIcon title={error} type="error" />}

      {loading ? (
        <Card className="workbench-panel">
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      ) : packet ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Space className="min-w-0" direction="vertical" size={16}>
            <Card className="workbench-panel" title="摘要">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="数据包 ID">{packet.packet_id}</Descriptions.Item>
                <Descriptions.Item label="交易日">{packet.trade_date ?? "--"}</Descriptions.Item>
                <Descriptions.Item label="模型">{packet.model_name}</Descriptions.Item>
                <Descriptions.Item label="模型版本">{packet.model_version ?? "--"}</Descriptions.Item>
                <Descriptions.Item label="生成时间">{packet.generated_at}</Descriptions.Item>
                <Descriptions.Item label="数据源">
                  <Space wrap>
                    {packet.source_status.length ? (
                      packet.source_status.map((status) => (
                        <Tag key={`${status.source}-${status.status}`}>{`${status.source}: ${status.status}`}</Tag>
                      ))
                    ) : (
                      <Tag>暂无</Tag>
                    )}
                  </Space>
                </Descriptions.Item>
              </Descriptions>
            </Card>

            <Card className="workbench-panel" title="模型分区">
              <Space wrap>
                {Object.keys(packet.model_sections).length ? (
                  Object.keys(packet.model_sections).map((key) => <Tag key={key}>{key}</Tag>)
                ) : (
                  <Tag>暂无分区</Tag>
                )}
              </Space>
            </Card>

            <Card className="workbench-panel" title="数据质量">
              {packet.data_quality_notes.length ? (
                <Space direction="vertical">
                  {packet.data_quality_notes.map((note) => (
                    <Alert key={note} showIcon title={note} type="warning" />
                  ))}
                </Space>
              ) : (
                <Alert showIcon title="未记录数据质量异常" type="success" />
              )}
            </Card>
          </Space>

          <Card className="workbench-panel min-w-0" title="原始数据包">
            <pre className="max-h-[70vh] overflow-auto rounded-lg bg-[#11100e] p-4 text-xs leading-5 text-[#f6f2ea]">
              {JSON.stringify(packet, null, 2)}
            </pre>
          </Card>
        </div>
      ) : (
        <Card className="workbench-panel">
          <Alert showIcon title="数据包不存在" type="warning" />
        </Card>
      )}
    </main>
  );
}
