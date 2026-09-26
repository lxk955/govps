"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Check,
  Copy,
  Loader2,
  RefreshCw,
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
import { MonitorNode } from "./types";
import { cn } from "@/lib/utils";

interface ShareDialogProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: MonitorNode[];
  userInfo: {
    public_enabled: boolean;
    share_token: string | null;
    is_owner: boolean;
    share_ip_mode?: "mask" | "hide" | "show";
  };
  onUpdateShare: (enabled: boolean, publicNodeIds?: number[], shareIpMode?: "mask" | "hide" | "show") => Promise<void>;
  onRefreshNodes: () => Promise<void>;
}

export function ShareDialog({
  isOpen,
  onClose,
  nodes,
  userInfo,
  onUpdateShare,
  onRefreshNodes,
}: ShareDialogProps) {
  const [selectedPublicNodeIds, setSelectedPublicNodeIds] = useState<number[]>([]);
  const [shareIpMode, setShareIpMode] = useState<"mask" | "hide" | "show">("mask");
  const [isSavingShare, setIsSavingShare] = useState(false);
  const [shareSavedSuccess, setShareSavedSuccess] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [isResettingToken, setIsResettingToken] = useState(false);
  const prevOpenRef = useRef(false);

  useEffect(() => {
    const wasOpen = prevOpenRef.current;
    prevOpenRef.current = isOpen;

    if (isOpen && !wasOpen) {
      setShareSavedSuccess(false);
      setShareCopied(false);
      setShareIpMode(userInfo.share_ip_mode || "mask");

      // 初始化选中的公开节点（默认为 is_public !== false 的节点）
      const publicIds = nodes.filter((n) => n.is_public !== false).map((n) => n.id);
      setSelectedPublicNodeIds(publicIds);
    }
  }, [isOpen, nodes, userInfo.share_ip_mode]);

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
      await onUpdateShare(userInfo.public_enabled, selectedPublicNodeIds, shareIpMode);
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

  const handleResetToken = async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
    if (!token) return;
    if (!confirm("重置分享 Token 将导致旧的分享链接全部失效，确认重置？")) return;

    setIsResettingToken(true);
    try {
      const res = await fetch("/api/monitor/share/token", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        await onRefreshNodes();
      }
    } catch {
      // 忽略
    } finally {
      setIsResettingToken(false);
    }
  };

  const origin = typeof window !== "undefined" ? window.location.origin : "https://govps.xyz";
  const shareUrl = userInfo.share_token
    ? `${origin}/monitor?share=${encodeURIComponent(userInfo.share_token)}`
    : "";

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[520px] rounded-3xl p-6">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-100 dark:border-blue-900 flex items-center justify-center text-blue-600">
              <Share2 className="w-4 h-4" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-slate-900 dark:text-slate-100">
                探针公开分享
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-500">
                生成只读分享链接，他人无需登录即可实时查看指定的 VPS 节点状态
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 pt-1">
          {/* 开关卡片 */}
          <div className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800">
            <div>
              <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                开启公开只读面板
              </div>
              <div className="text-[11px] text-slate-500">
                开启后，持有分享链接的用户可免密查看勾选的节点状态
              </div>
            </div>
            <button
              type="button"
              onClick={() => onUpdateShare(!userInfo.public_enabled, selectedPublicNodeIds, shareIpMode)}
              className={cn(
                "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden",
                userInfo.public_enabled ? "bg-blue-600" : "bg-slate-200 dark:bg-slate-700",
              )}
            >
              <span
                className={cn(
                  "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out",
                  userInfo.public_enabled ? "translate-x-4" : "translate-x-0",
                )}
              />
            </button>
          </div>

          {/* 分享链接输入框 */}
          {userInfo.public_enabled && userInfo.share_token && (
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                只读公开链接
              </label>
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  readOnly
                  value={shareUrl}
                  className="flex-1 h-8 px-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 font-mono text-xs text-slate-600 dark:text-slate-400 select-all"
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={copyShareLink}
                  className="h-8 px-3 rounded-xl text-xs gap-1"
                >
                  {shareCopied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      已复制
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      复制
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  title="重置分享 Token"
                  onClick={handleResetToken}
                  disabled={isResettingToken}
                  className="h-8 w-8 p-0 rounded-xl"
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", isResettingToken && "animate-spin")} />
                </Button>
              </div>
            </div>
          )}

          {/* 公开分享 IP 策略 */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              公开分享 IP 策略
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setShareIpMode("mask")}
                className={cn(
                  "flex flex-col items-center justify-center p-2 rounded-xl border text-center transition-all cursor-pointer",
                  shareIpMode === "mask"
                    ? "bg-blue-50/80 dark:bg-blue-950/40 border-blue-500 text-blue-600 dark:text-blue-400 font-medium shadow-xs"
                    : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 text-slate-600 dark:text-slate-400",
                )}
              >
                <span className="text-xs">掩码脱敏</span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono mt-0.5">
                  123.45.*.* (推荐)
                </span>
              </button>
              <button
                type="button"
                onClick={() => setShareIpMode("hide")}
                className={cn(
                  "flex flex-col items-center justify-center p-2 rounded-xl border text-center transition-all cursor-pointer",
                  shareIpMode === "hide"
                    ? "bg-blue-50/80 dark:bg-blue-950/40 border-blue-500 text-blue-600 dark:text-blue-400 font-medium shadow-xs"
                    : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 text-slate-600 dark:text-slate-400",
                )}
              >
                <span className="text-xs">完全隐藏</span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                  不公开 IP 地址
                </span>
              </button>
              <button
                type="button"
                onClick={() => setShareIpMode("show")}
                className={cn(
                  "flex flex-col items-center justify-center p-2 rounded-xl border text-center transition-all cursor-pointer",
                  shareIpMode === "show"
                    ? "bg-blue-50/80 dark:bg-blue-950/40 border-blue-500 text-blue-600 dark:text-blue-400 font-medium shadow-xs"
                    : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 text-slate-600 dark:text-slate-400",
                )}
              >
                <span className="text-xs">完整公开</span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono mt-0.5">
                  显示真实 IP
                </span>
              </button>
            </div>
          </div>

          {/* 节点选择过滤 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                选择公开展示的节点 ({selectedPublicNodeIds.length}/{nodes.length})
              </label>
              <div className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={handleSelectAllNodes}
                  className="text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                >
                  全选
                </button>
                <span className="text-slate-300 dark:text-slate-700">|</span>
                <button
                  type="button"
                  onClick={handleDeselectAllNodes}
                  className="text-slate-500 hover:underline cursor-pointer"
                >
                  清空
                </button>
              </div>
            </div>

            <div className="max-h-[220px] overflow-y-auto space-y-1.5 pr-1 no-scrollbar rounded-xl border border-slate-100 dark:border-slate-800/80 p-1.5">
              {nodes.map((node) => {
                const isChecked = selectedPublicNodeIds.includes(node.id);
                return (
                  <div
                    key={node.id}
                    onClick={() => handleToggleNodePublic(node.id)}
                    className={cn(
                      "flex items-center justify-between p-2 rounded-xl text-xs transition-colors cursor-pointer",
                      isChecked
                        ? "bg-blue-50/60 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-900/40"
                        : "hover:bg-slate-50 dark:hover:bg-slate-800/40 border border-transparent",
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <FlagIcon country={node.country} className="w-4 h-3 rounded-2xs shrink-0" />
                      <span className="font-medium truncate text-slate-800 dark:text-slate-200">
                        {node.name}
                      </span>
                      <span className="text-[10px] text-slate-400 truncate">
                        ({node.group_name || "主力"})
                      </span>
                    </div>
                    <div
                      className={cn(
                        "w-4 h-4 rounded-md border flex items-center justify-center transition-colors shrink-0",
                        isChecked
                          ? "bg-blue-600 border-blue-600 text-white"
                          : "border-slate-300 dark:border-slate-700",
                      )}
                    >
                      {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="text-[11px] text-slate-400">
              未勾选的节点将仅在登录后私有可见，不会对外公开。
            </p>
          </div>
        </div>

        <DialogFooter className="pt-4 border-t border-slate-100 dark:border-slate-800">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onClose}
            className="rounded-xl h-8 px-4 text-xs"
          >
            关闭
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleSavePublicNodes}
            disabled={isSavingShare}
            className="rounded-xl h-8 px-4 text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium"
          >
            {isSavingShare ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                正在保存...
              </>
            ) : shareSavedSuccess ? (
              <>
                <Check className="w-3.5 h-3.5 mr-1.5" />
                保存成功
              </>
            ) : (
              "保存分享设置"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
