"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Space, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { getSectorRadar } from "../../lib/api";
import type { SectorRadarResponse } from "../../lib/types";
import { SectorFlowWorkspace } from "./SectorFlowWorkspace";

export function SectorPageWorkspace() {
  const [data, setData] = useState<SectorRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setData(await getSectorRadar(20));
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取板块资金流失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Typography.Title className="m-0 text-[#11100e]" level={3}>
            板块资金流
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            按全市场板块热度、成交额和涨跌额追踪盘中资金方向。
          </Typography.Text>
        </div>
        <Space wrap>
          <Tag color={data?.capital_flow_status === "direct" ? "green" : "orange"}>
            资金流口径：{data?.flow_source ?? "读取中"}
          </Tag>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void refresh()} type="primary">
            刷新数据
          </Button>
        </Space>
      </div>

      {error && <Alert className="mb-4" showIcon title={error} type="error" />}

      <SectorFlowWorkspace data={data} loading={loading} />
    </main>
  );
}
