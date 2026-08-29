"use client";

import { useState } from "react";
import { Check, Scale } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useCompareIds, COMPARE_MAX } from "@/lib/compare-store";
import { cn } from "@/lib/utils";

/** 对比入口按钮（列表卡片/表格行/详情页共用）。
 * 已在对比集 → 高亮可移除；集满且未加入 → 提示上限。 */

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

  // xs：卡片头部 24px 专属槽内的紧凑形态
  if (size === "xs") {
    return (
      <Button
        variant="ghost"
        size="icon"
        aria-label={title}
        aria-pressed={ready ? inSet : undefined}
        title={title}
        onClick={onClick}
        className={cn(
          "h-6 w-6 shrink-0",
          ready && inSet && "text-blue-600 dark:text-blue-400",
        )}
      >
        {ready && inSet ? (
          <Check aria-hidden className="h-3.5 w-3.5" />
        ) : (
          <Scale aria-hidden className="text-slate-400 h-3.5 w-3.5" />
        )}
      </Button>
    );
  }

  if (size === "icon") {
    return (
      <Button
        variant="outline"
        size="icon"
        aria-label={title}
        aria-pressed={ready ? inSet : undefined}
        title={title}
        onClick={onClick}
        className="h-9 w-9 shrink-0"
      >
        {ready && inSet ? (
          <Check className="text-sky-700 dark:text-sky-400 h-4 w-4" />
        ) : (
          <Scale className="h-4 w-4" />
        )}
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
      className={cn("gap-1.5", ready && inSet && "text-sky-700 dark:text-sky-400")}
    >
      {ready && inSet ? <Check className="h-3.5 w-3.5" /> : <Scale className="h-3.5 w-3.5" />}
      对比
    </Button>
  );
}
