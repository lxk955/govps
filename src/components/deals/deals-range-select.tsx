"use client";

import { useRouter } from "next/navigation";

/** 时间窗口下拉（1:1 复刻旧站 Deals.vue 的 hours 选择器）。 */
export function DealsRangeSelect({ type, hours }: { type: string; hours: number }) {
  const router = useRouter();
  return (
    <select
      value={hours}
      onChange={(e) => router.push(`/deals?type=${type}&hours=${e.target.value}`)}
      aria-label="时间范围"
      className="border-border bg-card text-foreground focus:border-blue-400 rounded-lg border px-2 py-1.5 text-base focus:outline-none sm:text-sm"
    >
      <option value={24}>近 24 小时</option>
      <option value={72}>近 3 天</option>
      <option value={168}>近 7 天</option>
    </select>
  );
}
