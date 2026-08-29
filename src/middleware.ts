import { NextResponse, type NextRequest } from "next/server";

/**
 * 向后端转发 /api/* 与 /go/* 时透传客户端真实 IP。
 *
 * 背景：next.config 的 rewrites 由 Next.js 服务端代理转发，后端收到的
 * X-Forwarded-For 首段是本服务（Render）的出口 IP 而不是访客 IP，导致：
 *   1) /api/ip/check 留空时检测到的是服务器 IP，不是用户公网出口；
 *   2) auth 的 IP 限流把所有访客算成同一个 IP，互相挤占每分钟 5 次的配额。
 *
 * next.config 的 rewrites 不支持自定义转发头，因此在 middleware 中改写请求头，
 * 经 NextResponse.next({ request: { headers } }) 交给后续 rewrite 使用。
 *
 * 注意：NextRequest.ip 已在 Next 15 移除，这里只解析前置代理注入的头。
 */
function resolveClientIp(request: NextRequest): string | null {
  // Cloudflare 注入的访客真实 IP（优先，最可信）
  const cf = request.headers.get("cf-connecting-ip");
  if (cf?.trim()) return cf.trim();

  const real = request.headers.get("x-real-ip");
  if (real?.trim()) return real.trim();

  // X-Forwarded-For: client, proxy1, proxy2 —— 取首段
  const first = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return first || null;
}

export function middleware(request: NextRequest) {
  const ip = resolveClientIp(request);
  if (!ip) return NextResponse.next();

  const headers = new Headers(request.headers);
  headers.set("cf-connecting-ip", ip);
  headers.set("x-real-ip", ip);
  headers.set("x-forwarded-for", ip);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/api/:path*", "/go/:path*"],
};
