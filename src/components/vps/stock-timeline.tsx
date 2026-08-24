import { CheckCircle2, XCircle } from "lucide-react";

/** 库存状态时间线：最近快照按时间排列；状态色仅作辅助，文字标签承载信息。 */

export function StockTimeline({
  points,
}: {
  points: { in_stock: boolean; checked_at: string }[];
}) {
  const data = points
    .map((p) => ({ ...p, at: new Date(p.checked_at) }))
    .filter((p) => !Number.isNaN(p.at.getTime()))
    .sort((a, b) => b.at.getTime() - a.at.getTime())
    .slice(0, 24);

  if (data.length === 0) return null;

  return (
    <ol className="flex flex-col gap-1.5">
      {data.map((p) => (
        <li key={p.checked_at} className="text-muted-foreground flex items-center gap-2 text-xs">
          <span aria-hidden className={`h-1.5 w-1.5 shrink-0 rounded-full ${p.in_stock ? "bg-emerald-500" : "bg-muted-foreground/40"}`} />
          <span className="tabular-nums">{p.at.toLocaleString("zh-CN")}</span>
          <span className={p.in_stock ? "inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400" : ""}>
            {p.in_stock ? (
              <>
                <CheckCircle2 aria-hidden className="h-3 w-3" /> 在售
              </>
            ) : (
              <>
                <XCircle aria-hidden className="h-3 w-3" /> 缺货
              </>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}
