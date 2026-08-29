import { apiFetch } from "./client";

/**
 * 端点定义随各阶段逐步补齐（P2 详情/IP…）。
 * 类型只声明前端实际消费的字段；与 FastAPI 响应保持同形（refactor-plan §1）。
 */

// ── P1：VPS 列表域 ──────────────────────────────────────────────

export interface ProductPriceOption {
  billing_cycle: string;
  price: number;
  currency: string;
  purchase_url: string;
}

/** GET /api/products 列表项（B1，聚合后的卡片代表行） */
export interface ProductListItem {
  id: number;
  name: string;
  merchant: { slug: string; name: string };
  cpu_cores: number | null;
  ram_gb: number | null;
  disk_gb: number | null;
  bandwidth_gb: number | null;
  port_mbps: number | null;
  location: string | null;
  line_tags: string[];
  price: number;
  prev_price: number | null;
  price_yearly: number;
  /**
   * P5 契约：USD 换算价恒定返回（响应结构不随币种变化）。
   * USD 产品 = 原始美元价；非 USD 按当前汇率换算；汇率缺失为 null。
   * 禁止以「字段是否存在」推断币种（用 currency 判断）。
   */
  price_converted: number | null;
  price_yearly_converted: number | null;
  price_dropped: boolean;
  is_lowest_price: boolean;
  currency: string;
  billing_cycle: string;
  price_options: ProductPriceOption[];
  purchase_url: string;
  in_stock: boolean;
  recommended: boolean;
  hot_score: number | null;
  deal_score: number | null;
  popularity_score: number | null;
  recommend_reasons: string[];
  is_recent_restock: boolean;
  updated_at: string | null;
  last_checked_at: string | null;
}

export interface ProductsResponse {
  total: number;
  items: ProductListItem[];
}

// ── P5：多币种与汇率 ───────────────────────────────────────────

/** {iso_date: {code: units_per_usd}}，历史价格换算按日期匹配 */
export function getRateSnapshots(
  days = 90,
): Promise<{ base: string; days: number; since: string; snapshots: Record<string, Record<string, number>> }> {
  return apiFetch(`/api/rates/snapshots?days=${days}`, { cache: "no-store" });
}

/**
 * 历史外币金额换算 USD：USD = 金额 ÷ 当日（或之前最近）的 units_per_usd；
 * 找不到返回 null（宁缺毋滥，绝不用当前汇率回算历史）。
 * 与后端 services/rates.convert_historical 同规则。
 */
export function convertHistorical(
  amount: number,
  currency: string,
  onDate: string,
  snapshots: Record<string, Record<string, number>>,
): number | null {
  if (currency === "USD") return amount;
  const d = new Date(onDate);
  if (Number.isNaN(d.getTime())) return null;
  for (let i = 0; i < 31; i++) {
    const key = d.toISOString().slice(0, 10);
    const units = snapshots[key]?.[currency];
    if (units && units > 0) return amount / units;
    d.setUTCDate(d.getUTCDate() - 1);
  }
  return null;
}

export interface SnapshotPoint {
  price?: number;
  in_stock?: boolean;
  checked_at: string;
}

/** GET /api/products/{id} 详情（B3） */
export interface ProductDetail extends ProductListItem {
  price_snapshots: { price: number; checked_at: string }[];
  stock_snapshots: { in_stock: boolean; checked_at: string }[];
}

export function getProductDetail(id: number): Promise<ProductDetail> {
  return apiFetch<ProductDetail>(`/api/products/${id}`, { cache: "no-store" });
}

export interface MerchantSummary {
  slug: string;
  name: string;
  website: string;
  count: number;
  in_stock_count: number;
  last_success_at: string | null;
}

/** 列表查询参数；多选字段传数组，false/undefined 不下发 */
export type ProductListParams = {
  merchant?: string[];
  location?: string[];
  line?: string[];
  min_price?: number;
  max_price?: number;
  min_ram?: number;
  min_cpu?: number;
  min_bw?: number;
  min_port?: number;
  in_stock?: boolean;
  price_drop?: boolean;
  lowest_price?: boolean;
  recent_restock?: boolean;
  recommended?: boolean;
  keyword?: string;
  sort?: string;
  page?: number;
  size?: number;
};

export function buildProductsQuery(params: ProductListParams): string {
  const qs = new URLSearchParams();
  for (const key of ["merchant", "location", "line"] as const) {
    for (const v of params[key] ?? []) qs.append(key, v);
  }
  for (const key of [
    "min_price",
    "max_price",
    "min_ram",
    "min_cpu",
    "min_bw",
    "min_port",
  ] as const) {
    const v = params[key];
    if (v !== undefined) qs.set(key, String(v));
  }
  for (const key of [
    "in_stock",
    "price_drop",
    "lowest_price",
    "recent_restock",
    "recommended",
  ] as const) {
    const v = params[key];
    if (v) qs.set(key, "true");
  }
  if (params.keyword) qs.set("keyword", params.keyword);
  if (params.sort && params.sort !== "hot") qs.set("sort", params.sort);
  if (params.page && params.page > 1) qs.set("page", String(params.page));
  if (params.size && params.size !== 30) qs.set("size", String(params.size));
  return qs.toString();
}

export function listProducts(params: ProductListParams): Promise<ProductsResponse> {
  const qs = buildProductsQuery(params);
  // 库存/价格时效敏感：RSC 每请求回源（AGENTS.md Data Freshness）
  return apiFetch<ProductsResponse>(`/api/products${qs ? `?${qs}` : ""}`, { cache: "no-store" });
}

export function listMerchants(): Promise<MerchantSummary[]> {
  return apiFetch<MerchantSummary[]>("/api/products/merchants", { cache: "no-store" });
}

// ── P2：IP 检测域（B11/B12） ────────────────────────────────────

export interface IpRiskFactor {
  title: string;
  impact: string;
  desc: string;
}

export interface IpSecurityCheck {
  name: string;
  status: string;
  pass: boolean;
}

export interface IpSourceComparison {
  source: string;
  isp: string;
  as: string;
  type: string;
  country: string;
  status: string;
}

export interface IpUnlockPrediction {
  name: string;
  category: string;
  status: string;
  level: "pass" | "warn";
  note: string;
}

/** GET /api/ip/check 响应（字段与 FastAPI 返回同形） */
export interface IpCheckResult {
  ip: string;
  query_target: string;
  country: string;
  country_code: string;
  continent: string;
  rir: string;
  domain: string;
  flag: string;
  region: string;
  city: string;
  zip: string;
  lat: number | null;
  lon: number | null;
  timezone: string;
  isp: string;
  org: string;
  as_raw: string;
  as_name: string;
  reverse_dns: string;
  vendor_brand: string | null;
  ip_type: string;
  ip_type_tag: string;
  is_dual_isp: boolean;
  is_datacenter: boolean;
  is_proxy: boolean;
  is_mobile: boolean;
  is_tor: boolean;
  clean_score: number;
  fraud_score: number;
  risk_level: string;
  risk_color: string;
  scamalytics_rating: string;
  risk_factors: IpRiskFactor[];
  security_checks: IpSecurityCheck[];
  source_comparison: IpSourceComparison[];
  unlock_predictions: IpUnlockPrediction[];
}

/**
 * 留空 ip 时由后端自行判断客户端出口。注意：经 Next.js rewrite 转发后，
 * 后端看到的会是前端服务的出口 IP 而非访客 IP，因此调用方（/ip 页面）
 * 会先在服务端读出真实 IP 再显式传入，不要依赖留空让后端猜。
 */
export function checkIp(ip?: string): Promise<IpCheckResult> {
  const qs = ip && ip.trim() ? `?ip=${encodeURIComponent(ip.trim())}` : "";
  return apiFetch<IpCheckResult>(`/api/ip/check${qs}`, { cache: "no-store" });
}

// ── P3：事件流（B6/B7） ────────────────────────────────────────

/** GET /api/events/summary 首页动态摘要条 */
export interface EventsSummary {
  hours: number;
  restock_count: number;
  drop_count: number;
}

/**
 * 24 小时事件计数，用于首页与列表页的「实时动态」聚合条。
 * 计数天然滞后（事件按去重窗口累积），无需实时：走 RSC 数据缓存 5 分钟，
 * 避免每次列表请求都额外打一次后端（AGENTS.md：无需实时的数据应使用缓存）。
 */
export function getEventsSummary(hours = 24): Promise<EventsSummary> {
  return apiFetch<EventsSummary>(`/api/events/summary?hours=${hours}`, {
    next: { revalidate: 300 },
  });
}

export interface EventItem {
  id: number;
  type: "PRICE_DROP" | "RESTOCK";
  old_value: string | null;
  new_value: string | null;
  /** 仅降价事件有值（百分比，1 位小数） */
  drop_percent: number | null;
  created_at: string;
  product: {
    id: number;
    name: string;
    merchant: { slug: string; name: string };
    price: number;
    currency: string;
    billing_cycle: string;
    in_stock: boolean;
    location: string | null;
    line_tags: string[];
  };
}

export interface EventsResponse {
  items: EventItem[];
  hours: number;
  type: "PRICE_DROP" | "RESTOCK";
}

export function getEvents(
  type: "PRICE_DROP" | "RESTOCK",
  hours = 24,
  limit = 50,
): Promise<EventsResponse> {
  const qs = new URLSearchParams({ type, hours: String(hours), limit: String(limit) });
  return apiFetch<EventsResponse>(`/api/events?${qs.toString()}`, { cache: "no-store" });
}

// ── P4：关注域（B8） ───────────────────────────────────────────

export interface WatchPrefs {
  notify_restock: boolean;
  notify_price_drop: boolean;
  min_drop_percent: number;
}

export interface WatchlistItem extends WatchPrefs {
  id: number;
  product: ProductListItem;
  created_at: string;
}

export interface WatchStatus extends WatchPrefs {
  watching: boolean;
}

export function getWatchlist(): Promise<WatchlistItem[]> {
  return apiFetch<WatchlistItem[]>("/api/watchlist", { cache: "no-store" });
}

export function getWatchStatus(productId: number): Promise<WatchStatus> {
  return apiFetch<WatchStatus>(`/api/watchlist/${productId}`, { cache: "no-store" });
}

/** 关注/更新通知偏好（后端幂等：已存在则更新偏好） */
export function watchProduct(productId: number, prefs: WatchPrefs): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/watchlist/${productId}`, {
    method: "PUT",
    body: prefs,
  });
}

/** 取消关注（幂等：未关注也返回成功） */
export function unwatchProduct(productId: number): Promise<{ ok: boolean; watching: boolean }> {
  return apiFetch<{ ok: boolean; watching: boolean }>(`/api/watchlist/${productId}`, {
    method: "DELETE",
  });
}

export interface DnsLeakResults {
  configured: boolean;
  resolvers: { resolver: string; country?: string }[];
  token: string;
}

export function getDnsLeakResults(token: string): Promise<DnsLeakResults> {
  return apiFetch<DnsLeakResults>(
    `/api/ip/dns-leak/results?token=${encodeURIComponent(token)}`,
    { cache: "no-store" },
  );
}
