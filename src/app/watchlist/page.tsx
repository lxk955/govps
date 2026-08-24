import type { Metadata } from "next";

import { WatchlistPanel } from "@/components/watchlist-panel";

export const metadata: Metadata = {
  title: "我的关注",
  description: "管理你关注的 VPS 套餐与降价、补货邮件通知偏好。",
  robots: { index: false, follow: false },
};

export default function WatchlistPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6">
      <header className="mb-5">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">我的关注</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          关注的套餐发生补货或降价时，会按下面的通知偏好发送邮件。
        </p>
      </header>
      <WatchlistPanel />
    </div>
  );
}
