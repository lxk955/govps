"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Globe, Heart, Radar, Scale, Zap } from "lucide-react";

import { useCompareIds } from "@/lib/compare-store";
import { cn } from "@/lib/utils";

/**
 * 移动端底部高质感吸底导航栏（sm 以下常驻显示，原生 App 级触控体验）。
 * 5 等分设计：
 * 1. 首页 (VPS雷达)
 * 2. 动态 (特惠与补货流)
 * 3. 对比 (带实时选中数量红点 Badge)
 * 4. IP工具 (纯净度/WebRTC)
 * 5. 关注 (降价/到货提醒列表)
 */
const NAV_ITEMS = [
  { href: "/", label: "雷达", icon: Radar },
  { href: "/deals", label: "特惠", icon: Zap },
  { href: "/compare", label: "对比", icon: Scale },
  { href: "/ip", label: "IP工具", icon: Globe, prefix: true },
  { href: "/watchlist", label: "关注", icon: Heart },
] as const;

export function BottomNav() {
  const pathname = usePathname();
  const { ids, ready } = useCompareIds();
  const compareCount = ready ? ids.length : 0;

  return (
    <nav
      aria-label="移动端主导航"
      className="border-border/80 bg-card/90 fixed inset-x-0 bottom-0 z-30 border-t backdrop-blur-md transition-colors sm:hidden"
    >
      <ul className="flex items-center justify-around pb-[calc(env(safe-area-inset-bottom)+2px)] pt-1">
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
                  "relative flex flex-col items-center justify-center gap-0.5 py-1 text-[10.5px] transition-all active:scale-90",
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

                  {/* 对比数量角标 */}
                  {item.href === "/compare" && compareCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-600 px-1 text-[9px] font-black text-white shadow-xs">
                      {compareCount}
                    </span>
                  )}
                </div>
                <span className="leading-tight tracking-tight">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
