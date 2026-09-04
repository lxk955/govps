/**
 * FastAPI 客户端唯一封装（refactor-plan §1/§2.6）：
 * - 浏览器：相对路径，经 next.config rewrites 转发到 API_ORIGIN（同域，无 CORS）
 * - RSC：直连 API_ORIGIN（Docker 内网 http://api:8000），不绕公网 Host
 * - 错误统一归一为 ApiError，页面不得各自解析原始响应
 * - 缓存策略由调用方显式声明：RSC 用 next.revalidate，客户端交互用 no-store
 */

import { serverApiOrigin } from "@/lib/api-origin";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface ApiFetchInit extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** 透传 Next.js fetch 扩展项（如 revalidate） */
  next?: { revalidate?: number; tags?: string[] };
}

// ── 登录凭证（P4）：Bearer token 由 AuthProvider 注入，仅浏览器端携带 ──

let authToken: string | null = null;
const authExpiredListeners = new Set<() => void>();

/** 登录后注入 token；登出传 null。 */
export function setApiToken(token: string | null): void {
  authToken = token;
}

/** 注册「凭证失效」回调（401 且请求时带了凭证才触发），返回取消函数。 */
export function onAuthExpired(cb: () => void): () => void {
  authExpiredListeners.add(cb);
  return () => {
    authExpiredListeners.delete(cb);
  };
}

function resolveBaseUrl(): string {
  if (typeof window !== "undefined") return "";
  return serverApiOrigin();
}

/** 瞬时 502/503 短重试一次。429 是业务限流，不再当 Render 休眠来等。 */
const RETRY_STATUS = new Set([502, 503]);
const RETRY_DELAYS_MS = [300];

function shouldRetry(res: Response, method?: string): boolean {
  return (method ?? "GET").toUpperCase() === "GET" && RETRY_STATUS.has(res.status);
}

export async function apiFetch<T>(path: string, init: ApiFetchInit = {}): Promise<T> {
  const { body, next, headers, ...rest } = init;
  // 服务端（RSC）永不携带用户凭证：登录态不影响公开页 SSR/SEO
  const isClient = typeof window !== "undefined";
  const hadAuth = isClient && authToken != null;

  let res: Response;
  try {
    const base = resolveBaseUrl();
    const send = () =>
      fetch(`${base}${path}`, {
        ...rest,
        ...(next ? { next } : {}),
        headers: {
          "Content-Type": "application/json",
          ...(hadAuth ? { Authorization: `Bearer ${authToken}` } : {}),
          ...headers,
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });

    res = await send();
    for (const delay of RETRY_DELAYS_MS) {
      if (!shouldRetry(res, rest.method)) break;
      await new Promise((r) => setTimeout(r, delay));
      res = await send();
    }
  } catch (cause) {
    throw new ApiError(0, cause instanceof Error ? cause.message : "网络请求失败");
  }

  if (res.status === 401 && hadAuth) {
    setApiToken(null);
    for (const cb of authExpiredListeners) cb();
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      // 非 JSON 响应体：保留 statusText
    }
    throw new ApiError(res.status, detail);
  }

  return (await res.json()) as T;
}
