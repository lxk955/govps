"use client";

import React from "react";
import {
  ArrowUpDown,
  Check,
  Grid2X2,
  LayoutGrid,
  List,
  Plus,
  RefreshCw,
  Settings,
  SlidersHorizontal,
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
  onRefresh,
  isRefreshing = false,
  onAddNode,
  onLoadDemo,
  onClearDemo,
  hasDemoNodes,
  isOwner,
  onShare,
  shareEnabled = false,
}: FilterToolbarProps) {
  const allGroups = [{ name: "全部", count: groups.reduce((acc, g) => acc + g.count, 0) }, ...groups];

  const sortLabels: Record<SortMode, string> = {
    default: "默认排序",
    cpu: "CPU 从高到低",
    ram: "内存 从高到低",
    bandwidth: "实时带宽",
    expires: "即将到期",
    uptime: "在线时长",
  };

  return (
    <div className="flex flex-col gap-3 my-4 select-none">
      {/* 行 1：分组 Tab 与 右侧核心操作 */}
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        {/* 分组 Tab 胶囊 */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 no-scrollbar">
          {allGroups.map((g) => {
            const active = selectedGroup === g.name;
            return (
              <button
                key={g.name}
                onClick={() => onSelectGroup(g.name)}
                className={cn(
                  "px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 cursor-pointer",
                  active
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-xs"
                    : "bg-white dark:bg-slate-900/80 border border-slate-200/80 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/80",
                )}
              >
                {g.name}
              </button>
            );
          })}
        </div>

        {/* 右侧交互控件区 */}
        <div className="flex items-center gap-1.5 ml-auto shrink-0">
          {/* 排序方式下拉 */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1 text-xs px-2.5 rounded-xl bg-white dark:bg-slate-900 border-slate-200/80 dark:border-slate-800 font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50"
              >
                <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
                <span className="hidden sm:inline">{sortLabels[sortMode]}</span>
                <span className="sm:hidden">排序</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="text-xs">
              <DropdownMenuLabel>指标排序</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {(Object.keys(sortLabels) as SortMode[]).map((mode) => (
                <DropdownMenuItem
                  key={mode}
                  onClick={() => onChangeSortMode(mode)}
                  className="flex items-center justify-between gap-4 cursor-pointer"
                >
                  <span>{sortLabels[mode]}</span>
                  {sortMode === mode && <Check className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* 4 种视图切换按钮组 */}
          <div className="flex items-center p-0.5 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 text-slate-500">
            <button
              onClick={() => onChangeViewMode("large")}
              title="大卡片模式"
              className={cn(
                "p-1.5 rounded-lg transition-all cursor-pointer",
                viewMode === "large"
                  ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-xs"
                  : "hover:text-slate-900 dark:hover:text-slate-200",
              )}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onChangeViewMode("compact")}
              title="小卡片模式"
              className={cn(
                "p-1.5 rounded-lg transition-all cursor-pointer",
                viewMode === "compact"
                  ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-xs"
                  : "hover:text-slate-900 dark:hover:text-slate-200",
              )}
            >
              <Grid2X2 className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onChangeViewMode("mini")}
              title="迷你卡片模式"
              className={cn(
                "p-1.5 rounded-lg transition-all cursor-pointer",
                viewMode === "mini"
                  ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-xs"
                  : "hover:text-slate-900 dark:hover:text-slate-200",
              )}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onChangeViewMode("list")}
              title="列表模式"
              className={cn(
                "p-1.5 rounded-lg transition-all cursor-pointer",
                viewMode === "list"
                  ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-xs"
                  : "hover:text-slate-900 dark:hover:text-slate-200",
              )}
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* 刷新按钮 */}
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            title="即时刷新"
            className="h-8 w-8 p-0 rounded-xl bg-white dark:bg-slate-900 border-slate-200/80 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isRefreshing && "animate-spin")} />
          </Button>

          {/* 仅所有者显示的分享与管理操作 */}
          {isOwner && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={onShare}
                title="监控与通知设置"
                className={cn(
                  "h-8 gap-1.5 text-xs px-2.5 rounded-xl border-slate-200/80 dark:border-slate-800 font-medium",
                  shareEnabled
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800"
                    : "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300",
                )}
              >
                <Settings className="w-3.5 h-3.5" />
                <span className="hidden md:inline">设置与分享</span>
                <span className="md:hidden">设置</span>
              </Button>

              {/* 演示节点快捷入口 */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1 text-xs px-2 rounded-xl bg-white dark:bg-slate-900 border-slate-200/80 dark:border-slate-800 text-slate-600 dark:text-slate-400"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                    <span className="hidden lg:inline">演示集群</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="text-xs">
                  <DropdownMenuItem onClick={onLoadDemo} className="cursor-pointer gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                    <span>载入仿真演示节点</span>
                  </DropdownMenuItem>
                  {hasDemoNodes && (
                    <DropdownMenuItem onClick={onClearDemo} className="cursor-pointer text-red-600 dark:text-red-400 gap-2">
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>清空所有演示节点</span>
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>

              {/* + 添加节点按钮 */}
              <Button
                size="sm"
                onClick={onAddNode}
                className="h-8 gap-1 text-xs px-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-xs"
              >
                <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>添加节点</span>
              </Button>
            </>
          )}
        </div>
      </div>

      {/* 行 2：国家/地区国旗胶囊条 */}
      {countries.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto py-0.5 no-scrollbar">
          {countries.map((c) => {
            const isSelected = selectedCountry === c.code;
            return (
              <button
                key={c.code}
                onClick={() => onSelectCountry(isSelected ? null : c.code)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer",
                  isSelected
                    ? "bg-blue-50 text-blue-600 dark:bg-blue-950/80 dark:text-blue-400 border border-blue-200 dark:border-blue-800"
                    : "bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800/80 text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-700",
                )}
              >
                <FlagIcon country={c.code} className="w-3.5 h-2.5 rounded-2xs object-cover" />
                <span className="uppercase font-mono text-[11px]">{c.code}</span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                  {c.count}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
