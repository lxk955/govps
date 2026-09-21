"use client";

import React, { useMemo } from "react";
import { cn } from "@/lib/utils";
import { PingTargetStat } from "./types";

interface PingStripProps {
  carrierName: string; // "电信" | "联通" | "移动"
  currentStat?: PingTargetStat;
  history?: PingTargetStat[][];
  maxBlocks?: number;
}

/** 获取延迟对应的色彩等级 */
export function getLatencyColor(latencyMs: number, lossRate: number = 0): {
  bg: string;
  text: string;
  border: string;
} {
  if (lossRate > 0) {
    if (lossRate >= 10) return { bg: "bg-red-500", text: "text-red-500", border: "border-red-500" };
    return { bg: "bg-orange-500", text: "text-orange-500", border: "border-orange-500" };
  }
  if (latencyMs <= 0) {
    return { bg: "bg-slate-200 dark:bg-slate-700", text: "text-slate-400", border: "border-slate-300" };
  }
  if (latencyMs < 50) {
    return { bg: "bg-emerald-500", text: "text-emerald-500", border: "border-emerald-500" };
  }
  if (latencyMs < 90) {
    return { bg: "bg-emerald-400", text: "text-emerald-500 dark:text-emerald-400", border: "border-emerald-400" };
  }
  if (latencyMs < 130) {
    return { bg: "bg-lime-500", text: "text-lime-600 dark:text-lime-400", border: "border-lime-500" };
  }
  if (latencyMs < 170) {
    return { bg: "bg-amber-400", text: "text-amber-500", border: "border-amber-400" };
  }
  if (latencyMs < 220) {
    return { bg: "bg-orange-500", text: "text-orange-500", border: "border-orange-500" };
  }
  return { bg: "bg-rose-500", text: "text-rose-500", border: "border-rose-500" };
}

export function PingStrip({
  carrierName,
  currentStat,
  history = [],
  maxBlocks = 30,
}: PingStripProps) {
  // 提取该运营商在各轮测速中的数据
  const blocks = useMemo(() => {
    const list: Array<{ latency: number; loss: number }> = [];

    for (const round of history) {
      const found = round.find((item) => item.name === carrierName);
      if (found) {
        list.push({ latency: found.latency_ms, loss: found.loss_rate });
      }
    }

    // 若样本不足 maxBlocks，以当前值或历史均值补足
    const targetLatency = currentStat ? currentStat.latency_ms : 0;
    const targetLoss = currentStat ? currentStat.loss_rate : 0;

    while (list.length < maxBlocks) {
      if (targetLatency > 0) {
        list.unshift({ latency: targetLatency, loss: targetLoss });
      } else {
        list.unshift({ latency: 0, loss: 0 });
      }
    }

    return list.slice(-maxBlocks);
  }, [history, carrierName, currentStat, maxBlocks]);

  const latency = currentStat ? currentStat.latency_ms : 0;
  const loss = currentStat ? currentStat.loss_rate : 0;
  const colorTone = getLatencyColor(latency, loss);

  return (
    <div className="flex flex-col gap-1 text-xs">
      <div className="flex items-center justify-between font-mono select-none">
        <span className="text-slate-500 dark:text-slate-400 text-[11px] font-sans font-medium">
          {carrierName}
        </span>
        <div className="flex items-center gap-2.5">
          <span className={cn("font-bold text-[11px]", colorTone.text)}>
            {latency > 0 && loss < 100 ? `${Math.round(latency)} ms` : loss >= 100 ? "超时" : "--"}
          </span>
          <span
            className={cn(
              "font-medium text-[11px]",
              loss > 0 ? "text-red-500 font-bold" : "text-emerald-500 dark:text-emerald-400",
            )}
          >
            {loss.toFixed(1)} %
          </span>
        </div>
      </div>

      {/* 30 格热力色带 */}
      <div
        className="flex items-center gap-[2px] w-full h-[6px] overflow-hidden rounded-xs bg-slate-100 dark:bg-slate-800/80 p-[1px]"
        title={`${carrierName}: ${latency > 0 && loss < 100 ? `${Math.round(latency)}ms` : loss >= 100 ? "超时" : "无数据"}, 丢包: ${loss.toFixed(1)}%`}
      >
        {blocks.map((b, idx) => {
          const c = getLatencyColor(b.latency, b.loss);
          return (
            <div
              key={idx}
              className={cn(
                "flex-1 h-full rounded-[1px] transition-all hover:scale-y-150 hover:brightness-110",
                c.bg,
              )}
            />
          );
        })}
      </div>
    </div>
  );
}
