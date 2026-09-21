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
}

export function SegmentedMeter({
  percent,
  totalBlocks = 16,
  colorClass = "bg-indigo-500 dark:bg-indigo-400",
  bgClass = "bg-slate-100 dark:bg-slate-800",
  className,
  size = "md",
}: SegmentedMeterProps) {
  const safePercent = Math.max(0, Math.min(100, isNaN(percent) ? 0 : percent));
  const filledBlocks = Math.round((safePercent / 100) * totalBlocks);

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
}

export function WaveRateDots({ active = true, rateBytesPerSec = 0, className }: WaveRateDotsProps) {
  // 根据速率动态改变波形活跃度
  const isHigh = rateBytesPerSec > 1024 * 1024 * 2; // > 2MB/s

  return (
    <div className={cn("flex items-center gap-[3px] select-none", className)}>
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((idx) => {
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
              "w-[3.5px] h-[3.5px] rounded-full bg-amber-500 dark:bg-amber-400 transition-all",
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
