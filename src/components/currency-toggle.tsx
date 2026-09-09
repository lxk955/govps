"use client";

import { Check, ChevronDown } from "lucide-react";

import { useCurrency, type CurrencyMode } from "@/components/currency-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const MODES: { value: CurrencyMode; symbol: string; label: string; desc: string }[] = [
  { value: "original", symbol: "原", label: "原币", desc: "按商家标价显示" },
  { value: "CNY", symbol: "¥", label: "人民币", desc: "按汇率换算成人民币" },
  { value: "USD", symbol: "$", label: "美元", desc: "按汇率换算成美元" },
];

export function CurrencyToggle() {
  const { mode, setMode } = useCurrency();
  const current = MODES.find((m) => m.value === mode) || MODES[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`价格显示：${current.label}，点击切换`}
          title="切换价格显示币种"
          className={cn(
            "group inline-flex h-8 shrink-0 cursor-pointer items-center gap-1 rounded-full border pl-1 pr-2 text-xs font-medium transition-colors select-none",
            "hover:border-slate-300 dark:hover:border-slate-600",
            mode === "original"
              ? "border-border bg-card text-slate-700 dark:text-slate-200"
              : "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950/60 dark:text-blue-200",
          )}
        >
          <span
            aria-hidden
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded-full text-[13px] font-semibold leading-none",
              mode === "original"
                ? "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100"
                : "bg-white/80 text-blue-800 dark:bg-blue-900/80 dark:text-blue-100",
            )}
          >
            {current.symbol}
          </span>
          <span className="leading-none">{current.label}</span>
          <ChevronDown className="h-3 w-3 text-slate-400 transition-transform group-data-[state=open]:rotate-180" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-[min(18rem,calc(100vw-1.5rem))] p-1.5 shadow-xl">
        <div className="px-2.5 pb-1.5 pt-1 text-[11px] font-medium tracking-wide text-slate-400 dark:text-slate-500">
          价格显示
        </div>
        <div className="space-y-0.5">
          {MODES.map((item) => {
            const active = mode === item.value;
            return (
              <DropdownMenuItem
                key={item.value}
                onSelect={() => setMode(item.value)}
                className={cn(
                  "flex w-full cursor-pointer items-center gap-2.5 rounded-xl px-2 py-2 text-left",
                  active
                    ? "bg-blue-50 dark:bg-blue-950/70"
                    : "hover:bg-slate-100/80 dark:hover:bg-slate-800",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-base font-semibold",
                    active
                      ? "bg-blue-600 text-white dark:bg-blue-500"
                      : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
                  )}
                >
                  {item.symbol}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={cn(
                      "block text-sm leading-tight",
                      active
                        ? "font-semibold text-blue-700 dark:text-blue-200"
                        : "font-medium text-slate-800 dark:text-slate-100",
                    )}
                  >
                    {item.label}
                  </span>
                  <span className="mt-0.5 block text-[11px] font-normal leading-tight text-slate-400 dark:text-slate-500">
                    {item.desc}
                  </span>
                </span>
                {active && (
                  <Check className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
                )}
              </DropdownMenuItem>
            );
          })}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
