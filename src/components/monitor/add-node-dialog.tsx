"use client";

import React, { useEffect, useState } from "react";
import { Check, Copy, Server, Terminal, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MonitorNode } from "./types";

interface AddNodeDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  editingNode?: MonitorNode | null;
}

export function AddNodeDialog({
  isOpen,
  onClose,
  onSuccess,
  editingNode,
}: AddNodeDialogProps) {
  const [name, setName] = useState("");
  const [country, setCountry] = useState("hk");
  const [osType, setOsType] = useState("debian");
  const [groupName, setGroupName] = useState("主力");
  const [tagsInput, setTagsInput] = useState("");
  const [cpuCores, setCpuCores] = useState("1");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [billingCycle, setBillingCycle] = useState("monthly");
  const [trafficLimitGb, setTrafficLimitGb] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [installCommand, setInstallCommand] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isOpen && editingNode) {
      setName(editingNode.name);
      setCountry(editingNode.country);
      setOsType(editingNode.os_type);
      setGroupName(editingNode.group_name);
      setTagsInput(editingNode.tags.join(", "));
      setCpuCores(String(editingNode.cpu_cores));
      setPrice(editingNode.price !== null ? String(editingNode.price) : "");
      setCurrency(editingNode.currency);
      setBillingCycle(editingNode.billing_cycle);
      setTrafficLimitGb(
        editingNode.traffic_limit_gb !== null ? String(editingNode.traffic_limit_gb) : "",
      );
    } else if (isOpen) {
      setName("");
      setCountry("hk");
      setOsType("debian");
      setGroupName("主力");
      setTagsInput("");
      setCpuCores("1");
      setPrice("");
      setCurrency("USD");
      setBillingCycle("monthly");
      setTrafficLimitGb("");
    }
    setInstallCommand(null);
    setErrorMsg(null);
    setCopied(false);
  }, [isOpen, editingNode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg("请输入节点名称");
      return;
    }

    const token = typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
    if (!token) {
      setErrorMsg("未检测到有效登录凭证，请先登录账户后再执行此操作");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    const tags = tagsInput
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean);

    const payload = {
      name: name.trim(),
      country: country.trim().toLowerCase(),
      os_type: osType.trim().toLowerCase(),
      group_name: groupName.trim() || "主力",
      tags,
      cpu_cores: Number(cpuCores) || 1,
      price: price ? parseFloat(price) : null,
      currency: currency.toUpperCase(),
      billing_cycle: billingCycle,
      traffic_limit_gb: trafficLimitGb ? parseFloat(trafficLimitGb) : null,
    };

    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };

    try {
      if (editingNode) {
        const res = await fetch(`/api/monitor/nodes/${editingNode.id}`, {
          method: "PUT",
          headers,
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || (res.status === 401 ? "登录已过期，请重新登录" : "更新失败"));
        }
        onSuccess();
        onClose();
      } else {
        const res = await fetch("/api/monitor/nodes", {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || (res.status === 401 ? "登录已过期，请重新登录" : "创建失败"));
        }
        const data = await res.json();
        setInstallCommand(data.install_command);
        onSuccess();
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "请求异常，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!editingNode) return;
    if (!window.confirm(`确定要删除节点「${editingNode.name}」吗？相关监控历史将被彻底清除。`)) return;

    const token = typeof window !== "undefined" ? localStorage.getItem("govps_token") : null;
    if (!token) {
      setErrorMsg("未检测到有效登录凭证，请先登录账户");
      return;
    }

    setIsDeleting(true);
    setErrorMsg(null);

    try {
      const res = await fetch(`/api/monitor/nodes/${editingNode.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || (res.status === 401 ? "登录已过期，请重新登录" : "删除失败"));
      }
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "删除失败，请稍后重试");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCopy = () => {
    if (!installCommand) return;
    navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md sm:max-w-lg rounded-3xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-xl">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <span>{editingNode ? "编辑 VPS 节点" : "添加 VPS 监控节点"}</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-500">
            {editingNode
              ? "修改 VPS 资产属性与标签"
              : "添加后系统将生成专属一键安装命令，在 VPS 运行即可完成监控对接"}
          </DialogDescription>
        </DialogHeader>

        {installCommand ? (
          /* 安装命令呈现阶段 */
          <div className="flex flex-col gap-4 py-2">
            <div className="p-4 rounded-2xl bg-emerald-50/80 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300">
              <span className="font-bold">节点创建成功！</span>
              <p className="mt-1 text-[11px] leading-relaxed">
                请在您的 Linux VPS 终端中以 root 身份执行下方一键命令。脚本将自动配置后台监控服务并开始实时上报数据。
              </p>
            </div>

            <div className="relative flex flex-col gap-1.5">
              <Label className="text-xs text-slate-600 dark:text-slate-300 font-semibold flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-slate-400" />
                <span>一键安装命令</span>
              </Label>
              <div className="relative group">
                <textarea
                  readOnly
                  rows={3}
                  value={installCommand}
                  className="w-full font-mono text-xs p-3 pr-12 rounded-xl bg-slate-900 text-slate-100 border border-slate-800 focus:outline-hidden select-all"
                />
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleCopy}
                  className="absolute right-2 top-2 h-8 px-2.5 rounded-lg text-xs gap-1 bg-slate-800 hover:bg-slate-700 text-white"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">已复制</span>
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

            <DialogFooter className="mt-2">
              <Button onClick={onClose} className="rounded-xl px-5 bg-blue-600 hover:bg-blue-700 text-white font-semibold">
                完成
              </Button>
            </DialogFooter>
          </div>
        ) : (
          /* 节点表单填写阶段 */
          <form onSubmit={handleSubmit} className="flex flex-col gap-3.5 py-1">
            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-50 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300 text-xs font-medium">
                {errorMsg}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-semibold">节点名称 *</Label>
                <Input
                  placeholder="如: 香港 CMI"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="h-9 text-xs rounded-xl"
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-semibold">地区代码</Label>
                <select
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                >
                  <option value="hk">🇭🇰 香港 (HK)</option>
                  <option value="jp">🇯🇵 日本 (JP)</option>
                  <option value="us">🇺🇸 美国 (US)</option>
                  <option value="sg">🇸🇬 新加坡 (SG)</option>
                  <option value="de">🇩🇪 德国 (DE)</option>
                  <option value="gb">🇬🇧 英国 (GB)</option>
                  <option value="kr">🇰🇷 韩国 (KR)</option>
                  <option value="ca">🇨🇦 加拿大 (CA)</option>
                  <option value="tw">🇹🇼 台湾 (TW)</option>
                  <option value="cn">🇨🇳 中国大陆 (CN)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-semibold">操作系统</Label>
                <select
                  value={osType}
                  onChange={(e) => setOsType(e.target.value)}
                  className="h-9 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                >
                  <option value="debian">Debian</option>
                  <option value="ubuntu">Ubuntu</option>
                  <option value="centos">CentOS</option>
                  <option value="alpine">Alpine</option>
                  <option value="arch">Arch Linux</option>
                  <option value="windows">Windows</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-semibold">分组</Label>
                <Input
                  placeholder="如: 主力 / 吃灰"
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  className="h-9 text-xs rounded-xl"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-semibold">CPU 核数</Label>
                <Input
                  type="number"
                  min={1}
                  value={cpuCores}
                  onChange={(e) => setCpuCores(e.target.value)}
                  className="h-9 text-xs rounded-xl font-mono"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold">标签 (逗号分隔)</Label>
              <Input
                placeholder="如: 主力, V4, V6, CN2 GIA, 三网优化"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                className="h-9 text-xs rounded-xl"
              />
            </div>

            {/* 资产费用与流量 */}
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex flex-col gap-3">
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                资产与账单配置（可选）
              </span>

              <div className="grid grid-cols-3 gap-2.5">
                <div className="flex flex-col gap-1">
                  <Label className="text-[11px] text-slate-500">续费价格</Label>
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="如: 39.00"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    className="h-8 text-xs rounded-lg font-mono"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <Label className="text-[11px] text-slate-500">币种</Label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="h-8 px-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 font-mono"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="CNY">CNY (¥)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="CAD">CAD</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <Label className="text-[11px] text-slate-500">计费周期</Label>
                  <select
                    value={billingCycle}
                    onChange={(e) => setBillingCycle(e.target.value)}
                    className="h-8 px-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                  >
                    <option value="monthly">按月付</option>
                    <option value="quarterly">按季付</option>
                    <option value="semi-annually">按半年付</option>
                    <option value="annually">按年付</option>
                    <option value="triennially">按三年付</option>
                  </select>
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-[11px] text-slate-500">月度流量额度 (GB)</Label>
                <Input
                  type="number"
                  placeholder="留空为无限制流量，如: 1024"
                  value={trafficLimitGb}
                  onChange={(e) => setTrafficLimitGb(e.target.value)}
                  className="h-8 text-xs rounded-lg font-mono"
                />
              </div>
            </div>

            <DialogFooter className="mt-2 flex items-center justify-between sm:justify-between w-full">
              {editingNode ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleDelete}
                  disabled={isSubmitting || isDeleting}
                  className="rounded-xl h-9 text-xs px-3 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/50 border-red-200 dark:border-red-900"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" />
                  <span>{isDeleting ? "正在删除..." : "删除节点"}</span>
                </Button>
              ) : (
                <div />
              )}
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" onClick={onClose} className="rounded-xl h-9 text-xs">
                  取消
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting || isDeleting}
                  className="rounded-xl h-9 text-xs px-5 bg-blue-600 hover:bg-blue-700 text-white font-semibold"
                >
                  {isSubmitting ? "正在处理..." : editingNode ? "保存更改" : "创建并获取命令"}
                </Button>
              </div>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
