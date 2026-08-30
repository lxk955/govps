/**
 * Render Free 探活：只返回 200 + no-store，不打 FastAPI、不跑 RSC。
 * 必须绕过 Cloudflare 缓存，否则边缘命中、源站照样 15 分钟休眠。
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;

const HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate",
  "CDN-Cache-Control": "no-store",
  "Cloudflare-CDN-Cache-Control": "no-store",
};

export function GET() {
  return new Response("ok", { status: 200, headers: HEADERS });
}

export function HEAD() {
  return new Response(null, { status: 200, headers: HEADERS });
}
