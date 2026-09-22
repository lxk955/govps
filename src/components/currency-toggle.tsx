"use client";

import { useCurrency, type CurrencyMode } from "@/components/currency-provider";
import { cn } from "@/lib/utils";

const OPTIONS: { value: CurrencyMode; short: string; label: string }[] = [
  { value: "original", short: "原币", label: "商家原币种" },
  { value: "CNY", short: "¥", label: "人民币" },
  { value: "USD", short: "$", label: "美元" },
];

export function CurrencyToggle({ className }: { className?: string }) {
  const { mode, setMode } = useCurrency();

  return (
    <div
      role="radiogroup"
      aria-label="价格显示币种"
      className={cn(
        "inline-flex h-8 items-center rounded-lg border border-slate-200 bg-slate-50/80 p-0.5 dark:border-slate-800 dark:bg-slate-900/80",
        className,
      )}
    >
      {OPTIONS.map((opt) => {
        const active = mode === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={opt.label}
            title={opt.label}
            onClick={() => setMode(opt.value)}
            className={cn(
              "h-full min-w-8 rounded-md px-2 text-xs font-semibold transition-colors",
              active
                ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {opt.short}
          </button>
        );
      })}
    </div>
  );
}
