import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-[60dvh] flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="text-muted-foreground text-sm">404</p>
      <h1 className="text-xl font-bold">页面不存在或套餐已下架</h1>
      <p className="text-muted-foreground max-w-md text-sm leading-relaxed">
        你访问的页面不存在，对应的 VPS 套餐可能已被商家下架。
      </p>
      <Button asChild variant="outline" size="sm" className="mt-1">
        <Link href="/">浏览在售套餐</Link>
      </Button>
    </main>
  );
}
