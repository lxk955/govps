import type { NextConfig } from "next";

/**
 * /api/* 与 /go/* 的转发已移至 src/middleware.ts。
 *
 * 原因：next.config 的 rewrites 不支持自定义转发头，后端只能看到本服务
 * （Render）的出口 IP 而非访客 IP；而「middleware 仅改头 + rewrites 代理」
 * 经实测无效——代理层会覆盖 X-Forwarded-For，注入的真实 IP 被丢弃。
 * 改由 middleware 直接 rewrite，转发目标仍唯一由 API_ORIGIN 决定。
 */
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
