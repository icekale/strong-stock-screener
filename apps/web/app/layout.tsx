import type { Metadata } from "next";
import "kline-charts-react/style.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "强势股选股工作台",
  description: "独立强势股选股与自选股风控工具",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
