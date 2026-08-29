import { NextResponse, type NextRequest } from "next/server";

/**
 * /api/* 与 /go/* 的后端转发（原 next.config rewrites 的职责）。
 *
 * 为什么不用 next.config 的 rewrites：它不支持自定义转发头，后端收到的
 * X-Forwarded-For 首段是本服务（Render）的出口 IP 而非访客 IP，导致
 *   1) /api/ip/check 留空时检测到服务器 IP，不是用户公网出口；
 *   2) auth 的 IP 限流把所有访客算成同一个 IP，互相挤占每分钟 5 次配额。
 *
 * 实测「middleware 仅改写请求头 + rewrites 代理」无效：代理层会覆盖
 * X-Forwarded-For，注入的真实 IP 被丢弃。故改由 middleware 直接 rewrite
 * 到后端，转发头完全可控。转发目标仍唯一由 API_ORIGIN 决定。
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
  // Render fromService property:host 产出无协议主机名（如 govps-api.onrender.com）
  if (trimmed.includes("localhost") || trimmed.includes("127.0.0.1") || trimmed.includes(":8000")) {
    return `http://${trimmed}`;
  }
  return `https://${trimmed}`;
}

const API_ORIGIN = normalizeApiOrigin(process.env.API_ORIGIN);

/** 客户端真实 IP：Cloudflare 注入优先，其次 x-real-ip / XFF 首段。 */
function resolveClientIp(request: NextRequest): string | null {
  const cf = request.headers.get("cf-connecting-ip");
  if (cf?.trim()) return cf.trim();

  const real = request.headers.get("x-real-ip");
  if (real?.trim()) return real.trim();

  const first = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return first || null;
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const url = new URL(`${API_ORIGIN}${pathname}${search}`);

  const headers = new Headers(request.headers);
  const ip = resolveClientIp(request);
  if (ip) {
    headers.set("cf-connecting-ip", ip);
    headers.set("x-real-ip", ip);
    headers.set("x-forwarded-for", ip);
  }
  return NextResponse.rewrite(url, { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*", "/go/:path*"],
};
