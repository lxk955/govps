import { type NextRequest, NextResponse } from "next/server";

/**
 * /api/* 的后端代理（接管 next.config rewrites 的这部分职责）。
 *
 * 为什么需要：next.config 的 rewrites 由 Next.js 代理转发，后端收到的
 * X-Forwarded-For 首段是本服务（Render）的出口 IP 而非访客 IP，导致
 *   1) /api/ip/check 留空时检测到服务器 IP，不是用户公网出口；
 *   2) auth 的 IP 限流把所有访客算成同一个 IP，互相挤占每分钟 5 次配额。
 *
 * 为什么不用 middleware：实测两种改法都不行——「仅改写请求头 + rewrites
 * 代理」会被代理层覆盖 X-Forwarded-For；「middleware 直接 rewrite」在
 * Edge Runtime 下导致 /api/* 全部 500。Route Handler 走 Node.js Runtime，
 * 转发头完全可控，无 Edge 限制。
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

async function proxy(request: NextRequest): Promise<NextResponse> {
  const url = new URL(request.url);
  const target = `${API_ORIGIN}${url.pathname}${url.search}`;

  const headers = new Headers(request.headers);
  // Host 须按目标重新生成，否则后端按本站域名做 CORS/路由判断
  headers.delete("host");

  const ip = resolveClientIp(request);
  if (ip) {
    headers.set("cf-connecting-ip", ip);
    headers.set("x-real-ip", ip);
    headers.set("x-forwarded-for", ip);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: "manual",
  });

  // fetch 已自动解压，原样透传 content-encoding/content-length 会让客户端
  // 二次解压或长度校验失败，必须剔除
  const resHeaders = new Headers(upstream.headers);
  resHeaders.delete("content-encoding");
  resHeaders.delete("content-length");
  resHeaders.delete("transfer-encoding");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: resHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
export const PATCH = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
