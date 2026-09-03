"use client";

import { useState, useRef, useEffect } from "react";
import { Check, ChevronDown } from "lucide-react";
import { useCurrency, type CurrencyMode } from "@/components/currency-provider";
import { cn } from "@/lib/utils";

const MODES: { value: CurrencyMode; label: string; icon: string; desc: string }[] = [
  { value: "original", label: "原币", icon: "🪙", desc: "供应商原币与实际结算币种" },
  { value: "CNY", label: "约合 ¥", icon: "🇨🇳", desc: "折合人民币估算，方便对比" },
  { value: "USD", label: "约合 $", icon: "🇺🇸", desc: "折合美元估算" },
];

export function CurrencyToggle() {
  const { mode, setMode } = useCurrency();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  const current = MODES.find((m) => m.value === mode) || MODES[0];

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label="切换价格换算币种"
        title="切换价格换算币种"
        aria-expanded={open}
        className={cn(
          "flex cursor-pointer items-center gap-1 rounded-xl border px-2 py-1.5 text-xs font-bold transition-colors select-none",
          mode !== "original"
            ? "border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/70 dark:text-blue-300"
            : "border-border bg-card text-slate-700 hover:border-slate-300 dark:text-slate-300 dark:hover:border-slate-700",
        )}
      >
        <span aria-hidden className="text-xs">{current.icon}</span>
        <span className="leading-none">{current.label}</span>
        <ChevronDown className={cn("h-3 w-3 text-slate-400 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="border-border bg-card/95 absolute right-0 top-full z-50 mt-1.5 w-48 rounded-2xl border p-1.5 shadow-xl backdrop-blur-md">
          <div className="px-2.5 py-1 text-[11px] font-bold text-slate-400 dark:text-slate-500">
            全站价格展示
          </div>
          <div className="space-y-0.5">
            {MODES.map((item) => {
              const active = mode === item.value;
              return (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => {
                    setMode(item.value);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full cursor-pointer items-center justify-between rounded-xl px-2.5 py-2 text-left text-xs transition-colors",
                    active
                      ? "bg-blue-50 font-bold text-blue-600 dark:bg-blue-950/70 dark:text-blue-300"
                      : "text-slate-700 hover:bg-slate-100/80 dark:text-slate-300 dark:hover:bg-slate-800",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{item.icon}</span>
                    <div>
                      <div className="leading-tight">{item.label}</div>
                      <div className="text-[10px] font-normal text-slate-400 dark:text-slate-500">
                        {item.desc}
                      </div>
                    </div>
                  </div>
                  {active && <Check className="h-3.5 w-3.5 shrink-0 text-blue-600 dark:text-blue-400" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
