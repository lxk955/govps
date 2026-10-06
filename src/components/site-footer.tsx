"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BookmarkDialog } from "@/components/bookmark-dialog";

const LINES = [
  { href: "/?line=cn2_gia", label: "电信 CN2 GIA" },
  { href: "/?line=9929", label: "联通 9929" },
  { href: "/?line=cmin2", label: "移动 CMIN2" },
  { href: "/?line=4837", label: "联通 4837" },
];

/** 全站只留一行说明。IP 检测不重复套 VPS 专线和推广文案。 */
export function SiteFooter() {
  const path = usePathname() || "/";
  const ip = path === "/ip" || path.startsWith("/ip/");

  return (
    <footer className="border-border px-4 pb-24 pt-6 text-center text-xs text-slate-400 sm:pb-6 dark:text-slate-500">
      {!ip && (
        <nav
          aria-label="热门专线"
          className="mb-2 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 font-medium text-slate-500 dark:text-slate-400"
        >
          {LINES.map((line, i) => (
            <span key={line.href} className="inline-flex items-center gap-3">
              {i > 0 && <span aria-hidden className="text-slate-300 dark:text-slate-600">·</span>}
              <Link href={line.href} className="transition-colors hover:text-blue-600">
                {line.label}
              </Link>
            </span>
          ))}
        </nav>
      )}
      <p>
        {ip
          ? "检测结果来自公开情报，仅供参考。"
          : "价格与库存来自商家公开页面，仅供参考。推广链接不影响你的价格与排序。"}
      </p>
      <div className="mt-2 flex justify-center sm:hidden">
        <BookmarkDialog />
      </div>
    </footer>
  );
}
