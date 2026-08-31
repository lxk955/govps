"use client";

import { useState } from "react";
import { Check, Scale } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useCompareIds, COMPARE_MAX } from "@/lib/compare-store";
import { cn } from "@/lib/utils";

/** 对比入口按钮（列表卡片/表格行/详情页共用）。
 * 已在对比集 → 高亮可移除；集满且未加入 → 提示上限。
 *
 * 可发现性：早期版本是纯天平图标（无文字），很多用户不知道这是「加入对比」；
 * 现所有形态均带文字标签，加入后文案切换为「已加入」，状态自解释。 */

export function CompareButton({
  productId,
  size = "icon",
}: {
  productId: number;
  size?: "sm" | "icon" | "xs";
}) {
  const { ids, ready, toggle } = useCompareIds();
  const inSet = ids.includes(productId);
  const full = ids.length >= COMPARE_MAX;
  const [hint, setHint] = useState(false);

  const onClick = () => {
    const r = toggle(productId);
    if (r.full && !inSet) {
      setHint(true);
      setTimeout(() => setHint(false), 2000);
    }
  };

  const title = inSet
    ? "从对比中移除"
    : hint || (full && ready)
      ? `最多对比 ${COMPARE_MAX} 款，请先移除一款`
      : "加入对比";

  // xs：卡片头部 24px 专属槽内的紧凑形态（图标 + 文字）
  if (size === "xs") {
    return (
      <Button
        variant="ghost"
        aria-label={title}
        aria-pressed={ready ? inSet : undefined}
        title={title}
        onClick={onClick}
        className={cn(
          "h-6 shrink-0 gap-1 rounded-md px-1.5 text-[11px] font-semibold text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300",
          ready &&
            inSet &&
            "bg-blue-50 text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:bg-blue-950/50 dark:text-blue-400 dark:hover:bg-blue-950/50 dark:hover:text-blue-300",
        )}
      >
        {ready && inSet ? (
          <Check aria-hidden className="h-3 w-3" />
        ) : (
          <Scale aria-hidden className="h-3 w-3" />
        )}
        {ready && inSet ? "已加入" : "对比"}
      </Button>
    );
  }

  // icon：详情页底部按钮（历史命名，现为带文字的中号形态）
  if (size === "icon") {
    return (
      <Button
        variant="outline"
        aria-label={title}
        aria-pressed={ready ? inSet : undefined}
        title={title}
        onClick={onClick}
        className={cn(
          "h-9 shrink-0 gap-1.5 px-3",
          ready &&
            inSet &&
            "border-sky-300 bg-sky-50 text-sky-700 hover:bg-sky-50 hover:text-sky-800 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-400 dark:hover:bg-sky-950/40 dark:hover:text-sky-300",
        )}
      >
        {ready && inSet ? (
          <Check aria-hidden className="h-4 w-4" />
        ) : (
          <Scale aria-hidden className="h-4 w-4" />
        )}
        {ready && inSet ? "已加入" : "对比"}
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      aria-pressed={ready ? inSet : undefined}
      title={title}
      onClick={onClick}
      className={cn(
        "gap-1.5",
        ready && inSet && "border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-400",
      )}
    >
      {ready && inSet ? <Check className="h-3.5 w-3.5" /> : <Scale className="h-3.5 w-3.5" />}
      {ready && inSet ? "已加入" : "对比"}
    </Button>
  );
}
