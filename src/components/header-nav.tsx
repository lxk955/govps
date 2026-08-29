"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * 主导航（1:1 复刻旧站 App.vue 胶囊式导航与激活态着色）。
 *
 * 标签沿用旧站四项：产品 / 动态 / IP 检测 / 我的关注。
 * 「产品」指向 /vps——新站比旧站多出一个首页（含精选位与 SEO 入口），
 * 入口保留在站点 Logo 上，不占用导航位以免偏离旧站排版。
 */
const NAV_ITEMS = [
  { href: "/vps", label: "产品" },
  { href: "/deals", label: "动态" },
  { href: "/ip", label: "IP 检测", prefix: true },
  { href: "/watchlist", label: "我的关注" },
] as const;

export function HeaderNav() {
  const pathname = usePathname();

  return (
    /*
     * 窄屏放不下全部导航项（实测 390px 视口下需要 454px），若任由 flex 压缩
     * 会把链接文字挤变形，且右侧工具栏 shrink-0 会撑破页面产生横向溢出。
     * 这里让导航自己横向滚动：min-w-0 允许收缩，overflow-x-auto 承接溢出，
     * 滚动局限在导航内部，不会整页横向滚动（AGENTS.md 要求）。
     */
    <nav
      aria-label="主导航"
      className="no-scrollbar flex min-w-0 flex-1 items-center gap-1 overflow-x-auto text-xs sm:gap-1.5 sm:overflow-x-visible sm:text-sm"
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
          </Link>
        );
      })}
    </nav>
  );
}
