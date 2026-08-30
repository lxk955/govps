"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
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
 * 外观 1:1 还原旧站 web/src/components/WatchButton.vue：胶囊按钮 + 「关注/已关注」
 * 文字 + Heroicons heart 心形。旧站三处（卡片/列表行/详情页）共用的是同一个
 * 组件、同一种样式，因此这里也不再区分尺寸。
 *
 * 心形尺寸取 h-4 w-4（16px），比旧站的 14px 大 2px——纯图标形态下心形偏小、
 * 不够醒目；其余配色与结构均与旧站一致。
 */

/** 旧站同款心形（Heroicons heart）：已关注实心填充，未关注仅描边。 */
function HeartMark({ watching, className }: { watching: boolean; className?: string }) {
  return (
    <svg
      aria-hidden
      className={cn("shrink-0", className)}
      fill={watching ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
      />
    </svg>
  );
}

export function WatchButton({
  productId,
  hydrate = false,
  unwatchPrefs,
  onUnwatched,
}: {
  productId: number;
  /** 挂载后查询真实状态（详情页） */
  hydrate?: boolean;
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

  // 旧站三处共用同一个组件与样式，这里同样不做尺寸区分
  return (
    <Button
      type="button"
      variant="outline"
      aria-label={watching ? "取消关注" : "关注此套餐，到货或降价时邮件提醒"}
      title={watching ? "取消关注" : "关注此套餐，到货或降价时邮件提醒"}
      aria-pressed={watching}
      disabled={busy || user === undefined}
      onClick={() => void toggle()}
      className={cn(
        "h-auto w-[76px] shrink-0 justify-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors",
        watching
          ? "border-rose-200 bg-rose-50 text-rose-500 hover:bg-rose-100 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-400"
          : "border-slate-200 bg-white text-slate-500 hover:border-rose-300 hover:text-rose-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400",
      )}
    >
      <HeartMark watching={watching} className="h-4 w-4" />
      {watching ? "已关注" : "关注"}
    </Button>
  );
}
