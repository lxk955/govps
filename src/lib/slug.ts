/**
 * 详情页复合 slug（refactor-plan P2：`id-短名`，id 兜底）。
 * URL 形如 /vps/123-lax-value-2c2g；解析只信任前导 id，
 * 名称段仅用于可读性与 SEO，不参与查找（商家改名不断链）。
 */

export function slugify(name: string): string {
  const s = name
    .toLowerCase()
    .replace(/[^a-z0-9一-鿿]+/g, "-")
    .replace(/^-+|-+$/g, "");
  // 截短避免超长 URL；中文保留（percent-encoding 由浏览器处理）
  return s.slice(0, 60).replace(/-+$/g, "");
}

export function productHref(id: number, name: string): string {
  const s = slugify(name);
  return `/vps/${id}${s ? `-${s}` : ""}`;
}

/** 从 slug 解析产品 id；无合法 id 返回 null（触发 404）。 */
export function parseSlugId(slug: string): number | null {
  const m = /^(\d+)/.exec(decodeURIComponent(slug));
  if (!m) return null;
  const id = Number(m[1]);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
