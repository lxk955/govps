"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  BellOff,
  BellRing,
  Calendar,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Server,
  Sparkles,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FlagIcon } from "@/components/monitor/flag-icon";
import { RenewActionNode } from "@/components/monitor/types";

const CYCLE_MAP: Record<string, string> = {
  monthly: "按月付",
  quarterly: "按季付",
  "semi-annually": "按半年付",
  semi_annually: "按半年付",
  annually: "按年付",
  biennially: "按两年付",
  triennially: "按三年付",
};

function RenewActionContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [node, setNode] = useState<RenewActionNode | null>(null);
  const [isMuted, setIsMuted] = useState(true);

  // 到期日表单状态
  const [newDate, setNewDate] = useState("");
  const [isSubmittingDate, setIsSubmittingDate] = useState(false);
  const [isTogglingMute, setIsTogglingMute] = useState(false);
  const [saveSuccessDate, setSaveSuccessDate] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setErrorMsg("缺少续费操作 Token，请从邮件中的专属按钮点击进入。");
      setIsLoading(false);
      return;
    }

    const fetchNode = async () => {
      try {
        setIsLoading(true);
        setErrorMsg(null);
        const res = await fetch(`/api/monitor/renew-action?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "操作链接无效或已过期，请前往探针面板管理。");
        }
        const data: RenewActionNode = await res.json();
        setNode(data);
        setIsMuted(data.is_muted);

        // 默认将新到期日初始化为建议顺延日期，若无则使用当前到期日
        if (data.suggested_next_expires_at) {
          setNewDate(data.suggested_next_expires_at);
        } else if (data.current_expires_at) {
          setNewDate(data.current_expires_at.slice(0, 10));
        }
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : "获取节点信息失败");
      } finally {
        setIsLoading(false);
      }
    };

    fetchNode();
  }, [token]);

  // 快捷调整月份
  const handleQuickAddMonths = (monthsToAdd: number) => {
    const baseStr = newDate || node?.current_expires_at?.slice(0, 10) || new Date().toISOString().slice(0, 10);
    const d = new Date(baseStr);
    if (isNaN(d.getTime())) return;
    d.setMonth(d.getMonth() + monthsToAdd);
    setNewDate(d.toISOString().slice(0, 10));
  };

  // 撤销 / 恢复静音
  const handleToggleMute = async () => {
    if (!token) return;
    try {
      setIsTogglingMute(true);
      if (isMuted) {
        // 撤销静音
        const res = await fetch(`/api/monitor/renew-action/unmute?token=${encodeURIComponent(token)}`, {
          method: "POST",
        });
        if (!res.ok) {
          throw new Error("撤销静音失败，请稍后重试");
        }
        setIsMuted(false);
      } else {
        // 重新设为静音 (重新触发 GET 接口即可)
        const res = await fetch(`/api/monitor/renew-action?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          throw new Error("静音失败，请稍后重试");
        }
        setIsMuted(true);
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "操作失败");
    } finally {
      setIsTogglingMute(false);
    }
  };

  // 提交下次到期日
  const handleUpdateDate = async () => {
    if (!token || !newDate) return;
    try {
      setIsSubmittingDate(true);
      const res = await fetch(`/api/monitor/renew-action/update-date?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expires_at: newDate }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "更新到期日失败");
      }
      const data = await res.json();
      setSaveSuccessDate(newDate);
      setIsMuted(false);
      if (node) {
        setNode({
          ...node,
          current_expires_at: data.expires_at,
          is_muted: false,
        });
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "保存到期日失败");
    } finally {
      setIsSubmittingDate(false);
    }
  };

  // 1. 加载中状态
  if (isLoading) {
    return (
      <div className="min-h-dvh flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
          <p className="text-sm">正在验证安全签名并设置本周期静音...</p>
        </div>
      </div>
    );
  }

  // 2. 错误状态
  if (errorMsg || !node) {
    return (
      <div className="min-h-dvh flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xl p-6 sm:p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 mx-auto flex items-center justify-center mb-4">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-2">链接失效或已过期</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-6">
            {errorMsg || "未找到对应的节点信息。该链接可能已被使用或超过30天有效期。"}
          </p>
          <div className="flex flex-col gap-2">
            <Button asChild className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-xl">
              <Link href="/monitor">前往探针面板登录查看</Link>
            </Button>
            <Button asChild variant="outline" className="w-full rounded-xl">
              <Link href="/">返回 GoVPS 首页</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const cycleText = CYCLE_MAP[node.billing_cycle?.toLowerCase() || "monthly"] || node.billing_cycle || "月付";
  const currentExpDateStr = node.current_expires_at ? node.current_expires_at.slice(0, 10) : "未设置";

  return (
    <div className="min-h-dvh flex flex-col justify-between bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <div className="w-full max-w-xl mx-auto px-4 py-8 sm:py-12 flex-1">
        {/* 顶部 Brand */}
        <div className="flex items-center justify-between mb-6">
          <Link
            href="/monitor"
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            返回探针管理
          </Link>
          <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5" />
            免密快速续费通道
          </span>
        </div>

        {/* 核心卡片容器 */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-xl overflow-hidden">
          {/* 卡片头部：节点资产概览 */}
          <div className="p-5 sm:p-6 border-b border-slate-100 dark:border-slate-800/80 bg-gradient-to-br from-slate-50/50 to-slate-100/30 dark:from-slate-800/20 dark:to-slate-900/50">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <FlagIcon country={node.country} className="w-5 h-3.5 rounded-2xs object-cover shadow-2xs shrink-0" />
                  <h1 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white truncate">
                    {node.name}
                  </h1>
                  <Badge variant="secondary" className="text-[11px] px-2 py-0 h-5 font-normal">
                    {node.group_name || "主力"}
                  </Badge>
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2 flex-wrap">
                  <span>计费周期: <strong className="text-slate-700 dark:text-slate-200">{cycleText}</strong></span>
                  {node.price !== null && (
                    <span>续费金额: <strong className="text-slate-700 dark:text-slate-200">{node.currency} {node.price.toFixed(2)}</strong></span>
                  )}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-[11px] text-slate-400 mb-0.5">当前设定到期日</div>
                <div className="font-mono text-xs sm:text-sm font-semibold text-slate-800 dark:text-slate-200">
                  {currentExpDateStr}
                </div>
              </div>
            </div>
          </div>

          <div className="p-5 sm:p-6 space-y-6">
            {/* 状态板块：本周期静音反馈 */}
            {isMuted ? (
              <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200/80 dark:border-emerald-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                    <BellOff className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-emerald-900 dark:text-emerald-200 flex items-center gap-1.5">
                      本周期提醒已设为静音
                      <Badge className="bg-emerald-600 text-white text-[10px] h-4.5 px-1.5 font-normal">
                        已生效
                      </Badge>
                    </h3>
                    <p className="text-xs text-emerald-700/90 dark:text-emerald-300/80 mt-0.5 leading-relaxed">
                      系统已为您停止当前到期日前（{currentExpDateStr}）的所有催促邮件。
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleToggleMute}
                  disabled={isTogglingMute}
                  className="shrink-0 text-xs h-8 rounded-lg border-emerald-300 dark:border-emerald-700 text-emerald-800 dark:text-emerald-200 hover:bg-emerald-100 dark:hover:bg-emerald-900/60"
                >
                  {isTogglingMute ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  ) : (
                    <BellRing className="w-3.5 h-3.5 mr-1" />
                  )}
                  撤销静音
                </Button>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200/80 dark:border-amber-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0 mt-0.5">
                    <BellRing className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-amber-900 dark:text-amber-200">
                      当前处于正常提醒状态
                    </h3>
                    <p className="text-xs text-amber-700/90 dark:text-amber-300/80 mt-0.5 leading-relaxed">
                      已撤销静音。在到达设定的阶梯阈值时，系统仍将发送邮件提醒。
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleToggleMute}
                  disabled={isTogglingMute}
                  className="shrink-0 text-xs h-8 rounded-lg border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/60"
                >
                  {isTogglingMute ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  ) : (
                    <BellOff className="w-3.5 h-3.5 mr-1" />
                  )}
                  静音本周期
                </Button>
              </div>
            )}

            {/* 设置下次到期日 */}
            {saveSuccessDate ? (
              <div className="p-5 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200/80 dark:border-blue-800/60 text-center space-y-3">
                <div className="w-10 h-10 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 mx-auto flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-blue-900 dark:text-blue-100">
                    🎉 下次到期日已成功设定为 {saveSuccessDate}！
                  </h4>
                  <p className="text-xs text-blue-700/90 dark:text-blue-300/80 mt-1 max-w-sm mx-auto leading-relaxed">
                    本周期的静音标记已自动解除，下一轮到期多阶梯提醒已正式就绪。
                  </p>
                </div>
                <div className="pt-2 flex justify-center gap-2">
                  <Button asChild size="sm" className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs h-8 px-4">
                    <Link href="/monitor">前往探针面板管理</Link>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setSaveSuccessDate(null)}
                    className="rounded-lg text-xs h-8 px-3"
                  >
                    再次微调
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                    <Calendar className="w-4 h-4 text-blue-500" />
                    设置下次续费到期日
                  </Label>
                  <span className="text-[11px] text-slate-400">设定后自动开启新一轮提醒</span>
                </div>

                {/* 周期性推荐一键顺延按钮 */}
                {node.suggested_next_expires_at && (
                  <div className="p-3 rounded-xl bg-slate-100/80 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <Zap className="w-4 h-4 text-amber-500 shrink-0" />
                      <div className="text-xs truncate">
                        <span className="text-slate-500">推算下次到期：</span>
                        <span className="font-mono font-bold text-slate-900 dark:text-white">
                          {node.suggested_next_expires_at}
                        </span>
                        <span className="text-slate-400 ml-1.5 hidden sm:inline">({cycleText})</span>
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => setNewDate(node.suggested_next_expires_at!)}
                      className="text-xs h-7 px-2.5 rounded-lg shrink-0 font-medium"
                    >
                      使用此日期
                    </Button>
                  </div>
                )}

                {/* 日期选择与快捷微调 */}
                <div className="space-y-2">
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <Input
                      type="date"
                      value={newDate}
                      onChange={(e) => setNewDate(e.target.value)}
                      className="h-9 text-xs sm:text-sm rounded-lg font-mono flex-1"
                    />
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => handleQuickAddMonths(1)}
                        className="h-8 px-2.5 text-xs rounded-lg"
                      >
                        +1月
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => handleQuickAddMonths(3)}
                        className="h-8 px-2.5 text-xs rounded-lg"
                      >
                        +3月
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => handleQuickAddMonths(12)}
                        className="h-8 px-2.5 text-xs rounded-lg"
                      >
                        +1年
                      </Button>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    如果您已在 VPS 服务商处完成续费，选择续费后的新到期日即可。
                  </p>
                </div>

                {/* 提交新到期日 */}
                <Button
                  type="button"
                  onClick={handleUpdateDate}
                  disabled={!newDate || isSubmittingDate}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl h-10 text-xs sm:text-sm font-semibold shadow-sm transition-all"
                >
                  {isSubmittingDate ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                      正在保存到期时间...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 mr-1.5" />
                      确认并更新下次到期日
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>

          {/* 卡片底部链接 */}
          <div className="px-5 py-3.5 bg-slate-50 dark:bg-slate-900/80 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <Server className="w-3.5 h-3.5 text-slate-400" />
              GoVPS 探针自动资产巡检
            </span>
            <Link
              href="/monitor"
              className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
            >
              控制台管理
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function RenewActionPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-dvh flex items-center justify-center p-4">
          <div className="flex flex-col items-center gap-3 text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
            <p className="text-sm">正在加载...</p>
          </div>
        </div>
      }
    >
      <RenewActionContent />
    </Suspense>
  );
}
