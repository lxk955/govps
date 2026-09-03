import type { NextConfig } from "next";

/**
 * 同域 API 转发（refactor-plan §1）：
 * /api/* 与 /go/* 由服务端 rewrite 转发到 FastAPI，前端代码只写相对路径。
 * 目标地址必须通过环境变量配置，禁止硬编码到业务代码。
 * 未来拆分 api.govps.xyz 时仅需修改 API_ORIGIN，业务代码零改动。
 */
function normalizeApiOrigin(raw?: string): string {
  if (!raw || !raw.trim()) {
    return process.env.NODE_ENV === "production" ? "http://api:8000" : "http://localhost:8000";
  }
  const trimmed = raw.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  if (
    trimmed.includes("localhost") ||
    trimmed.includes("127.0.0.1") ||
    trimmed.startsWith("api:") ||
    trimmed.includes(":8000")
  ) {
    return `http://${trimmed}`;
  }
  return `https://${trimmed}`;
}

const API_ORIGIN = normalizeApiOrigin(process.env.API_ORIGIN);

const nextConfig: NextConfig = {
  output: "standalone",
  eslint: {
    // 提交前本地已强制跑过 eslint 验证，跳过容器内重复耗时检查
    ignoreDuringBuilds: true,
  },
  typescript: {
    // 提交前本地已强制跑过 tsc 验证，避免 2GB 内存 VPS 上高负载内存换页
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` },
      { source: "/go/:path*", destination: `${API_ORIGIN}/go/:path*` },
    ];
  },
  async redirects() {
    return [
      {
        source: "/vps",
        destination: "/",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
