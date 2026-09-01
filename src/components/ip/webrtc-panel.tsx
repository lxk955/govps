"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Globe, Loader2, Wifi } from "lucide-react";

import { Button } from "@/components/ui/button";
import { checkIp, type IpCheckResult } from "@/lib/api/endpoints";

/**
 * WebRTC 泄露检测：RTCPeerConnection 收集 ICE 候选，
 * host 候选暴露本机局域网 IP，srflx 候选暴露 STUN 视角的公网 IP。
 * 与后端 /api/ip/check 的出口 IP 比对：若 srflx 公网 IP ≠ HTTP 出口 IP，
 * 说明存在代理/VPN 下的 WebRTC 真实 IP 泄露面。
 */

interface LeakResult {
  /** mDNS 混淆前的本机候选（含局域网 IP 或 .local 主机名） */
  localCandidates: string[];
  /** STUN 视角公网 IP（srflx / relay） */
  publicCandidates: string[];
}

const STUN_SERVERS = [
  "stun:stun.l.google.com:19302",
  "stun:stun.cloudflare.com:3478",
];

function extractIpsFromSdp(sdp: string): { local: string[]; public: string[] } {
  const local: string[] = [];
  const pub: string[] = [];
  // ICE 候选行形如 candidate:... typ host|srflx|prflx|relay
  for (const line of sdp.split("\n")) {
    if (!line.includes("candidate:")) continue;
    const isHost = /\btyp\s+host\b/.test(line);
    const isSrflx = /\btyp\s+(srflx|relay)\b/.test(line);
    if (!isHost && !isSrflx) continue;
    const ipMatch = /(?:\d{1,3}(?:\.\d{1,3}){3}|[a-f0-9]{0,4}(?::[a-f0-9]{0,4}){2,7})/i.exec(
      line,
    );
    if (!ipMatch) continue;
    const ip = ipMatch[0].toLowerCase();
    // 过滤无效占位与 mDNS 地址（.local 由浏览器隐藏真实 IP）
    if (ip.endsWith(".local")) {
      local.push(ip);
      continue;
    }
    if (isHost) local.push(ip);
    else pub.push(ip);
  }
  return { local, public: pub };
}

function dedupe(list: string[]): string[] {
  return [...new Set(list)];
}

export function WebrtcPanel() {
  const [result, setResult] = useState<LeakResult | null>(null);
  const [exitIp, setExitIp] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [unsupported, setUnsupported] = useState(false);

  const runCheck = useCallback(async () => {
    if (typeof RTCPeerConnection === "undefined") {
      setUnsupported(true);
      return;
    }
    setRunning(true);
    setResult(null);

    checkIp()
      .then((r: IpCheckResult) => setExitIp(r.ip))
      .catch(() => setExitIp(null));

    const leaked: LeakResult = { localCandidates: [], publicCandidates: [] };
    try {
      const pc = new RTCPeerConnection({ iceServers: [{ urls: STUN_SERVERS }] });
      pc.createDataChannel("probe");
      pc.onicecandidate = (e) => {
        if (!e.candidate) return;
        const { local, public: pub } = extractIpsFromSdp(e.candidate.candidate);
        leaked.localCandidates.push(...local);
        leaked.publicCandidates.push(...pub);
      };
      await pc.setLocalDescription(await pc.createOffer());
      // 给 ICE 收集留出时间窗口
      await new Promise((r) => setTimeout(r, 4000));
      pc.close();
    } catch {
      /* 收集失败按无泄露处理 */
    }
    leaked.localCandidates = dedupe(leaked.localCandidates).filter((x) => !/^fe80|^fd[0-9a-f]{2}:|^169\.254/i.test(x));
    leaked.publicCandidates = dedupe(leaked.publicCandidates);
    setResult(leaked);
    setRunning(false);
  }, []);

  useEffect(() => {
    document.title = "WebRTC 泄露检测 | GoVPS · VPS雷达";
  }, []);

  const hasLeak =
    result != null &&
    (result.localCandidates.some((c) => c.includes(".")) ||
      (exitIp != null && result.publicCandidates.some((c) => c !== exitIp.toLowerCase())));

  return (
    <>
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">WebRTC 泄露检测</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          浏览器的 WebRTC 功能可能绕过代理，向 STUN 服务器暴露你的真实公网 IP 与本机局域网地址。
          使用 VPN/代理的用户尤其需要关注。
        </p>
      </header>

      <Button onClick={runCheck} disabled={running} className="mb-4">
        {running ? (
          <>
            <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
            正在收集 ICE 候选…
          </>
        ) : (
          "开始检测"
        )}
      </Button>

      {unsupported && (
        <div role="alert" className="bg-card text-muted-foreground rounded-xl border p-6 text-sm">
          当前浏览器不支持 WebRTC，无法进行此项检测。
        </div>
      )}

      {!unsupported && result && (
        <div
          role="status"
          className={`rounded-xl border p-5 ${hasLeak ? "border-amber-500/40 bg-amber-500/5" : "bg-card"}`}
        >
          <p className="flex items-center gap-2 font-medium">
            {hasLeak ? (
              <>
                <AlertTriangle aria-hidden className="h-5 w-5 text-amber-500" />
                发现潜在泄露面
              </>
            ) : (
              <>
                <CheckCircle2 aria-hidden className="h-5 w-5 text-emerald-600" />
                未发现明显泄露
              </>
            )}
          </p>

          <dl className="mt-4 flex flex-col gap-3 text-sm">
            <div className="flex min-w-0 items-start gap-2">
              <Wifi aria-hidden className="text-muted-foreground mt-0.5 h-4 w-4 shrink-0" />
              <div className="min-w-0">
                <dt className="font-medium">HTTP 出口 IP（对照）</dt>
                <dd className="text-muted-foreground break-all tabular-nums">{exitIp ?? "获取失败"}</dd>
              </div>
            </div>
            <div className="flex min-w-0 items-start gap-2">
              <Globe aria-hidden className="text-muted-foreground mt-0.5 h-4 w-4 shrink-0" />
              <div className="min-w-0">
                <dt className="font-medium">STUN 视角公网 IP（srflx）</dt>
                <dd className="text-muted-foreground mt-0.5 break-all tabular-nums">
                  {result.publicCandidates.length > 0 ? result.publicCandidates.join(", ") : "未收集到"}
                  {exitIp != null && result.publicCandidates.length > 0 && !hasLeakPublic(result.publicCandidates, exitIp) && (
                    <span className="ml-1 inline-block rounded bg-emerald-100 px-1 text-xs text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      与出口一致
                    </span>
                  )}
                  {exitIp != null && hasLeakPublic(result.publicCandidates, exitIp) && (
                    <span className="ml-1 inline-block rounded bg-amber-100 px-1 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                      与出口不一致 → 存在绕过代理的直连路径
                    </span>
                  )}
                </dd>
              </div>
            </div>
            <div className="flex min-w-0 items-start gap-2">
              <Wifi aria-hidden className="text-muted-foreground mt-0.5 h-4 w-4 shrink-0" />
              <div className="min-w-0">
                <dt className="font-medium">本机候选地址（host）</dt>
                <dd className="text-muted-foreground mt-0.5 break-all">
                  {result.localCandidates.length > 0 ? result.localCandidates.join(", ") : "未收集到（浏览器已通过 mDNS 隐藏）"}
                </dd>
              </div>
            </div>
          </dl>

          <p className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
            缓解方式：浏览器禁用 WebRTC 或安装 uBlock Origin 等扩展限制非媒体站的 ICE 收集；
            本页面仅在本地与 STUN 服务间建立探测连接，不向你以外的任何服务器上报结果。
          </p>
        </div>
      )}
    </>
  );
}

function hasLeakPublic(publics: string[], exitIp: string): boolean {
  return publics.some((c) => c !== exitIp.toLowerCase());
}
