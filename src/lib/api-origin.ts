/**
 * FastAPI 基址。浏览器走同域相对路径；RSC 必须绝对 URL，直连 API_ORIGIN，
 * 不绕公网 Host（否则请求会再进 Caddy → Cloudflare，列表每次筛选多一跳）。
 * 与 next.config.ts 的 rewrite 目标保持同一套规则。
 */
export function serverApiOrigin(): string {
  const raw = process.env.API_ORIGIN?.trim();
  if (!raw) {
    return process.env.NODE_ENV === "production" ? "http://api:8000" : "http://localhost:8000";
  }
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    return raw.replace(/\/$/, "");
  }
  if (
    raw.includes("localhost") ||
    raw.includes("127.0.0.1") ||
    raw.startsWith("api:") ||
    raw.includes(":8000")
  ) {
    return `http://${raw.replace(/\/$/, "")}`;
  }
  return `https://${raw.replace(/\/$/, "")}`;
}
