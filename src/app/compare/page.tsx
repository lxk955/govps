import type { Metadata } from "next";

import { CompareView } from "@/components/compare/compare-view";

export const metadata: Metadata = {
  title: "套餐对比",
  description: "并排对比最多 4 款 VPS 套餐的价格、配置、机房、三网线路与库存。",
  // 交互工具页且内容随用户选择变化：不建索引
  robots: { index: false, follow: true },
};

function parseIds(raw: string | string[] | undefined): number[] {
  const v = Array.isArray(raw) ? raw[0] : raw;
  if (!v) return [];
  return v
    .split(",")
    .map((s) => Number(s))
    .filter((n) => Number.isSafeInteger(n) && n > 0)
    .slice(0, 4);
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const ids = parseIds(sp.ids);

  return (
    <div className="border-border bg-card rounded-xl border p-5 shadow-sm">
      <CompareView initialIds={ids} />
    </div>
  );
}
