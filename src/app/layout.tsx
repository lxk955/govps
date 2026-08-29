import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { AuthProvider } from "@/components/auth-provider";
import { BookmarkDialog } from "@/components/bookmark-dialog";
import { HeaderAuth } from "@/components/header-auth";
import { HeaderNav } from "@/components/header-nav";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "GoVPS - VPS 库存与降价监控",
    template: "%s | GoVPS",
  },
  description:
    "多商家 VPS 套餐聚合：库存监控、降价提醒、线路对比与购买推荐，数据定期同步自各商家官网。",
  alternates: { canonical: "/" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="bg-background text-foreground flex min-h-dvh flex-col antialiased">
        <ThemeProvider>
          <AuthProvider>
            <header className="bg-card/90 border-border sticky top-0 z-20 border-b backdrop-blur">
              <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-3 px-4 sm:gap-6">
                <Link
                  href="/"
                  className="flex shrink-0 items-center gap-2 text-lg font-bold text-blue-600 dark:text-blue-400"
                >
                  {/* 旧站雷达标识（App.vue 同款 20/24 描边图形） */}
                  <svg
                    aria-hidden
                    className="h-5 w-5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <circle cx="12" cy="12" r="9" />
                    <circle cx="12" cy="12" r="4" />
                    <line x1="12" y1="3" x2="12" y2="6" />
                    <line x1="12" y1="18" x2="12" y2="21" />
                    <line x1="3" y1="12" x2="6" y2="12" />
                    <line x1="18" y1="12" x2="21" y2="12" />
                  </svg>
                  GoVPS
                </Link>
                <HeaderNav />
                <div className="ml-auto flex shrink-0 items-center gap-2.5 text-sm sm:gap-3">
                  <BookmarkDialog />
                  <HeaderAuth />
                  <ThemeToggle />
                </div>
              </div>
            </header>

            <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6">{children}</main>

            <footer className="border-border px-4 py-6 text-center text-xs text-slate-400 dark:text-slate-500">
              <div className="mb-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
                <span>GoVPS · 库存与价格数据来自各商家官网公开页面，仅供参考</span>
                <BookmarkDialog />
              </div>
              <p className="mt-1">
                部分商家链接为推广链接，通过它们购买我们会获得佣金，你的购买价格不受任何影响，也不影响本站的数据展示与排序。
              </p>
            </footer>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
