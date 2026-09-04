"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Globe, Heart, Radar, Zap } from "lucide-react";

import { cn } from "@/lib/utils";
import { MOBILE_NAV, navItemActive } from "@/lib/nav";

/**
 * 移动端底部吸底导航栏（sm 以下常驻显示）。
 * 对比用 CompareBar 按需浮起，不占常驻位。
 */
const NAV_ICONS = {
  "/": Radar,
  "/deals": Zap,
  "/ip": Globe,
  "/watchlist": Heart,
} as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="移动端主导航"
      className="border-border/80 bg-card/95 fixed inset-x-0 bottom-0 z-40 border-t backdrop-blur-md transition-colors sm:hidden"
      style={{ paddingBottom: "max(env(safe-area-inset-bottom, 0px), 10px)" }}
    >
      <ul className="flex h-13 items-center justify-around">
        {MOBILE_NAV.map((item) => {
          const Icon = NAV_ICONS[item.href as keyof typeof NAV_ICONS];
          const active = navItemActive(pathname, item);

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
