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
          colorBgBase: "#edf3f8",
          colorBgContainer: "#fff",
          colorBgLayout: "#edf3f8",
          colorBorder: "#d9e2ed",
          colorInfo: "#1769e0",
          colorPrimary: "#1769e0",
          colorText: "#182336",
          colorTextSecondary: "#697991",
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
            bodyBg: "#edf3f8",
            headerBg: "#fff",
            siderBg: "#13233f",
          },
          Menu: {
            itemBorderRadius: 6,
            itemHeight: 36,
            itemMarginBlock: 3,
          },
          Table: {
            borderColor: "#d9e2ed",
            headerBg: "#f7f9fc",
          },
        },
      }}
    >
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}
