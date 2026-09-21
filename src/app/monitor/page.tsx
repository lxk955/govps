"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Activity,
  AlertCircle,
  Check,
  Copy,
  LogIn,
  Plus,
  Server,
  Share2,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { OverviewHeader } from "@/components/monitor/overview-header";
import { FilterToolbar } from "@/components/monitor/filter-toolbar";
import { LargeNodeCard } from "@/components/monitor/large-node-card";
import { CompactNodeCard } from "@/components/monitor/compact-node-card";
import { MiniNodeCard } from "@/components/monitor/mini-node-card";
import { NodeListView } from "@/components/monitor/node-list-view";
import { NodeDetailModal } from "@/components/monitor/node-detail-modal";
import { AddNodeDialog } from "@/components/monitor/add-node-dialog";
import {
  MonitorApiResponse,
  MonitorNode,
  MonitorSummary,
  MonitorUserInfo,
  SortMode,
  ViewMode,
} from "@/components/monitor/types";

const DEFAULT_SUMMARY: MonitorSummary = {
  online_count: 0,
  total_count: 0,
  online_segments: [],
  bandwidth: { rx_rate: 0, tx_rate: 0, total_rate: 0 },
  traffic: { rx_total: 0, tx_total: 0, total: 0 },
  asset: { total_cost_cny: 0, currency: "CNY" },
  groups: [],
  countries: [],
};

export default function MonitorPage() {
  const searchParams = useSearchParams();
  const shareToken = searchParams.get("share");

  const { user } = useAuth(); // undefined = loading, null = not logged in, object = logged in

  const [nodes, setNodes] = useState<MonitorNode[]>([]);
  const [summary, setSummary] = useState<MonitorSummary>(DEFAULT_SUMMARY);
  const [userInfo, setUserInfo] = useState<MonitorUserInfo>({
    is_owner: false,
    public_enabled: false,
    share_token: null,
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 筛选与视图状态
  const [selectedGroup, setSelectedGroup] = useState<string>("全部");
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("default");
  const [viewMode, setViewMode] = useState<ViewMode>("large");

  // 弹窗状态
  const [detailNode, setDetailNode] = useState<MonitorNode | null>(null);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingNode, setEditingNode] = useState<MonitorNode | null>(null);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  // 持久化用户偏好的视图模式
  useEffect(() => {
    try {
      const saved = localStorage.getItem("govps_monitor_view_mode") as ViewMode;
      if (saved && ["large", "compact", "mini", "list"].includes(saved)) {
        setViewMode(saved);
      }
    } catch {
      // 忽略 localStorage 限制
    }
  }, []);

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode);
    try {
      localStorage.setItem("govps_monitor_view_mode", mode);
    } catch {
      // 忽略
    }
  };

  // 数据拉取
  const fetchData = useCallback(
    async (isManual: boolean = false) => {
      if (isManual) setIsRefreshing(true);

      const endpoint = shareToken
        ? `/api/monitor/nodes?share=${encodeURIComponent(shareToken)}`
        : "/api/monitor/nodes";

      try {
        const token =
          typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
        const headers: Record<string, string> = {};
        if (!shareToken && token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(endpoint, {
          headers,
          cache: "no-store",
        });

        if (res.status === 401 && !shareToken) {
          setIsLoading(false);
          setIsRefreshing(false);
          return;
        }

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `请求失败 (${res.status})`);
        }

        const data: MonitorApiResponse = await res.json();
        setNodes(data.nodes || []);
        setSummary(data.summary || DEFAULT_SUMMARY);
        setUserInfo(data.user_info);
        setError(null);
      } catch (err: unknown) {
        if (isManual || isLoading) {
          const message = err instanceof Error ? err.message : "无法连接到探针服务器";
          setError(message);
        }
      } finally {
        setIsLoading(false);
        if (isManual) setIsRefreshing(false);
      }
    },
    [shareToken, isLoading],
  );

  // 初始加载
  useEffect(() => {
    if (user !== undefined || shareToken) {
      fetchData(false);
    }
  }, [user, shareToken, fetchData]);

  // 3~5 秒自适应短轮询（切后台或熄屏时自动休眠）
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;

    const schedulePoll = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(async () => {
        if (document.visibilityState === "visible") {
          await fetchData(false);
        }
        schedulePoll();
      }, 4000);
    };

    schedulePoll();

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        fetchData(false);
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchData]);

  // 一键载入演示数据
  const handleLoadDemo = async () => {
    try {
      setIsRefreshing(true);
      const token = localStorage.getItem("govps_token");
      const res = await fetch("/api/monitor/demo", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        await fetchData(true);
      }
    } catch {
      // 忽略
    } finally {
      setIsRefreshing(false);
    }
  };

  // 一键清理演示数据
  const handleClearDemo = async () => {
    try {
      setIsRefreshing(true);
      const token = localStorage.getItem("govps_token");
      const res = await fetch("/api/monitor/demo", {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        await fetchData(true);
      }
    } catch {
      // 忽略
    } finally {
      setIsRefreshing(false);
    }
  };

  // 切换公开分享
  const handleToggleShare = async () => {
    try {
      const token = localStorage.getItem("govps_token");
      const nextState = !userInfo.public_enabled;
      const res = await fetch(`/api/monitor/share?enabled=${nextState}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const json = await res.json();
        setUserInfo((prev) => ({
          ...prev,
          public_enabled: json.public_enabled,
          share_token: json.share_token,
        }));
      }
    } catch {
      // 忽略
    }
  };

  // 复制分享链接
  const copyShareLink = () => {
    if (!userInfo.share_token) return;
    const origin = typeof window !== "undefined" ? window.location.origin : "https://govps.xyz";
    const shareUrl = `${origin}/monitor?share=${encodeURIComponent(userInfo.share_token)}`;
    navigator.clipboard.writeText(shareUrl);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  };

  // 节点过滤与排序
  const filteredNodes = useMemo(() => {
    let result = [...nodes];

    // 分组筛选
    if (selectedGroup !== "全部") {
      result = result.filter(
        (n) => n.group_name === selectedGroup || n.tags.includes(selectedGroup),
      );
    }

    // 国家代码筛选
    if (selectedCountry) {
      result = result.filter((n) => n.country === selectedCountry);
    }

    // 排序
    result.sort((a, b) => {
      if (sortMode === "cpu") return b.metrics.cpu_percent - a.metrics.cpu_percent;
      if (sortMode === "ram") {
        const aRamPct = a.metrics.ram_total_bytes > 0 ? a.metrics.ram_used_bytes / a.metrics.ram_total_bytes : 0;
        const bRamPct = b.metrics.ram_total_bytes > 0 ? b.metrics.ram_used_bytes / b.metrics.ram_total_bytes : 0;
        return bRamPct - aRamPct;
      }
      if (sortMode === "bandwidth") {
        const aBw = a.metrics.net_rx_rate + a.metrics.net_tx_rate;
        const bBw = b.metrics.net_rx_rate + b.metrics.net_tx_rate;
        return bBw - aBw;
      }
      if (sortMode === "expires") {
        if (a.days_left === null) return 1;
        if (b.days_left === null) return -1;
        return a.days_left - b.days_left;
      }
      if (sortMode === "uptime") return b.metrics.uptime_seconds - a.metrics.uptime_seconds;
      // default: 在线优先，其次创建时间
      if (a.is_online !== b.is_online) return a.is_online ? -1 : 1;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

    return result;
  }, [nodes, selectedGroup, selectedCountry, sortMode]);

  const hasDemoNodes = nodes.some((n) => n.is_demo);

  // 未登录且无分享 Token 时的引导状态
  if (!shareToken && user === null && !isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 sm:py-24 text-center">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-3xl bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-400 mb-6 shadow-xs">
          <Activity className="h-8 w-8 stroke-[2.2]" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
          GoVPS 探针 · 我的 VPS 监控看板
        </h1>
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
          全景监控您的多节点 VPS 资产。实时掌握 CPU/内存/磁盘负载、网络上下行速率与国内三大运营商（电信/联通/移动）Ping 丢包热力色带。
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg" className="rounded-2xl px-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-xs">
            <Link href="/login?redirect=/monitor">
              <LogIn className="w-4 h-4 mr-2" />
              <span>登录并管理我的 VPS</span>
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/50 dark:bg-slate-950/40 pb-20 pt-4 sm:pt-6">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        {/* 页面顶栏：标题与状态 */}
        <div className="flex items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-600 text-white shadow-xs">
              <Activity className="w-4 h-4 stroke-[2.5]" />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
                我的探针
              </h1>
              <p className="text-[11px] text-slate-400 font-mono hidden sm:block">
                GoVPS 节点监控看板 · 4秒自适应刷新
              </p>
            </div>
          </div>

          {/* 公开模式徽标 */}
          {shareToken && (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/80 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>公开只读面板 ({userInfo.email || "访客模式"})</span>
            </div>
          )}
        </div>

        {/* 1. 顶部 4 大概览卡片 */}
        <OverviewHeader summary={summary} />

        {/* 2. 分组、国旗筛选与视图切换工具栏 */}
        <FilterToolbar
          groups={summary.groups}
          countries={summary.countries}
          selectedGroup={selectedGroup}
          onSelectGroup={setSelectedGroup}
          selectedCountry={selectedCountry}
          onSelectCountry={setSelectedCountry}
          viewMode={viewMode}
          onChangeViewMode={handleViewModeChange}
          sortMode={sortMode}
          onChangeSortMode={setSortMode}
          onRefresh={() => fetchData(true)}
          isRefreshing={isRefreshing}
          onAddNode={() => {
            setEditingNode(null);
            setIsAddOpen(true);
          }}
          onLoadDemo={handleLoadDemo}
          onClearDemo={handleClearDemo}
          hasDemoNodes={hasDemoNodes}
          isOwner={userInfo.is_owner}
          onShare={() => setIsShareModalOpen(true)}
          shareEnabled={userInfo.public_enabled}
        />

        {/* 3. 错误提示 */}
        {error && (
          <div className="flex items-center justify-between p-4 mb-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 dark:bg-rose-950/60 dark:border-rose-900 dark:text-rose-300 text-xs">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
            <Button size="sm" variant="ghost" onClick={() => fetchData(true)} className="h-7 text-xs px-2">
              重试
            </Button>
          </div>
        )}

        {/* 4. 节点列表 / 网格渲染 */}
        {isLoading && nodes.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-[380px] rounded-2xl bg-slate-200/70 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800"
              />
            ))}
          </div>
        ) : filteredNodes.length === 0 ? (
          /* 空状态 */
          <div className="flex flex-col items-center justify-center p-12 text-center rounded-3xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 my-4 shadow-xs">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 mb-4">
              <Server className="w-7 h-7" />
            </div>
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">
              {nodes.length === 0 ? "尚未添加任何 VPS 节点" : "没有符合当前筛选条件的节点"}
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1 mb-6">
              {nodes.length === 0
                ? "您可以点击下方按钮添加真实 VPS 并生成一键安装脚本，或一键载入逼真演示集群立即预览看板。"
                : "请尝试切换或清除上方分组与地区筛选。"}
            </p>
            {userInfo.is_owner && nodes.length === 0 && (
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  onClick={() => setIsAddOpen(true)}
                  className="rounded-xl px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs"
                >
                  <Plus className="w-3.5 h-3.5 mr-1" />
                  <span>添加我的第一台 VPS</span>
                </Button>
                <Button
                  variant="outline"
                  onClick={handleLoadDemo}
                  className="rounded-xl px-4 border-slate-200 dark:border-slate-800 text-xs font-semibold"
                >
                  <Sparkles className="w-3.5 h-3.5 mr-1 text-amber-500" />
                  <span>一键载入演示集群</span>
                </Button>
              </div>
            )}
          </div>
        ) : (
          /* 根据 4 种视图模式渲染 */
          <div>
            {viewMode === "large" && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
                {filteredNodes.map((node) => (
                  <LargeNodeCard
                    key={node.id}
                    node={node}
                    onClick={(n) => setDetailNode(n)}
                  />
                ))}
              </div>
            )}

            {viewMode === "compact" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5">
                {filteredNodes.map((node) => (
                  <CompactNodeCard
                    key={node.id}
                    node={node}
                    onClick={(n) => setDetailNode(n)}
                  />
                ))}
              </div>
            )}

            {viewMode === "mini" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {filteredNodes.map((node) => (
                  <MiniNodeCard
                    key={node.id}
                    node={node}
                    onClick={(n) => setDetailNode(n)}
                  />
                ))}
              </div>
            )}

            {viewMode === "list" && (
              <NodeListView
                nodes={filteredNodes}
                onSelectNode={(n) => setDetailNode(n)}
              />
            )}
          </div>
        )}
      </div>

      {/* 节点详情 24h Ping 与负载图表弹窗 */}
      <NodeDetailModal
        node={detailNode}
        isOpen={!!detailNode}
        onClose={() => setDetailNode(null)}
        shareToken={shareToken}
        isOwner={userInfo.is_owner}
        onEdit={(node) => {
          setEditingNode(node);
          setIsAddOpen(true);
        }}
      />

      {/* 添加 / 编辑节点弹窗 */}
      <AddNodeDialog
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        onSuccess={() => fetchData(true)}
        editingNode={editingNode}
      />

      {/* 公开分享设置弹窗 */}
      <Dialog open={isShareModalOpen} onOpenChange={setIsShareModalOpen}>
        <DialogContent className="max-w-md rounded-3xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xl">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2">
              <Share2 className="w-4 h-4 text-blue-600" />
              <span>公开监控主页设置</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-500">
              开启后，任何人可通过您的专属链接访问只读探针面板，无需登录。
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-2">
            <div className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
              <div className="flex flex-col">
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  公开监控面板
                </span>
                <span className="text-[11px] text-slate-400">
                  {userInfo.public_enabled ? "当前处于公开状态" : "当前为私有状态"}
                </span>
              </div>
              <Button
                size="sm"
                variant={userInfo.public_enabled ? "destructive" : "default"}
                onClick={handleToggleShare}
                className="h-8 text-xs rounded-xl"
              >
                {userInfo.public_enabled ? "关闭公开" : "开启公开"}
              </Button>
            </div>

            {userInfo.public_enabled && userInfo.share_token && (
              <div className="flex flex-col gap-1.5">
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

          <DialogFooter>
            <Button onClick={() => setIsShareModalOpen(false)} className="rounded-xl text-xs">
              完成
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
