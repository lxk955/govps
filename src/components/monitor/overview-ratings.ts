export type OverviewRatingKind = "traffic" | "bandwidth" | "asset";

export interface OverviewRating {
  level: 0 | 1 | 2 | 3;
  label: string;
}

const GB = 1024 ** 3;
const MBPS_IN_BYTES_PER_SECOND = 1_000_000 / 8;

const DEFAULT_LABELS: Record<OverviewRatingKind, readonly string[]> = {
  traffic: ["轻量", "常规", "重度", "海量"],
  bandwidth: ["闲置", "轻载", "活跃", "爆发"],
  asset: ["入门", "标准", "顶级", "发烧"],
};

function levelFromThresholds(
  value: number,
  thresholds: readonly [number, number, number],
): 0 | 1 | 2 | 3 {
  if (!Number.isFinite(value) || value <= thresholds[0]) return 0;
  if (value <= thresholds[1]) return 1;
  if (value <= thresholds[2]) return 2;
  return 3;
}

export function getOverviewRating({
  kind,
  value,
}: {
  kind: OverviewRatingKind;
  value: number;
}): OverviewRating {
  const labels = DEFAULT_LABELS[kind];
  const level =
    kind === "asset"
      ? levelFromThresholds(value, [500, 1500, 3000])
      : kind === "traffic"
        ? levelFromThresholds(value, [500 * GB, 2000 * GB, 10000 * GB])
        : levelFromThresholds(value, [
            1 * MBPS_IN_BYTES_PER_SECOND,
            10 * MBPS_IN_BYTES_PER_SECOND,
            100 * MBPS_IN_BYTES_PER_SECOND,
          ]);

  return {
    level,
    label: labels[level],
  };
}

/** 速率按单位着色：B/s 绿色, KB/s 琥珀黄, MB/s 橙色, GB/s 警示红 */
const SPEED_RATE_COLOR: Record<string, string> = {
  "B/s": "var(--speed-idle)",
  "KB/s": "var(--speed-low)",
  "MB/s": "var(--speed-high)",
  "GB/s": "var(--speed-max)",
  "TB/s": "var(--speed-max)",
  "PB/s": "var(--speed-max)",
};

export function speedRateColor(unit: string): string {
  return SPEED_RATE_COLOR[unit] ?? "var(--text-tertiary)";
}

/** 延迟状态阶梯颜色 */
export function latencyHeatColor(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) {
    return "var(--text-tertiary)";
  }
  if (ms <= 60) return "var(--latency-excellent)";
  if (ms <= 100) return "var(--latency-good)";
  if (ms <= 160) return "var(--latency-moderate)";
  if (ms <= 200) return "var(--latency-elevated)";
  return "var(--latency-critical)";
}

/** 丢包阶梯色 */
export function lossHeatColor(loss: number | null | undefined): string {
  if (loss == null || !Number.isFinite(loss) || loss <= 0) {
    return "var(--status-success)";
  }
  if (loss <= 2) return "var(--latency-good)";
  if (loss <= 5) return "var(--latency-moderate)";
  if (loss <= 15) return "var(--latency-elevated)";
  return "var(--latency-critical)";
}

/** 配额分段进度条色阶 (从绿色到琥珀到红色) */
const TRAFFIC_QUOTA_STOPS = [
  { pos: 0, color: "#10b981" },
  { pos: 0.2, color: "#10b981" },
  { pos: 0.45, color: "#84cc16" },
  { pos: 0.65, color: "#eab308" },
  { pos: 0.8, color: "#f97316" },
  { pos: 1.0, color: "#ef4444" },
];

export function trafficQuotaSegmentColor(pos: number): string {
  const p = Math.max(0, Math.min(1, pos));
  for (let i = 0; i < TRAFFIC_QUOTA_STOPS.length - 1; i++) {
    const a = TRAFFIC_QUOTA_STOPS[i];
    const b = TRAFFIC_QUOTA_STOPS[i + 1];
    if (p >= a.pos && p <= b.pos) {
      return b.color;
    }
  }
  return "#ef4444";
}
