"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

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
    <div className="mx-auto w-full max-w-sm">
      <div className="border-border bg-card rounded-2xl border p-6 shadow-sm">

        {step === "email" ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void requestCode();
            }}
            className="space-y-3"
          >
            <Label htmlFor="login-email" className="sr-only">
              邮箱地址
            </Label>
            <Input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="focus-visible:border-blue-400 focus-visible:ring-0 h-auto w-full rounded-lg border-border px-3 py-2.5 text-base sm:text-sm"
            />
            <Button
              type="submit"
              disabled={loading || !email.trim()}
              className="h-auto w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              {loading ? "发送中…" : "获取验证码"}
            </Button>
          </form>
        ) : (
          <form onSubmit={submitCode} className="space-y-3">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              验证码已发送至{" "}
              <b className="text-slate-700 dark:text-slate-300">{email}</b>
              <button
                type="button"
                onClick={() => {
                  setStep("email");
                  setCode("");
                }}
                className="ml-2 cursor-pointer text-blue-600 hover:underline dark:text-blue-400"
              >
                更换邮箱
              </button>
            </p>
            <Label htmlFor="login-code" className="sr-only">
              6 位验证码
            </Label>
            <Input
              id="login-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              required
              placeholder="6 位验证码"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="focus-visible:border-blue-400 focus-visible:ring-0 h-auto w-full rounded-lg border-border px-3 py-2.5 text-center text-lg tracking-[0.5em]"
            />
            <Button
              type="submit"
              disabled={loading || code.length !== 6}
              className="h-auto w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              {loading ? "验证中…" : "登录"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={cooldown > 0 || loading}
              onClick={() => void requestCode()}
              className="hover:text-blue-600 dark:text-slate-500 h-auto w-full text-sm text-slate-400 hover:bg-transparent"
            >
              {cooldown > 0 ? `${cooldown}s 后可重新发送` : "重新发送验证码"}
            </Button>
            {devCode && (
              <p className="rounded bg-amber-50 p-2 text-center text-xs text-amber-600 dark:bg-amber-950/50 dark:text-amber-400">
                开发模式（未配置邮件服务），验证码：<b>{devCode}</b>
              </p>
            )}
          </form>
        )}

        {error && (
          <p role="alert" className="mt-3 text-sm text-red-500 dark:text-red-400">
            {error}
          </p>
        )}

        <p className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
          登录即注册；邮箱仅用于发送库存与降价通知。验证码 10 分钟内有效、
          连续输错 5 次将锁定，需重新获取。
        </p>
      </div>
    </div>
  );
}
