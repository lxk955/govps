"use client";

import React, { useState } from "react";
import {
  Calendar,
  Check,
  Copy,
  Cpu,
  Database,
  HardDrive,
  Network,
  RotateCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { FlagIcon } from "./flag-icon";
import { OsLogo } from "./os-logo";
import { PingStrip } from "./ping-strip";
import { SegmentedMeter, WaveRateDots } from "./segmented-meter";
import { MonitorNode } from "./types";
import { formatBytes, formatRate } from "./overview-header";

interface LargeNodeCardProps {
  node: MonitorNode;
  onClick?: (node: MonitorNode) => void;
}

export function LargeNodeCard({ node, onClick }: LargeNodeCardProps) {
  const [copied, setCopied] = useState(false);
  const { metrics } = node;

  const upRate = formatRate(metrics.net_tx_rate);
  const downRate = formatRate(metrics.net_rx_rate);

  const ramUsed = formatBytes(metrics.ram_used_bytes);
  const ramTotal = formatBytes(metrics.ram_total_bytes);

  const diskUsed = formatBytes(metrics.disk_used_bytes);
  const diskTotal = formatBytes(metrics.disk_total_bytes);

  const outTraffic = formatBytes(metrics.net_tx_total);
  const inTraffic = formatBytes(metrics.net_rx_total);

  // 内存百分比
  const ramPercent =
    metrics.ram_total_bytes > 0
      ? Math.round((metrics.ram_used_bytes / metrics.ram_total_bytes) * 100)
      : 0;

  // 磁盘百分比
  const diskPercent =
    metrics.disk_total_bytes > 0
      ? Math.round((metrics.disk_used_bytes / metrics.disk_total_bytes) * 100)
      : 0;

  // 周期流量使用与百分比
  const cycleUsedBytes =
    typeof node.cycle_traffic_used_bytes === "number"
      ? node.cycle_traffic_used_bytes
      : metrics.net_rx_total + metrics.net_tx_total;

  const trafficPercent =
    node.traffic_limit_gb && node.traffic_limit_gb > 0
      ? Math.min(
          100,
          Math.round(
            (cycleUsedBytes / (node.traffic_limit_gb * 1024 * 1024 * 1024)) * 100,
          ),
        )
      : 0;

  const trafficMeterColor =
    trafficPercent >= 90
      ? "bg-rose-500 dark:bg-rose-400"
      : trafficPercent >= 75
        ? "bg-amber-500 dark:bg-amber-400"
        : "bg-emerald-500 dark:bg-emerald-400";

  // 计费周期展示
  const cycleLabels: Record<string, string> = {
    monthly: "/月",
    quarterly: "/季",
    "semi-annually": "/半年",
    annually: "/年",
    biennially: "/两年",
    triennially: "/三年",
  };
  const cycleText = cycleLabels[node.billing_cycle] || `/${node.billing_cycle}`;

  // 运营商实时测速
  const pingStats = metrics.ping_stats || [];
  const statCT = pingStats.find((p) => p.name === "电信");
  const statCU = pingStats.find((p) => p.name === "联通");
  const statCM = pingStats.find((p) => p.name === "移动");

  // 到期提醒
  const isExpiringSoon = node.days_left !== null && node.days_left <= 7;

  return (
    <div
      onClick={() => onClick?.(node)}
      className={cn(
        "group relative flex flex-col justify-between rounded-2xl bg-white dark:bg-slate-900 border p-4 sm:p-5 transition-all duration-200 cursor-pointer shadow-xs select-none",
        node.is_online
          ? "border-slate-200/80 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-md"
          : "border-rose-200/60 dark:border-rose-950/60 opacity-85",
      )}
    >
      {/* 头部：国旗、名称、状态点、公网IP、操作系统图标 */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <FlagIcon country={node.country} className="w-5 h-3.5 rounded-2xs object-cover shadow-2xs shrink-0" />
            <h3 className="font-bold text-base text-slate-900 dark:text-slate-50 truncate">
              {node.name}
            </h3>
            <span
              className={cn(
                "w-2 h-2 rounded-full shrink-0",
                node.is_online ? "bg-emerald-500 animate-pulse" : "bg-rose-500",
              )}
              title={node.is_online ? "在线" : "离线"}
            />
          </div>
          {node.public_ip && (
            <div
              className="inline-flex items-center gap-1.5 self-start px-2 py-0.5 rounded-md bg-slate-100/90 dark:bg-slate-800/80 hover:bg-slate-200/80 dark:hover:bg-slate-700/80 border border-slate-200/60 dark:border-slate-700/60 text-slate-600 dark:text-slate-300 font-mono text-[11px] transition-colors cursor-pointer group/ip"
              title="点击复制 IP"
              onClick={(e) => {
                e.stopPropagation();
                if (node.public_ip) {
                  navigator.clipboard.writeText(node.public_ip);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }
              }}
            >
              <span>{node.public_ip}</span>
              {copied ? (
                <Check className="w-3 h-3 text-emerald-500" />
              ) : (
                <Copy className="w-3 h-3 text-slate-400 group-hover/ip:text-slate-600 dark:group-hover/ip:text-slate-200" />
              )}
            </div>
          )}
        </div>

        {/* 操作系统徽标 */}
        <div
          className="p-1 rounded-lg bg-slate-50 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-800 shrink-0"
          title={`操作系统: ${node.os_type.toUpperCase()}`}
        >
          <OsLogo os={node.os_type} className="w-4 h-4" />
        </div>
      </div>

      {/* 标签胶囊行 */}
      <div className="flex flex-wrap items-center gap-1.5 mt-2">
        <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
          {node.group_name}
        </span>
        {node.tags.map((t, idx) => {
          const isV4V6 = t === "V4" || t === "V6";
          return (
            <span
              key={idx}
              className={cn(
                "px-2 py-0.5 rounded-md text-[10px] font-semibold",
                isV4V6
                  ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200/60 dark:border-emerald-800/60"
                  : "bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 border border-slate-200/60 dark:border-slate-800",
              )}
            >
              {t}
            </span>
          );
        })}
      </div>

      {/* 核心资源指标仪表行 */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 text-xs">
        {/* CPU */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between font-mono">
            <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400 font-sans">
              <Cpu className="w-3 h-3 text-slate-400" />
              <span>CPU</span>
            </div>
            <span className="font-bold text-slate-800 dark:text-slate-200 text-[11px]">
              {(typeof metrics?.cpu_percent === "number" ? metrics.cpu_percent : 0).toFixed(2)} %
            </span>
          </div>
          <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
            {node.cpu_cores || 1} 核
          </div>
          <SegmentedMeter
            percent={metrics?.cpu_percent ?? 0}
            totalBlocks={14}
            colorClass="bg-blue-600 dark:bg-blue-500"
          />
        </div>

        {/* 内存 */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between font-mono">
            <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400 font-sans">
              <Database className="w-3 h-3 text-slate-400" />
              <span>内存</span>
            </div>
            <span className="font-bold text-slate-800 dark:text-slate-200 text-[11px]">
              {ramPercent.toFixed(2)} %
            </span>
          </div>
          <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono truncate">
            {ramUsed.full} / {ramTotal.full}
          </div>
          <SegmentedMeter
            percent={ramPercent}
            totalBlocks={14}
            colorClass="bg-indigo-600 dark:bg-indigo-400"
          />
        </div>

        {/* 磁盘 */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between font-mono">
            <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400 font-sans">
              <HardDrive className="w-3 h-3 text-slate-400" />
              <span>磁盘</span>
            </div>
            <span className="font-bold text-slate-800 dark:text-slate-200 text-[11px]">
              {diskPercent.toFixed(1)} %
            </span>
          </div>
          <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono truncate">
            {diskUsed.full} / {diskTotal.full}
          </div>
          <SegmentedMeter
            percent={diskPercent}
            totalBlocks={14}
            colorClass="bg-amber-500 dark:bg-amber-400"
          />
        </div>

        {/* 负载 */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between font-mono">
            <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400 font-sans">
              <Network className="w-3 h-3 text-slate-400" />
              <span>负载</span>
            </div>
            <span className="font-bold text-slate-800 dark:text-slate-200 text-[11px]">
              {(metrics?.load_1 ?? 0).toFixed(2)}
            </span>
          </div>
          <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
            {(metrics?.load_5 ?? 0).toFixed(2)} / {(metrics?.load_15 ?? 0).toFixed(2)}
          </div>
          <SegmentedMeter
            percent={Math.min(100, (metrics?.load_1 ?? 0) * 50)}
            totalBlocks={14}
            colorClass="bg-rose-500 dark:bg-rose-400"
          />
        </div>
      </div>

      {/* 实时上下行速率 */}
      <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80">
        {/* 上行 */}
        <div className="flex flex-col">
          <div className="flex items-baseline justify-between">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              ↑ 上行
            </span>
            <div className="flex items-baseline gap-0.5 font-mono">
              <span className="text-base font-extrabold text-amber-600 dark:text-amber-500">
                {upRate.value}
              </span>
              <span className="text-[10px] font-bold text-amber-600/80 dark:text-amber-500/80">
                {upRate.unit}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between mt-1">
            <WaveRateDots active={node.is_online} rateBytesPerSec={metrics.net_tx_rate} />
            <span className="text-[9px] text-slate-400 font-sans">● 实时</span>
          </div>
        </div>

        {/* 下行 */}
        <div className="flex flex-col">
          <div className="flex items-baseline justify-between">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              ↓ 下行
            </span>
            <div className="flex items-baseline gap-0.5 font-mono">
              <span className="text-base font-extrabold text-amber-600 dark:text-amber-500">
                {downRate.value}
              </span>
              <span className="text-[10px] font-bold text-amber-600/80 dark:text-amber-500/80">
                {downRate.unit}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between mt-1">
            <WaveRateDots active={node.is_online} rateBytesPerSec={metrics.net_rx_rate} />
            <span className="text-[9px] text-slate-400 font-sans">● 实时</span>
          </div>
        </div>
      </div>

      {/* 累计出入站流量 */}
      <div className="grid grid-cols-2 gap-3 mt-2.5 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
        <div className="flex items-center justify-between">
          <span className="font-sans">网卡累计出站</span>
          <span className="font-semibold text-slate-700 dark:text-slate-300">{outTraffic.full}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="font-sans">网卡累计入站</span>
          <span className="font-semibold text-slate-700 dark:text-slate-300">{inTraffic.full}</span>
        </div>
      </div>

      {/* 本周期流量额度与重置周期 */}
      {node.traffic_limit_gb && (
        <div className="flex flex-col gap-1 mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/80">
          <div className="flex items-center justify-between text-[11px] font-mono select-none">
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300 font-sans">
              <span>本周期已用流量</span>
              <span className="text-[10px] px-1 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                {node.traffic_direction === "out" ? "仅出站" : "双向"}
              </span>
            </div>
            <span className="text-slate-400 text-[10px]">
              {formatBytes(cycleUsedBytes).full} / {node.traffic_limit_gb} GB
              {typeof node.cycle_reset_days_left === "number" && (
                <span className="ml-1 text-slate-500 dark:text-slate-400 font-medium">
                  · {node.cycle_reset_days_left === 0 ? "今天重置" : `${node.cycle_reset_days_left}天后重置`}
                </span>
              )}
            </span>
          </div>
          <SegmentedMeter
            percent={trafficPercent}
            totalBlocks={24}
            colorClass={trafficMeterColor}
            size="sm"
          />
        </div>
      )}

      {/* 三网延迟丢包热力色带 */}
      <div className="flex flex-col gap-2 mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80">
        <PingStrip
          carrierName="电信"
          currentStat={statCT}
          history={metrics.ping_history}
        />
        <PingStrip
          carrierName="联通"
          currentStat={statCU}
          history={metrics.ping_history}
        />
        <PingStrip
          carrierName="移动"
          currentStat={statCM}
          history={metrics.ping_history}
        />
      </div>

      {/* 底部信息栏：在线天数、到期天数、价格徽标 */}
      <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 text-xs font-medium">
        <div className="flex items-center gap-3 text-slate-500 dark:text-slate-400 font-mono text-[11px]">
          <div className="flex items-center gap-1" title="持续运行时间">
            <RotateCw className="w-3 h-3 text-slate-400" />
            <span>在线</span>
            <span className="font-bold text-blue-600 dark:text-blue-400">
              {node.uptime_days}
            </span>
            <span>天</span>
          </div>

          {node.days_left !== null && (
            <div
              className={cn(
                "flex items-center gap-1",
                isExpiringSoon
                  ? "text-red-600 dark:text-red-400 font-bold animate-pulse"
                  : "text-slate-500 dark:text-slate-400",
              )}
              title="距离续费到期时间"
            >
              <Calendar className="w-3 h-3" />
              <span>余</span>
              <span className="font-bold text-amber-600 dark:text-amber-500">
                {node.days_left}
              </span>
              <span>天</span>
            </div>
          )}
        </div>

        {/* 价格胶囊 */}
        {node.price !== null && (
          <div className="inline-flex items-center px-2 py-0.5 rounded-lg text-[11px] font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/80 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/80 font-mono shrink-0">
            <span>
              {node.currency === "CNY" ? "¥" : node.currency === "EUR" ? "€" : "$"}
              {node.price}
              {cycleText}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
