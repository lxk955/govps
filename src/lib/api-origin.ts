/**
 * API 源地址解析（next.config.ts rewrites 与 RSC 服务端直连共用，避免两份逻辑漂移）。
 *
 * 服务端直连的意义：此前 RSC 取数还原公网域名自呼自身（/api/* rewrite 转发），
 * 每次筛选/翻页都要「Cloudflare 进 + Render 路由 + 出公网到 API 服务」两段边缘
 * 往返；直连 API_ORIGIN 砍掉第一段，筛选类导航显著提速。
 */

export function normalizeApiOrigin(raw?: string): string {
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

/** 运行时 API 源地址（含协议）。服务端 fetch 直连用；浏览器端仍走同域相对路径。 */
export function apiOrigin(): string {
  return normalizeApiOrigin(process.env.API_ORIGIN);
}
