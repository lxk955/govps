import { Suspense } from "react";
import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { AuthProvider } from "@/components/auth-provider";
import { BookmarkDialog } from "@/components/bookmark-dialog";
import { CompareBar } from "@/components/compare/compare-bar";
import { BottomNav } from "@/components/bottom-nav";
import { HeaderAuth } from "@/components/header-auth";
import { HeaderNav } from "@/components/header-nav";
import { PageViewTracker } from "@/components/page-view-tracker";
import { RouteProgress } from "@/components/route-progress";
import { ScrollToTop } from "@/components/scroll-to-top";
import { CurrencyProvider } from "@/components/currency-provider";
import { CurrencyToggle } from "@/components/currency-toggle";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { getCurrentRates } from "@/lib/api/endpoints";
import { CURRENCY_COOKIE, parseCurrencyMode } from "@/lib/currency-mode";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "GoVPS · VPS雷达 - VPS 实时库存与降价监控",
    template: "%s | GoVPS · VPS雷达",
  },
  description:
    "多商家 VPS 套餐实时聚合：按商家、机房、线路、价格与配置极速筛选，支持 CN2 GIA / 9929 / CMIN2 优质线路、降价与补货自动监控。",
  keywords: [
    "VPS",
    "VPS雷达",
    "VPS监控",
    "VPS推荐",
    "CN2 GIA",
    "联通9929",
    "移动CMIN2",
    "搬瓦工库存",
    "DMIT补货",
    "VPS降价",
    "便宜VPS",
    "香港VPS",
    "日本VPS",
    "美国VPS",
    "VPS线路对比",
  ],
  authors: [{ name: "GoVPS" }],
  creator: "GoVPS",
  openGraph: {
    type: "website",
    locale: "zh_CN",
    url: SITE_URL,
    siteName: "GoVPS · VPS雷达",
    title: "GoVPS · VPS雷达 - VPS 实时库存与降价监控",
    description:
      "多商家 VPS 套餐实时聚合：按商家、机房、线路、价格与配置极速筛选，支持 CN2 GIA / 9929 / CMIN2 优质线路、降价与补货自动监控。",
  },
  twitter: {
    card: "summary_large_image",
    title: "GoVPS · VPS雷达 - VPS 实时库存与降价监控",
    description:
      "多商家 VPS 套餐实时聚合：按商家、机房、线路、价格与配置极速筛选，支持 CN2 GIA / 9929 / CMIN2 优质线路、降价与补货自动监控。",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const ratesData = await getCurrentRates().catch(() => null);
  const ratesMap: Record<string, number> = {};
  if (ratesData?.rates) {
    for (const r of ratesData.rates) {
      ratesMap[r.code] = r.units_per_usd;
    }
  }
  const cookieMode = parseCurrencyMode((await cookies()).get(CURRENCY_COOKIE)?.value);

  return (
    <html lang="zh-CN" className="overflow-x-hidden" suppressHydrationWarning>
      <body className="bg-background text-foreground flex min-h-dvh flex-col antialiased overflow-x-hidden w-full max-w-full">
        <ThemeProvider>
          <AuthProvider>
            <CurrencyProvider initialRates={ratesMap} initialMode={cookieMode}>
              <header className="bg-card/90 border-border sticky top-0 z-20 border-b backdrop-blur w-full">
                <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center justify-between gap-1.5 px-3 sm:gap-6 sm:px-4">
                  <Link
                    href="/"
                    className="flex shrink-0 items-center gap-1.5 text-base font-bold text-blue-600 sm:gap-2 sm:text-lg dark:text-blue-400"
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
                    {/* 主名 + 旧站中文名：同行胶囊标签 */}
                    <div className="flex flex-col justify-center leading-none sm:flex-row sm:items-center sm:gap-1.5">
                      <span className="text-base font-extrabold tracking-tight sm:text-lg">GoVPS</span>
                      <span className="text-[10px] font-medium tracking-tight text-slate-400 dark:text-slate-500 sm:rounded-md sm:bg-blue-50 sm:px-1.5 sm:py-0.5 sm:text-[11px] sm:font-semibold sm:text-blue-600 sm:dark:bg-blue-950/60 sm:dark:text-blue-400">
                        VPS雷达
                      </span>
                    </div>
                  </Link>
                  <HeaderNav />
                  <div className="flex shrink-0 items-center gap-1 text-sm sm:gap-2.5">
                    <CurrencyToggle />
                    <div className="hidden sm:block">
                      <BookmarkDialog />
                    </div>
                    <HeaderAuth />
                    <ThemeToggle />
                  </div>
                </div>
              </header>

              <main className="mx-auto w-full max-w-[1600px] flex-1 px-3 py-4 sm:px-4 sm:py-6 min-w-0">{children}</main>

            {/* 窄屏底部留出标签栏净空（pb-24）。留白必须加在页脚而非 main 上：
                main 的 padding 保护不到它之后的页脚，实测会被 fixed 标签栏压住 56px。 */}
            <footer className="border-border px-4 pb-24 pt-6 text-center text-xs text-slate-400 sm:pb-6 dark:text-slate-500">
              <div className="mb-2.5 flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 font-medium text-slate-500 dark:text-slate-400">
                <span className="text-slate-400">热门专线：</span>
                <Link href="/routes/cn2-gia" className="hover:text-blue-600 transition-colors">电信 CN2 GIA</Link>
                <span>·</span>
                <Link href="/routes/9929" className="hover:text-blue-600 transition-colors">联通 9929</Link>
                <span>·</span>
                <Link href="/routes/cmin2" className="hover:text-blue-600 transition-colors">移动 CMIN2</Link>
                <span>·</span>
                <Link href="/routes/4837" className="hover:text-blue-600 transition-colors">联通 4837</Link>
                <span>·</span>
                <Link href="/routes" className="hover:text-blue-600 transition-colors">全部线路指南 →</Link>
              </div>
              <div className="mb-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
                <span>GoVPS · VPS雷达 · 库存与价格数据来自各商家官网公开页面，仅供参考</span>
                <span className="sm:hidden">
                  <BookmarkDialog />
                </span>
              </div>
              <p className="mt-1">
                部分商家链接为推广链接，通过它们购买我们会获得佣金，你的购买价格不受任何影响，也不影响本站的数据展示与排序。
              </p>
            </footer>

            <BottomNav />
            <ScrollToTop />
            <CompareBar />
            <PageViewTracker />
            {/* 全局路由加载进度条：useSearchParams 须包 Suspense，避免静态预渲染 CSR bailout */}
            <Suspense fallback={null}>
              <RouteProgress />
            </Suspense>
            </CurrencyProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
