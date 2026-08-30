"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Scale, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useCompareIds } from "@/lib/compare-store";

/**
 * 对比浮动条：选中套餐后常驻底部，引导前往 /compare。
 *
 * 存在原因：对比功能此前只有列表/详情里的「加入对比」按钮，全站没有任何导航
 * 入口，用户加入后找不到查看位置，等于功能不存在。此条在选中非空且不在
 * /compare 页时出现，提供直达链接与清空入口。
 *
 * 位置：移动端 bottom-20（让开底部导航栏），sm 以上 bottom-4 靠右下角。
 */
export function CompareBar() {
  const { ids, ready, clear } = useCompareIds();
  const pathname = usePathname();

  if (!ready || ids.length === 0 || pathname === "/compare") return null;

  return (
    <div
      role="status"
      className="bg-card fixed inset-x-4 bottom-20 z-30 mx-auto flex max-w-md items-center justify-between gap-3 rounded-xl border p-3 shadow-lg sm:bottom-4 sm:left-auto sm:right-6"
    >
      <p className="min-w-0 truncate text-sm">
        <Scale aria-hidden className="mr-1.5 inline h-4 w-4 align-text-bottom" />
        已选 <b className="font-black tabular-nums">{ids.length}</b> 款套餐
      </p>
      <div className="flex shrink-0 items-center gap-1">
        <Button asChild size="sm">
          <Link href={`/compare?ids=${ids.join(",")}`}>查看对比</Link>
        </Button>
        <Button
          size="icon"
          variant="ghost"
          aria-label="清空对比"
          title="清空对比"
          className="h-8 w-8"
          onClick={clear}
        >
          <X aria-hidden className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
