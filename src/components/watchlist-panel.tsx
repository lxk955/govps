"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { LayoutGrid, List, Loader2, RotateCcw, Star, X } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { VpsCard } from "@/components/vps/VpsCard";
import { VpsRow } from "@/components/vps/VpsRow";
import { cn } from "@/lib/utils";
import {
  getWatchlist,
  watchProduct,
  type WatchlistItem,
  type WatchPrefs,
} from "@/lib/api/endpoints";

/** 关注页视图偏好的本地存储键 */
const VIEW_KEY = "govps_watchlist_view";

/** 关注管理面板：通知开关、降幅阈值、取关 + 撤销（方案 P4 交付物「取关撤销」）。 */

export function WatchlistPanel() {
  const { user } = useAuth();
  const [items, setItems] = useState<WatchlistItem[] | null>(null);
  const [error, setError] = useState(false);
  /**
   * 卡片偏好行改过开关后，父级 items 不会自动刷新（避免每次切换都重拉列表）。
   * 这里记下被改动的偏好，供右上角心形取关时带上——撤销要还原的是用户最后一
   * 次设置的值，而不是列表加载时的旧值。
   */
  const [prefsOverride, setPrefsOverride] = useState<Record<number, WatchPrefs>>({});

  const handlePrefsChange = useCallback((productId: number, prefs: WatchPrefs) => {
    setPrefsOverride((prev) => ({ ...prev, [productId]: prefs }));
  }, []);

  /*
   * 视图偏好存 localStorage：关注页是客户端取数，没有 URL 状态可依托，
   * 因此不像产品页那样用 ?view= 参数（后者为 RSC 服务端取数，参数可分享）。
   * 读取放在 effect 以保证 SSR 首屏与水合一致，写失败（隐私模式）静默忽略。
   */
  const [view, setView] = useState<"card" | "list">("card");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(VIEW_KEY);
      if (saved === "list" || saved === "card") setView(saved);
    } catch {
      /* 隐私模式：保持默认卡片视图 */
    }
  }, []);

  const changeView = (v: "card" | "list") => {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* 忽略写入失败 */
    }
  };

  const load = useCallback(async () => {
    try {
      setItems(await getWatchlist());
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    if (user) void load();
    else setItems(null);
  }, [user, load]);

  if (user === undefined || (user && items === null && !error)) {
    return (
      /* 骨架屏：与卡片网格同构，减少加载时的视觉跳动 */
      <div className="grid grid-cols-[repeat(auto-fill,minmax(min(300px,100%),1fr))] gap-4" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="bg-muted h-72 animate-pulse rounded-2xl" />
        ))}
      </div>
    );
  }

  if (user === null) {
    return (
      <div className="border-border rounded-xl border border-dashed p-12 text-center">
        <Star aria-hidden className="text-muted-foreground mx-auto h-8 w-8" />
        <p className="text-muted-foreground mt-3 text-sm">
          登录后即可关注套餐，降价与补货第一时间收到邮件。
        </p>
        <Button asChild size="sm" className="mt-3">
          <Link href="/login?next=%2Fwatchlist">登录 / 注册</Link>
        </Button>
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="flex flex-col items-center gap-3 rounded-xl border border-red-100 bg-red-50 p-12 text-center dark:border-red-900 dark:bg-red-950/30"
      >
        <div className="text-3xl">📡</div>
        <p className="text-sm font-medium text-red-600 dark:text-red-400">加载失败，请稍后重试。</p>
        <Button
          size="sm"
          onClick={() => void load()}
          className="rounded-xl bg-red-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-red-700"
        >
          重新加载
        </Button>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="border-border rounded-xl border border-dashed p-12 text-center">
        <p className="text-muted-foreground text-sm">还没有关注任何套餐</p>
        <Button
          asChild
          size="sm"
          className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Link href="/">去逛逛</Link>
        </Button>
      </div>
    );
  }

  /** 条目当前的通知偏好：优先取被改动过的覆盖值（撤销时按最后设置还原） */
  const prefsOf = (w: WatchlistItem): WatchPrefs =>
    prefsOverride[w.product.id] ?? {
      notify_restock: w.notify_restock,
      notify_price_drop: w.notify_price_drop,
      min_drop_percent: w.min_drop_percent,
    };

  return (
    <>
      {/* 视图切换：md 以上显示，与产品页口径一致（窄屏行信息密度低，不如卡片） */}
      <div className="mb-3 hidden justify-end md:flex">
        <div
          role="group"
          aria-label="视图模式"
          className="border-border flex items-center gap-0.5 rounded-xl border bg-slate-50/70 p-0.5 dark:bg-slate-800/60"
        >
          {(
            [
              ["card", "卡片视图", LayoutGrid],
              ["list", "列表视图", List],
            ] as const
          ).map(([v, label, Icon]) => (
            <button
              key={v}
              type="button"
              onClick={() => changeView(v)}
              aria-pressed={view === v}
              aria-label={label}
              title={label}
              className={cn(
                "cursor-pointer rounded-lg px-2 py-1 transition-colors",
                view === v
                  ? "bg-card text-blue-600 shadow-sm dark:text-blue-400"
                  : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
              )}
            >
              <Icon aria-hidden className="h-4 w-4" />
            </button>
          ))}
        </div>
      </div>

      <div
        className={
          view === "card"
            ? "grid grid-cols-[repeat(auto-fill,minmax(min(300px,100%),1fr))] gap-4"
            : "flex flex-col gap-3"
        }
      >
        {items.map((w) => (
          <div key={w.id} className="flex min-w-0 flex-col gap-1">
            {view === "card" ? (
              <VpsCard
                product={w.product}
                watchHydrate
                unwatchPrefs={prefsOf(w)}
                onUnwatched={load}
              />
            ) : (
              <VpsRow
                product={w.product}
                watchHydrate
                unwatchPrefs={prefsOf(w)}
                onUnwatched={load}
              />
            )}
            <WatchPrefsBar item={w} onPrefsChange={handlePrefsChange} />
          </div>
        ))}
      </div>
      <UndoZone onUndoDone={load} />
    </>
  );
}

/** 取关撤销：最近一次取关在窗口期内可一键恢复（含原通知偏好）。 */
function UndoZone({ onUndoDone }: { onUndoDone: () => Promise<void> }) {
  const [undo, setUndo] = useState<{
    productId: number;
    prefs: WatchPrefs;
    timer: ReturnType<typeof setTimeout>;
  } | null>(null);

  // WatchRow 取关时经 window 事件把「产品+原偏好」递给撤销区
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ productId: number; prefs: WatchPrefs }>).detail;
      setUndo((prev) => {
        if (prev) clearTimeout(prev.timer);
        const timer = setTimeout(() => setUndo(null), 6000);
        return { ...detail, timer };
      });
    };
    window.addEventListener("govps:unwatch", handler);
    return () => window.removeEventListener("govps:unwatch", handler);
  }, []);

  const undoWatch = async () => {
    if (!undo) return;
    clearTimeout(undo.timer);
    await watchProduct(undo.productId, undo.prefs).catch(() => {});
    setUndo(null);
    await onUndoDone();
  };

  if (!undo) return null;
  return (
    <div
      role="status"
      className="bg-card fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-md items-center justify-between gap-3 rounded-xl border p-3 shadow-lg sm:left-auto sm:right-6"
    >
      <p className="min-w-0 truncate text-sm">已取消关注</p>
      <div className="flex shrink-0 items-center gap-1">
        <Button size="sm" onClick={() => void undoWatch()}>
          <RotateCcw aria-hidden className="h-3.5 w-3.5" />
          撤销
        </Button>
        <Button
          size="icon"
          variant="ghost"
          aria-label="关闭提示"
          className="h-8 w-8"
          onClick={() => {
            clearTimeout(undo.timer);
            setUndo(null);
          }}
        >
          <X aria-hidden className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

/** 卡片下方的通知偏好行（1:1 复刻旧站卡下开关；降幅阈值为新站增补）。 */
function WatchPrefsBar({
  item,
  onPrefsChange,
}: {
  item: WatchlistItem;
  /** 偏好保存后回传最新值，供父级记录（心形取关撤销时按此还原） */
  onPrefsChange: (productId: number, prefs: WatchPrefs) => void;
}) {
  const p = item.product;
  const [prefs, setPrefs] = useState({
    notify_restock: item.notify_restock,
    notify_price_drop: item.notify_price_drop,
    min_drop_percent: item.min_drop_percent,
  });
  const [saving, setSaving] = useState(false);

  const save = useCallback(
    async (next: typeof prefs) => {
      setSaving(true);
      try {
        await watchProduct(p.id, next);
        onPrefsChange(p.id, next);
      } finally {
        setSaving(false);
      }
    },
    [p.id, onPrefsChange],
  );

  const togglePref = (key: "notify_restock" | "notify_price_drop") => {
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    void save(next);
  };

  return (
    <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-1.5 px-1 text-xs text-slate-500 dark:text-slate-400">
      <label
        className="flex cursor-pointer items-center gap-1.5"
        title={p.in_stock ? "有货时不会发信；售罄后再补货会通知" : "缺货补货时邮件提醒"}
      >
        <input
          type="checkbox"
          className="accent-primary h-3.5 w-3.5"
          checked={prefs.notify_restock}
          onChange={() => togglePref("notify_restock")}
        />
        <span>到货通知</span>
      </label>
      <label className="flex cursor-pointer items-center gap-1.5">
        <input
          type="checkbox"
          className="accent-primary h-3.5 w-3.5"
          checked={prefs.notify_price_drop}
          onChange={() => togglePref("notify_price_drop")}
        />
        <span>降价通知</span>
      </label>
      {prefs.notify_price_drop && (
        <label className="flex items-center gap-1.5">
          <span className="whitespace-nowrap">降幅 ≥</span>
          <Input
            type="number"
            min={0}
            max={100}
            defaultValue={prefs.min_drop_percent}
            aria-label="最低降幅百分比"
            onBlur={(e) => {
              const v = Math.max(0, Math.min(100, Number(e.target.value) || 0));
              e.target.value = String(v);
              const next = { ...prefs, min_drop_percent: v };
              setPrefs(next);
              void save(next);
            }}
            className="h-6 w-14 px-1.5 text-center text-base sm:text-xs"
          />
          <span>%</span>
        </label>
      )}
      {saving && <Loader2 aria-hidden className="h-3 w-3 animate-spin" />}
    </div>
  );
}
