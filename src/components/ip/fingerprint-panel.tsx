"use client";

import { useState } from "react";
import { Fingerprint } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * 浏览器指纹检测：采集常见可指纹化属性并本地哈希展示。
 * 全部计算在本页内完成，不上传任何结果。
 */

interface FpEntry {
  label: string;
  value: string;
}

async function sha256Hex(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function canvasFingerprint(): string {
  const c = document.createElement("canvas");
  c.width = 240;
  c.height = 60;
  const ctx = c.getContext("2d");
  if (!ctx) return "unavailable";
  ctx.textBaseline = "top";
  ctx.font = "16px 'Arial'";
  ctx.fillStyle = "#f60";
  ctx.fillRect(0, 0, 100, 30);
  ctx.fillStyle = "#069";
  ctx.fillText("GoVPS 指纹探测 🖼", 2, 12);
  ctx.strokeStyle = "rgba(102,204,0,0.7)";
  ctx.arc(50, 30, 20, 0, Math.PI * 1.5);
  ctx.stroke();
  return c.toDataURL();
}

function webglInfo(): { vendor: string; renderer: string } {
  try {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl") ?? c.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (!gl) return { vendor: "unavailable", renderer: "" };
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    return {
      vendor: ext ? String(gl.getParameter(ext.UNMASKED_VENDOR_WEBGL)) : String(gl.getParameter(gl.VENDOR)),
      renderer: ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : "",
    };
  } catch {
    return { vendor: "unavailable", renderer: "" };
  }
}

export function FingerprintPanel() {
  const [entries, setEntries] = useState<FpEntry[] | null>(null);
  const [hash, setHash] = useState<string | null>(null);

  const run = async () => {
    const nav = navigator;
    const gl = webglInfo();
    let timezone = "";
    try {
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";
    } catch {
      /* 忽略 */
    }
    const list: FpEntry[] = [
      { label: "User-Agent", value: nav.userAgent },
      { label: "语言", value: nav.language },
      { label: "语言列表", value: (nav.languages ?? []).join(", ") },
      { label: "CPU 逻辑核数", value: String(nav.hardwareConcurrency ?? "?") },
      { label: "内存近似值 (GB)", value: String((nav as Navigator & { deviceMemory?: number }).deviceMemory ?? "不可用") },
      { label: "屏幕分辨率", value: `${screen.width}×${screen.height} @${window.devicePixelRatio}x` },
      { label: "可用窗口", value: `${screen.availWidth}×${screen.availHeight}` },
      { label: "色深 (bit)", value: String(screen.colorDepth) },
      { label: "时区", value: timezone || "?" },
      { label: "平台", value: nav.platform || "?" },
      { label: "触控点数", value: String(nav.maxTouchPoints ?? 0) },
      { label: "Cookie 开启", value: nav.cookieEnabled ? "是" : "否" },
      { label: "WebGL 厂商", value: gl.vendor },
      { label: "WebGL 渲染器", value: gl.renderer || "—" },
      { label: "Canvas 绘制哈希", value: await sha256Hex(canvasFingerprint()) },
    ];
    setEntries(list);
    setHash(await sha256Hex(list.map((e) => `${e.label}:${e.value}`).join("|")));
  };

  return (
    <>
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">浏览器指纹</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          即使不用 Cookie，网站也可以通过浏览器与硬件特征组合唯一识别你。本页演示最常见的指纹来源，
          所有计算仅在本地进行、不回传服务器——但请记住：任何网站都可以做同样的事并悄悄上传。
        </p>
      </header>

      <Button onClick={run} className="mb-4">
        <Fingerprint aria-hidden className="h-4 w-4" />
        生成我的指纹
      </Button>

      {entries && (
        <div role="status" className="bg-card rounded-xl border p-5">
          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-xs font-medium">综合指纹（SHA-256，仅本地计算）</p>
            <p className="mt-1 break-all font-mono text-xs leading-relaxed">{hash}</p>
          </div>
          <dl className="mt-4 flex flex-col divide-y">
            {entries.map((e) => (
              <div key={e.label} className="flex min-w-0 items-start justify-between gap-4 py-2">
                <dt className="text-muted-foreground shrink-0 text-xs">{e.label}</dt>
                <dd className="min-w-0 break-all text-right font-mono text-xs">{e.value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
            缓解方式：使用 Firefox 的 resistFingerprinting、Brave 的随机化指纹或 Tor Browser；
            常规浏览器的扩展级缓解（如 Canvas Blocker）也能显著提高追踪成本。
          </p>
        </div>
      )}
    </>
  );
}
