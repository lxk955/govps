"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, MailCheck } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api/client";

/** 验证码登录两步表单：邮箱 → 6 位验证码。
 * 发送冷却 60s（后端强制）；dev_code 仅在服务端未配置发信时返回（本地开发）。 */

function safeNext(next: string | null): string {
  // 仅允许站内路径，防开放重定向
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return "/";
}

export function LoginForm({ next }: { next: string | null }) {
  const router = useRouter();
  const { user, login } = useAuth();

  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);

  // 已登录用户无需再看登录页
  useEffect(() => {
    if (user) router.replace(safeNext(next));
  }, [user, router, next]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const requestCode = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await apiFetch<{ ok: boolean; dev_code: string | null }>(
        "/api/auth/request-code",
        { method: "POST", body: { email: email.trim() } },
      );
      setDevCode(res.dev_code ?? null);
      setStep("code");
      setCooldown(60);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "发送失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  const submitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await apiFetch<{ token: string }>("/api/auth/verify", {
        method: "POST",
        body: { email: email.trim(), code: code.trim() },
      });
      await login(res.token);
      router.replace(safeNext(next));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "登录失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card mx-auto w-full max-w-sm rounded-xl border p-5">
      {step === "email" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void requestCode();
          }}
          className="flex flex-col gap-3"
        >
          <Label htmlFor="login-email">邮箱地址</Label>
          <Input
            id="login-email"
            type="email"
            required
            autoComplete="email"
            placeholder="you@example.com"
            className="text-base"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" disabled={loading || !email.trim()}>
            {loading && <Loader2 aria-hidden className="h-4 w-4 animate-spin" />}
            获取验证码
          </Button>
        </form>
      ) : (
        <form onSubmit={submitCode} className="flex flex-col gap-3">
          <p className="text-muted-foreground flex items-center gap-1.5 text-sm">
            <MailCheck aria-hidden className="h-4 w-4 shrink-0" />
            验证码已发送至 <span className="truncate font-medium">{email}</span>
          </p>
          <Label htmlFor="login-code">6 位验证码（10 分钟内有效）</Label>
          <Input
            id="login-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            required
            placeholder="000000"
            className="text-center font-mono text-base tracking-[0.4em]"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          />
          <Button type="submit" disabled={loading || code.length !== 6}>
            {loading && <Loader2 aria-hidden className="h-4 w-4 animate-spin" />}
            登录 / 注册
          </Button>
          <div className="flex items-center justify-between text-xs">
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
              onClick={() => setStep("email")}
            >
              换一个邮箱
            </button>
            <Button
              type="button"
              variant="link"
              size="sm"
              className="h-auto p-0 text-xs"
              disabled={cooldown > 0 || loading}
              onClick={() => void requestCode()}
            >
              {cooldown > 0 ? `${cooldown}s 后可重发` : "重新发送"}
            </Button>
          </div>
        </form>
      )}

      {/* 仅本地开发（服务端未配置发信）时后端会回传验证码 */}
      {devCode && (
        <p className="mt-3 rounded-lg bg-muted px-3 py-2 text-xs" role="note">
          本地开发模式：邮件未配置，本次验证码为{" "}
          <span className="font-mono font-bold tracking-widest">{devCode}</span>
        </p>
      )}

      {error && (
        <p role="alert" className="text-destructive mt-3 text-sm">
          {error}
        </p>
      )}

      <p className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
        登录即注册；邮箱仅用于发送库存与降价通知。验证码 10 分钟内有效、
        连续输错 5 次将锁定，需重新获取。
      </p>
    </div>
  );
}
