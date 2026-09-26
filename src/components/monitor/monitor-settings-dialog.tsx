"use client";

import React, { useEffect, useState } from "react";
import {
  Bell,
  Check,
  Copy,
  Globe,
  Loader2,
  Mail,
  Send,
  Settings,
  Share2,
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
import { FlagIcon } from "./flag-icon";
import { MonitorNode, MonitorSettings } from "./types";
import { cn } from "@/lib/utils";

interface MonitorSettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: MonitorNode[];
  userInfo: {
    public_enabled: boolean;
    share_token: string | null;
    is_owner: boolean;
  };
  onUpdateShare: (enabled: boolean, publicNodeIds?: number[]) => Promise<void>;
  onRefreshNodes: () => Promise<void>;
  initialTab?: "expire" | "channels" | "share";
}

export function MonitorSettingsDialog({
  isOpen,
  onClose,
  nodes,
  userInfo,
  onUpdateShare,
  onRefreshNodes,
  initialTab = "expire",
}: MonitorSettingsDialogProps) {
  const [activeTab, setActiveTab] = useState<"expire" | "channels" | "share">(initialTab);

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

  // 公开分享状态
  const [selectedPublicNodeIds, setSelectedPublicNodeIds] = useState<number[]>([]);
  const [isSavingShare, setIsSavingShare] = useState(false);
  const [shareSavedSuccess, setShareSavedSuccess] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  // 载入全局配置
  useEffect(() => {
    if (!isOpen) return;
    setActiveTab(initialTab);
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

    // 同步公开节点选择
    const publicIds = nodes.filter((n) => n.is_public !== false).map((n) => n.id);
    setSelectedPublicNodeIds(publicIds);
  }, [isOpen, initialTab, nodes]);

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

  // 分享操作逻辑
  const handleToggleNodePublic = (nodeId: number) => {
    setSelectedPublicNodeIds((prev) =>
      prev.includes(nodeId) ? prev.filter((id) => id !== nodeId) : [...prev, nodeId],
    );
  };

  const handleSelectAllNodes = () => {
    setSelectedPublicNodeIds(nodes.map((n) => n.id));
  };

  const handleDeselectAllNodes = () => {
    setSelectedPublicNodeIds([]);
  };

  const handleSavePublicNodes = async () => {
    setIsSavingShare(true);
    setShareSavedSuccess(false);
    try {
      await onUpdateShare(userInfo.public_enabled, selectedPublicNodeIds);
      setShareSavedSuccess(true);
      await onRefreshNodes();
      setTimeout(() => setShareSavedSuccess(false), 2000);
    } finally {
      setIsSavingShare(false);
    }
  };

  const copyShareLink = () => {
    if (!userInfo.share_token) return;
    const origin = typeof window !== "undefined" ? window.location.origin : "https://govps.xyz";
    const shareUrl = `${origin}/monitor?share=${encodeURIComponent(userInfo.share_token)}`;
    navigator.clipboard.writeText(shareUrl);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[540px] rounded-3xl p-6">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-100 dark:border-blue-900 flex items-center justify-center text-blue-600">
              <Settings className="w-4 h-4" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-slate-900 dark:text-slate-100">
                探针与通知设置
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-500">
                管理 VPS 到期自动化提醒、通知推送渠道与公开分享策略
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* 顶部三标签栏 */}
        <div className="flex items-center p-1 rounded-2xl bg-slate-100/80 dark:bg-slate-800/80 border border-slate-200/60 dark:border-slate-700/60 mt-1">
          <button
            type="button"
            onClick={() => setActiveTab("expire")}
            className={cn(
              "flex-1 py-1.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all",
              activeTab === "expire"
                ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-xs"
                : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
            )}
          >
            <Bell className="w-3.5 h-3.5" />
            <span>到期提醒</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("channels")}
            className={cn(
              "flex-1 py-1.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all",
              activeTab === "channels"
                ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-xs"
                : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
            )}
          >
            <Send className="w-3.5 h-3.5" />
            <span>通知渠道</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("share")}
            className={cn(
              "flex-1 py-1.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all",
              activeTab === "share"
                ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-xs"
                : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
            )}
          >
            <Share2 className="w-3.5 h-3.5" />
            <span>公开分享</span>
          </button>
        </div>

        {/* 标签页内容区域 */}
        <div className="py-2">
          {/* TAB 1: 到期提醒 */}
          {activeTab === "expire" && (
            <div className="flex flex-col gap-4">
              {isLoadingSettings ? (
                <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-400 text-xs">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                  <span>正在加载提醒配置...</span>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                        全局自动到期提醒
                      </span>
                      <span className="text-[11px] text-slate-500 leading-tight">
                        开启后，当所管理的 VPS 临近到期时，系统将通过已启用的渠道自动发出阶梯提醒
                      </span>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer shrink-0 ml-3">
                      <input
                        type="checkbox"
                        checked={expireEnabled}
                        onChange={(e) => setExpireEnabled(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-10 h-5.5 bg-slate-200 peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4.5 after:w-4.5 after:transition-all peer-checked:bg-blue-600 dark:bg-slate-700" />
                    </label>
                  </div>

                  {/* 阶段天数配置 */}
                  <div className="flex flex-col gap-2 p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                        默认阶梯提醒时间节点
                      </span>
                      <span className="text-[10px] text-slate-400">单节点可单独覆盖</span>
                    </div>
                    <p className="text-[11px] text-slate-500 leading-tight">
                      请勾选需要触发通知的天数节点，进入对应天数时各推送一次：
                    </p>
                    <div className="flex items-center gap-2 pt-1 flex-wrap">
                      {[15, 7, 3, 1].map((stage) => {
                        const isChecked = expireStages.includes(stage);
                        return (
                          <button
                            key={stage}
                            type="button"
                            onClick={() => toggleStage(stage)}
                            className={cn(
                              "px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border",
                              isChecked
                                ? "bg-blue-600 text-white border-blue-600 shadow-2xs"
                                : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-100",
                            )}
                          >
                            提前 {stage} 天
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* 测试邮件与保存操作 */}
                  <div className="flex flex-col gap-2.5">
                    {testResult && (
                      <div
                        className={cn(
                          "px-3.5 py-2.5 rounded-xl text-xs flex items-center justify-between border",
                          testResult.ok
                            ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
                            : "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800",
                        )}
                      >
                        <span>{testResult.message}</span>
                        <button
                          type="button"
                          onClick={() => setTestResult(null)}
                          className="text-[11px] underline opacity-80"
                        >
                          关闭
                        </button>
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleSendTestNotify}
                        disabled={isTesting}
                        className="rounded-xl text-xs h-8.5 gap-1.5 border-slate-200 dark:border-slate-700"
                      >
                        {isTesting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />
                        ) : (
                          <Send className="w-3.5 h-3.5 text-blue-500" />
                        )}
                        <span>{isTesting ? "正在发送测试..." : "发送测试邮件"}</span>
                      </Button>

                      <Button
                        type="button"
                        size="sm"
                        onClick={handleSaveExpireSettings}
                        disabled={isSavingSettings}
                        className="rounded-xl text-xs h-8.5 px-4 font-semibold bg-blue-600 hover:bg-blue-700 text-white"
                      >
                        {saveSuccess
                          ? "✓ 设置已保存"
                          : isSavingSettings
                            ? "正在保存..."
                            : "保存提醒设置"}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 2: 通知渠道 */}
          {activeTab === "channels" && (
            <div className="flex flex-col gap-3">
              <div className="text-[11px] text-slate-500">
                GoVPS 采用可插拔多渠道分发架构，首期默认启用账号邮箱通道，更多即时触达渠道正在接入中：
              </div>

              {/* 渠道 1: 电子邮箱 */}
              <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/60 flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-blue-100 dark:bg-blue-900/60 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 mt-0.5">
                    <Mail className="w-4 h-4" />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                        电子邮箱通知 (Resend)
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400">
                        主通道 · 已激活
                      </span>
                    </div>
                    <span className="text-xs font-mono text-slate-600 dark:text-slate-300">
                      {userEmail || "当前登录注册邮箱"}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      节点到期通知、补货与降价提醒等系统消息将直接投递至此邮箱。
                    </span>
                  </div>
                </div>
              </div>

              {/* 渠道 2: Webhook */}
              <div className="p-3.5 rounded-2xl bg-slate-50/50 dark:bg-slate-800/20 border border-dashed border-slate-200 dark:border-slate-800 flex items-start justify-between opacity-80">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center shrink-0 mt-0.5">
                    <Globe className="w-4 h-4" />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        自定义 HTTP Webhook
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-400">
                        架构已预留 · 规划中
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400">
                      支持向飞书、钉钉、企业微信机器人或个人自动化服务投递 JSON 格式事件。
                    </span>
                  </div>
                </div>
              </div>

              {/* 渠道 3: Telegram */}
              <div className="p-3.5 rounded-2xl bg-slate-50/50 dark:bg-slate-800/20 border border-dashed border-slate-200 dark:border-slate-800 flex items-start justify-between opacity-80">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center shrink-0 mt-0.5">
                    <Send className="w-4 h-4" />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Telegram Bot 机器人
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-400">
                        架构已预留 · 规划中
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400">
                      通过 Telegram 官方 Bot API 实现秒级消息推送与交互。
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: 公开分享 */}
          {activeTab === "share" && (
            <div className="flex flex-col gap-3.5">
              <div className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                    开启公开监控面板
                  </span>
                  <span className="text-[11px] text-slate-500 leading-tight">
                    开启后将生成专属免登录只读链接，访客可查看所选节点的实时监控
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer shrink-0 ml-3">
                  <input
                    type="checkbox"
                    checked={userInfo.public_enabled}
                    onChange={(e) => onUpdateShare(e.target.checked, selectedPublicNodeIds)}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5.5 bg-slate-200 peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4.5 after:w-4.5 after:transition-all peer-checked:bg-blue-600 dark:bg-slate-700" />
                </label>
              </div>

              {userInfo.public_enabled && (
                <div className="flex flex-col gap-2 p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-700 dark:text-slate-300">
                      公开展示节点范围 ({selectedPublicNodeIds.length} / {nodes.length} 已选)
                    </span>
                    <div className="flex items-center gap-2 text-xs">
                      <button
                        type="button"
                        onClick={handleSelectAllNodes}
                        className="text-blue-600 hover:text-blue-700 dark:text-blue-400 font-semibold"
                      >
                        全选
                      </button>
                      <span className="text-slate-300 dark:text-slate-600">·</span>
                      <button
                        type="button"
                        onClick={handleDeselectAllNodes}
                        className="text-slate-500 hover:text-slate-700 dark:text-slate-400 font-medium"
                      >
                        清空
                      </button>
                    </div>
                  </div>

                  <div className="max-h-40 overflow-y-auto rounded-xl border border-slate-200/70 dark:border-slate-700/60 bg-white dark:bg-slate-900 p-1.5 flex flex-col gap-1 no-scrollbar">
                    {nodes.length > 0 ? (
                      nodes.map((node) => {
                        const isChecked = selectedPublicNodeIds.includes(node.id);
                        return (
                          <label
                            key={node.id}
                            className={cn(
                              "flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer select-none transition-all",
                              isChecked
                                ? "bg-blue-50/60 dark:bg-blue-950/30 text-slate-900 dark:text-slate-100 font-medium"
                                : "hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-500 opacity-60",
                            )}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => handleToggleNodePublic(node.id)}
                                className="w-3.5 h-3.5 rounded text-blue-600 border-slate-300 dark:border-slate-600 focus:ring-0 cursor-pointer"
                              />
                              <FlagIcon
                                country={node.country}
                                className="w-4 h-3 rounded-2xs object-cover shrink-0 shadow-2xs"
                              />
                              <span className="truncate">{node.name}</span>
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-400">
                                {node.group_name}
                              </span>
                            </div>
                            <span
                              className={cn(
                                "w-1.5 h-1.5 rounded-full shrink-0",
                                node.is_online ? "bg-emerald-500" : "bg-rose-500",
                              )}
                            />
                          </label>
                        );
                      })
                    ) : (
                      <div className="text-center py-3 text-xs text-slate-400">暂无节点</div>
                    )}
                  </div>

                  <Button
                    size="sm"
                    onClick={handleSavePublicNodes}
                    disabled={isSavingShare}
                    className="mt-0.5 h-8 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    {shareSavedSuccess
                      ? "✓ 公开范围已保存"
                      : isSavingShare
                        ? "正在保存..."
                        : "保存公开范围"}
                  </Button>
                </div>
              )}

              {userInfo.public_enabled && userInfo.share_token && (
                <div className="flex flex-col gap-1.5 pt-1">
                  <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                    专属公开链接
                  </span>
                  <div className="flex items-center gap-2">
                    <input
                      readOnly
                      value={`${typeof window !== "undefined" ? window.location.origin : "https://govps.xyz"}/monitor?share=${encodeURIComponent(userInfo.share_token)}`}
                      className="flex-1 font-mono text-xs px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 select-all"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={copyShareLink}
                      className="h-9 px-3 rounded-xl gap-1 text-xs"
                    >
                      {shareCopied ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-500" />
                          <span className="text-emerald-500">已复制</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>复制</span>
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="mt-2">
          <Button onClick={onClose} className="rounded-xl text-xs h-9 px-6 font-semibold">
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
