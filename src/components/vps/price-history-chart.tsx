"use client";

import { useMemo, useState } from "react";

import {
  convertHistorical,
  type SnapshotPoint,
} from "@/lib/api/endpoints";
import { currencySymbol, formatPrice } from "@/lib/format";

/**
 * 价格历史折线图（单序列）。
 * 设计与工程保障：
 * 1. 左侧预留充足边距（PAD.left = 60），杜绝 Y 轴与价格标签在最左侧被裁切遮挡。
 * 2. 单快照（或历史价格无波动）友好支持：智能向当前时间延伸出基准稳定线，防止除以 0 导致 NaN / 坐标归零。
 * 3. 标签自适应居中并 Clamp 在安全可视区内，避免边界截断。
 * 4. 搭配柔和背景渐变与悬浮十字线交互。
 */

const W = 640;
const H = 200;
const PAD = { top: 28, right: 60, bottom: 28, left: 60 };

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) {
    const pad = Math.max(1, Math.abs(min) * 0.15);
    min -= pad;
    max += pad;
  }
  const span = max - min;
  const step = span / (count - 1);
  return Array.from({ length: count }, (_, i) => min + step * i);
}

export function PriceHistoryChart({
  points,
  currency,
  snapshots = {},
}: {
  points: SnapshotPoint[];
  currency: string;
  /** P5：{iso_date: {code: units_per_usd}}，悬浮提示按「当日或之前最近」快照换算 USD（÷） */
  snapshots?: Record<string, Record<string, number>>;
}) {
  const [hover, setHover] = useState<number | null>(null);

  const rawData = useMemo(
    () =>
      points
        .map((p) => ({ price: Number(p.price), at: new Date(p.checked_at) }))
        .filter((p) => !Number.isNaN(p.at.getTime()) && !Number.isNaN(p.price))
        .sort((a, b) => a.at.getTime() - b.at.getTime()),
    [points],
  );

  const geom = useMemo(() => {
    if (rawData.length === 0) return null;

    const t0 = rawData[0].at.getTime();
    let t1 = rawData[rawData.length - 1].at.getTime();
    const isSinglePoint = rawData.length === 1 || t1 === t0;

    // 若只有一个记录点或时间相同：向当前时间延伸，形成一条稳定走势基准线
    if (isSinglePoint) {
      t1 = Math.max(Date.now(), t0 + 86400 * 1000);
    }

    const plotData = isSinglePoint
      ? [rawData[0], { price: rawData[0].price, at: new Date(t1) }]
      : rawData;

    const prices = plotData.map((d) => d.price);
    let lo = Math.min(...prices);
    let hi = Math.max(...prices);
    const isPriceConstant = lo === hi;

    if (isPriceConstant) {
      const margin = Math.max(1, lo * 0.15);
      lo -= margin;
      hi += margin;
    } else {
      const padY = (hi - lo) * 0.2;
      lo -= padY;
      hi += padY;
    }

    const x = (t: number) => {
      const ratio = t1 > t0 ? (t - t0) / (t1 - t0) : 0.5;
      return PAD.left + ratio * (W - PAD.left - PAD.right);
    };

    const y = (v: number) => {
      const ratio = hi > lo ? (v - lo) / (hi - lo) : 0.5;
      return H - PAD.bottom - ratio * (H - PAD.top - PAD.bottom);
    };

    const xy = plotData.map((d) => ({
      ...d,
      cx: Number(x(d.at.getTime()).toFixed(1)),
      cy: Number(y(d.price).toFixed(1)),
    }));

    const linePath = xy
      .map((p, i) => `${i === 0 ? "M" : "L"}${p.cx},${p.cy}`)
      .join(" ");

    const areaPath = `${linePath} L${xy[xy.length - 1].cx},${H - PAD.bottom} L${xy[0].cx},${H - PAD.bottom} Z`;

    const last = xy[xy.length - 1];
    const minP = xy.reduce((a, b) => (b.price < a.price ? b : a));
    const maxP = xy.reduce((a, b) => (b.price > a.price ? b : a));

    return {
      xy,
      linePath,
      areaPath,
      last,
      minP,
      maxP,
      lo,
      hi,
      isSinglePoint,
      isPriceConstant,
      startDate: rawData[0].at,
      endDate: new Date(t1),
    };
  }, [rawData]);

  if (!geom) return null;

  const fmt = (v: number) => formatPrice(v, currency);
  const fmtDate = (d: Date) =>
    d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });

  const ticks = niceTicks(geom.lo, geom.hi);
  const hoverPt = hover != null ? geom.xy[hover] : null;
  const hoverUsd =
    hoverPt != null && currency !== "USD"
      ? convertHistorical(hoverPt.price, currency, hoverPt.at.toISOString(), snapshots)
      : null;

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0;
    let bestD = Infinity;
    for (let i = 0; i < geom.xy.length; i++) {
      const d = Math.abs(geom.xy[i].cx - mx);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    setHover(best);
  };

  return (
    <figure className="m-0 space-y-2">
      {/* 顶部状态提示 */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        {geom.isPriceConstant ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 font-medium text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            监控至今价格稳定维持在 {fmt(geom.last.price)}，暂无调价波动
          </span>
        ) : (
          <div className="flex items-center gap-3 text-slate-600 dark:text-slate-400">
            <span>
              最低：<strong className="text-emerald-600 dark:text-emerald-400">{fmt(geom.minP.price)}</strong>
            </span>
            <span>
              最高：<strong className="text-rose-600 dark:text-rose-400">{fmt(geom.maxP.price)}</strong>
            </span>
            <span>
              最新：<strong>{fmt(geom.last.price)}</strong>
            </span>
          </div>
        )}

        {/* 表格视图兜底：读屏/打印/极简场景 */}
        <details className="text-muted-foreground text-xs">
          <summary className="cursor-pointer select-none hover:underline">查看数据表</summary>
          <div className="border-border bg-card mt-2 max-h-48 overflow-auto rounded-lg border p-2">
            <table className="w-full text-left">
              <caption className="sr-only">价格快照数据</caption>
              <thead>
                <tr className="text-muted-foreground border-border border-b text-[11px]">
                  <th scope="col" className="pb-1 font-medium">核对时间</th>
                  <th scope="col" className="pb-1 text-right font-medium">价格</th>
                </tr>
              </thead>
              <tbody className="divide-border divide-y">
                {rawData.map((d) => (
                  <tr key={d.at.toISOString()}>
                    <td className="py-1 text-[11px] tabular-nums text-slate-600 dark:text-slate-400">
                      {d.at.toLocaleString("zh-CN")}
                    </td>
                    <td className="py-1 text-right text-[11px] font-semibold tabular-nums">
                      {fmt(d.price)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full select-none"
        role="img"
        aria-label={`价格走势图：最新 ${fmt(geom.last.price)}，最低 ${fmt(geom.minP.price)}，最高 ${fmt(geom.maxP.price)}`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="price-chart-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#2563eb" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* 网格与 Y 轴刻度（靠右对齐于 x=52，左侧有 52px 空间，彻底杜绝切字） */}
        {ticks.map((t) => {
          const gy =
            geom.hi > geom.lo
              ? H - PAD.bottom - ((t - geom.lo) / (geom.hi - geom.lo)) * (H - PAD.top - PAD.bottom)
              : H / 2;
          return (
            <g key={t}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={gy}
                y2={gy}
                className="stroke-border/70"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              <text
                x={PAD.left - 8}
                y={gy + 3.5}
                textAnchor="end"
                className="fill-muted-foreground text-[10px] tabular-nums"
              >
                {currencySymbol(currency)}
                {t % 1 === 0 ? t.toFixed(0) : t.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* X 轴时间刻度：起点与终点 */}
        <text
          x={PAD.left}
          y={H - 8}
          textAnchor="start"
          className="fill-muted-foreground text-[10px] tabular-nums"
        >
          {fmtDate(geom.startDate)} {geom.isSinglePoint ? "起监控" : ""}
        </text>
        <text
          x={W - PAD.right}
          y={H - 8}
          textAnchor="end"
          className="fill-muted-foreground text-[10px] tabular-nums"
        >
          {geom.isSinglePoint ? "至今" : fmtDate(geom.endDate)}
        </text>

        {/* 面积渐变底色 */}
        <path d={geom.areaPath} fill="url(#price-chart-gradient)" />

        {/* 十字线（悬浮指示） */}
        {hoverPt && (
          <line
            x1={hoverPt.cx}
            x2={hoverPt.cx}
            y1={PAD.top}
            y2={H - PAD.bottom}
            className="stroke-slate-400 dark:stroke-slate-500"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        )}

        {/* 折线主体 */}
        <path
          d={geom.linePath}
          fill="none"
          stroke="#2563eb"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* 关键数据点标记 */}
        {geom.isPriceConstant ? (
          // 价格恒定时：标记左右两端与正中间常驻价格标签
          <g>
            <circle
              cx={geom.xy[0].cx}
              cy={geom.xy[0].cy}
              r="4"
              className="fill-blue-600 stroke-white dark:stroke-slate-900"
              strokeWidth="2"
            />
            <circle
              cx={geom.xy[geom.xy.length - 1].cx}
              cy={geom.xy[geom.xy.length - 1].cy}
              r="4"
              className="fill-blue-600 stroke-white dark:stroke-slate-900"
              strokeWidth="2"
            />
            {/* 居中固定常显价格标签，不贴边、不截断 */}
            <g transform={`translate(${W / 2}, ${geom.xy[0].cy - 12})`}>
              <rect
                x="-42"
                y="-14"
                width="84"
                height="20"
                rx="10"
                className="fill-blue-600 text-white shadow-xs"
              />
              <text
                x="0"
                y="0"
                textAnchor="middle"
                dominantBaseline="central"
                className="fill-white text-[11px] font-bold tabular-nums"
              >
                {fmt(geom.last.price)}
              </text>
            </g>
          </g>
        ) : (
          // 价格有变动时：分别标记最低/最高/最新点
          [
            { p: geom.minP, label: "最低", dy: 16 },
            { p: geom.maxP, label: "最高", dy: -12 },
            { p: geom.last, label: "最新", dy: -12 },
          ]
            .filter((m, i, arr) => arr.findIndex((q) => q.p.cx === m.p.cx && q.p.cy === m.p.cy) === i)
            .map(({ p, label, dy }) => {
              // 安全 Clamp，保证文字居中时左右留足边距
              const safeX = Math.min(Math.max(p.cx, PAD.left + 36), W - PAD.right - 36);
              return (
                <g key={`${p.cx}-${p.cy}`}>
                  <circle
                    cx={p.cx}
                    cy={p.cy}
                    r="4"
                    className="fill-blue-600 stroke-white dark:stroke-slate-900"
                    strokeWidth="2"
                  />
                  <text
                    x={safeX}
                    y={p.cy + dy}
                    textAnchor="middle"
                    className="fill-foreground text-[11px] font-bold tabular-nums"
                  >
                    {label} {fmt(p.price)}
                  </text>
                </g>
              );
            })
        )}

        {/* 悬浮提示 Tooltip */}
        {hoverPt && (
          <g pointerEvents="none">
            <circle
              cx={hoverPt.cx}
              cy={hoverPt.cy}
              r="5"
              className="fill-blue-600 stroke-white dark:stroke-slate-900"
              strokeWidth="2.5"
            />
            <g
              transform={`translate(${Math.min(hoverPt.cx + 10, W - 160)}, ${Math.max(hoverPt.cy - 44, 8)})`}
            >
              <rect
                width={hoverUsd != null ? "148" : "116"}
                height={hoverUsd != null ? "44" : "32"}
                rx="8"
                className="fill-slate-900/95 stroke-slate-700/80 shadow-lg"
                strokeWidth="1"
              />
              <text x="10" y="14" className="fill-slate-400 text-[10px]">
                {hoverPt.at.toLocaleString("zh-CN", {
                  month: "numeric",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </text>
              <text x="10" y="27" className="fill-white text-[12px] font-bold tabular-nums">
                {fmt(hoverPt.price)}
              </text>
              {hoverUsd != null && (
                <text x="10" y="38" className="fill-blue-400 text-[10px] tabular-nums">
                  ≈ ${hoverUsd.toFixed(2)}（历史汇率）
                </text>
              )}
            </g>
          </g>
        )}
      </svg>

      <figcaption className="text-muted-foreground text-[11px] leading-normal">
        * 价格为商家原币标价（{currency}）。当原厂售价无调整时走势呈平稳基准线；检测到打折降价或调价时将自动记录拐点。
      </figcaption>
    </figure>
  );
}
