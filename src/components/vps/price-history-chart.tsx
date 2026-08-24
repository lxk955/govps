"use client";

import { useMemo, useState } from "react";

import {
  convertHistorical,
  type SnapshotPoint,
} from "@/lib/api/endpoints";
import { currencySymbol } from "@/lib/format";

/**
 * 价格历史折线图（单序列）。
 * dataviz 规范落点：2px 线宽、≥8px 关键点标记、隐性网格、
 * 常显末点/最高/最低数值标签（暗色对比 WARN 的 relief 义务）、
 * 悬浮十字线 + 提示框（命中区大于标记）、<details> 表格视图兜底。
 * 颜色用项目 --chart-1 令牌，明暗两态均已跑 validate_palette 校验。
 */

const W = 640;
const H = 200;
const PAD = { top: 16, right: 56, bottom: 24, left: 44 };

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) {
    const pad = Math.max(1, Math.abs(min) * 0.05);
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

  const data = useMemo(
    () =>
      points
        .map((p) => ({ price: Number(p.price), at: new Date(p.checked_at) }))
        .filter((p) => !Number.isNaN(p.at.getTime()))
        .sort((a, b) => a.at.getTime() - b.at.getTime()),
    [points],
  );

  const geom = useMemo(() => {
    if (data.length === 0) return null;
    const prices = data.map((d) => d.price);
    let lo = Math.min(...prices);
    let hi = Math.max(...prices);
    const padY = (hi - lo || hi * 0.1 || 1) * 0.12;
    lo -= padY;
    hi += padY;

    const t0 = data[0].at.getTime();
    const t1 = data[data.length - 1].at.getTime() || t0 + 1;
    const x = (t: number) =>
      PAD.left + ((t - t0) / (t1 - t0)) * (W - PAD.left - PAD.right);
    const y = (v: number) =>
      H - PAD.bottom - ((v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);

    const xy = data.map((d) => ({ ...d, cx: x(d.at.getTime()), cy: y(d.price) }));
    const path = xy.map((p, i) => `${i === 0 ? "M" : "L"}${p.cx.toFixed(1)},${p.cy.toFixed(1)}`).join(" ");
    const last = xy[xy.length - 1];
    const minP = xy.reduce((a, b) => (b.price < a.price ? b : a));
    const maxP = xy.reduce((a, b) => (b.price > a.price ? b : a));
    return { xy, path, last, minP, maxP, lo, hi };
  }, [data]);

  if (!geom) return null;

  const fmt = (v: number) => `${currencySymbol(currency)}${v.toFixed(2)}`;
  const fmtDate = (d: Date) =>
    d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  const ticks = niceTicks(geom.lo, geom.hi);
  const hoverPt = hover != null ? geom.xy[hover] : null;
  // USD 产品无需参考位；非 USD 按当日快照换算，缺失为 null（与 0 明确区分）
  const hoverUsd =
    hoverPt != null && currency !== "USD"
      ? convertHistorical(hoverPt.price, currency, hoverPt.at.toISOString(), snapshots)
      : null;
  // 单点时画一个标记而非线段
  const single = geom.xy.length === 1;

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
    <figure className="m-0">
      {/* 表格视图兜底：读屏/无 JS/打印场景 */}
      <details className="text-muted-foreground mb-2 text-xs">
        <summary className="cursor-pointer select-none hover:underline">查看数据表</summary>
        <table className="mt-2 w-full text-left">
          <caption className="sr-only">价格快照数据</caption>
          <thead>
            <tr className="text-muted-foreground">
              <th scope="col" className="py-1 font-medium">日期</th>
              <th scope="col" className="py-1 font-medium">价格</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.at.toISOString()}>
                <td className="py-0.5 tabular-nums">{d.at.toLocaleString("zh-CN")}</td>
                <td className="py-0.5 tabular-nums">{fmt(d.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`价格走势图：最新 ${fmt(geom.last.price)}，最低 ${fmt(geom.minP.price)}，最高 ${fmt(geom.maxP.price)}`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {/* 网格与 Y 轴刻度（隐性：hairline + 弱化文字） */}
        {ticks.map((t) => {
          const gy = H - PAD.bottom - ((t - geom.lo) / (geom.hi - geom.lo)) * (H - PAD.top - PAD.bottom);
          return (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={gy} y2={gy}
                className="stroke-border" strokeWidth="1" />
              <text x={PAD.left - 6} y={gy + 3} textAnchor="end"
                className="fill-muted-foreground text-[10px] tabular-nums">
                {currencySymbol(currency)}{t % 1 === 0 ? t.toFixed(0) : t.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* X 轴首中末时间刻度 */}
        {[geom.xy[0], geom.xy[Math.floor((geom.xy.length - 1) / 2)], geom.xy[geom.xy.length - 1]]
          .filter((p, i, arr) => arr.findIndex((q) => q.cx === p.cx) === i)
          .map((p) => (
            <text key={p.at.toISOString()} x={p.cx} y={H - 8} textAnchor="middle"
              className="fill-muted-foreground text-[10px] tabular-nums">
              {fmtDate(p.at)}
            </text>
          ))}

        {/* 十字线（悬浮层在数据线下方绘制） */}
        {hoverPt && !single && (
          <line x1={hoverPt.cx} x2={hoverPt.cx} y1={PAD.top} y2={H - PAD.bottom}
            className="stroke-border" strokeWidth="1" strokeDasharray="3 3" />
        )}

        {/* 主折线：2px */}
        {!single && (
          <path d={geom.path} fill="none"
            className="stroke-[color:var(--chart-1)]" strokeWidth="2"
            strokeLinejoin="round" strokeLinecap="round" />
        )}

        {/* 选择性标记：最低 / 最高 / 最新（≥8px 直径），带常显数值标签（relief 义务） */}
        {[
          { p: geom.minP, dy: 14, anchor: "middle" as const },
          { p: geom.maxP, dy: -8, anchor: "middle" as const },
          { p: geom.last, dy: -10, anchor: "end" as const },
        ]
          .filter((m, i, arr) => arr.findIndex((q) => q.p.at === m.p.at && q.p.price === m.p.price) === i)
          .map(({ p, dy, anchor }) => (
            <g key={`${p.at.toISOString()}-${p.price}`}>
              <circle cx={p.cx} cy={p.cy} r="4"
                className="fill-[color:var(--chart-1)] stroke-[var(--card)]" strokeWidth="2" />
              <text x={Math.min(Math.max(p.cx, PAD.left + 20), W - PAD.right)}
                y={p.cy + dy} textAnchor={anchor}
                className="fill-foreground text-[11px] font-medium tabular-nums">
                {fmt(p.price)}
              </text>
            </g>
          ))}

        {/* 悬浮提示框（命中区为整个绘图区，大于任何标记） */}
        {hoverPt && (
          <g pointerEvents="none">
            <circle cx={hoverPt.cx} cy={hoverPt.cy} r="4.5"
              className="fill-[color:var(--chart-1)] stroke-[var(--card)]" strokeWidth="2" />
            <g transform={`translate(${Math.min(hoverPt.cx + 8, W - 150)},${Math.max(hoverPt.cy - 34, 4)})`}>
              <rect width={hoverUsd != null ? "142" : "110"} height={hoverUsd != null ? "40" : "30"} rx="6"
                className="fill-card stroke-border" strokeWidth="1" />
              <text x="8" y="13" className="fill-muted-foreground text-[9px]">
                {hoverPt.at.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
              </text>
              <text x="8" y="25" className="fill-foreground text-[11px] font-semibold tabular-nums">
                {fmt(hoverPt.price)}
              </text>
              {hoverUsd != null && (
                <text x="8" y="36" className="fill-muted-foreground text-[9px] tabular-nums">
                  ≈ ${hoverUsd.toFixed(2)}（按当日快照）
                </text>
              )}
            </g>
          </g>
        )}
      </svg>
      <figcaption className="text-muted-foreground mt-1 text-xs">
        价格为商家原币标价（{currency}）；USD 换算按当日汇率快照，快照缺失时不显示换算值。
      </figcaption>
    </figure>
  );
}
