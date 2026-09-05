import type { MetadataRoute } from "next";

import { listMerchants, listProducts } from "@/lib/api/endpoints";
import { productHref } from "@/lib/slug";
import { SITE_URL } from "@/lib/site";

/**
 * 动态全站 Sitemap：
 * 1. 核心功能与工具页面；
 * 2. 各服务商专属聚合入口（/?merchant=...）；
 * 3. 全量在售及收录的 VPS 套餐详情页（支持上百款，动态取 lastmod）。
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  // 1. 核心公开静态路由
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, lastModified: now, changeFrequency: "hourly", priority: 1.0 },
    { url: `${SITE_URL}/deals`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${SITE_URL}/routes`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/routes/cn2-gia`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/routes/9929`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/routes/cmin2`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/routes/4837`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/providers`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/ip`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${SITE_URL}/ip/dnsleak`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/ip/webrtc`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/ip/fingerprint`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
  ];

  // 2. 服务商聚合入口
  const merchants = await listMerchants().catch(() => []);
  const merchantRoutes: MetadataRoute.Sitemap = merchants.map((m) => ({
    url: `${SITE_URL}/?merchant=${encodeURIComponent(m.slug)}`,
    lastModified: m.last_success_at ? new Date(m.last_success_at) : now,
    changeFrequency: "daily" as const,
    priority: 0.8,
  }));

  // 3. 全量套餐详情页（覆盖全部在售套餐，通过分页获取全部收录）
  const allProducts: Array<{ id: number; name: string; updated_at?: string | null }> = [];
  try {
    for (let page = 1; page <= 6; page++) {
      const res = await listProducts({ page, size: 100, sort: "hot" });
      if (!res.items || res.items.length === 0) break;
      allProducts.push(...res.items);
      if (allProducts.length >= res.total || res.items.length < 100) break;
    }
  } catch {
    // 数据获取失败时降级，不阻塞地图构建
  }

  const productRoutes: MetadataRoute.Sitemap = allProducts.map((p) => ({
    url: `${SITE_URL}${productHref(p.id, p.name)}`,
    lastModified: p.updated_at ? new Date(p.updated_at) : now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  return [...staticRoutes, ...merchantRoutes, ...productRoutes];
}
