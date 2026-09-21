"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { FlagIcon } from "./flag-icon";
import { OsLogo } from "./os-logo";
import { MonitorNode } from "./types";
import { formatRate } from "./overview-header";

interface MiniNodeCardProps {
  node: MonitorNode;
  onClick?: (node: MonitorNode) => void;
}

export function MiniNodeCard({ node, onClick }: MiniNodeCardProps) {
  const { metrics } = node;
  const upRate = formatRate(metrics.net_tx_rate);
  const downRate = formatRate(metrics.net_rx_rate);

  // 平均延迟
  const pingStats = metrics.ping_stats || [];
  const validPings = pingStats.filter((p) => p.latency_ms > 0);
  const avgPing =
    validPings.length > 0
      ? Math.round(validPings.reduce((acc, p) => acc + p.latency_ms, 0) / validPings.length)
      : 0;

  return (
    <div
      onClick={() => onClick?.(node)}
      className={cn(
        "group flex items-center justify-between rounded-xl bg-white dark:bg-slate-900 border p-3 transition-all duration-200 cursor-pointer shadow-xs select-none gap-3",
        node.is_online
          ? "border-slate-200/80 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-sm"
          : "border-rose-200/60 dark:border-rose-950/60 opacity-80",
      )}
    >
      {/* 左侧：国旗与名称 */}
      <div className="flex items-center gap-2.5 min-w-0">
        <FlagIcon country={node.country} className="w-4 h-3 rounded-2xs shrink-0" />
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-xs text-slate-900 dark:text-slate-100 truncate">
              {node.name}
            </span>
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full shrink-0",
                node.is_online ? "bg-emerald-500 animate-pulse" : "bg-rose-500",
              )}
            />
          </div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5 flex items-center gap-1.5">
            <span>CPU: {Math.round(metrics?.cpu_percent ?? 0)}%</span>
            <span>·</span>
            <span>RAM: {Math.round(((metrics?.ram_used_bytes ?? 0) / (metrics?.ram_total_bytes || 1)) * 100)}%</span>
          </div>
        </div>
      </div>

      {/* 右侧：实时速率与平均延迟 */}
      <div className="flex items-center gap-3 shrink-0 font-mono text-xs">
        <div className="hidden sm:flex flex-col items-end text-[11px]">
          <span className="text-amber-600 dark:text-amber-500 font-bold">↑ {upRate.full}</span>
          <span className="text-amber-600 dark:text-amber-500 font-bold">↓ {downRate.full}</span>
        </div>

        <div className="flex flex-col items-end">
          <span
            className={cn(
              "px-2 py-0.5 rounded-md text-[11px] font-bold",
              avgPing > 0 && avgPing < 80
                ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-400"
                : avgPing < 150
                ? "bg-amber-50 text-amber-600 dark:bg-amber-950/80 dark:text-amber-400"
                : "bg-rose-50 text-rose-600 dark:bg-rose-950/80 dark:text-rose-400",
            )}
          >
            {avgPing > 0 ? `${avgPing}ms` : "--"}
          </span>
        </div>

        <OsLogo os={node.os_type} className="w-3.5 h-3.5 text-slate-400 hidden md:block" />
      </div>
    </div>
  );
}
