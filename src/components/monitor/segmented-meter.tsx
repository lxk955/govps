"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface SegmentedMeterProps {
  percent: number; // 0 ~ 100
  totalBlocks?: number; // 默认 16 格
  colorClass?: string; // 填充色
  bgClass?: string; // 底色
  className?: string;
  size?: "sm" | "md";
  minBlocks?: number; // 接近 0% 时的最少显示格数，默认为 1（避免看起来像数据异常）
}

export function SegmentedMeter({
  percent,
  totalBlocks = 16,
  colorClass = "bg-indigo-500 dark:bg-indigo-400",
  bgClass = "bg-slate-100 dark:bg-slate-800",
  className,
  size = "md",
  minBlocks = 1,
}: SegmentedMeterProps) {
  const safePercent = Math.max(0, Math.min(100, isNaN(percent) ? 0 : percent));
  const calculatedBlocks = Math.round((safePercent / 100) * totalBlocks);
  // 当接近或等于 0% 时，至少保证显示 minBlocks 格（避免完全空白看起来像未加载或异常）
  const filledBlocks = Math.min(
    totalBlocks,
    Math.max(minBlocks, calculatedBlocks),
  );

  return (
    <div
      className={cn(
        "flex items-center gap-[2.5px] w-full select-none",
        size === "sm" ? "h-[5px]" : "h-[6.5px]",
        className,
      )}
      aria-valuenow={safePercent}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: totalBlocks }).map((_, i) => {
        const isFilled = i < filledBlocks;
        return (
          <div
            key={i}
            className={cn(
              "flex-1 h-full rounded-[1.5px] transition-colors duration-300",
              isFilled ? colorClass : bgClass,
            )}
          />
        );
      })}
    </div>
  );
}

interface WaveRateDotsProps {
  active?: boolean;
  rateBytesPerSec?: number;
  className?: string;
  count?: number;
  colorClass?: string;
}

export function WaveRateDots({
  active = true,
  rateBytesPerSec = 0,
  className,
  count = 6,
  colorClass = "bg-amber-500 dark:bg-amber-400",
}: WaveRateDotsProps) {
  // 根据速率动态改变波形活跃度
  const isHigh = rateBytesPerSec > 1024 * 1024 * 2; // > 2MB/s

  return (
    <div className={cn("flex items-center gap-[3px] select-none shrink-0", className)}>
      {Array.from({ length: count }).map((_, idx) => {
        const opacity = active
          ? idx % 3 === 0
            ? "opacity-100"
            : idx % 2 === 0
            ? "opacity-75"
            : "opacity-40"
          : "opacity-20";
        return (
          <div
            key={idx}
            className={cn(
              "w-[3px] h-[3px] rounded-full transition-all",
              colorClass,
              opacity,
              isHigh && "animate-pulse",
            )}
            style={{ animationDelay: `${idx * 80}ms` }}
          />
        );
      })}
    </div>
  );
}
