import type { MetadataRoute } from "next";

import { listProducts } from "@/lib/api/endpoints";
import { productHref } from "@/lib/slug";
import { SITE_URL } from "@/lib/site";

/**
 * 站点地图：静态路由 + 在售产品详情页（取热榜第一页，上限 100 条）。
 * 数据获取失败时降级为仅静态路由，保证 sitemap 始终可返回。
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/vps`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${SITE_URL}/deals`, lastModified: now, changeFrequency: "hourly", priority: 0.8 },
    { url: `${SITE_URL}/providers`, lastModified: now, changeFrequency: "daily", priority: 0.7 },
    { url: `${SITE_URL}/ip`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/ip/webrtc`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/ip/dnsleak`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/ip/fingerprint`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
  ];

  const products = await listProducts({ size: 100, sort: "hot" }).catch(() => ({ total: 0, items: [] }));
  return [
    ...staticRoutes,
    ...products.items.map((p) => ({
      url: `${SITE_URL}${productHref(p.id, p.name)}`,
      lastModified: p.updated_at ? new Date(p.updated_at) : now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
  ];
}
