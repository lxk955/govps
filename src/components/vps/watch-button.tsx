"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Heart } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  getWatchStatus,
  unwatchProduct,
  watchProduct,
  type WatchPrefs,
} from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

/**
 * 关注按钮（P4）。
 * - 未登录：跳转 /login?next=当前路径，登录后回到原位
 * - 已登录：点击即关注（默认通知偏好），再次点击取关
 * - hydrate=true 时挂载后拉取真实关注状态（详情页用；列表网格不逐个查询）
 *
 * 图标用 ❤️ 心形而非书签：旧站「我的关注」即心形（见 ListToolbar 关于
 * 「❤️ 我的关注」胶囊的说明），此前误用 lucide Bookmark，语义与旧站不一致。
 * 未关注为灰色描边，已关注为红色实心（fill-current 填充同一 currentColor）。
 */

export function WatchButton({
  productId,
  hydrate = false,
  size = "sm",
  unwatchPrefs,
  onUnwatched,
}: {
  productId: number;
  /** 挂载后查询真实状态（详情页） */
  hydrate?: boolean;
  size?: "sm" | "icon" | "xs";
  /**
   * 取关时随 govps:unwatch 事件带上的「原通知偏好」，用于撤销时还原。
   * 仅关注页传入——该页撤销区依赖此事件弹出撤销条。
   */
  unwatchPrefs?: WatchPrefs;
  /** 取关成功后的回调（关注页用于重新拉取列表） */
  onUnwatched?: () => void;
}) {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [watching, setWatching] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!hydrate || user === null) return;
    if (user === undefined) return;
    let cancelled = false;
    void getWatchStatus(productId)
      .then((s) => {
        if (!cancelled) setWatching(s.watching);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [hydrate, productId, user]);

  const toggle = useCallback(async () => {
    if (user === undefined) return; // 挂载检查未完成
    if (user === null) {
      router.push(`/login?next=${encodeURIComponent(pathname || "/")}`);
      return;
    }
    setBusy(true);
    try {
      if (watching) {
        await unwatchProduct(productId);
        setWatching(false);
        // 取关后把原偏好交给撤销区，误点可在 6s 内连通知偏好一起还原
        if (unwatchPrefs) {
          window.dispatchEvent(
            new CustomEvent("govps:unwatch", {
              detail: { productId, prefs: unwatchPrefs },
            }),
          );
        }
        onUnwatched?.();
      } else {
        await watchProduct(productId, {
          notify_restock: true,
          notify_price_drop: true,
          min_drop_percent: 0,
        });
        setWatching(true);
      }
    } catch {
      /* 失败保持原状态；401 已由统一处理登出 */
    } finally {
      setBusy(false);
    }
  }, [user, watching, productId, router, pathname, unwatchPrefs, onUnwatched]);

  // xs：卡片头部 24px 专属槽内的紧凑形态（1:1 复刻旧站卡片头部关注按钮）
  if (size === "xs") {
    return (
      <Button
        variant="ghost"
        size="icon"
        aria-label={watching ? "取消关注该套餐" : "关注该套餐"}
        title={watching ? "取消关注" : "关注"}
        aria-pressed={watching}
        disabled={busy || user === undefined}
        onClick={() => void toggle()}
        className={cn("h-6 w-6 shrink-0", watching && "text-rose-500 dark:text-rose-400")}
      >
        <Heart
          aria-hidden
          className={cn("h-3.5 w-3.5", watching ? "fill-current" : "text-slate-400")}
        />
      </Button>
    );
  }

  if (size === "icon") {
    return (
      <Button
        variant="outline"
        size="icon"
        aria-label={watching ? "取消关注该套餐" : "关注该套餐"}
        title={watching ? "取消关注" : "关注"}
        aria-pressed={watching}
        disabled={busy || user === undefined}
        onClick={() => void toggle()}
        className={cn("h-9 w-9 shrink-0", watching && "text-rose-500 dark:text-rose-400")}
      >
        <Heart className={cn("h-4 w-4", watching && "fill-current")} />
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      aria-pressed={watching}
      disabled={busy || user === undefined}
      onClick={() => void toggle()}
      className={cn("shrink-0 gap-1.5", watching && "text-rose-500 dark:text-rose-400")}
    >
      <Heart className={cn("h-3.5 w-3.5", watching && "fill-current")} />
      {watching ? "已关注" : "关注"}
    </Button>
  );
}
