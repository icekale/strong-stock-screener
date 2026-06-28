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
          colorBgBase: "#f8f7f4",
          colorBgContainer: "#f8f7f4",
          colorBgLayout: "#f5f3f0",
          colorBorder: "#ddd8d0",
          colorInfo: "#11100e",
          colorPrimary: "#11100e",
          colorText: "#11100e",
          colorTextSecondary: "#7b756d",
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
            bodyBg: "#f5f3f0",
            headerBg: "#f8f7f4",
            siderBg: "#1d1b18",
          },
          Menu: {
            itemBorderRadius: 6,
            itemHeight: 36,
            itemMarginBlock: 3,
          },
          Table: {
            borderColor: "#ddd8d0",
            headerBg: "#eee9df",
          },
        },
      }}
    >
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}
