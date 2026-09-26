"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";

export interface CanvasStripInteraction {
  hoverIndex: number | null;
}

interface CanvasStripProps {
  className?: string;
  height: number;
  redrawKey?: string | number;
  draw: (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    interaction: CanvasStripInteraction,
  ) => void;
  getHoverIndex?: (offsetX: number, width: number) => number | null;
  onHoverIndex?: (index: number | null) => void;
}

export function CanvasStrip({
  className,
  height,
  redrawKey,
  draw,
  getHoverIndex,
  onHoverIndex,
}: CanvasStripProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [width, setWidth] = useState(0);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const updateWidth = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width > 0) {
        setWidth(rect.width);
      }
    };

    updateWidth();
    const observer = new ResizeObserver(() => updateWidth());
    observer.observe(canvas);

    return () => {
      observer.disconnect();
    };
  }, []);

  const render = useCallback(() => {
    void redrawKey;
    const canvas = canvasRef.current;
    if (!canvas || width <= 0) return;

    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    const pixelWidth = Math.max(1, Math.round(width * dpr));
    const pixelHeight = Math.max(1, Math.round(height * dpr));

    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    draw(ctx, width, height, { hoverIndex });
  }, [width, height, draw, hoverIndex, redrawKey]);

  useEffect(() => {
    render();
  }, [render]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: "100%", height }}
      aria-hidden
      onPointerMove={(e) => {
        if (!getHoverIndex || width <= 0) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const offsetX = e.clientX - rect.left;
        const index = getHoverIndex(offsetX, width);
        setHoverIndex(index);
        onHoverIndex?.(index);
      }}
      onPointerLeave={() => {
        setHoverIndex(null);
        onHoverIndex?.(null);
      }}
    />
  );
}

/** 绘制圆角矩形 */
export function fillRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  if (width <= 0 || height <= 0) return;
  const r = Math.max(0, Math.min(radius, width / 2, height / 2));
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  ctx.fill();
}

/** 解析 CSS 变量并提供兜底安全的 Canvas 颜色 */
export function safeCanvasColor(color: string): string {
  if (!color) return "#888888";
  if (typeof document === "undefined") return color;

  const match = color.match(/^var\((--[^),\s]+)/);
  if (match) {
    const varName = match[1];
    const resolved = getComputedStyle(document.documentElement)
      .getPropertyValue(varName)
      .trim();
    if (resolved) return resolved;
  }
  return color;
}
