import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || (process.env.NODE_ENV === "development" ? ".next-dev" : ".next"),
  experimental: {
    proxyTimeout: 240_000,
  },
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8010/api/:path*",
      },
      {
        source: "/health",
        destination: "http://127.0.0.1:8010/health",
      },
    ];
  },
};

export default nextConfig;
