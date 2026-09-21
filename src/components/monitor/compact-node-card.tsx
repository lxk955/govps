"use client";

import React from "react";
import { Cpu, Database, RotateCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { FlagIcon } from "./flag-icon";
import { OsLogo } from "./os-logo";
import { PingStrip } from "./ping-strip";
import { MonitorNode } from "./types";
import { formatRate } from "./overview-header";

interface CompactNodeCardProps {
  node: MonitorNode;
  onClick?: (node: MonitorNode) => void;
}

export function CompactNodeCard({ node, onClick }: CompactNodeCardProps) {
  const { metrics } = node;
  const upRate = formatRate(metrics.net_tx_rate);
  const downRate = formatRate(metrics.net_rx_rate);

  const ramPercent =
    metrics.ram_total_bytes > 0
      ? Math.round((metrics.ram_used_bytes / metrics.ram_total_bytes) * 100)
      : 0;

  const pingStats = metrics.ping_stats || [];
  const statCT = pingStats.find((p) => p.name === "电信");
  const statCU = pingStats.find((p) => p.name === "联通");
  const statCM = pingStats.find((p) => p.name === "移动");

  return (
    <div
      onClick={() => onClick?.(node)}
      className={cn(
        "group flex flex-col justify-between rounded-2xl bg-white dark:bg-slate-900 border p-3.5 transition-all duration-200 cursor-pointer shadow-xs select-none",
        node.is_online
          ? "border-slate-200/80 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-md"
          : "border-rose-200/60 dark:border-rose-950/60 opacity-85",
      )}
    >
      {/* 头部 */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FlagIcon country={node.country} className="w-4 h-3 rounded-2xs shrink-0" />
          <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100 truncate">
            {node.name}
          </h4>
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full shrink-0",
              node.is_online ? "bg-emerald-500 animate-pulse" : "bg-rose-500",
            )}
          />
        </div>
        <div title={`操作系统: ${node.os_type.toUpperCase()}`} className="shrink-0">
          <OsLogo os={node.os_type} className="w-3.5 h-3.5 text-slate-400" />
        </div>
      </div>

      {/* 资源简明进度 */}
      <div className="grid grid-cols-2 gap-2 mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 text-xs font-mono">
        <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/60 px-2 py-1 rounded-lg">
          <div className="flex items-center gap-1 text-[11px] text-slate-500">
            <Cpu className="w-3 h-3 text-blue-500" />
            <span>CPU</span>
          </div>
          <span className="font-bold text-slate-800 dark:text-slate-200 text-[11px]">
            {Math.round(metrics?.cpu_percent ?? 0)}%
          </span>
        </div>

        <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/60 px-2 py-1 rounded-lg">
          <div className="flex items-center gap-1 text-[11px] text-slate-500">
            <Database className="w-3 h-3 text-indigo-500" />
            <span>RAM</span>
          </div>
          <span className="font-bold text-slate-800 dark:text-slate-200 text-[11px]">
            {ramPercent}%
          </span>
        </div>
      </div>

      {/* 实时速率 */}
      <div className="flex items-center justify-between mt-2.5 px-1 text-xs font-mono">
        <div className="flex items-center gap-1">
          <span className="text-slate-400 font-sans text-[11px]">↑</span>
          <span className="font-bold text-amber-600 dark:text-amber-500 text-[11px]">
            {upRate.full}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-slate-400 font-sans text-[11px]">↓</span>
          <span className="font-bold text-amber-600 dark:text-amber-500 text-[11px]">
            {downRate.full}
          </span>
        </div>
      </div>

      {/* 精简 Ping 色带 */}
      <div className="flex flex-col gap-1.5 mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800">
        <PingStrip carrierName="电信" currentStat={statCT} history={metrics.ping_history} maxBlocks={20} />
        <PingStrip carrierName="联通" currentStat={statCU} history={metrics.ping_history} maxBlocks={20} />
        <PingStrip carrierName="移动" currentStat={statCM} history={metrics.ping_history} maxBlocks={20} />
      </div>

      {/* 底部 */}
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] text-slate-400 font-mono">
        <div className="flex items-center gap-1">
          <RotateCw className="w-2.5 h-2.5" />
          <span>{node.uptime_days}d 在线</span>
        </div>
        {node.price !== null && (
          <span className="font-bold text-emerald-600 dark:text-emerald-400">
            {node.currency === "CNY" ? "¥" : "$"}{node.price}
          </span>
        )}
      </div>
    </div>
  );
}
