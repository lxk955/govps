/**
 * /vps 列表页 URL 状态 ↔ 查询参数的唯一转换层。
 * 筛选状态全部落在 URL searchParams 上（可分享/可回退/SSR 可渲染）；
 * 本模块同时被 RSC（解析）与 Client 组件（增删改）引用，保持单一口径。
 */

/**
 * 支持的排序值（URL 上的 ?sort=）。列表页目前没有排序 UI（与旧站一致），
 * 仅通过 URL 参数生效，因此这里只保留合法值的单一定义用于解析与类型约束，
 * 不再维护从未被渲染的 label。
 */
export type SortValue = "hot" | "deal" | "popularity" | "price_asc" | "price_desc" | "updated";

/** 线路筛选分类（与后端 LINE_FILTERS 的 key 对齐） */
export const LINE_OPTIONS = [
  { value: "cn2_gia", label: "CN2 GIA" },
  { value: "9929", label: "联通 9929" },
  { value: "cmin2", label: "移动 CMIN2" },
  { value: "4837", label: "联通 4837" },
  { value: "cn2_gt", label: "CN2 GT" },
  { value: "bgp", label: "普通 BGP" },
  { value: "international", label: "国际线路" },
] as const;

export interface ListQueryState {
  merchant: string[];
  location: string[];
  line: string[];
  keyword: string;
  sort: SortValue;
  page: number;
  size: number;
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
  /** 视图形态（旧站 view_mode 复刻）。未设置时列表页按视口自行决定。 */
  view?: "card" | "list";
}

const MULTI_KEYS = ["merchant", "location", "line"] as const;
const BOOL_KEYS = [
  "in_stock",
  "price_drop",
  "lowest_price",
  "recent_restock",
  "recommended",
] as const;
const NUM_KEYS = [
  "min_price",
  "max_price",
  "min_ram",
  "min_cpu",
  "min_bw",
  "min_port",
] as const;

export function parseListQuery(sp: URLSearchParams | Record<string, string | string[] | undefined>): ListQueryState {
  const get = (key: string): string | undefined => {
    if (sp instanceof URLSearchParams) return sp.get(key) ?? undefined;
    const v = sp[key];
    return Array.isArray(v) ? v[0] : v;
  };
  const getAll = (key: string): string[] => {
    if (sp instanceof URLSearchParams) return sp.getAll(key);
    const v = sp[key];
    return Array.isArray(v) ? v : v ? [v] : [];
  };

  const state: ListQueryState = {
    merchant: getAll("merchant"),
    location: getAll("location"),
    line: getAll("line"),
    keyword: get("keyword") ?? "",
    sort: (get("sort") as SortValue) || "hot",
    page: Math.max(1, Number(get("page")) || 1),
    size: Math.min(100, Math.max(1, Number(get("size")) || 30)),
  };
  for (const k of NUM_KEYS) {
    const raw = get(k);
    if (raw !== undefined && raw !== "" && !Number.isNaN(Number(raw))) {
      state[k] = Number(raw);
    }
  }
  for (const k of BOOL_KEYS) {
    const raw = get(k);
    if (raw === "true" || raw === "1") state[k] = true;
  }
  const view = get("view");
  if (view === "card" || view === "list") state.view = view;
  return state;
}

export function queryToString(state: ListQueryState): string {
  const qs = new URLSearchParams();
  for (const k of MULTI_KEYS) for (const v of state[k]) qs.append(k, v);
  if (state.keyword.trim()) qs.set("keyword", state.keyword.trim());
  for (const k of NUM_KEYS) {
    const v = state[k];
    if (v !== undefined) qs.set(k, String(v));
  }
  for (const k of BOOL_KEYS) if (state[k]) qs.set(k, "true");
  if (state.view) qs.set("view", state.view);
  if (state.sort && state.sort !== "hot") qs.set("sort", state.sort);
  if (state.page > 1) qs.set("page", String(state.page));
  if (state.size !== 30) qs.set("size", String(state.size));
  return qs.toString();
}

/** 更新单个字段后的完整查询串（翻页等操作重置回第一页由调用方决定） */
export function withParams(
  current: ListQueryState,
  patch: Partial<ListQueryState>,
  opts: { resetPage?: boolean } = {},
): string {
  return queryToString({ ...current, ...patch, ...(opts.resetPage === false ? {} : { page: 1 }) });
}
