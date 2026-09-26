"use client";

import React, { useCallback, useMemo } from "react";
import { CanvasStrip, fillRoundedRect, safeCanvasColor } from "./canvas-strip";
import { latencyHeatColor, lossHeatColor } from "./overview-ratings";

export interface PingBucket {
  latency_ms: number | null;
  loss_rate: number | null;
  time_label?: string;
  is_offline?: boolean;
}

const BAR_COUNT = 20;

interface BarProps {
  buckets: PingBucket[];
  height?: number;
  onHoverIndex?: (index: number | null) => void;
}

export function LatencyBars({ buckets, height = 11, onHoverIndex }: BarProps) {
  const bars = useMemo(() => {
    // 补齐或截取 20 根柱子
    const list = buckets.length > 0 ? buckets.slice(-BAR_COUNT) : [];
    while (list.length < BAR_COUNT) {
      list.unshift({ latency_ms: null, loss_rate: null });
    }
    return list;
  }, [buckets]);

  const draw = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      width: number,
      h: number,
      interaction: { hoverIndex: number | null },
    ) => {
      const count = bars.length;
      const gap = 2;
      const barWidth = Math.max(1, (width - gap * (count - 1)) / count);

      bars.forEach((bucket, index) => {
        const isHovered = interaction.hoverIndex === index;
        const val = bucket.latency_ms;
        const hasVal = val !== null && Number.isFinite(val) && val >= 0;

        const colorStr = hasVal
          ? latencyHeatColor(val)
          : bucket.is_offline
            ? "var(--status-error)"
            : "var(--progress-bg)";
        const tone = safeCanvasColor(colorStr);

        const baseFraction = hasVal || bucket.is_offline ? 0.85 : 0.28;
        const heightFraction = isHovered ? Math.min(1, baseFraction * 1.35) : baseFraction;
        const barHeight = Math.max(2, h * heightFraction);
        const x = index * (barWidth + gap);
        const y = h - barHeight;

        ctx.globalAlpha = hasVal ? (isHovered ? 1 : 0.92) : 0.55;
        ctx.fillStyle = tone;
        fillRoundedRect(ctx, x, y, barWidth, barHeight, 1.5);
      });

      ctx.globalAlpha = 1;
    },
    [bars],
  );

  const getHoverIndex = useCallback(
    (offsetX: number, width: number) => {
      if (width <= 0) return null;
      const slotWidth = width / BAR_COUNT;
      return Math.max(0, Math.min(BAR_COUNT - 1, Math.floor(offsetX / slotWidth)));
    },
    [],
  );

  return (
    <CanvasStrip
      className="health-bar-row"
      height={height}
      redrawKey={bars.map((b) => b.latency_ms).join(",")}
      getHoverIndex={getHoverIndex}
      onHoverIndex={onHoverIndex}
      draw={draw}
    />
  );
}

export function QualityBars({ buckets, height = 11, onHoverIndex }: BarProps) {
  const bars = useMemo(() => {
    const list = buckets.length > 0 ? buckets.slice(-BAR_COUNT) : [];
    while (list.length < BAR_COUNT) {
      list.unshift({ latency_ms: null, loss_rate: null });
    }
    return list;
  }, [buckets]);

  const draw = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      width: number,
      h: number,
      interaction: { hoverIndex: number | null },
    ) => {
      const count = bars.length;
      const gap = 2;
      const barWidth = Math.max(1, (width - gap * (count - 1)) / count);

      bars.forEach((bucket, index) => {
        const isHovered = interaction.hoverIndex === index;
        const loss = bucket.loss_rate;
        const hasLoss = loss !== null && Number.isFinite(loss);

        const colorStr = hasLoss
          ? lossHeatColor(loss)
          : bucket.is_offline
            ? "var(--status-error)"
            : "var(--progress-bg)";
        const tone = safeCanvasColor(colorStr);

        const baseFraction = hasLoss || bucket.is_offline ? 0.85 : 0.28;
        const heightFraction = isHovered ? Math.min(1, baseFraction * 1.35) : baseFraction;
        const barHeight = Math.max(2, h * heightFraction);
        const x = index * (barWidth + gap);
        const y = h - barHeight;

        ctx.globalAlpha = hasLoss ? (isHovered ? 1 : 0.92) : 0.55;
        ctx.fillStyle = tone;
        fillRoundedRect(ctx, x, y, barWidth, barHeight, 1.5);
      });

      ctx.globalAlpha = 1;
    },
    [bars],
  );

  const getHoverIndex = useCallback(
    (offsetX: number, width: number) => {
      if (width <= 0) return null;
      const slotWidth = width / BAR_COUNT;
      return Math.max(0, Math.min(BAR_COUNT - 1, Math.floor(offsetX / slotWidth)));
    },
    [],
  );

  return (
    <CanvasStrip
      className="health-bar-row"
      height={height}
      redrawKey={bars.map((b) => b.loss_rate).join(",")}
      getHoverIndex={getHoverIndex}
      onHoverIndex={onHoverIndex}
      draw={draw}
    />
  );
}

/** 悬浮交互提示 */
export function HealthBucketTooltip({
  text,
  index,
  count = 20,
}: {
  text: string | null;
  index: number | null;
  count?: number;
}) {
  if (!text || index == null) return null;
  const leftPct = ((index + 0.5) / count) * 100;

  return (
    <div
      className="absolute bottom-[calc(100%+6px)] z-30 pointer-events-none -translate-x-1/2 rounded-md bg-slate-900/90 dark:bg-slate-100/95 text-slate-100 dark:text-slate-900 px-2 py-0.5 text-[10px] font-mono shadow-md whitespace-nowrap"
      style={{ left: `${leftPct}%` }}
    >
      {text}
    </div>
  );
}
