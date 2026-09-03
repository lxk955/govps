"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCompareIds } from "@/lib/compare-store";

/**
 * 桌面端主导航：
 * 产品（根路径）/ 动态 / IP 检测 / 我的关注 / 对比。
 */
const NAV_ITEMS = [
  { href: "/", label: "产品" },
  { href: "/deals", label: "动态" },
  { href: "/ip", label: "IP 检测", prefix: true },
  { href: "/watchlist", label: "我的关注" },
  { href: "/compare", label: "对比" },
] as const;

export function HeaderNav() {
  const pathname = usePathname();
  const { ids, ready } = useCompareIds();
  const compareCount = ready ? ids.length : 0;

  return (
    /*
     * 仅 sm 以上显示：窄屏由底部等分标签栏 BottomNav 承担，更符合触屏操作。
     */
    <nav
      aria-label="主导航"
      className="hidden items-center gap-1 text-xs sm:flex sm:gap-1.5 sm:text-sm"
    >
      {NAV_ITEMS.map((item) => {
        const active =
          "prefix" in item && item.prefix
            ? pathname === item.href || pathname.startsWith(`${item.href}/`)
            : pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-xl px-2.5 py-1.5 transition-all sm:px-3 ${
              active
                ? "bg-blue-50 font-bold text-blue-600 dark:bg-blue-950/70 dark:text-blue-300"
                : "font-medium text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
            }`}
          >
            {item.label}
            {item.href === "/compare" && compareCount > 0 && (
              <span className="ml-1 rounded-full bg-blue-600 px-1.5 py-px text-[10px] font-bold text-white tabular-nums">
                {compareCount}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
