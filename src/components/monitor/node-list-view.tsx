"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { FlagIcon } from "./flag-icon";
import { OsLogo } from "./os-logo";
import { MonitorNode } from "./types";
import { formatBytes, formatRate } from "./overview-header";

interface NodeListViewProps {
  nodes: MonitorNode[];
  onSelectNode: (node: MonitorNode) => void;
}

export function NodeListView({ nodes, onSelectNode }: NodeListViewProps) {
  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs select-none">
      <table className="w-full text-left text-xs border-collapse min-w-[850px]">
        <thead>
          <tr className="border-b border-slate-100 dark:border-slate-800 text-slate-400 font-semibold bg-slate-50/50 dark:bg-slate-800/30">
            <th className="py-3 px-4">节点</th>
            <th className="py-3 px-3">系统</th>
            <th className="py-3 px-3">分组</th>
            <th className="py-3 px-3">CPU</th>
            <th className="py-3 px-3">内存</th>
            <th className="py-3 px-3">磁盘</th>
            <th className="py-3 px-3">实时速率</th>
            <th className="py-3 px-3">累计流量</th>
            <th className="py-3 px-3">三网延迟</th>
            <th className="py-3 px-3">运行 / 到期</th>
            <th className="py-3 px-4 text-right">费用</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono">
          {nodes.map((node) => {
            const { metrics } = node;
            const upRate = formatRate(metrics.net_tx_rate);
            const downRate = formatRate(metrics.net_rx_rate);

            const ramPercent =
              metrics.ram_total_bytes > 0
                ? Math.round((metrics.ram_used_bytes / metrics.ram_total_bytes) * 100)
                : 0;
            const diskPercent =
              metrics.disk_total_bytes > 0
                ? Math.round((metrics.disk_used_bytes / metrics.disk_total_bytes) * 100)
                : 0;

            const pingStats = metrics.ping_stats || [];
            const pCT = pingStats.find((p) => p.name === "电信")?.latency_ms || 0;
            const pCU = pingStats.find((p) => p.name === "联通")?.latency_ms || 0;
            const pCM = pingStats.find((p) => p.name === "移动")?.latency_ms || 0;

            return (
              <tr
                key={node.id}
                onClick={() => onSelectNode(node)}
                className="hover:bg-slate-50/80 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
              >
                {/* 节点 */}
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <FlagIcon country={node.country} className="w-4 h-3 rounded-2xs shrink-0" />
                    <span className="font-bold text-slate-900 dark:text-slate-100 font-sans">
                      {node.name}
                    </span>
                    <span
                      className={cn(
                        "w-1.5 h-1.5 rounded-full shrink-0",
                        node.is_online ? "bg-emerald-500 animate-pulse" : "bg-rose-500",
                      )}
                    />
                  </div>
                </td>

                {/* 系统 */}
                <td className="py-3 px-3">
                  <div className="flex items-center gap-1.5 font-sans capitalize text-slate-600 dark:text-slate-400">
                    <OsLogo os={node.os_type} className="w-3.5 h-3.5 shrink-0" />
                    <span>{node.os_type}</span>
                  </div>
                </td>

                {/* 分组 */}
                <td className="py-3 px-3">
                  <span className="px-2 py-0.5 rounded text-[10px] font-sans font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {node.group_name}
                  </span>
                </td>

                {/* CPU */}
                <td className="py-3 px-3">
                  <div className="flex flex-col">
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      {Math.round(metrics?.cpu_percent ?? 0)}%
                    </span>
                    <span className="text-[10px] text-slate-400 font-sans">{node.cpu_cores || 1} 核</span>
                  </div>
                </td>

                {/* 内存 */}
                <td className="py-3 px-3">
                  <div className="flex flex-col">
                    <span className="font-bold text-slate-800 dark:text-slate-200">{ramPercent}%</span>
                    <span className="text-[10px] text-slate-400">
                      {formatBytes(metrics.ram_used_bytes).full}
                    </span>
                  </div>
                </td>

                {/* 磁盘 */}
                <td className="py-3 px-3">
                  <div className="flex flex-col">
                    <span className="font-bold text-slate-800 dark:text-slate-200">{diskPercent}%</span>
                    <span className="text-[10px] text-slate-400">
                      {formatBytes(metrics.disk_used_bytes).full}
                    </span>
                  </div>
                </td>

                {/* 实时速率 */}
                <td className="py-3 px-3">
                  <div className="flex flex-col text-[11px] text-amber-600 dark:text-amber-500 font-bold">
                    <span>↑ {upRate.full}</span>
                    <span>↓ {downRate.full}</span>
                  </div>
                </td>

                {/* 累计流量 */}
                <td className="py-3 px-3 text-[11px] text-slate-500 dark:text-slate-400">
                  <div className="flex flex-col">
                    <span>出: {formatBytes(metrics.net_tx_total).full}</span>
                    <span>入: {formatBytes(metrics.net_rx_total).full}</span>
                  </div>
                </td>

                {/* 三网延迟 */}
                <td className="py-3 px-3 text-[11px]">
                  <div className="flex items-center gap-1.5">
                    <span className="text-emerald-500 font-bold" title="电信">
                      {pCT > 0 ? `${Math.round(pCT)}ms` : "--"}
                    </span>
                    <span className="text-slate-300">/</span>
                    <span className="text-lime-500 font-bold" title="联通">
                      {pCU > 0 ? `${Math.round(pCU)}ms` : "--"}
                    </span>
                    <span className="text-slate-300">/</span>
                    <span className="text-amber-500 font-bold" title="移动">
                      {pCM > 0 ? `${Math.round(pCM)}ms` : "--"}
                    </span>
                  </div>
                </td>

                {/* 运行 / 到期 */}
                <td className="py-3 px-3 text-[11px] text-slate-500 dark:text-slate-400 font-sans">
                  <div>{node.uptime_days} 天在线</div>
                  {node.days_left !== null && (
                    <div className="text-[10px] text-amber-600 dark:text-amber-500">
                      余 {node.days_left} 天到期
                    </div>
                  )}
                </td>

                {/* 费用 */}
                <td className="py-3 px-4 text-right">
                  {node.price !== null ? (
                    <span className="inline-block px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
                      {node.currency === "CNY" ? "¥" : "$"}{node.price}
                    </span>
                  ) : (
                    <span className="text-slate-400">--</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
