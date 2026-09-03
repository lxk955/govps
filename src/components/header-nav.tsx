"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCompareIds } from "@/lib/compare-store";

/**
 * 主导航（1:1 复刻旧站 App.vue 胶囊式导航与激活态着色）。
 *
 * 标签沿用旧站四项：产品 / 动态 / IP 检测 / 我的关注。
 * 「产品」指向 /vps——新站比旧站多出一个首页（含精选位与 SEO 入口），
 * 入口保留在站点 Logo 上，不占用导航位以免偏离旧站排版。
 *
 * 「对比」为新增项：对比功能此前只有「加入对比」按钮而无任何入口，
 * 用户加入后找不到查看位置，故在此补一个常驻入口并显示已选数量。
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
     * 仅 sm 以上显示：窄屏放不下全部导航项（390px 视口下需要 454px，可用 358px），
     * 曾在顶部改为横向滚动，但滚动条隐藏后用户看不出还有内容，等于没有导航。
     * 窄屏的导航改由 BottomNav（底部等分标签栏）承担，四项全部完整可见。
     */
    <nav
      aria-label="主导航"
      className="hidden items-center gap-1 text-xs sm:flex sm:gap-1.5 sm:text-sm"
    >
      {NAV_ITEMS.map((item) => {
        const active =
          item.href === "/"
            ? pathname === "/" || pathname === "/vps"
            : "prefix" in item && item.prefix
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
