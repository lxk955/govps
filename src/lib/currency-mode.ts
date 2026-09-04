/** 展示币种偏好：cookie 给 SSR，localStorage 作回退。 */

export type CurrencyMode = "original" | "CNY" | "USD";

export const CURRENCY_COOKIE = "govps_currency";
export const CURRENCY_STORAGE_KEY = "govps_currency_mode";

export function parseCurrencyMode(raw?: string | null): CurrencyMode {
  if (raw === "USD" || raw === "original" || raw === "CNY") return raw;
  return "CNY";
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

export function writeCurrencyCookie(mode: CurrencyMode): void {
  if (typeof document === "undefined") return;
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${CURRENCY_COOKIE}=${mode}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}
