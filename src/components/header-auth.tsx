"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CircleUserRound, LogOut, Star } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** 头部登录态区域：未登录显示登录链接；已登录显示账户菜单。
 * 挂载前渲染占位（主题同策略），保证 SSR HTML 稳定、不泄露也不误判登录态。 */

export function HeaderAuth() {
  const { user } = useAuth();
  const pathname = usePathname();

  // 挂载检查完成前渲染等尺寸占位，避免水合不一致
  if (user === undefined) {
    return (
      <Button variant="ghost" size="sm" disabled aria-hidden className="h-8 gap-1.5 px-2 text-xs opacity-0">
        登录
      </Button>
    );
  }

  if (user === null) {
    return (
      <Button asChild variant="outline" size="sm" className="h-8 gap-1.5 px-2.5 text-xs">
        <Link href={`/login?next=${encodeURIComponent(pathname || "/")}`}>登录</Link>
      </Button>
    );
  }

  return <AccountMenu email={user.email} />;
}

function AccountMenu({ email }: { email: string }) {
  const { logout } = useAuth();
  const router = useRouter();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 max-w-44 gap-1.5 px-2 text-xs">
          <CircleUserRound aria-hidden className="h-4 w-4 shrink-0" />
          <span className="truncate">{email}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="max-w-52 truncate">{email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/watchlist")}>
          <Star aria-hidden />
          我的关注
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onSelect={() => {
            logout();
            router.push("/");
          }}
        >
          <LogOut aria-hidden />
          退出登录
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
