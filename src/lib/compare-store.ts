"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * 对比清单存储（P6）：localStorage 为工作集（跨页面持久），
 * /compare 页将其镜像到 URL ?ids=（可分享）；上限 4 款（方案锁定，不做扩展）。
 */

const KEY = "govps_compare_ids";
export const COMPARE_MAX = 4;
const EVENT = "govps:compare";

function read(): number[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(Number)
      .filter((n) => Number.isSafeInteger(n) && n > 0)
      .slice(0, COMPARE_MAX);
  } catch {
    return [];
  }
}

function write(ids: number[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    /* storage 不可用时仅内存态 */
  }
  window.dispatchEvent(new Event(EVENT));
}

/** 读取当前对比集（一次性）。 */
export function getCompareIds(): number[] {
  if (typeof window === "undefined") return [];
  return read();
}

/** 覆盖写入（/compare 页从 URL 恢复时用）。 */
export function setCompareIds(ids: number[]): void {
  if (typeof window === "undefined") return;
  write([...new Set(ids)].slice(0, COMPARE_MAX));
}

/** 订阅对比集变化的 hook；初始值在挂载后读取（避免水合不一致）。 */
export function useCompareIds(): {
  ids: number[];
  /** true=已挂载并完成首次读取 */
  ready: boolean;
  toggle: (id: number) => { added: boolean; full: boolean };
  remove: (id: number) => void;
  clear: () => void;
  replace: (ids: number[]) => void;
} {
  const [ids, setIds] = useState<number[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setIds(read());
    setReady(true);
    const sync = () => setIds(read());
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const toggle = useCallback((id: number): { added: boolean; full: boolean } => {
    const cur = read();
    if (cur.includes(id)) {
      write(cur.filter((x) => x !== id));
      return { added: false, full: false };
    }
    if (cur.length >= COMPARE_MAX) return { added: false, full: true };
    write([...cur, id]);
    return { added: true, full: false };
  }, []);

  const remove = useCallback((id: number) => {
    write(read().filter((x) => x !== id));
  }, []);

  const clear = useCallback(() => write([]), []);
  const replace = useCallback((next: number[]) => setCompareIds(next), []);

  return { ids, ready, toggle, remove, clear, replace };
}
