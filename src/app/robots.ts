import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://govps.xyz";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // API 与购买跳转不进索引
        disallow: ["/api/", "/go/"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
