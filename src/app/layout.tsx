import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { AuthProvider } from "@/components/auth-provider";
import { HeaderAuth } from "@/components/header-auth";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://govps.xyz";

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
      <body className="bg-background text-foreground antialiased">
        <ThemeProvider>
          <AuthProvider>
          <header className="border-b">
            <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-4 px-4">
              <Link href="/" className="text-base font-bold tracking-tight">
                GoVPS
              </Link>
              <nav aria-label="主导航" className="flex items-center gap-1 overflow-x-auto text-sm">
                <Link
                  href="/vps"
                  className="hover:bg-muted whitespace-nowrap rounded-md px-2.5 py-1.5 transition-colors"
                >
                  VPS 列表
                </Link>
                <Link
                  href="/deals"
                  className="hover:bg-muted whitespace-nowrap rounded-md px-2.5 py-1.5 transition-colors"
                >
                  降价动态
                </Link>
                <Link
                  href="/providers"
                  className="hover:bg-muted whitespace-nowrap rounded-md px-2.5 py-1.5 transition-colors"
                >
                  服务商
                </Link>
                <Link
                  href="/ip"
                  className="hover:bg-muted whitespace-nowrap rounded-md px-2.5 py-1.5 transition-colors"
                >
                  IP 检测
                </Link>
              </nav>
              <div className="ml-auto flex shrink-0 items-center gap-1">
                <HeaderAuth />
                <ThemeToggle />
              </div>
            </div>
          </header>
          {children}
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
