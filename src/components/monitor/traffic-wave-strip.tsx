"use client";

import React, { useCallback, useRef, useEffect, useState } from "react";
import { CanvasStrip, safeCanvasColor } from "./canvas-strip";

interface TrafficWaveStripProps {
  rateBytesPerSec: number;
  color: string;
  isOnline: boolean;
}

const DOT_COUNT = 20;

export function TrafficWaveStrip({
  rateBytesPerSec,
  color,
  isOnline,
}: TrafficWaveStripProps) {
  const [samples, setSamples] = useState<number[]>(() =>
    Array(DOT_COUNT).fill(rateBytesPerSec > 0 ? 0.3 + Math.random() * 0.4 : 0),
  );

  const prevRateRef = useRef(rateBytesPerSec);

  // 模拟/滚动最近速率趋势采样
  useEffect(() => {
    prevRateRef.current = rateBytesPerSec;
    const interval = setInterval(() => {
      setSamples((prev) => {
        const nextVal =
          prevRateRef.current > 0
            ? Math.min(1, Math.max(0.15, 0.4 + (Math.sin(Date.now() / 1200) * 0.35 + (Math.random() - 0.5) * 0.2)))
            : 0;
        return [...prev.slice(1), nextVal];
      });
    }, 1500);

    return () => clearInterval(interval);
  }, [rateBytesPerSec]);

  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, width: number, height: number) => {
      const slotWidth = width / DOT_COUNT;
      const baseColor = safeCanvasColor(color);
      const inactiveColor = safeCanvasColor("var(--progress-bg)");

      samples.forEach((level, index) => {
        const hasTraffic = level > 0 && isOnline;
        const radius = hasTraffic ? 1.4 + level * 1.6 : 1.2;
        const x = index * slotWidth + slotWidth / 2;
        const y = height / 2;

        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = hasTraffic ? baseColor : inactiveColor;
        ctx.globalAlpha = hasTraffic ? Math.min(1, 0.4 + level * 0.6) : 0.45;
        ctx.fill();
      });

      ctx.globalAlpha = 1;
    },
    [samples, color, isOnline],
  );

  const hasActiveTraffic = isOnline && rateBytesPerSec > 0;

  return (
    <div className="traffic-stat-trend">
      <CanvasStrip
        className="traffic-dot-strip"
        height={10}
        redrawKey={`${samples.join(",")}-${color}-${isOnline}`}
        draw={draw}
      />
      <div
        className="traffic-stat-live"
        data-live={isOnline ? "true" : "false"}
        title={isOnline ? (hasActiveTraffic ? "实时吞吐中" : "网络空闲") : "离线"}
      >
        <span
          className="traffic-stat-live-dot"
          style={{ background: hasActiveTraffic ? color : "var(--text-tertiary)" }}
        />
        <span>{isOnline ? (hasActiveTraffic ? "实时" : "空闲") : "离线"}</span>
      </div>
    </div>
  );
}
