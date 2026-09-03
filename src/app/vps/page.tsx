import { redirect } from "next/navigation";

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * /vps 路由重定向：
 * 产品列表已直接并入根路径 /，访问 /vps 及其带参链接时（如 /vps?merchant=dmit），
 * 自动重定向到根路径对应地址（/?merchant=dmit），保持旧链接与 SEO 完全兼容。
 */
export default async function VpsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) {
      for (const item of v) qs.append(k, item);
    } else {
      qs.set(k, v);
    }
  }
  const query = qs.toString();
  redirect(query ? `/?${query}` : "/");
}
