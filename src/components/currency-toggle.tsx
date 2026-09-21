"use client";

import React from "react";
import { useCurrency, type CurrencyMode } from "@/components/currency-provider";
import { cn } from "@/lib/utils";

interface CurrencyToggleProps {
  className?: string;
}

export function CurrencyToggle({ className }: CurrencyToggleProps) {
  const { mode, setMode } = useCurrency();

  return (
    <div className={cn("relative inline-flex items-center", className)}>
      <select
        value={mode}
        onChange={(e) => setMode(e.target.value as CurrencyMode)}
        aria-label="切换价格显示币种"
        className="h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 font-mono text-slate-700 dark:text-slate-200 focus:outline-hidden cursor-pointer shadow-2xs hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
      >
        <option value="original">原币 (商家)</option>
        <option value="CNY">CNY (¥)</option>
        <option value="USD">USD ($)</option>
      </select>
    </div>
  );
}
