"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BellRing, X } from "lucide-react";

import { useAuth } from "@/components/auth-provider";

/**
 * 未登录通知引导横幅（1:1 复刻旧站 ProductList.vue 的登录引导条）。
 * 关闭状态记在 localStorage；SSR 阶段不渲染，避免挂载前后闪烁。
 */
export function NotifyBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    setDismissed(localStorage.getItem("notifyBannerDismissed") === "1");
  }, []);

  // 登录状态未确定、或已登录、或已关闭 → 不渲染
  if (user === undefined || user !== null || dismissed) return null;

  return (
    <div className="mb-4 flex items-center justify-between gap-2.5 rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50/90 to-indigo-50/90 px-3.5 py-2 text-xs text-blue-700 dark:border-blue-900 dark:from-blue-950/50 dark:to-indigo-950/50 dark:text-blue-300">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <BellRing aria-hidden className="h-4 w-4 shrink-0 text-blue-500" />
        <span className="truncate">
          点击套餐上的<b>「关注」</b>，<b>到货补货</b>或<b>降价</b>将第一时间邮件提醒！
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link
          href="/login"
          className="rounded-lg bg-blue-600 px-2.5 py-1 text-[11px] font-bold text-white transition-colors hover:bg-blue-700"
        >
          开启提醒
        </Link>
        <button
          type="button"
          aria-label="关闭提示"
          title="关闭提示"
          onClick={() => {
            localStorage.setItem("notifyBannerDismissed", "1");
            setDismissed(true);
          }}
          className="cursor-pointer rounded p-0.5 text-slate-400 transition-colors hover:text-slate-600"
        >
          <X aria-hidden className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
