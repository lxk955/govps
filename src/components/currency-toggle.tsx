"use client";

import { useCurrency, type CurrencyMode } from "@/components/currency-provider";
import { cn } from "@/lib/utils";

const MODES: { value: CurrencyMode; face: string; label: string }[] = [
  { value: "original", face: "原币", label: "按商家标价显示" },
  { value: "CNY", face: "¥", label: "人民币，按汇率换算" },
  { value: "USD", face: "$", label: "美元，按汇率换算" },
];

export function CurrencyToggle() {
  const { mode, setMode } = useCurrency();

  return (
    <div
      role="radiogroup"
      aria-label="价格显示币种"
      className="inline-flex h-8 shrink-0 items-center rounded-full border border-border bg-slate-100/90 p-0.5 dark:bg-slate-800/80"
    >
      {MODES.map((item) => {
        const active = mode === item.value;
        return (
          <button
            key={item.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={item.label}
            title={item.label}
            onClick={() => setMode(item.value)}
            className={cn(
              "flex h-7 min-w-8 cursor-pointer items-center justify-center rounded-full px-2.5 text-xs leading-none transition-all select-none",
              active
                ? "bg-white font-semibold text-slate-900 shadow-sm dark:bg-slate-950 dark:text-white"
                : "font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {item.face}
          </button>
        );
      })}
    </div>
  );
}
