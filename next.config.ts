import type { NextConfig } from "next";

/**
 * 同域 API 转发（refactor-plan §1）：
 * /api/* 与 /go/* 由服务端 rewrite 转发到 FastAPI，前端代码只写相对路径。
 * 目标地址必须通过环境变量配置，禁止硬编码到业务代码。
 * 未来拆分 api.govps.xyz 时仅需修改 API_ORIGIN，业务代码零改动。
 */
function normalizeApiOrigin(raw?: string): string {
  if (!raw) {
    if (process.env.NODE_ENV === "production" || process.env.RENDER) {
      return "https://govps-api.onrender.com";
    }
    return "http://localhost:8000";
  }
  const trimmed = raw.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  // Render fromService property:host 产出无协议的主机名（如 govps-api.onrender.com 或 govps-api:8000）
  if (trimmed.includes("localhost") || trimmed.includes("127.0.0.1") || trimmed.includes(":8000")) {
    return `http://${trimmed}`;
  }
  return `https://${trimmed}`;
}

const API_ORIGIN = normalizeApiOrigin(process.env.API_ORIGIN);

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      // 注意：/api/* 已由 src/app/api/[...path]/route.ts 接管。
      // rewrites 不支持自定义转发头，后端只能看到本服务的出口 IP（影响
      // /api/ip/check 的默认检测与 auth 的 IP 限流）；Route Handler 走
      // Node.js Runtime，可在转发时注入客户端真实 IP。
      { source: "/go/:path*", destination: `${API_ORIGIN}/go/:path*` },
    ];
  },
};

export default nextConfig;
