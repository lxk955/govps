import type { Metadata } from "next";

import { WatchlistPanel } from "@/components/watchlist-panel";

export const metadata: Metadata = {
  title: "我的关注",
  description: "管理你关注的 VPS 套餐与降价、补货邮件通知偏好。",
  robots: { index: false, follow: false },
};

export default function WatchlistPage() {
  return (
    <div className="border-border bg-card rounded-xl border p-5 shadow-sm">
      <div className="mb-5">
        <h1 className="text-slate-900 mb-1 text-xl font-bold dark:text-slate-100">我的关注</h1>
        <p className="text-muted-foreground text-sm">
          关注的套餐到货或降价时，会自动发送邮件通知你。
        </p>
      </div>
      <WatchlistPanel />
    </div>
  );
}
