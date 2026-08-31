"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { listProducts, type ProductsResponse } from "@/lib/api/endpoints";
import {
  parseListQuery,
  queryToString,
  type ListQueryState,
  toProductParams,
} from "@/lib/query-state";

/**
 * 列表数据 store（SWR 语义）：筛选变更不再触发 RSC 全页导航，而是
 *
 * 1. 缓存命中 → 立即渲染上次同参数的服务端结果，后台静默刷新，到货后替换；
 * 2. 缓存未命中 → 保留旧列表 + 加载态，请求完成替换；
 * 3. URL 用原生 history API 同步（可分享/可前进后退），不触发 RSC 请求；
 * 4. 数据口径永远以服务端为准——缓存存的是服务端同参数历史结果，
 *    客户端不复刻后端过滤逻辑（折年价/线路匹配/评分排序）。
 *
 * 缓存与 in-flight 表放模块级：RSC 导航（如点站内 Link 回 /vps）重建
 * Provider 时缓存仍有效，会话内跨页面往返同样瞬时。仅内存、不持久化
 * （库存时效敏感，AGENTS.md Data Freshness）。
 */

/** 缓存条目上限：会话内筛选组合有限，30 组足够；超限淘汰最早写入的 */
const CACHE_MAX = 30;

const cache = new Map<string, ProductsResponse>();
const inflight = new Map<string, Promise<ProductsResponse>>();

/** 数据缓存键：view 只影响呈现形态不影响取数，排除在 key 之外 */
function dataKey(state: ListQueryState): string {
  return queryToString({ ...state, view: undefined });
}

interface StoreState {
  state: ListQueryState;
  data: ProductsResponse | null;
  /** 无缓存可用的加载态（保留旧列表渲染，叠加视觉反馈） */
  loading: boolean;
  /** 缓存已显示、后台刷新中 */
  revalidating: boolean;
  error: string | null;
}

interface ListDataStore extends StoreState {
  /** 筛选变更（默认重置回第 1 页；翻页传 { resetPage: false }） */
  apply: (patch: Partial<ListQueryState>, opts?: { resetPage?: boolean }) => void;
  /** 清空全部筛选，回到默认列表 */
  reset: () => void;
  /** 重试当前筛选（首屏错误/请求失败后） */
  refresh: () => void;
}

const ListDataContext = createContext<ListDataStore | null>(null);

const EMPTY_STATE = (): ListQueryState => parseListQuery(new URLSearchParams());

function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "列表加载失败";
}

export function ListDataProvider({
  initialState,
  initialData,
  initialError = null,
  children,
}: {
  initialState: ListQueryState;
  /** RSC 首屏取数结果（null 表示首屏失败，走 initialError） */
  initialData: ProductsResponse | null;
  initialError?: string | null;
  children: React.ReactNode;
}) {
  const [store, setStore] = useState<StoreState>(() => {
    if (initialData) {
      // 首屏结果即第一个缓存条目：会话内回到同参数筛选时瞬时呈现
      cache.set(dataKey(initialState), initialData);
    }
    return {
      state: initialState,
      data: initialData,
      loading: false,
      revalidating: false,
      error: initialError,
    };
  });

  /**
   * 事件处理器（apply/commit 等）需要读到「最新」状态来计算 next。
   * 通过 ref 同步（每轮渲染更新），避免在 setStore 函数式 updater 里嵌套
   * 副作用——React StrictMode 下 updater 会被调用两次，副作用会翻倍。
   */
  const storeRef = useRef(store);
  storeRef.current = store;

  /** 竞态防护：仅采纳最后一次请求的结果（快速连续筛选时旧响应作废） */
  const seqRef = useRef(0);

  const runFetch = useCallback(
    async (key: string, target: ListQueryState) => {
      const seq = ++seqRef.current;
      let p = inflight.get(key);
      if (!p) {
        p = listProducts(toProductParams(target)).finally(() => inflight.delete(key));
        inflight.set(key, p);
      }
      try {
        const fresh = await p;
        cache.set(key, fresh);
        // LRU 近似：超限淘汰最早写入（Map 迭代序即插入序）
        if (cache.size > CACHE_MAX) {
          const oldest = cache.keys().next().value;
          if (oldest !== undefined) cache.delete(oldest);
        }
        if (seqRef.current !== seq) return;
        setStore((s) => ({ ...s, data: fresh, loading: false, revalidating: false, error: null }));
      } catch (e) {
        if (seqRef.current !== seq) return;
        // 失败保留当前已显示数据（不清空列表），仅提示错误
        setStore((s) => ({
          ...s,
          loading: false,
          revalidating: false,
          error: errorMessage(e),
        }));
      }
    },
    [],
  );

  const pushUrl = useCallback((next: ListQueryState, mode: "push" | "replace") => {
    const qs = queryToString(next);
    const url = qs ? `/vps?${qs}` : "/vps";
    window.history[mode === "push" ? "pushState" : "replaceState"](null, "", url);
  }, []);

  /**
   * 应用新筛选状态并同步 URL。仅 view（呈现形态）变化时不发请求；
   * 数据参数变化走缓存优先链路：命中 → 渲染缓存 + 后台刷新；未命中 → 加载态。
   */
  const commit = useCallback(
    (next: ListQueryState, urlMode: "push" | "replace") => {
      const prev = storeRef.current;
      const sameData = dataKey(prev.state) === dataKey(next);
      if (sameData) {
        // 仅 view 变化：数据与请求均不动
        pushUrl(next, urlMode);
        setStore((s) => ({ ...s, state: next, error: s.data ? null : s.error }));
        return;
      }
      const key = dataKey(next);
      const cached = cache.get(key);
      pushUrl(next, urlMode);
      if (cached) {
        // SWR：先渲染缓存结果，后台刷新最新
        setStore({
          state: next,
          data: cached,
          loading: false,
          revalidating: true,
          error: null,
        });
        void runFetch(key, next);
      } else {
        // 未命中：保留旧列表 + 加载态
        setStore({
          state: next,
          data: prev.data,
          loading: true,
          revalidating: false,
          error: null,
        });
        void runFetch(key, next);
      }
    },
    [pushUrl, runFetch],
  );

  const apply = useCallback(
    (patch: Partial<ListQueryState>, opts?: { resetPage?: boolean }) => {
      const prev = storeRef.current;
      const next: ListQueryState = {
        ...prev.state,
        ...patch,
        ...(opts?.resetPage === false ? {} : { page: 1 }),
      };
      // 翻页与旧版 RSC 导航行为对齐：回到列表顶部
      if (next.page !== prev.state.page) window.scrollTo({ top: 0 });
      commit(next, "push");
    },
    [commit],
  );

  const reset = useCallback(() => {
    commit(EMPTY_STATE(), "push");
  }, [commit]);

  const refresh = useCallback(() => {
    const prev = storeRef.current;
    void runFetch(dataKey(prev.state), prev.state);
    setStore((s) => ({
      ...s,
      loading: s.data === null,
      revalidating: s.data !== null,
    }));
  }, [runFetch]);

  /** 浏览器前进/后退：解析目标 URL 状态后走同一缓存链路（URL 已由浏览器更新） */
  useEffect(() => {
    const onPop = () => {
      const next = parseListQuery(new URLSearchParams(window.location.search));
      commit(next, "replace");
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [commit]);

  const value = useMemo<ListDataStore>(
    () => ({ ...store, apply, reset, refresh }),
    [store, apply, reset, refresh],
  );

  return <ListDataContext.Provider value={value}>{children}</ListDataContext.Provider>;
}

export function useListData(): ListDataStore {
  const ctx = useContext(ListDataContext);
  if (!ctx) throw new Error("useListData 必须在 ListDataProvider 内使用");
  return ctx;
}
