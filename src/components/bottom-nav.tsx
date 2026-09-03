"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Globe, Heart, Radar, Zap } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * 移动端底部吸底导航栏（sm 以下常驻显示，原生 App 级触控体验）。
 * 4 大核心板块：
 * 1. 首页 (VPS雷达)
 * 2. 特惠 (降价榜与秒杀补货流)
 * 3. IP工具 (纯净度检测/DNS/WebRTC)
 * 4. 关注 (降价与到货提醒列表)
 *
 * 注：对比功能采用上下文浮动条（CompareBar），仅在用户主动勾选套餐时按需浮起，
 * 避免占用常驻导航空间。
 */
const NAV_ITEMS = [
  { href: "/", label: "雷达", icon: Radar },
  { href: "/deals", label: "特惠", icon: Zap },
  { href: "/ip", label: "IP工具", icon: Globe, prefix: true },
  { href: "/watchlist", label: "关注", icon: Heart },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="移动端主导航"
      className="border-border/80 bg-card/95 fixed inset-x-0 bottom-0 z-30 border-t backdrop-blur-md transition-colors sm:hidden"
    >
      <ul className="flex items-center justify-around pt-1.5 pb-[max(env(safe-area-inset-bottom),10px)]">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active =
            "prefix" in item && item.prefix
              ? pathname === item.href || pathname.startsWith(`${item.href}/`)
              : pathname === item.href;

          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex flex-col items-center justify-center gap-0.5 py-0.5 text-[11px] transition-all active:scale-95 shrink-0 select-none",
                  active
                    ? "font-bold text-blue-600 dark:text-blue-400"
                    : "font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
                )}
              >
                <div
                  className={cn(
                    "relative flex h-7 w-12 items-center justify-center rounded-full transition-colors",
                    active
                      ? "bg-blue-100/70 text-blue-600 dark:bg-blue-950/80 dark:text-blue-400"
                      : "text-slate-600 dark:text-slate-400",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 transition-transform",
                      active && "scale-110",
                      item.href === "/watchlist" && active && "fill-current",
                    )}
                    aria-hidden
                  />
                </div>
                <span className="leading-tight tracking-tight block shrink-0">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
