"use client";

import React, { useEffect, useState } from "react";
import {
  BellRing,
  Check,
  Loader2,
  Mail,
  Send,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { MonitorSettings } from "./types";

interface ExpireReminderDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSettingsSaved?: () => void;
}

export function ExpireReminderDialog({
  isOpen,
  onClose,
  onSettingsSaved,
}: ExpireReminderDialogProps) {
  // 到期提醒设置状态
  const [expireEnabled, setExpireEnabled] = useState(true);
  const [expireStages, setExpireStages] = useState<number[]>([15, 7, 3, 1]);
  const [userEmail, setUserEmail] = useState("");
  const [isLoadingSettings, setIsLoadingSettings] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // 测试邮件状态
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  // 载入全局配置
  useEffect(() => {
    if (!isOpen) return;
    setSaveSuccess(false);
    setTestResult(null);

    const token = typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
    if (!token) return;

    setIsLoadingSettings(true);
    fetch("/api/monitor/settings", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: MonitorSettings | null) => {
        if (data) {
          setExpireEnabled(data.expire_notify_enabled !== false);
          setExpireStages(data.expire_notify_stages || [15, 7, 3, 1]);
          setUserEmail(data.email || "");
        }
      })
      .catch(() => {})
      .finally(() => setIsLoadingSettings(false));
  }, [isOpen]);

  // 保存到期提醒设置
  const handleSaveExpireSettings = async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
    if (!token) return;

    setIsSavingSettings(true);
    setSaveSuccess(false);
    try {
      const res = await fetch("/api/monitor/settings", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          expire_notify_enabled: expireEnabled,
          expire_notify_stages: expireStages,
        }),
      });
      if (res.ok) {
        setSaveSuccess(true);
        onSettingsSaved?.();
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch {
      // 忽略
    } finally {
      setIsSavingSettings(false);
    }
  };

  // 发送测试邮件
  const handleSendTestNotify = async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
    if (!token) return;

    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch("/api/monitor/notify/test", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setTestResult({
          ok: true,
          message: data.message || `测试邮件已发送至 ${userEmail || "您的邮箱"}`,
        });
      } else {
        setTestResult({
          ok: false,
          message: data.detail || "测试邮件发送失败，请检查邮件配置",
        });
      }
    } catch (e: unknown) {
      setTestResult({
        ok: false,
        message: e instanceof Error ? e.message : "网络请求异常，请稍后重试",
      });
    } finally {
      setIsTesting(false);
    }
  };

  // 阶段勾选切换
  const toggleStage = (stage: number) => {
    setExpireStages((prev) =>
      prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage].sort((a, b) => b - a),
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[480px] rounded-3xl p-6">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-amber-50 dark:bg-amber-950/60 border border-amber-100 dark:border-amber-900 flex items-center justify-center text-amber-600">
              <BellRing className="w-4 h-4" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-slate-900 dark:text-slate-100">
                续费到期提醒设置
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-500">
                配置 VPS 到期多阶段邮件提醒与测试通知
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {isLoadingSettings ? (
          <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
            <span className="text-xs">加载设置中...</span>
          </div>
        ) : (
          <div className="space-y-4 pt-1">
            {/* 全局开关 */}
            <div className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800">
              <div>
                <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                  开启 VPS 到期提醒
                </div>
                <div className="text-[11px] text-slate-500">
                  在 VPS 到达设定的到期临界天数时，自动向绑定邮箱推送提醒
                </div>
              </div>
              <button
                type="button"
                onClick={() => setExpireEnabled(!expireEnabled)}
                className={cn(
                  "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden",
                  expireEnabled ? "bg-amber-500" : "bg-slate-200 dark:bg-slate-700",
                )}
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out",
                    expireEnabled ? "translate-x-4" : "translate-x-0",
                  )}
                />
              </button>
            </div>

            {/* 提醒阶段选择 */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                默认提前提醒阶段
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[15, 7, 3, 1].map((stage) => {
                  const checked = expireStages.includes(stage);
                  return (
                    <button
                      key={stage}
                      type="button"
                      disabled={!expireEnabled}
                      onClick={() => toggleStage(stage)}
                      className={cn(
                        "flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer",
                        checked
                          ? "bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-300 shadow-2xs"
                          : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:bg-slate-50",
                        !expireEnabled && "opacity-50 cursor-not-allowed",
                      )}
                    >
                      {checked && <Check className="w-3.5 h-3.5 shrink-0" />}
                      <span>{stage} 天前</span>
                    </button>
                  );
                })}
              </div>
              <p className="text-[11px] text-slate-400">
                系统将在到达每个已选阶段时各提醒一次，并支持在通知邮件中一键「已续费顺延」或「静音本期」。
              </p>
            </div>

            {/* 接收邮箱信息 */}
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <Mail className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-slate-500 shrink-0">接收邮箱:</span>
                <span className="font-mono font-medium text-slate-700 dark:text-slate-300 truncate">
                  {userEmail || "当前账号邮箱"}
                </span>
              </div>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-md font-medium shrink-0">
                已生效
              </span>
            </div>

            {/* 发送测试邮件 */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">验证邮件通知通道</span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleSendTestNotify}
                  disabled={isTesting || !expireEnabled}
                  className="h-7 text-xs px-2.5 rounded-lg border-slate-200 dark:border-slate-700"
                >
                  {isTesting ? (
                    <Loader2 className="w-3 h-3 animate-spin mr-1" />
                  ) : (
                    <Send className="w-3 h-3 mr-1" />
                  )}
                  发送测试邮件
                </Button>
              </div>

              {testResult && (
                <div
                  className={cn(
                    "text-[11px] p-2 rounded-lg leading-relaxed flex items-center gap-1.5",
                    testResult.ok
                      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400"
                      : "bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400",
                  )}
                >
                  <span>{testResult.ok ? "✅" : "⚠️"}</span>
                  <span className="flex-1">{testResult.message}</span>
                </div>
              )}
            </div>
          </div>
        )}

        <DialogFooter className="pt-4 border-t border-slate-100 dark:border-slate-800">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onClose}
            className="rounded-xl h-8 px-4 text-xs"
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleSaveExpireSettings}
            disabled={isSavingSettings || isLoadingSettings}
            className="rounded-xl h-8 px-4 text-xs bg-amber-600 hover:bg-amber-700 text-white font-medium"
          >
            {isSavingSettings ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                正在保存...
              </>
            ) : saveSuccess ? (
              <>
                <Check className="w-3.5 h-3.5 mr-1.5" />
                保存成功
              </>
            ) : (
              "保存提醒配置"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
