import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { Suspense } from "react";
import { AntdAppProvider } from "../components/AntdAppProvider";
import { AppShell } from "../components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "强势股选股工作台",
  description: "独立强势股选股与自选股风控工具",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <AntdRegistry>
          <AntdAppProvider>
            <Suspense fallback={<div className="app-shell app-shell--loading">{children}</div>}>
              <AppShell>{children}</AppShell>
            </Suspense>
          </AntdAppProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
