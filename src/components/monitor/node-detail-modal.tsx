"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { FlagIcon } from "./flag-icon";
import { HistoryPoint, MonitorNode, NodeHistoryResponse } from "./types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

interface NodeDetailModalProps {
  node: MonitorNode | null;
  isOpen: boolean;
  onClose: () => void;
  shareToken?: string | null;
  onEdit?: (node: MonitorNode) => void;
  isOwner?: boolean;
}

export function NodeDetailModal({
  node,
  isOpen,
  onClose,
  shareToken,
  onEdit,
  isOwner,
}: NodeDetailModalProps) {
  const [historyData, setHistoryData] = useState<HistoryPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showLossStrip, setShowLossStrip] = useState(true);
  const [smoothCurve, setSmoothCurve] = useState(true);
  const [activeTab, setActiveTab] = useState<"ping" | "resources">("ping");

  const nodeId = node?.id;

  // 加载 24h 历史时序数据
  const fetchHistory = useCallback(async () => {
    if (!nodeId) return;
    setIsLoading(true);
    try {
      const url = shareToken
        ? `/api/monitor/nodes/${nodeId}/history?hours=24&share=${encodeURIComponent(shareToken)}`
        : `/api/monitor/nodes/${nodeId}/history?hours=24`;
      const token = typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const res = await fetch(url, { headers });
      if (res.ok) {
        const json: NodeHistoryResponse = await res.json();
        setHistoryData(json.points || []);
      }
    } catch {
      // 忽略网络错误
    } finally {
      setIsLoading(false);
    }
  }, [nodeId, shareToken]);

  useEffect(() => {
    if (isOpen && nodeId) {
      void fetchHistory();
    } else {
      setHistoryData([]);
    }
  }, [isOpen, nodeId, fetchHistory]);

  // 获取最大延迟以缩放 Y 轴
  const maxLatency = useMemo(() => {
    let m = 100;
    for (const pt of historyData) {
      for (const ps of pt.ping_stats || []) {
        if (ps.latency_ms > m) m = ps.latency_ms;
      }
    }
    return Math.ceil((m * 1.2) / 20) * 20; // 留 20% 余量并规整为 20 的倍数
  }, [historyData]);

  // 生成 SVG 折线路径
  const generatePath = useCallback(
    (carrierName: string): string => {
      if (historyData.length < 2) return "";
      const w = 700;
      const h = 200;
      const padding = 20;

      const coords = historyData.map((p, idx) => {
        const x = padding + (idx / (historyData.length - 1)) * (w - 2 * padding);
        const stat = (p.ping_stats || []).find((s) => s.name === carrierName);
        const val = stat ? stat.latency_ms : 0;
        const y = h - padding - (val / maxLatency) * (h - 2 * padding);
        return { x, y };
      });

      if (smoothCurve) {
        // 贝塞尔平滑
        let d = `M ${coords[0].x} ${coords[0].y}`;
        for (let i = 0; i < coords.length - 1; i++) {
          const x_mid = (coords[i].x + coords[i + 1].x) / 2;
          const y_mid = (coords[i].y + coords[i + 1].y) / 2;
          d += ` Q ${coords[i].x} ${coords[i].y} ${x_mid} ${y_mid}`;
        }
        d += ` T ${coords[coords.length - 1].x} ${coords[coords.length - 1].y}`;
        return d;
      } else {
        return coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
      }
    },
    [historyData, maxLatency, smoothCurve],
  );

  // 生成系统资源 (CPU/RAM) 折线路径
  const generateResourcePath = useCallback(
    (key: "cpu_percent" | "ram_percent"): string => {
      if (historyData.length < 2) return "";
      const w = 700;
      const h = 200;
      const padding = 20;

      return historyData
        .map((p, idx) => {
          const x = padding + (idx / (historyData.length - 1)) * (w - 2 * padding);
          const val = p[key] || 0;
          const y = h - padding - (val / 100) * (h - 2 * padding);
          return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
        })
        .join(" ");
    },
    [historyData],
  );

  if (!node) return null;

  const { metrics } = node;
  const pingStats = metrics.ping_stats || [];
  const statCT = pingStats.find((p) => p.name === "电信");
  const statCU = pingStats.find((p) => p.name === "联通");
  const statCM = pingStats.find((p) => p.name === "移动");

  // 智能解析系统发行版与内核展示
  const isGenericLinux = node.os_type.toLowerCase() === "linux";
  const isKernelPattern = Boolean(
    node.os_version &&
      (node.os_version.includes("-generic") ||
        node.os_version.includes("-amd64") ||
        node.os_version.includes("-pve") ||
        node.os_version.includes("-lts") ||
        node.os_version.includes("-arch") ||
        node.os_version.split(".").length >= 3),
  );

  const kernelDisplay = node.metrics?.kernel_version || (isKernelPattern ? node.os_version : null);
  const versionDisplay = isKernelPattern ? null : node.os_version;
  const distroDisplay = isGenericLinux
    ? (versionDisplay ? `Linux ${versionDisplay}` : "Linux")
    : `${node.os_type.charAt(0).toUpperCase() + node.os_type.slice(1)}${versionDisplay ? ` ${versionDisplay}` : ""}`;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl sm:max-w-4xl p-0 gap-0 overflow-hidden rounded-3xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xl">
        {/* 顶部标题栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <FlagIcon country={node.country} className="w-5 h-3.5 rounded-2xs object-cover shadow-xs" />
            <div>
              <DialogTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <span>{node.name}</span>
                <span
                  className={cn(
                    "w-2 h-2 rounded-full inline-block",
                    node.is_online ? "bg-emerald-500 animate-pulse" : "bg-rose-500",
                  )}
                />
              </DialogTitle>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400 font-mono mt-0.5">
                <span>{distroDisplay}</span>
                {kernelDisplay && (
                  <>
                    <span>·</span>
                    <span title="Linux 内核版本">内核 {kernelDisplay}</span>
                  </>
                )}
                <span>·</span>
                <span>{node.cpu_cores || 1} 核 CPU</span>
                {node.arch && (
                  <>
                    <span>·</span>
                    <span className="uppercase">{node.arch}</span>
                  </>
                )}
                <span>·</span>
                <span>在线 {node.uptime_days} 天</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isOwner && onEdit && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onClose();
                  onEdit(node);
                }}
                className="h-8 gap-1 text-xs px-2.5 rounded-xl border-slate-200/80 dark:border-slate-800 font-medium text-slate-700 dark:text-slate-300"
              >
                <Settings className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">编辑配置</span>
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={fetchHistory}
              disabled={isLoading}
              className="h-8 gap-1 text-xs px-2.5 rounded-xl border-slate-200/80 dark:border-slate-800 font-medium"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin")} />
              <span className="hidden sm:inline">刷新图表</span>
            </Button>
          </div>
        </div>

        {/* 标签页切换 */}
        <div className="flex items-center justify-between px-6 pt-3 select-none">
          <div className="flex items-center gap-1.5 p-0.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200/60 dark:border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab("ping")}
              className={cn(
                "px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer",
                activeTab === "ping"
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-xs"
                  : "text-slate-500 hover:text-slate-900 dark:hover:text-slate-200",
              )}
            >
              Ping 延迟与丢包图表
            </button>
            <button
              onClick={() => setActiveTab("resources")}
              className={cn(
                "px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer",
                activeTab === "resources"
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-xs"
                  : "text-slate-500 hover:text-slate-900 dark:hover:text-slate-200",
              )}
            >
              系统负载与网络曲线
            </button>
          </div>

          {activeTab === "ping" && (
            <div className="hidden sm:flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showLossStrip}
                  onChange={(e) => setShowLossStrip(e.target.checked)}
                  className="rounded text-blue-600 focus:ring-0 cursor-pointer"
                />
                <span>丢包色带</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={smoothCurve}
                  onChange={(e) => setSmoothCurve(e.target.checked)}
                  className="rounded text-blue-600 focus:ring-0 cursor-pointer"
                />
                <span>削峰平滑</span>
              </label>
            </div>
          )}
        </div>

        {/* 图表主区域 */}
        <div className="p-6">
          {activeTab === "ping" ? (
            <div>
              {/* 运营商当前指标胶囊 */}
              <div className="flex flex-wrap items-center gap-2 mb-4 font-mono text-xs">
                {/* 电信 */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/60 dark:bg-rose-950/30">
                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                  <span className="font-sans font-bold text-slate-700 dark:text-slate-200">电信</span>
                  <span
                    className={cn(
                      "font-bold",
                      statCT && statCT.loss_rate < 100 && statCT.latency_ms > 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-rose-500",
                    )}
                  >
                    {statCT && statCT.loss_rate < 100 && statCT.latency_ms > 0
                      ? `${statCT.latency_ms.toFixed(1)} ms`
                      : statCT && statCT.loss_rate >= 100
                      ? "超时"
                      : "--"}
                  </span>
                  <span
                    className={cn(
                      statCT && statCT.loss_rate >= 10
                        ? "text-rose-500 font-bold"
                        : statCT && statCT.loss_rate > 0
                        ? "text-amber-500 font-bold dark:text-amber-400"
                        : "text-slate-400",
                    )}
                  >
                    {statCT ? `${statCT.loss_rate.toFixed(1)}%` : "0%"}
                  </span>
                </div>

                {/* 联通 */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-lime-200 dark:border-lime-900/60 bg-lime-50/60 dark:bg-lime-950/30">
                  <span className="w-2 h-2 rounded-full bg-lime-500" />
                  <span className="font-sans font-bold text-slate-700 dark:text-slate-200">联通</span>
                  <span
                    className={cn(
                      "font-bold",
                      statCU && statCU.loss_rate < 100 && statCU.latency_ms > 0
                        ? "text-lime-600 dark:text-lime-400"
                        : "text-rose-500",
                    )}
                  >
                    {statCU && statCU.loss_rate < 100 && statCU.latency_ms > 0
                      ? `${statCU.latency_ms.toFixed(1)} ms`
                      : statCU && statCU.loss_rate >= 100
                      ? "超时"
                      : "--"}
                  </span>
                  <span
                    className={cn(
                      statCU && statCU.loss_rate >= 10
                        ? "text-rose-500 font-bold"
                        : statCU && statCU.loss_rate > 0
                        ? "text-amber-500 font-bold dark:text-amber-400"
                        : "text-slate-400",
                    )}
                  >
                    {statCU ? `${statCU.loss_rate.toFixed(1)}%` : "0%"}
                  </span>
                </div>

                {/* 移动 */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-sky-200 dark:border-sky-900/60 bg-sky-50/60 dark:bg-sky-950/30">
                  <span className="w-2 h-2 rounded-full bg-sky-500" />
                  <span className="font-sans font-bold text-slate-700 dark:text-slate-200">移动</span>
                  <span
                    className={cn(
                      "font-bold",
                      statCM && statCM.loss_rate < 100 && statCM.latency_ms > 0
                        ? "text-sky-600 dark:text-sky-400"
                        : "text-rose-500",
                    )}
                  >
                    {statCM && statCM.loss_rate < 100 && statCM.latency_ms > 0
                      ? `${statCM.latency_ms.toFixed(1)} ms`
                      : statCM && statCM.loss_rate >= 100
                      ? "超时"
                      : "--"}
                  </span>
                  <span
                    className={cn(
                      statCM && statCM.loss_rate >= 10
                        ? "text-rose-500 font-bold"
                        : statCM && statCM.loss_rate > 0
                        ? "text-amber-500 font-bold dark:text-amber-400"
                        : "text-slate-400",
                    )}
                  >
                    {statCM ? `${statCM.loss_rate.toFixed(1)}%` : "0%"}
                  </span>
                </div>
              </div>

              {/* 丢包连续色带条 */}
              {showLossStrip && historyData.length > 0 && (
                <div className="flex flex-col gap-1.5 my-3 p-2 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  {["电信", "联通", "移动"].map((cname) => (
                    <div key={cname} className="flex items-center gap-2 text-[10px] font-mono">
                      <span className="w-6 text-slate-400 shrink-0 font-sans">{cname}</span>
                      <div className="flex-1 flex h-[5px] rounded-[1px] overflow-hidden gap-[1px] bg-slate-200 dark:bg-slate-700">
                        {historyData.map((pt, i) => {
                          const s = (pt.ping_stats || []).find((item) => item.name === cname);
                          const loss = s ? s.loss_rate : 0;
                          const lat = s ? s.latency_ms : 0;
                          const color =
                            loss >= 10
                              ? "bg-red-500"
                              : loss > 0
                              ? "bg-amber-500"
                              : lat < 60
                              ? "bg-emerald-500"
                              : lat < 120
                              ? "bg-lime-500"
                              : lat < 180
                              ? "bg-amber-500"
                              : "bg-orange-500";
                          return (
                            <div
                              key={i}
                              className={cn("flex-1 h-full", color)}
                              title={`${cname}: ${lat > 0 && loss < 100 ? `${lat.toFixed(1)}ms` : loss >= 100 ? "超时" : "--"} (丢包: ${loss.toFixed(1)}%)`}
                            />
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 24 小时 Ping 延迟曲线 SVG */}
              <div className="relative w-full h-[220px] rounded-2xl bg-slate-50/70 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800/80 p-2 overflow-hidden">
                {historyData.length > 1 ? (
                  <svg viewBox="0 0 700 200" className="w-full h-full overflow-visible">
                    {/* Y 轴背景刻度线 */}
                    {[0.25, 0.5, 0.75, 1].map((frac, idx) => {
                      const y = 20 + (1 - frac) * 160;
                      const val = Math.round(frac * maxLatency);
                      return (
                        <g key={idx}>
                          <line x1="20" y1={y} x2="680" y2={y} stroke="currentColor" className="text-slate-200 dark:text-slate-800" strokeDasharray="3 3" />
                          <text x="10" y={y + 4} textAnchor="end" className="fill-slate-400 text-[9px] font-mono">
                            {val}
                          </text>
                        </g>
                      );
                    })}

                    {/* 电信折线 */}
                    <path d={generatePath("电信")} fill="none" stroke="#F43F5E" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
                    {/* 联通折线 */}
                    <path d={generatePath("联通")} fill="none" stroke="#84CC16" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
                    {/* 移动折线 */}
                    <path d={generatePath("移动")} fill="none" stroke="#0EA5E9" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
                  </svg>
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-400 text-xs font-mono">
                    {isLoading ? "正在加载 24 小时历史采样..." : "暂无足够时序样本"}
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* 系统资源曲线 */
            <div>
              <div className="flex items-center gap-4 mb-4 text-xs font-mono">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                  <span className="font-sans text-slate-600 dark:text-slate-300">CPU 使用率 (%)</span>
                  <span className="font-bold text-blue-600 dark:text-blue-400">{Math.round(metrics?.cpu_percent ?? 0)}%</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
                  <span className="font-sans text-slate-600 dark:text-slate-300">内存占用 (%)</span>
                  <span className="font-bold text-indigo-600 dark:text-indigo-400">
                    {Math.round((metrics.ram_used_bytes / (metrics.ram_total_bytes || 1)) * 100)}%
                  </span>
                </div>
              </div>

              <div className="relative w-full h-[220px] rounded-2xl bg-slate-50/70 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800/80 p-2 overflow-hidden">
                {historyData.length > 1 ? (
                  <svg viewBox="0 0 700 200" className="w-full h-full overflow-visible">
                    {[25, 50, 75, 100].map((val, idx) => {
                      const y = 20 + (1 - val / 100) * 160;
                      return (
                        <g key={idx}>
                          <line x1="20" y1={y} x2="680" y2={y} stroke="currentColor" className="text-slate-200 dark:text-slate-800" strokeDasharray="3 3" />
                          <text x="10" y={y + 4} textAnchor="end" className="fill-slate-400 text-[9px] font-mono">
                            {val}%
                          </text>
                        </g>
                      );
                    })}

                    {/* CPU 曲线 */}
                    <path d={generateResourcePath("cpu_percent")} fill="none" stroke="#3B82F6" strokeWidth="2.2" strokeLinecap="round" />
                    {/* RAM 曲线 */}
                    <path d={generateResourcePath("ram_percent")} fill="none" stroke="#6366F1" strokeWidth="2.2" strokeLinecap="round" />
                  </svg>
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-400 text-xs font-mono">
                    {isLoading ? "正在加载 24 小时资源历史..." : "暂无足够时序样本"}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
