/** 展示币种偏好：cookie 给 SSR，localStorage 作回退，登录用户再异步写服务器。 */

export type CurrencyMode = "original" | "CNY" | "USD";

export const CURRENCY_COOKIE = "govps_currency";
export const CURRENCY_STORAGE_KEY = "govps_currency_mode";
export const DEFAULT_CURRENCY_MODE: CurrencyMode = "original";

const AUTH_TOKEN_KEY = "govps_token";

export function parseCurrencyMode(raw?: string | null): CurrencyMode {
  if (raw === "USD" || raw === "original" || raw === "CNY") return raw;
  return DEFAULT_CURRENCY_MODE;
}

/** 本地已保存的偏好；未写过则返回 null，不要当成默认值。 */
export function readStoredCurrencyMode(): CurrencyMode | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(CURRENCY_STORAGE_KEY);
    if (stored === "USD" || stored === "original" || stored === "CNY") return stored;
  } catch {
    // 隐私模式等
  }
  return null;
}

export function writeCurrencyCookie(mode: CurrencyMode): void {
  if (typeof document === "undefined") return;
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${CURRENCY_COOKIE}=${mode}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

export function persistCurrencyPreference(mode: CurrencyMode): void {
  writeCurrencyCookie(mode);
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(CURRENCY_STORAGE_KEY, mode);
  } catch {
    // 忽略隐私模式下的存储异常
  }
}

/**
 * 登录用户把偏好异步写到服务器。不阻塞 UI，不走 apiFetch（避免等 JSON / 401 误登出）。
 * keepalive 让切页时请求仍能发出。
 */
export function pushCurrencyPreferenceRemote(mode: CurrencyMode): void {
  if (typeof window === "undefined") return;
  let token: string | null = null;
  try {
    token = localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return;
  }
  if (!token) return;
  void fetch("/api/auth/preferences", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ currency_mode: mode }),
    keepalive: true,
  }).catch(() => {});
}

/** 价格区间筛选只支持 CNY/USD；原币模式按美元年付横比。 */
export function priceFilterCurrency(mode: CurrencyMode): "CNY" | "USD" {
  return mode === "CNY" ? "CNY" : "USD";
}

export function priceFilterSymbol(mode: CurrencyMode): "¥" | "$" {
  return mode === "CNY" ? "¥" : "$";
}

export function priceFilterHint(mode: CurrencyMode): string {
  if (mode === "CNY") return "人民币年付";
  if (mode === "USD") return "美元年付";
  return "按美元年付横比";
}

export function convertFilterAmount(
  n: number,
  from: "CNY" | "USD",
  to: "CNY" | "USD",
  cnyPerUsd: number,
): number {
  if (from === to) return n;
  const rate = cnyPerUsd > 0 ? cnyPerUsd : 7.2;
  if (from === "USD" && to === "CNY") return Math.round(n * rate);
  return Math.round((n / rate) * 100) / 100;
}
