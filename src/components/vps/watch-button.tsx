"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Bookmark, BookmarkCheck } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  getWatchStatus,
  unwatchProduct,
  watchProduct,
} from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

/**
 * 关注按钮（P4）。
 * - 未登录：跳转 /login?next=当前路径，登录后回到原位
 * - 已登录：点击即关注（默认通知偏好），再次点击取关
 * - hydrate=true 时挂载后拉取真实关注状态（详情页用；列表网格不逐个查询）
 */

export function WatchButton({
  productId,
  hydrate = false,
  size = "sm",
}: {
  productId: number;
  /** 挂载后查询真实状态（详情页） */
  hydrate?: boolean;
  size?: "sm" | "icon" | "xs";
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
  }, [user, watching, productId, router, pathname]);

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
        className={cn("h-6 w-6 shrink-0", watching && "text-blue-600 dark:text-blue-400")}
      >
        {watching ? (
          <BookmarkCheck aria-hidden className="h-3.5 w-3.5" />
        ) : (
          <Bookmark aria-hidden className="text-slate-400 h-3.5 w-3.5" />
        )}
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
        className="h-9 w-9 shrink-0"
      >
        {watching ? (
          <BookmarkCheck className="text-sky-700 dark:text-sky-400 h-4 w-4" />
        ) : (
          <Bookmark className="h-4 w-4" />
        )}
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
      className={cn("shrink-0 gap-1.5", watching && "text-sky-700 dark:text-sky-400")}
    >
      {watching ? <BookmarkCheck className="h-3.5 w-3.5" /> : <Bookmark className="h-3.5 w-3.5" />}
      {watching ? "已关注" : "关注"}
    </Button>
  );
}
