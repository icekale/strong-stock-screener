"use client";

import { App as AntdApp, ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";

export function AntdAppProvider({ children }: { children: React.ReactNode }) {
  return (
    <ConfigProvider
      button={{ autoInsertSpace: false }}
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          borderRadius: 8,
          colorBgLayout: "#f8fafc",
          colorInfo: "#1677ff",
          colorPrimary: "#0f172a",
          colorText: "#0f172a",
          colorTextSecondary: "#475569",
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
        components: {
          Button: {
            borderRadius: 6,
            controlHeight: 34,
          },
          Card: {
            borderRadiusLG: 8,
            paddingLG: 16,
          },
          Form: {
            itemMarginBottom: 14,
          },
          Layout: {
            bodyBg: "#f8fafc",
            headerBg: "#ffffff",
            siderBg: "#ffffff",
          },
          Menu: {
            itemBorderRadius: 6,
            itemHeight: 36,
            itemMarginBlock: 3,
          },
          Table: {
            borderColor: "#e2e8f0",
            headerBg: "#f8fafc",
          },
        },
      }}
    >
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}
