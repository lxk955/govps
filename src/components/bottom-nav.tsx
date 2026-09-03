"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Globe, LayoutGrid } from "lucide-react";

/**
 * 移动端底部导航（sm 以下显示，与顶部 HeaderNav 互补）。
 *
 * 顶部导航在窄屏放不下：390px 视口下「Logo 95 + 导航 228 + 右侧工具栏 131 +
 * 间距」需要 454px，可用仅 358px。此前改为顶部横向滚动，但滚动条被隐藏，用户
 * 看不出后面还有内容（反馈「导航栏太窄了显示不出来」）——看不见的滚动等于没有
 * 导航。故窄屏改用底部等分标签栏：4 项各占约 97px，全部完整可见且拇指可达。
 *
 * 标签与 HeaderNav 保持一致，仅呈现方式不同（图标 + 文字）。
 */
const NAV_ITEMS = [
  { href: "/", label: "产品", icon: LayoutGrid },
  { href: "/deals", label: "动态", icon: Activity },
  { href: "/ip", label: "IP 检测", icon: Globe, prefix: true },
  // 关注入口用与关注按钮同款的心形（icon 为 null 时渲染 HeartIcon）
  { href: "/watchlist", label: "我的关注", icon: null },
] as const;

/** 与关注按钮同款的心形（旧站 Heroicons heart）：激活时实心、否则空心描边。 */
function HeartIcon({ filled, className }: { filled: boolean; className?: string }) {
  return (
    <svg
      aria-hidden
      className={className}
      fill={filled ? "currentColor" : "none"}
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

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="主导航"
      className="border-border bg-card/95 fixed inset-x-0 bottom-0 z-30 border-t backdrop-blur sm:hidden"
    >
      <ul className="flex pb-[env(safe-area-inset-bottom)]">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/" || pathname === "/vps"
              : "prefix" in item && item.prefix
                ? pathname === item.href || pathname.startsWith(`${item.href}/`)
                : pathname === item.href;

          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center gap-0.5 py-2 text-[11px] transition-colors ${
                  active
                    ? "font-bold text-blue-600 dark:text-blue-400"
                    : "font-medium text-slate-500 dark:text-slate-400"
                }`}
              >
                {Icon ? (
                  <Icon className="h-5 w-5" aria-hidden />
                ) : (
                  <HeartIcon filled={active} className="h-5 w-5" />
                )}
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
