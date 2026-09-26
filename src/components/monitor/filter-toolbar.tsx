"use client";

import React from "react";
import {
  ArrowUpDown,
  Bell,
  Check,
  Grid2X2,
  LayoutGrid,
  List,
  Plus,
  Share2,
  Sparkles,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { FlagIcon } from "./flag-icon";
import { SortMode, ViewMode } from "./types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface FilterToolbarProps {
  groups: Array<{ name: string; count: number }>;
  countries: Array<{ code: string; count: number }>;
  selectedGroup: string;
  onSelectGroup: (group: string) => void;
  selectedCountry: string | null;
  onSelectCountry: (country: string | null) => void;
  viewMode: ViewMode;
  onChangeViewMode: (mode: ViewMode) => void;
  sortMode: SortMode;
  onChangeSortMode: (mode: SortMode) => void;
  onRefresh: () => void;
  isRefreshing?: boolean;
  onAddNode: () => void;
  onLoadDemo: () => void;
  onClearDemo: () => void;
  hasDemoNodes: boolean;
  isOwner: boolean;
  onOpenExpireReminder?: () => void;
  onShare: () => void;
  shareEnabled?: boolean;
}

export function FilterToolbar({
  groups,
  countries,
  selectedGroup,
  onSelectGroup,
  selectedCountry,
  onSelectCountry,
  viewMode,
  onChangeViewMode,
  sortMode,
  onChangeSortMode,
  onAddNode,
  onLoadDemo,
  onClearDemo,
  hasDemoNodes,
  isOwner,
  onOpenExpireReminder,
  onShare,
  shareEnabled = false,
}: FilterToolbarProps) {
  const allGroups = [{ name: "全部", count: groups.reduce((acc, g) => acc + g.count, 0) }, ...groups];

  const sortLabels: Record<SortMode, string> = {
    default: "默认",
    cpu: "CPU 最高",
    ram: "内存 最高",
    bandwidth: "实时带宽",
    expires: "即将到期",
    uptime: "在线最长",
  };

  return (
    <div className="flex flex-col gap-2.5 my-3.5 select-none">
      {/* 行 1：分组 Tabs 与 右侧操作集合 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* 分组 Tab 容器 (LuminaPlus 风格浅色药丸) */}
        <div className="inline-flex items-center p-1 rounded-xl bg-slate-200/60 dark:bg-slate-800/60 border border-[var(--border)] overflow-x-auto max-w-full">
          {allGroups.map((g) => {
            const active = selectedGroup === g.name;
            return (
              <button
                key={g.name}
                type="button"
                onClick={() => onSelectGroup(g.name)}
                className={cn(
                  "px-3 py-1 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer",
                  active
                    ? "bg-[var(--surface)] text-[var(--text-primary)] shadow-2xs border border-[var(--border)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                )}
              >
                {g.name}
              </button>
            );
          })}
        </div>

        {/* 右侧操作按钮组：排序、添加节点、续费提醒、分享、视图切换 */}
        <div className="flex items-center gap-1.5 ml-auto flex-wrap">
          {/* 排序按钮 (对齐 ⇅ 默认) */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1.5 text-xs px-2.5 rounded-xl bg-[var(--surface)] border-[var(--border)] font-medium text-[var(--text-primary)] hover:bg-[var(--hover-bg)]"
              >
                <ArrowUpDown className="w-3.5 h-3.5 text-[var(--text-tertiary)]" />
                <span>{sortLabels[sortMode]}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36 text-xs rounded-xl">
              <DropdownMenuLabel className="text-[11px] text-[var(--text-tertiary)]">
                节点排序
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {(Object.keys(sortLabels) as SortMode[]).map((mode) => (
                <DropdownMenuItem
                  key={mode}
                  onClick={() => onChangeSortMode(mode)}
                  className="flex items-center justify-between text-xs cursor-pointer py-1.5"
                >
                  <span>{sortLabels[mode]}</span>
                  {sortMode === mode && <Check className="w-3.5 h-3.5 text-[var(--accent-500)]" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* 视图切换 */}
          <div className="flex items-center p-0.5 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
            <button
              type="button"
              onClick={() => onChangeViewMode("large")}
              className={cn(
                "p-1.5 rounded-lg transition-colors cursor-pointer",
                viewMode === "large"
                  ? "bg-slate-200/80 dark:bg-slate-700/80 text-[var(--text-primary)]"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
              )}
              title="大卡片视图"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onChangeViewMode("compact")}
              className={cn(
                "p-1.5 rounded-lg transition-colors cursor-pointer",
                viewMode === "compact"
                  ? "bg-slate-200/80 dark:bg-slate-700/80 text-[var(--text-primary)]"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
              )}
              title="紧凑卡片视图"
            >
              <Grid2X2 className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onChangeViewMode("list")}
              className={cn(
                "p-1.5 rounded-lg transition-colors cursor-pointer",
                viewMode === "list"
                  ? "bg-slate-200/80 dark:bg-slate-700/80 text-[var(--text-primary)]"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
              )}
              title="列表表格视图"
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* 续费提醒管理 */}
          {isOwner && onOpenExpireReminder && (
            <Button
              variant="outline"
              size="sm"
              onClick={onOpenExpireReminder}
              className="h-8 gap-1.5 text-xs px-2.5 rounded-xl bg-[var(--surface)] border-[var(--border)] font-medium text-[var(--text-primary)] hover:bg-[var(--hover-bg)]"
              title="设置续费到期提醒与通知通道"
            >
              <Bell className="w-3.5 h-3.5 text-amber-500" />
              <span className="hidden sm:inline">续费提醒</span>
            </Button>
          )}

          {/* 分享看板 */}
          {isOwner && (
            <Button
              variant="outline"
              size="sm"
              onClick={onShare}
              className="h-8 gap-1.5 text-xs px-2.5 rounded-xl bg-[var(--surface)] border-[var(--border)] font-medium text-[var(--text-primary)] hover:bg-[var(--hover-bg)]"
              title="生成公开监控链接与状态卡片"
            >
              <Share2 className={cn("w-3.5 h-3.5", shareEnabled ? "text-emerald-500" : "text-[var(--text-tertiary)]")} />
              <span className="hidden sm:inline">分享</span>
            </Button>
          )}

          {/* 添加节点 */}
          {isOwner && (
            <Button
              size="sm"
              onClick={onAddNode}
              className="h-8 gap-1 text-xs px-3 rounded-xl bg-[var(--accent-500)] hover:bg-[var(--accent-strong)] text-white font-semibold shadow-2xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>添加节点</span>
            </Button>
          )}

          {/* 演示节点快捷切换 */}
          {isOwner && hasDemoNodes ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearDemo}
              className="h-8 text-[11px] px-2 text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-xl"
              title="移除模拟演示节点"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              <span>清空演示</span>
            </Button>
          ) : isOwner ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onLoadDemo}
              className="h-8 text-[11px] px-2 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 rounded-xl"
              title="载入逼真模拟节点预览"
            >
              <Sparkles className="w-3.5 h-3.5 mr-1 text-amber-500" />
              <span>演示集群</span>
            </Button>
          ) : null}
        </div>
      </div>

      {/* 行 2：国家/地区二级过滤（如果存在多个国家时显示） */}
      {countries.length > 1 && (
        <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 no-scrollbar text-xs">
          <button
            onClick={() => onSelectCountry(null)}
            className={cn(
              "px-2.5 py-1 rounded-lg transition-colors cursor-pointer text-[11px] font-medium shrink-0",
              selectedCountry === null
                ? "bg-slate-200 dark:bg-slate-800 text-[var(--text-primary)] font-semibold"
                : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
            )}
          >
            全部地区 ({countries.reduce((acc, c) => acc + c.count, 0)})
          </button>
          {countries.map((c) => (
            <button
              key={c.code}
              onClick={() => onSelectCountry(selectedCountry === c.code ? null : c.code)}
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition-colors cursor-pointer text-[11px] font-medium shrink-0",
                selectedCountry === c.code
                  ? "bg-slate-200 dark:bg-slate-800 text-[var(--text-primary)] font-semibold"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
              )}
            >
              <FlagIcon country={c.code} className="w-3.5 h-2.5 rounded-2xs object-cover" />
              <span>{c.code.toUpperCase()}</span>
              <span className="opacity-70">({c.count})</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
