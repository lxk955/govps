/**
 * FastAPI 客户端唯一封装（refactor-plan §1/§2.6）：
 * - 一律相对路径，经 next.config rewrites 转发到 API_ORIGIN（同域，无 CORS）
 * - 错误统一归一为 ApiError，页面不得各自解析原始响应
 * - 缓存策略由调用方显式声明：RSC 用 next.revalidate，客户端交互用 no-store
 */

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

/**
 * 解析请求基址：浏览器端相对路径走同域；RSC 在服务端执行，fetch 不支持相对路径，
 * 从请求头还原同源绝对地址后仍经自身 /api/* rewrite 转发（服务端转发，无 CORS），
 * 业务代码依旧只写相对路径。
 */
async function resolveBaseUrl(): Promise<string> {
  if (typeof window !== "undefined") return "";
  const { headers } = await import("next/headers");
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  return `${proto}://${host}`;
}

/**
 * Render 免费实例空闲后会休眠，唤醒窗口内请求被边缘直接拒绝：
 * 429 + x-render-routing: hibernate-rate-limited，body 为纯文本（非 JSON）。
 *
 * 退避时长必须匹配冷启动量级：免费实例唤醒实测 5~30s，原先只退避
 * 600/1200ms（累计 1.8s）必然抢在实例就绪前放弃，用户每次都看到 429。
 * 现改为阶梯退避累计约 8s（第 0.8 / 2.3 / 4.8 / 8.3s 各重试一次），
 * 覆盖多数冷启动；再久就不宜让 RSC 继续阻塞，交给页面提示刷新重试。
 *
 * 仅对幂等 GET 退避重试；非 GET 重试可能造成重复写入。
 */
const RETRY_STATUS = new Set([429, 502, 503]);
const RETRY_DELAYS_MS = [800, 1500, 2500, 3500];

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
    const base = await resolveBaseUrl();
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
    // 凭证失效：清除本地登录态并通知（避免各页面重复处理）
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
    // 休眠拒绝是纯文本 429，不是业务限流：换成用户可操作的提示，
    // 避免把 HTTP 状态文本 "Too Many Requests" 直接丢到页面上。
    if (res.status === 429 && res.headers.get("x-render-routing") === "hibernate-rate-limited") {
      detail = "数据服务正在启动，请稍后刷新页面";
    }
    throw new ApiError(res.status, detail);
  }

  return (await res.json()) as T;
}
