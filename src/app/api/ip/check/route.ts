import { type NextRequest, NextResponse } from "next/server";

/**
 * 仅代理 /api/ip/check 一个端点（其余 /api/* 仍走 next.config 的 rewrites）。
 *
 * 为什么只有它需要特殊处理：IP 检测留空时要返回「访客自己的公网出口」，
 * 但 rewrites 由 Next.js 代理转发，后端看到的 X-Forwarded-For 首段是本服务
 * （Render）的出口 IP，检测结果会是 74.220.48.219（org: Render）这类服务器
 * 地址而不是访客 IP。这里在转发时把客户端真实 IP 注入进去。
 *
 * 为什么只接管这一个路径而不是全部 /api/*：此前两次尝试（middleware 改头、
 * middleware 直接 rewrite）在生产都导致 /api/* 全部 500。收窄到单端点可把
 * 故障 blast radius 限制在 IP 检测一页；即便转发失败也只返回 502，
 * 不影响列表、详情、登录等其余功能。
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
  try {
    const url = new URL(request.url);
    const target = `${API_ORIGIN}${url.pathname}${url.search}`;

    const headers = new Headers(request.headers);
    // Host 须按目标重新生成，否则后端按本站域名做路由/CORS 判断
    headers.delete("host");

    const ip = resolveClientIp(request);
    if (ip) {
      headers.set("cf-connecting-ip", ip);
      headers.set("x-real-ip", ip);
      headers.set("x-forwarded-for", ip);
    }

    const upstream = await fetch(target, {
      method: "GET",
      headers,
      redirect: "manual",
    });

    // 完整读取后再返回而非流式转发 upstream.body：流式传输的错误发生在
    // try/catch 之外（生产实测表现为 Cloudflare 502 而非本函数的 JSON 502）。
    // IP 检测响应仅数 KB，完整读取没有内存压力。
    const body = await upstream.text();

    // fetch 已自动解压，原样透传 content-encoding/content-length 会让客户端
    // 二次解压或长度校验失败
    const resHeaders = new Headers(upstream.headers);
    resHeaders.delete("content-encoding");
    resHeaders.delete("content-length");
    resHeaders.delete("transfer-encoding");

    return new NextResponse(body, {
      status: upstream.status,
      headers: resHeaders,
    });
  } catch (cause) {
    // 转发失败只影响本端点：返回 502 让前端显示检测失败，不牵连其他 API
    const message = cause instanceof Error ? cause.message : "unknown";
    return NextResponse.json({ detail: `IP 检测服务暂时不可用：${message}` }, { status: 502 });
  }
}

export const GET = proxy;

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
