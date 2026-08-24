import type { Metadata } from "next";

import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = {
  title: "登录",
  description: "邮箱验证码登录 GoVPS，关注套餐并接收降价与补货通知。",
  // 登录页对搜索引擎无价值：不建索引
  robots: { index: false, follow: true },
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const nextRaw = Array.isArray(sp.next) ? sp.next[0] : sp.next;

  return (
    <div className="mx-auto flex min-h-[60dvh] w-full max-w-7xl flex-col justify-center px-4 py-8">
      <header className="mb-5 text-center">
        <h1 className="text-xl font-bold tracking-tight">登录 GoVPS</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          无密码登录：输入邮箱获取验证码即可，注册与登录是同一步。
        </p>
      </header>
      <LoginForm next={nextRaw ?? null} />
    </div>
  );
}
