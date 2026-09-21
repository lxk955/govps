"use client";

import React from "react";
import { DollarSign, TrendingUp, Wifi } from "lucide-react";
import { cn } from "@/lib/utils";
import { MonitorSummary } from "./types";

interface OverviewHeaderProps {
  summary: MonitorSummary;
}

export function formatRate(bytesPerSec: number): { value: string; unit: string; full: string } {
  if (isNaN(bytesPerSec) || bytesPerSec <= 0) return { value: "0", unit: "B/s", full: "0 B/s" };
  const k = 1024;
  if (bytesPerSec < k) return { value: bytesPerSec.toFixed(0), unit: "B/s", full: `${bytesPerSec.toFixed(0)} B/s` };
  if (bytesPerSec < k * k) {
    const val = (bytesPerSec / k).toFixed(1);
    return { value: val, unit: "KB/s", full: `${val} KB/s` };
  }
  if (bytesPerSec < k * k * k) {
    const val = (bytesPerSec / (k * k)).toFixed(1);
    return { value: val, unit: "MB/s", full: `${val} MB/s` };
  }
  const val = (bytesPerSec / (k * k * k)).toFixed(2);
  return { value: val, unit: "GB/s", full: `${val} GB/s` };
}

export function formatBytes(bytes: number): { value: string; unit: string; full: string } {
  if (isNaN(bytes) || bytes <= 0) return { value: "0", unit: "B", full: "0 B" };
  const k = 1024;
  if (bytes < k) return { value: `${bytes}`, unit: "B", full: `${bytes} B` };
  if (bytes < k * k) return { value: (bytes / k).toFixed(1), unit: "KB", full: `${(bytes / k).toFixed(1)} KB` };
  if (bytes < k * k * k) return { value: (bytes / (k * k)).toFixed(1), unit: "MB", full: `${(bytes / (k * k)).toFixed(1)} MB` };
  if (bytes < k * k * k * k) return { value: (bytes / (k * k * k)).toFixed(1), unit: "GB", full: `${(bytes / (k * k * k)).toFixed(1)} GB` };
  const val = (bytes / (k * k * k * k)).toFixed(1);
  return { value: val, unit: "TB", full: `${val} TB` };
}

export function OverviewHeader({ summary }: OverviewHeaderProps) {
  const { online_count, total_count, online_segments, bandwidth, traffic, asset } = summary;

  const totalRate = formatRate(bandwidth.total_rate);
  const rxRate = formatRate(bandwidth.rx_rate);
  const txRate = formatRate(bandwidth.tx_rate);

  const totalTraffic = formatBytes(traffic.total);
  const rxTraffic = formatBytes(traffic.rx_total);
  const txTraffic = formatBytes(traffic.tx_total);

  // 带宽爆发状态判定
  const isHighTraffic = bandwidth.total_rate > 1024 * 1024 * 5; // > 5MB/s

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 select-none">
      {/* 1. 在线节点 */}
      <div className="relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800/80 p-4 shadow-xs flex flex-col justify-between min-h-[110px]">
        <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
          <span>在线节点</span>
          <div className="flex items-center gap-1.5 text-slate-400 dark:text-slate-500">
            <span
              className={cn(
                "inline-block w-2 h-2 rounded-full",
                online_count > 0 ? "bg-emerald-500 animate-pulse" : "bg-slate-400",
              )}
            />
          </div>
        </div>

        <div className="flex items-baseline gap-1.5 my-1.5">
          <span className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50 font-mono">
            {online_count}
          </span>
          <span className="text-sm font-semibold text-slate-400 dark:text-slate-500">
            / {total_count}
          </span>
        </div>

        {/* 分段状态方块条 */}
        <div className="flex items-center gap-1.5 w-full h-[7px] mt-1">
          {online_segments.length > 0 ? (
            online_segments.map((isOnline, i) => (
              <div
                key={i}
                className={cn(
                  "flex-1 h-full rounded-xs transition-colors",
                  isOnline
                    ? "bg-emerald-500 dark:bg-emerald-400"
                    : "bg-rose-500 dark:bg-rose-500",
                )}
                title={isOnline ? "节点正常在线" : "节点掉线/离线"}
              />
            ))
          ) : (
            <div className="w-full h-full bg-slate-100 dark:bg-slate-800 rounded-xs" />
          )}
        </div>
      </div>

      {/* 2. 实时带宽 */}
      <div className="relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800/80 p-4 shadow-xs flex flex-col justify-between min-h-[110px]">
        <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
          <span>实时带宽</span>
          <Wifi className="w-3.5 h-3.5 text-amber-500/80" />
        </div>

        <div className="flex items-baseline gap-1 my-1.5">
          <span className="text-3xl font-extrabold tracking-tight text-amber-600 dark:text-amber-500 font-mono">
            {totalRate.value}
          </span>
          <span className="text-sm font-bold text-amber-600/80 dark:text-amber-500/80">
            {totalRate.unit}
          </span>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
          <div className="font-mono flex items-center gap-1">
            <span>↑ {txRate.full}</span>
            <span className="text-slate-300 dark:text-slate-600">·</span>
            <span>↓ {rxRate.full}</span>
          </div>
          {isHighTraffic && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
              爆发
            </span>
          )}
        </div>
      </div>

      {/* 3. 累计流量 */}
      <div className="relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800/80 p-4 shadow-xs flex flex-col justify-between min-h-[110px]">
        <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
          <span>累计流量</span>
          <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
        </div>

        <div className="flex items-baseline gap-1 my-1.5">
          <span className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50 font-mono">
            {totalTraffic.value}
          </span>
          <span className="text-sm font-bold text-slate-500 dark:text-slate-400">
            {totalTraffic.unit}
          </span>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
          <div className="font-mono flex items-center gap-1">
            <span>↑ {txTraffic.full}</span>
            <span className="text-slate-300 dark:text-slate-600">·</span>
            <span>↓ {rxTraffic.full}</span>
          </div>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
            海量
          </span>
        </div>
      </div>

      {/* 4. 资产概览 */}
      <div className="relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800/80 p-4 shadow-xs flex flex-col justify-between min-h-[110px]">
        <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
          <span>资产概览</span>
          <div className="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-950 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
            <DollarSign className="w-2.5 h-2.5" />
          </div>
        </div>

        <div className="flex items-baseline gap-1 my-1.5">
          <span className="text-xl font-bold text-slate-600 dark:text-slate-300 font-mono">
            ¥
          </span>
          <span className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50 font-mono">
            {asset.total_cost_cny.toFixed(2)}
          </span>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
          <span>实时汇率计算</span>
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
            月度均摊
          </span>
        </div>
      </div>
    </div>
  );
}
