"use client";

import React from "react";
import { CircleDollarSign, RotateCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { MonitorSummary } from "./types";
import { getOverviewRating, speedRateColor } from "./overview-ratings";

interface OverviewHeaderProps {
  summary: MonitorSummary;
  onRefresh?: () => void;
  isRefreshing?: boolean;
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
  const val = (bytes / (k * k * k * k)).toFixed(2);
  return { value: val, unit: "TB", full: `${val} TB` };
}

export function OverviewHeader({ summary, onRefresh, isRefreshing }: OverviewHeaderProps) {
  const { online_count, total_count, online_segments, bandwidth, traffic, asset } = summary;

  const totalRate = formatRate(bandwidth.total_rate);
  const rxRate = formatRate(bandwidth.rx_rate);
  const txRate = formatRate(bandwidth.tx_rate);

  const totalTraffic = formatBytes(traffic.total);
  const rxTraffic = formatBytes(traffic.rx_total);
  const txTraffic = formatBytes(traffic.tx_total);

  // 动态评级徽章
  const bandwidthRating = getOverviewRating({ kind: "bandwidth", value: bandwidth.total_rate });
  const trafficRating = getOverviewRating({ kind: "traffic", value: traffic.total });
  const assetRating = getOverviewRating({ kind: "asset", value: asset.total_cost_cny });

  const onlinePct = total_count > 0 ? (online_count / total_count) * 100 : 0;
  const offlineCount = Math.max(0, total_count - online_count);
  const offlinePct = total_count > 0 ? (offlineCount / total_count) * 100 : 0;

  return (
    <div className="select-none mb-4">
      {/* 顶部主标题与操作栏 */}
      <div className="flex items-center justify-between gap-4 mb-4 pt-1">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-[26px] font-extrabold tracking-tight text-[var(--text-primary)] leading-tight">
            GoVPS 探针监控
          </h1>
        </div>

        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={isRefreshing}
              className="w-9 h-9 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--hover-bg)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center justify-center transition-colors shadow-2xs cursor-pointer disabled:opacity-60"
              title="刷新实时数据"
              aria-label="刷新数据"
            >
              <RotateCw className={cn("w-4 h-4", isRefreshing && "animate-spin text-[var(--accent-500)]")} />
            </button>
          )}
        </div>
      </div>

      {/* 4 张概览卡片 */}
      <section className="home-overview" aria-label="监控总览">
        {/* 1. 在线节点 */}
        <article className="overview-card" data-metric="online">
          <div className="overview-card-head">
            <span className="overview-card-label">在线节点</span>
          </div>
          <div className="overview-card-main">
            <p className="overview-card-value">
              {online_count}
              <span className="overview-card-unit">/ {total_count}</span>
            </p>
          </div>
          {total_count >= 5 && total_count <= 12 ? (
            <div className="overview-blocks" role="presentation">
              {Array.from({ length: total_count }, (_, i) => {
                const isOnline =
                  online_segments.length > i
                    ? online_segments[i]
                    : i < online_count;
                return (
                  <span
                    key={i}
                    className={cn(
                      "overview-block",
                      isOnline ? "is-online" : "is-offline",
                    )}
                  />
                );
              })}
            </div>
          ) : (
            <div className="overview-bar" role="presentation">
              <span className="overview-bar-online" style={{ width: `${onlinePct}%` }} />
              <span className="overview-bar-offline" style={{ width: `${offlinePct}%` }} />
            </div>
          )}
        </article>

        {/* 2. 实时带宽 */}
        <article className="overview-card" data-metric="bandwidth">
          <div className="overview-card-head">
            <span className="overview-card-label">实时带宽</span>
          </div>
          <div className="overview-card-main">
            <p
              className="overview-card-value font-mono"
              style={{ color: speedRateColor(totalRate.unit) }}
            >
              {totalRate.value}
              <span className="overview-card-unit font-sans">{totalRate.unit}</span>
            </p>
          </div>
          <div className="overview-card-footer">
            <p className="overview-card-sub" title={`↑ ${txRate.full} · ↓ ${rxRate.full}`}>
              ↑ {txRate.full} · ↓ {rxRate.full}
            </p>
            <span
              className="overview-card-rating"
              data-rating-level={bandwidthRating.level}
              title={bandwidthRating.label}
            >
              {bandwidthRating.label}
            </span>
          </div>
        </article>

        {/* 3. 累计流量 */}
        <article className="overview-card" data-metric="traffic">
          <div className="overview-card-head">
            <span className="overview-card-label">累计流量</span>
          </div>
          <div className="overview-card-main">
            <p className="overview-card-value font-mono">
              {totalTraffic.value}
              <span className="overview-card-unit font-sans">{totalTraffic.unit}</span>
            </p>
          </div>
          <div className="overview-card-footer">
            <p className="overview-card-sub" title={`↑ ${txTraffic.full} · ↓ ${rxTraffic.full}`}>
              ↑ {txTraffic.full} · ↓ {rxTraffic.full}
            </p>
            <span
              className="overview-card-rating"
              data-rating-level={trafficRating.level}
              title={trafficRating.label}
            >
              {trafficRating.label}
            </span>
          </div>
        </article>

        {/* 4. 资产概览 */}
        <article className="overview-card" data-metric="asset">
          <div className="overview-card-head">
            <span className="overview-card-label">资产概览</span>
            <CircleDollarSign className="w-4 h-4 text-[var(--text-tertiary)]" />
          </div>
          <div className="overview-card-main">
            <p className="overview-card-value font-mono">
              ¥ {asset.total_cost_cny > 0 ? Math.round(asset.total_cost_cny).toLocaleString() : "0.00"}
            </p>
          </div>
          <div className="overview-card-footer">
            <p className="overview-card-caption">
              实时汇率计算
            </p>
            <span
              className="overview-card-rating"
              data-rating-level={assetRating.level}
              title={assetRating.label}
            >
              {assetRating.label}
            </span>
          </div>
        </article>
      </section>
    </div>
  );
}
