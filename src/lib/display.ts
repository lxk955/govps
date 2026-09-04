/**
 * 展示层派生逻辑（1:1 移植自旧站 web/src/display.ts，规则零改动）。
 *
 * 涉及三处：套餐短名称、三网线路归纳、线路等级着色。
 * 着色 class 在原亮色值基础上补 dark: 变体——旧站无暗色模式，此为新站增补。
 */

type NameLike = { name: string; merchant?: { slug?: string } };
type LineLike = NameLike & { line_tags?: string[] };

// 全大写词 → 友好写法
const ACRONYMS: Record<string, string> = {
  ECOMMERCE: "E-Commerce",
  KVM: "KVM",
  VPS: "VPS",
  CN2: "CN2",
  GIA: "GIA",
  SLA: "SLA",
  PROMO: "Promo",
  AMD: "AMD",
};

/** 全大写单词转首字母大写；已知缩写按映射处理；含点的代号（如 LAX.VPS.CN）保持原样 */
function friendlyCase(s: string): string {
  return s
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => {
      const key = w.toUpperCase().replace(/[^A-Z0-9]/g, "");
      if (ACRONYMS[key]) return ACRONYMS[key];
      // 仅转换字母开头的全大写单词，数字开头的代号（15T、2C）保持原样
      if (/^[A-Z][A-Z0-9]+$/.test(w) && w.length > 2) return w[0] + w.slice(1).toLowerCase();
      return w;
    })
    .join(" ");
}

/** 搬瓦工：`SPECIAL 20G KVM PROMO V5 - CN2 GIA ECOMMERCE` → `CN2 GIA E-Commerce` */
function bandwagonShort(name: string): string {
  let n = name
    .replace(/^SPECIAL\s+\d+G\s+KVM\s+PROMO\s+V\d+\s*-\s*/i, "")
    .replace(/^\d+G\s+KVM\s*-\s*/i, "")
    .replace(/\s+HIBW\s+(\d+T)\b/i, " · $1 大流量")
    .replace(/\s+-\s+/g, " ")
    .trim();
  n = friendlyCase(n);
  if (n === "Promo") n = "KVM Promo";
  return n || name;
}

/** DMIT：剥掉冗余的 PVM. 前缀与中文括号注释 → `LAX.Pro.WEE` */
function dmitShort(name: string): string {
  return name.replace(/^PVM\./i, "").replace(/\s*[(（].*$/, "").trim() || name;
}

/** Dedione：剥掉日期前缀与价格后缀 → `LAX.VPS.CN.1C1G20G Special` */
function dedioneShort(name: string): string {
  return (
    name
      .replace(/^\d{6,8}-/, "")
      .replace(/-\d+\.\d{2}$/, "")
      .replace(/-Special$/i, " Special")
      .replace(/-Annual$/i, " 年付")
      .trim() || name
  );
}

/** ZgoCloud：国家码前缀与冗余分隔符清理 */
function zgocloudShort(name: string): string {
  return (
    name
      .replace(/^(DE|US|UK|JP|SG|NL)\s+/i, "")
      .replace(/\bHongKong\b/g, "Hong Kong")
      .replace(/\s+-\s+/g, " ")
      .replace(/\bSpecials\b/g, "Special")
      .trim() || name
  );
}

/** V.PS：剥掉括号中文注释 → `Tokyo Mini Pro` */
function vpsShort(name: string): string {
  return name.replace(/\s*[(（].*$/, "").trim() || name;
}

const RULES: Record<string, (name: string) => string> = {
  bandwagon: bandwagonShort,
  dmit: dmitShort,
  dedione: dedioneShort,
  zgocloud: zgocloudShort,
  vps: vpsShort,
};

/** 列表/卡片展示用短名称；未知商家原样返回 */
export function shortName(p: NameLike): string {
  const rule = p.merchant?.slug ? RULES[p.merchant.slug] : undefined;
  return rule ? rule(p.name) : p.name;
}

// ─── 线路展示（上层总结性等级 + 下层分电信/联通/移动三家各自走什么网） ───

export interface LineBadge {
  text: string;
  class: string;
  title: string;
}

export interface LineInfo {
  /** 上层总结：如 `三网 CN2 GIA`、`三网各自优化`、`普通BGP` */
  tier: string;
  /** 下层拆分的三家运营商行：['电信:CN2 GIA', '联通:9929', '移动:CMIN2'] */
  carrierRows: string[];
  /** 线路价值等级：3 顶级 > 2 高端 > 1 优化 > 0 普通，决定着色 */
  level: 0 | 1 | 2 | 3;
  badges: LineBadge[];
}

export function lineBadgeClass(text: string): string {
  const t = text.toUpperCase();
  if (t.includes("GIA"))
    return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300";
  if (t.includes("9929"))
    return "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/60 dark:text-blue-300";
  if (t.includes("CMIN2"))
    return "border-purple-200 bg-purple-50 text-purple-700 dark:border-purple-800 dark:bg-purple-950/60 dark:text-purple-300";
  if (t.includes("4837"))
    return "border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-800 dark:bg-cyan-950/60 dark:text-cyan-300";
  if (t.includes("GT") || t === "CN2")
    return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-300";
  if (t.includes("国际"))
    return "border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400";
  return "border-indigo-100 bg-indigo-50 text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300";
}

/** 三家运营商固定顺序拼出 `电信:xx 联通:xx 移动:xx`，空值用「普通直连」补位 */
function carriers(ct: string, cu: string, cm: string): string[] {
  return [`电信:${ct || "普通直连"}`, `联通:${cu || "普通直连"}`, `移动:${cm || "普通直连"}`];
}

export function lineInfo(p: LineLike): LineInfo {
  const tags = (p.line_tags ?? []).filter(Boolean);
  const name = (p.name || "").toLowerCase();
  const mSlug = p.merchant?.slug || "";

  const hasGia = tags.includes("CN2 GIA");
  const has9929 = tags.includes("9929");
  const hasCmin2 = tags.includes("CMIN2");
  const has4837 = tags.includes("4837");
  const hasGt = tags.includes("CN2 GT");
  const hasIntl = tags.includes("国际线路");
  const hasCmi = tags.includes("CMI");
  const hasSoftbank = tags.includes("软银") || tags.includes("SoftBank");

  // 1. 三网各自拉满顶级专线（如 瓦工 DC6 ECOMMERCE、DMIT Pro）
  if (hasGia && has9929 && hasCmin2) {
    return {
      tier: "三网各自优化",
      carrierRows: ["电信:CN2 GIA", "联通:9929", "移动:CMIN2"],
      level: 3,
      badges: [
        { text: "CN2 GIA", class: lineBadgeClass("CN2 GIA"), title: "中国电信：CN2 GIA 极速专线" },
        { text: "9929", class: lineBadgeClass("9929"), title: "中国联通：9929 精品 A 网专线" },
        { text: "CMIN2", class: lineBadgeClass("CMIN2"), title: "中国移动：CMIN2 二代精品专线" },
      ],
    };
  }

  // 2. 三网同走单条优质专线（如 搬瓦工 CN2 GIA 系列、三网 4837）
  const isTri = mSlug === "bandwagon" || mSlug === "dmit" || name.includes("三网") || name.includes("tri");
  if (hasGia && isTri) {
    return {
      tier: "三网 CN2 GIA",
      carrierRows: ["电信:CN2 GIA", "联通:CN2 GIA", "移动:CN2 GIA"],
      level: 3,
      badges: [
        {
          text: "三网 CN2 GIA",
          class: lineBadgeClass("三网 CN2 GIA"),
          title: "电信/联通/移动三网全走 CN2 GIA",
        },
      ],
    };
  }
  if (has4837 && isTri) {
    return {
      tier: "三网优化",
      carrierRows: ["电信:4837", "联通:4837", "移动:4837"],
      level: 1,
      badges: [
        { text: "三网 4837", class: lineBadgeClass("三网 4837"), title: "电信/联通/移动三网全走 AS4837" },
      ],
    };
  }

  // 3. 双网优化组合（未优化的一家用普通直连补位）
  if (has9929 && hasCmin2) {
    return {
      tier: "联通 + 移动优化",
      carrierRows: carriers("", "9929", "CMIN2"),
      level: 2,
      badges: [
        { text: "9929", class: lineBadgeClass("9929"), title: "中国联通：9929 精品专线" },
        { text: "CMIN2", class: lineBadgeClass("CMIN2"), title: "中国移动：CMIN2 精品专线" },
      ],
    };
  }
  if (hasGt && has4837) {
    return {
      tier: "电信 + 联通优化",
      carrierRows: ["电信:CN2 GT", "联通:4837", "移动:普通直连"],
      level: 1,
      badges: [
        { text: "CN2 GT", class: lineBadgeClass("CN2 GT"), title: "中国电信：CN2 GT 半程优化" },
        { text: "4837", class: lineBadgeClass("4837"), title: "中国联通：AS4837 大带宽直连" },
      ],
    };
  }

  // 4. 单 VIP 线路（其余两网普通直连）
  if (hasGia) {
    return {
      tier: "电信 CN2 GIA",
      carrierRows: ["电信:CN2 GIA", "联通:普通直连", "移动:普通直连"],
      level: 2,
      badges: [
        {
          text: "电信 CN2 GIA",
          class: lineBadgeClass("电信 CN2 GIA"),
          title: "电信专属 CN2 GIA，联/移走普通直连",
        },
      ],
    };
  }
  if (has9929) {
    return {
      tier: "联通 9929",
      carrierRows: ["电信:普通直连", "联通:9929", "移动:普通直连"],
      level: 2,
      badges: [
        { text: "联通 9929", class: lineBadgeClass("联通 9929"), title: "联通专属 9929，电/移走普通直连" },
      ],
    };
  }
  if (hasCmin2) {
    return {
      tier: "移动 CMIN2",
      carrierRows: ["电信:普通直连", "联通:普通直连", "移动:CMIN2"],
      level: 2,
      badges: [
        {
          text: "移动 CMIN2",
          class: lineBadgeClass("移动 CMIN2"),
          title: "移动专属 CMIN2，电/联走普通直连",
        },
      ],
    };
  }
  if (has4837) {
    return {
      tier: "联通 4837",
      carrierRows: ["电信:普通直连", "联通:4837", "移动:普通直连"],
      level: 1,
      badges: [
        { text: "联通 4837", class: lineBadgeClass("联通 4837"), title: "联通专属 AS4837，电/移走普通直连" },
      ],
    };
  }
  if (hasGt) {
    return {
      tier: "电信 CN2 GT",
      carrierRows: ["电信:CN2 GT", "联通:普通直连", "移动:普通直连"],
      level: 1,
      badges: [
        { text: "电信 CN2 GT", class: lineBadgeClass("电信 CN2 GT"), title: "电信专属 CN2 GT，联/移走普通直连" },
      ],
    };
  }

  // 5. 商家专有线路（66 云 CMI / 软银等），不要落成普通 BGP
  if (hasCmi) {
    return {
      tier: "香港 CMI",
      carrierRows: ["电信:CMI", "联通:CMI", "移动:CMI"],
      level: 2,
      badges: [{ text: "CMI", class: lineBadgeClass("CMI"), title: "中国移动 CMI 国际出口" }],
    };
  }
  if (hasSoftbank) {
    return {
      tier: "日本软银",
      carrierRows: ["电信:软银", "联通:软银", "移动:软银"],
      level: 1,
      badges: [{ text: "软银", class: lineBadgeClass("软银"), title: "日本软银 BBTEC" }],
    };
  }

  // 6. 国际线路 / 普通 BGP（统一为标准三网格式，保持三列微胶囊严格对齐）
  if (hasIntl) {
    return {
      tier: "国际线路",
      carrierRows: ["电信:国际BGP", "联通:国际BGP", "移动:国际BGP"],
      level: 0,
      badges: [
        {
          text: "国际线路",
          class: lineBadgeClass("国际线路"),
          title: "纯海外国际骨干，未针对国内优化",
        },
      ],
    };
  }

  return {
    tier: "普通BGP",
    carrierRows: carriers("", "", ""),
    level: 0,
    badges: [{ text: "普通BGP", class: lineBadgeClass("普通BGP"), title: "三网骨干普通直连" }],
  };
}

/**
 * 线路等级着色 class（价值越高越醒目）：
 * 3 顶级 → 实心紫渐变白字（最重要买点，最突出）
 * 2 高端 → 蓝色文字
 * 1 优化 → 琥珀文字
 * 0 普通 → 灰色文字
 */
export function lineTierClass(level: 0 | 1 | 2 | 3): string {
  if (level === 3)
    return "bg-gradient-to-r from-violet-600 to-purple-600 rounded px-1.5 py-0.5 font-bold text-white ring-1 ring-violet-300 shadow-sm shadow-violet-500/30";
  if (level === 2) return "font-semibold text-blue-600 dark:text-blue-400";
  if (level === 1) return "font-medium text-amber-600 dark:text-amber-500";
  return "text-gray-400 dark:text-slate-500";
}

/** 内存/硬盘：`12G`；0 当作 1G（与旧卡片一致，避免展示 0G） */
export function fmtSize(gb: number): string {
  return `${gb || 1}G`;
}

/** 月流量：`500G` / `1.5T` / `不限` */
export function fmtTraffic(gb: number): string {
  if (gb < 0) return "不限";
  return gb >= 1000 ? `${(gb / 1000).toFixed(gb % 1000 === 0 ? 0 : 1)}T` : `${gb}G`;
}

/** 带宽：`100Mbps` / `1Gbps` */
export function fmtPort(mbps: number): string {
  if (mbps >= 1000) return `${(mbps / 1000).toFixed(mbps % 1000 === 0 ? 0 : 1)}Gbps`;
  return `${mbps}Mbps`;
}
