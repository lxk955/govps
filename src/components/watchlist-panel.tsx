"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Loader2, RotateCcw, Star, X } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getWatchlist,
  unwatchProduct,
  watchProduct,
  type WatchlistItem,
  type WatchPrefs,
} from "@/lib/api/endpoints";
import { currencySymbol, formatCycle, timeAgo } from "@/lib/format";
import { productHref } from "@/lib/slug";

/** 关注管理面板：通知开关、降幅阈值、取关 + 撤销（方案 P4 交付物「取关撤销」）。 */

export function WatchlistPanel() {
  const { user } = useAuth();
  const [items, setItems] = useState<WatchlistItem[] | null>(null);
  const [error, setError] = useState(false);

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
      <div className="bg-card text-muted-foreground flex items-center justify-center gap-2 rounded-xl border p-10 text-sm" role="status">
        <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
        加载中…
      </div>
    );
  }

  if (user === null) {
    return (
      <div className="bg-card flex flex-col items-center gap-3 rounded-xl border p-10 text-center">
        <Star aria-hidden className="text-muted-foreground h-8 w-8" />
        <p className="text-sm">登录后即可关注套餐，降价与补货第一时间收到邮件。</p>
        <Button asChild size="sm">
          <Link href="/login?next=%2Fwatchlist">登录 / 注册</Link>
        </Button>
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="border-destructive/30 bg-destructive/5 text-destructive flex flex-col items-center gap-3 rounded-xl border p-10 text-center text-sm">
        加载失败，请稍后重试。
        <Button variant="outline" size="sm" onClick={() => void load()}>
          重试
        </Button>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed p-12 text-center">
        <Star aria-hidden className="text-muted-foreground h-8 w-8" />
        <p className="text-muted-foreground text-sm">还没有关注的套餐。</p>
        <Button asChild variant="outline" size="sm">
          <Link href="/vps">去列表挑一个</Link>
        </Button>
      </div>
    );
  }

  return (
    <>
      <ul className="flex flex-col gap-3">
        {items.map((w) => (
          <WatchRow key={w.id} item={w} onChanged={load} />
        ))}
      </ul>
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

/** 单个关注行：产品信息 + 通知开关 + 降幅阈值 + 取关。 */
function WatchRow({
  item,
  onChanged,
}: {
  item: WatchlistItem;
  onChanged: () => Promise<void>;
}) {
  const p = item.product;
  const [prefs, setPrefs] = useState({
    notify_restock: item.notify_restock,
    notify_price_drop: item.notify_price_drop,
    min_drop_percent: item.min_drop_percent,
  });
  const savedRef = useRef(prefs);
  const [saving, setSaving] = useState(false);

  const save = useCallback(
    async (next: typeof prefs) => {
      setSaving(true);
      try {
        await watchProduct(p.id, next);
        savedRef.current = next;
      } finally {
        setSaving(false);
      }
    },
    [p.id],
  );

  const togglePref = (key: "notify_restock" | "notify_price_drop") => {
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    void save(next);
  };

  const unwatch = async () => {
    const removedPrefs = { ...savedRef.current };
    await unwatchProduct(p.id).catch(() => {});
    window.dispatchEvent(
      new CustomEvent("govps:unwatch", { detail: { productId: p.id, prefs: removedPrefs } }),
    );
    await onChanged();
  };

  return (
    <li className="bg-card rounded-xl border p-4">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={productHref(p.id, p.name)} className="block truncate font-medium hover:text-sky-700 hover:underline dark:hover:text-sky-400">
            {p.name}
          </Link>
          <p className="text-muted-foreground mt-0.5 truncate text-xs">
            {p.merchant.name} · {p.location || "—"} · 关注于 {timeAgo(item.created_at)}
          </p>
          <p className="mt-1 text-sm font-bold tabular-nums">
            {currencySymbol(p.currency)}
            {p.price.toFixed(2)}
            <span className="text-muted-foreground text-xs font-normal">{formatCycle(p.billing_cycle)}</span>
            {!p.in_stock && (
              <Badge variant="secondary" className="ml-2 text-muted-foreground">
                缺货
              </Badge>
            )}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void unwatch()} disabled={saving}>
          取消关注
        </Button>
      </div>

      {/* 通知偏好 */}
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t pt-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="accent-primary h-4 w-4"
            checked={prefs.notify_restock}
            onChange={() => togglePref("notify_restock")}
          />
          补货通知
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="accent-primary h-4 w-4"
            checked={prefs.notify_price_drop}
            onChange={() => togglePref("notify_price_drop")}
          />
          降价通知
        </label>
        {prefs.notify_price_drop && (
          <label className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground whitespace-nowrap">降幅 ≥</span>
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
              className="h-7 w-16 px-2 text-center text-base md:text-sm"
            />
            <span className="text-muted-foreground">%</span>
            {saving && <Loader2 aria-hidden className="h-3 w-3 animate-spin" />}
          </label>
        )}
      </div>
    </li>
  );
}
