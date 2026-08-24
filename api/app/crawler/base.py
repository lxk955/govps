import re
from dataclasses import dataclass, field
from decimal import Decimal

import httpx


@dataclass
class RawProduct:
    """爬虫统一输出：一个商家的一个套餐在某时刻的快照。"""

    external_id: str  # 商家侧产品 ID（WHMCS 的 pid），取不到则用 name 的 slug
    name: str
    price: Decimal
    currency: str = "USD"
    billing_cycle: str = "annually"  # monthly/quarterly/semi-annually/annually/...
    price_options: list[dict] = field(default_factory=list)
    purchase_url: str = ""
    # 悲观默认：适配器必须拿到明确的有货证据才能置 True，防止解析失配时静默显示有货
    in_stock: bool = False
    location: str | None = None
    line_tags: list[str] = field(default_factory=list)
    cpu_cores: int | None = None
    ram_gb: Decimal | None = None
    disk_gb: int | None = None
    bandwidth_gb: int | None = None
    port_mbps: int | None = None
    recommended: bool = False
    # 预置目录/悲观回退：扫描时不得凭此把线上仍在售的 SKU 标成缺货
    from_preset: bool = False


class MerchantCrawler:
    """商家适配器基类。一个商家一个子类，声明元信息与产品页列表。"""

    slug: str = ""
    name: str = ""
    website: str = ""
    aff_url_template: str | None = None  # 上线前填入自己的返利模板

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        raise NotImplementedError


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def make_client(timeout: float) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cookie": "WHMCSLanguage=chinese; language=chinese; lang=zh_CN; language_chosen=chinese",
        },
    )


# ---------- 配置信息正则提取 ----------

_RE_CPU = re.compile(r"(\d+)\s*(?:v?cpu|core|核)", re.I)
# "2 GB DDR4 RAM" / "2G RAM" / "2 GB Memory" / "1GB DDR5 ECC RAM"
_RE_RAM = re.compile(r"(\d+(?:\.\d+)?)\s*GB?(?:\s+DDR\d+)?(?:\s+ECC)?\s*(?:RAM|内存|memory)", re.I)
# 裸 MB 内存写法（如 VMiss 的 "1024 MB"）：需排除 Mbps/Mbit，且限定 256~65536 的合理内存区间
_RE_RAM_MB = re.compile(r"(?<![\d.])(\d{3,5})\s*MB(?![a-z])", re.I)
# "40G NVMe SSD" / "40 GB SSD" / "40G NVMe" / "40 GB Disk" / "20G PCIe 4.0 NVMe SSD"
_RE_DISK = re.compile(r"(\d+)\s*GB?\s*(?:(?:PCIe\s*\d+(?:\.\d+)?|NVMe|SAS|SATA|SSD)\s*){0,3}(?:SSD|NVMe|磁盘|disk|storage)", re.I)

# 识别无限流量 / 不限量 / Unmetered Bandwidth
_RE_UNMETERED = re.compile(r"unmetered|unlimited|不限流量|无限流量|不限量", re.I)

# 识别月流量：如 "1TB Monthly Transfer", "1T/Month", "500G/mo", "1000 GB Transfer", "2TB Bandwidth", "1000G/月"
_RE_BW = re.compile(
    r"(\d+(?:\.\d+)?)\s*(GB?|TB?)\s*(?:(?:Monthly|per\s+month|/\s*(?:Month|mo|月))\s*)?(?:transfer|bandwidth|流量|traffic|Monthly|/\s*(?:Month|mo|月))",
    re.I,
)

# 识别端口速率/带宽：如 "1 Gbps Port", "1000 Mbps", "200M口", "1G Port", "100M Bandwidth"
_RE_PORT = re.compile(r"(\d+(?:\.\d+)?)\s*(Mbps|Gbps|M口|G口|M\s+Port|G\s+Port|G\s+Bandwidth|M\s+Bandwidth)", re.I)


def parse_specs(text: str, p: RawProduct) -> RawProduct:
    """从一段杂乱的文本中用正则提取硬件规格，就地更新到 RawProduct 上。"""
    if m := _RE_CPU.search(text):
        p.cpu_cores = p.cpu_cores or int(m.group(1))
    if m := _RE_RAM.search(text):
        p.ram_gb = p.ram_gb or Decimal(m.group(1))
    if p.ram_gb is None and (m := _RE_RAM_MB.search(text)):
        mb = int(m.group(1))
        if 256 <= mb <= 65536:
            p.ram_gb = (Decimal(mb) / 1024).quantize(Decimal("0.1"))
    if m := _RE_DISK.search(text):
        p.disk_gb = p.disk_gb or int(m.group(1))

    # 流量提取：优先识别不限量，其次匹配数值月流量
    if p.bandwidth_gb is None:
        if _RE_UNMETERED.search(text):
            p.bandwidth_gb = -1  # -1 标识无限流量
        elif m := _RE_BW.search(text):
            v = float(m.group(1))
            unit = m.group(2).upper()
            p.bandwidth_gb = int(v * 1000 if "T" in unit else v)

    if m := _RE_PORT.search(text):
        v = int(float(m.group(1)))
        unit = m.group(2).upper()
        p.port_mbps = p.port_mbps or (v * 1000 if "G" in unit else v)

    return p


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def normalize_line_tags(text: str, existing_tags: list[str] | None = None) -> list[str]:
    """统一清洗为 7 大标准规范线路分类：
    - CN2 GIA (电信顶级精品网)
    - 9929 (联通 VIP 专线)
    - CMIN2 (移动顶级精品网)
    - 4837 (联通骨干大带宽)
    - CN2 GT (电信半程优化)
    - 普通BGP (三网直连普通优化)
    - 国际线路 (纯海外骨干)
    """
    raw_str = " ".join(existing_tags or [])
    combined = f"{text} {raw_str}".lower()
    tags: list[str] = []

    # 商家专有线路（必须先于 7 档归并，否则 CMI/软银会被落成「普通BGP」）
    extra_keep = []
    for t in existing_tags or []:
        if t in ("CMI", "软银", "三网优化") and t not in extra_keep:
            extra_keep.append(t)
    if re.search(r"(?<![a-z0-9])cmi(?![a-z0-9n])", combined) and "CMI" not in extra_keep:
        extra_keep.append("CMI")
    if re.search(r"软银|softbank|bbtec", combined) and "软银" not in extra_keep:
        extra_keep.append("软银")

    # 1. 精品专线与优化骨干
    # 注意：部分商家直接写 `GIA`（省略 CN2 前缀，如 zgo 的 `GIA&9929&CMIN2`），
    # 需兼容裸 `GIA` 写法；但 `GIA` 紧邻 `&` 或边界才算线路关键词，避免误命中无关词。
    if re.search(r"cn2[\s_-]?gia|as4809|(?<![a-z0-9])gia(?![a-z0-9])", combined):
        tags.append("CN2 GIA")
    elif re.search(r"cn2[\s_-]?gt|(?<![a-z0-9])cn2(?![a-z0-9])", combined):
        tags.append("CN2 GT")

    if re.search(r"9929|as9929|cuii", combined):
        tags.append("9929")

    if re.search(r"cmin2|as58807", combined):
        tags.append("CMIN2")

    if re.search(r"4837|as4837|china direct", combined):
        tags.append("4837")

    # 2. 国际线路与普通BGP
    if re.search(r"global|intl|international|国际线路|国际", combined):
        tags.append("国际线路")

    for t in extra_keep:
        if t not in tags:
            tags.append(t)

    if not tags:
        tags.append("普通BGP")

    return list(dict.fromkeys(tags))


def extract_line_tags(text: str) -> list[str]:
    """从套餐描述文本中提取标准线路标签。"""
    return normalize_line_tags(text)


_LOCATION_TRANSLATIONS = {
    # 美国
    "los angeles": "洛杉矶",
    "lax": "洛杉矶",
    "usca_6": "洛杉矶 DC6",
    "usca_9": "洛杉矶 DC9",
    "san jose": "圣何塞",
    "sjc": "圣何塞",
    "fremont": "弗里蒙特",
    "fmt": "弗里蒙特",
    "new york": "纽约",
    "nyc": "纽约",
    "new jersey": "新泽西",
    "kansas city": "堪萨斯",
    "kansas": "堪萨斯",
    "kc": "堪萨斯",
    "dallas": "达拉斯",
    "seattle": "西雅图",
    "chicago": "芝加哥",
    "salt lake city": "盐湖城",
    "phoenix": "凤凰城",
    "miami": "迈阿密",
    "atlanta": "亚特兰大",
    "missouri": "密苏里",
    "united states": "美西",
    "usa": "美西",
    # 亚洲
    "hong kong": "香港",
    "hongkong": "香港",
    "hkg": "香港",
    "hk": "香港",
    "tokyo": "东京",
    "tyo": "东京",
    "osaka": "大阪",
    "kix": "大阪",
    "japan": "东京",
    "singapore": "新加坡",
    "sin": "新加坡",
    "sg": "新加坡",
    "seoul": "首尔",
    "korea": "首尔",
    "taiwan": "台北",
    "taipei": "台北",
    "dubai": "迪拜",
    # 欧洲
    "amsterdam": "阿姆斯特丹",
    "ams": "阿姆斯特丹",
    "netherlands": "阿姆斯特丹",
    "frankfurt": "法兰克福",
    "fra": "法兰克福",
    "falkenstein": "法尔肯施泰因",
    "germany": "法兰克福",
    "london": "伦敦",
    "uk": "伦敦",
    "united kingdom": "伦敦",
    # 大洋洲 / 美洲其他
    "vancouver": "温哥华",
    "canada": "温哥华",
    "sydney": "悉尼",
    "australia": "悉尼",
}

_COUNTRY_PREFIXES = (
    "日本",
    "中国",
    "美国",
    "德国",
    "英国",
    "荷兰",
    "法国",
    "加拿大",
    "澳大利亚",
    "韩国",
    "阿联酋",
)


def normalize_location(loc: str | None) -> str | None:
    """将英文机房/混合机房名统一清洗为标准规范中文城市名（如 日本东京/东京 -> 东京，中国香港 -> 香港）。"""
    if not loc:
        return None
    loc_clean = loc.strip()
    if not loc_clean:
        return None
    low = loc_clean.lower()
    if "multi-dc" in low or "multi-location" in low or "多机房" in low:
        return "多机房 (可迁)"
    if low in _LOCATION_TRANSLATIONS:
        return _LOCATION_TRANSLATIONS[low]
    for eng, zh in _LOCATION_TRANSLATIONS.items():
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(eng) + r"(?![A-Za-z0-9])", low):
            return zh
    # 清洗中文国家前缀，统一仅保留城市名（如 日本东京 -> 东京，中国香港 -> 香港，美国堪萨斯 -> 堪萨斯）
    for pfx in _COUNTRY_PREFIXES:
        if loc_clean.startswith(pfx) and len(loc_clean) > len(pfx):
            return loc_clean[len(pfx) :].strip()
    return loc_clean


_RE_LOCATION_FIELD = re.compile(r"Location:\s*([^,;<]+)", re.I)


def extract_location(text: str) -> str | None:
    """从套餐名称/描述中识别机房并返回规范中文名。"""
    if m := _RE_LOCATION_FIELD.search(text):
        return normalize_location(m.group(1).strip())
    for eng, zh in _LOCATION_TRANSLATIONS.items():
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(eng) + r"(?![A-Za-z0-9])", text, re.I):
            return zh
    return None
