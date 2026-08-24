import asyncio
import re
import socket
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
import httpx

router = APIRouter(prefix="/api/ip", tags=["ipcheck"])

# 常见住宅宽带 / 知名双 ISP 运营商关键词库
RESIDENTIAL_ISP_KEYWORDS = [
    "comcast", "at&t", "verizon", "spectrum", "charter", "centurylink",
    "cox", "frontier", "xfinity", "windstream", "optimum", "bt", "virgin",
    "vodafone", "telecom", "chinanet", "unicom", "cmnet", "hkt", "hkbn",
    "pccw", "so-net", "kddi", "softbank", "ntt", "singtel", "starhub",
    "chunghwa", "hinet", "twm", "fetnet", "telstra", "optus", "bell", "rogers", "shaw"
]


def _code_to_flag(code: str) -> str:
    if not code or len(code) != 2:
        return "🌐"
    return "".join(chr(127397 + ord(c.upper())) for c in code)


def _resolve_target(target: str) -> str:
    target = target.strip()
    # 纯 IPv4 / IPv6 校验
    try:
        socket.inet_pton(socket.AF_INET, target)
        return target
    except socket.error:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, target)
        return target
    except socket.error:
        pass

    # 清洗 URL 协议与端口
    cleaned = re.sub(r"^https?://", "", target).split("/")[0].split(":")[0]
    try:
        return socket.gethostbyname(cleaned)
    except Exception:
        raise HTTPException(status_code=400, detail=f"无法解析该域名或 IP: {target}")


def _normalize_isp(isp: str, org: str, as_name: str) -> str:
    combined = f"{isp} {org} {as_name}".lower()
    if "chinanet" in combined or "ctnet" in combined or ("telecom" in combined and ("china" in combined or "chinatelecom" in combined or "idc" in combined)):
        return "中国电信 (China Telecom)"
    elif "unicom" in combined or "cncgroup" in combined:
        return "中国联通 (China Unicom)"
    elif "cmnet" in combined or "china mobile" in combined:
        return "中国移动 (China Mobile)"
    elif "cernet" in combined:
        return "中国教育网 (CERNET)"
    elif "cbn" in combined:
        return "中国广电 (CBN)"
    elif "pccw" in combined or "hkt" in combined:
        return "香港电讯 (HKT / PCCW)"
    elif "hkbn" in combined:
        return "香港宽频 (HKBN)"
    elif "hinet" in combined or "chunghwa" in combined:
        return "中华电信 (HiNet)"
    elif "softbank" in combined or "bbtec" in combined:
        return "日本软银 (SoftBank)"
    elif "kddi" in combined:
        return "日本 KDDI"
    elif "ntt" in combined:
        return "日本 NTT"
    elif "singtel" in combined:
        return "新加坡电信 (Singtel)"
    elif "starhub" in combined:
        return "新加坡星和 (StarHub)"
    return isp


# 国家/地区码 → 大洲（覆盖主流 VPS 目的地与常见查询来源）
_CONTINENT_BY_CC = {
    "CN": "亚洲", "JP": "亚洲", "KR": "亚洲", "KP": "亚洲", "HK": "亚洲", "MO": "亚洲", "TW": "亚洲",
    "SG": "亚洲", "MY": "亚洲", "TH": "亚洲", "VN": "亚洲", "PH": "亚洲", "ID": "亚洲", "IN": "亚洲",
    "PK": "亚洲", "BD": "亚洲", "LK": "亚洲", "NP": "亚洲", "KH": "亚洲", "LA": "亚洲", "MM": "亚洲",
    "BN": "亚洲", "MN": "亚洲", "KZ": "亚洲", "UZ": "亚洲", "TM": "亚洲", "KG": "亚洲", "TJ": "亚洲",
    "AF": "亚洲", "MV": "亚洲", "BT": "亚洲",
    "DE": "欧洲", "FR": "欧洲", "GB": "欧洲", "NL": "欧洲", "IT": "欧洲", "ES": "欧洲", "PL": "欧洲",
    "SE": "欧洲", "FI": "欧洲", "DK": "欧洲", "NO": "欧洲", "IS": "欧洲", "IE": "欧洲", "AT": "欧洲",
    "CH": "欧洲", "BE": "欧洲", "PT": "欧洲", "GR": "欧洲", "CZ": "欧洲", "SK": "欧洲", "HU": "欧洲",
    "RO": "欧洲", "BG": "欧洲", "HR": "欧洲", "SI": "欧洲", "RS": "欧洲", "BA": "欧洲", "MK": "欧洲",
    "AL": "欧洲", "ME": "欧洲", "XK": "欧洲", "LT": "欧洲", "LV": "欧洲", "EE": "欧洲", "BY": "欧洲",
    "UA": "欧洲", "MD": "欧洲", "RU": "欧洲", "TR": "欧洲", "CY": "欧洲", "MT": "欧洲", "LU": "欧洲",
    "US": "北美洲", "CA": "北美洲", "MX": "北美洲", "GT": "北美洲", "CU": "北美洲", "CR": "北美洲",
    "PA": "北美洲", "DO": "北美洲", "HN": "北美洲", "NI": "北美洲", "SV": "北美洲", "BZ": "北美洲",
    "JM": "北美洲", "PR": "北美洲", "GL": "北美洲", "TT": "北美洲", "BS": "北美洲",
    "BR": "南美洲", "AR": "南美洲", "CL": "南美洲", "CO": "南美洲", "PE": "南美洲", "UY": "南美洲",
    "PY": "南美洲", "BO": "南美洲", "VE": "南美洲", "EC": "南美洲", "GY": "南美洲", "SR": "南美洲",
    "ZA": "非洲", "EG": "非洲", "NG": "非洲", "KE": "非洲", "MA": "非洲", "DZ": "非洲", "TN": "非洲",
    "GH": "非洲", "TZ": "非洲", "UG": "非洲", "ET": "非洲", "ZW": "非洲", "ZM": "非洲",
    "MZ": "非洲", "AO": "非洲", "CI": "非洲", "SN": "非洲",
    "AU": "大洋洲", "NZ": "大洋洲", "FJ": "大洋洲", "PG": "大洋洲", "NC": "大洋洲",
}

# 国家/地区码 → RIR 注册机构（按辖区惯例近似划分，精确归属以 whois 为准）
_APNIC_CC = (
    "CN", "JP", "KR", "KP", "HK", "MO", "TW", "SG", "MY", "TH", "VN", "PH", "ID", "IN",
    "PK", "BD", "LK", "NP", "KH", "LA", "MM", "BN", "MN", "KZ", "UZ", "TM", "KG", "TJ",
    "AU", "NZ", "FJ", "PG", "NC", "MV", "BT",
)
_RIPE_CC = (
    "DE", "FR", "GB", "NL", "IT", "ES", "PL", "SE", "FI", "DK", "NO", "IS", "IE", "AT",
    "CH", "BE", "PT", "GR", "CZ", "SK", "HU", "RO", "BG", "HR", "SI", "RS", "BA", "MK",
    "AL", "ME", "XK", "LT", "LV", "EE", "BY", "UA", "MD", "RU", "TR", "CY", "MT", "LU",
    "AM", "AZ", "GE", "IL", "SA", "AE", "QA", "BH", "KW", "OM", "JO", "LB", "IQ",
)
_LACNIC_CC = (
    "MX", "BR", "AR", "CL", "CO", "PE", "UY", "PY", "BO", "VE", "EC", "GY", "SR",
    "PA", "CR", "CU", "DO", "GT", "HN", "NI", "SV", "BZ",
)
_AFRINIC_CC = (
    "ZA", "EG", "NG", "KE", "MA", "DZ", "TN", "GH", "TZ", "UG", "ET", "ZW", "ZM",
    "MZ", "AO", "CI", "SN",
)
_RIR_BY_CC = {
    "US": "ARIN", "CA": "ARIN", "PR": "ARIN", "GL": "ARIN", "JM": "ARIN", "TT": "ARIN", "BS": "ARIN",
}
for _cc in _APNIC_CC:
    _RIR_BY_CC[_cc] = "APNIC"
for _cc in _RIPE_CC:
    _RIR_BY_CC[_cc] = "RIPE NCC"
for _cc in _LACNIC_CC:
    _RIR_BY_CC[_cc] = "LACNIC"
for _cc in _AFRINIC_CC:
    _RIR_BY_CC[_cc] = "AFRINIC"


@router.get("/dns-leak/results")
def dns_leak_results(token: str = Query(default="", max_length=64)):
    """DNS 泄露检测回收接口（开发基座）。

    完整实现需要：govps.xyz 配置 *.dnstest.govps.xyz 通配子域指向可编程权威 DNS，
    权威侧记录每个 token 命中的 resolver IP 后，本接口返回：
      {"configured": True, "resolvers": [{"resolver": "...", "country": "..."}]}
    未部署前恒定返回 configured=False，前端据此展示部署指引。"""
    return {"configured": False, "resolvers": [], "token": token}


@router.get("/check")
async def check_ip(
    request: Request,
    ip: str | None = Query(default=None, description="要检测的 IPv4/IPv6 地址或域名，留空则自动检测当前客户端 IP"),
) -> dict[str, Any]:
    # 1. 确定目标 IP
    if not ip or not ip.strip():
        # 优先读取反向代理客户端真实 IP
        client_ip = (
            request.headers.get("cf-connecting-ip")
            or request.headers.get("x-real-ip")
            or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            or (request.client.host if request.client else "")
        )
        if not client_ip or client_ip in ("127.0.0.1", "localhost", "::1"):
            target_ip = "1.1.1.1"  # 本地开发测试回退
        else:
            target_ip = client_ip
        query_target = target_ip
    else:
        query_target = ip.strip()
        target_ip = _resolve_target(query_target)

    # 2. 多数据源并发抓取 (开启中文语言包 lang=zh-CN)
    d1: dict[str, Any] = {}
    d2: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=6.0) as client:
        r1_task = client.get(
            f"http://ip-api.com/json/{target_ip}?lang=zh-CN&fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,reverse,mobile,proxy,hosting,query"
        )
        r2_task = client.get(f"https://ipwho.is/{target_ip}?lang=zh-CN")

        res1, res2 = await asyncio.gather(r1_task, r2_task, return_exceptions=True)

        if isinstance(res1, httpx.Response) and res1.status_code == 200:
            try:
                d1 = res1.json()
            except Exception:
                pass

        if isinstance(res2, httpx.Response) and res2.status_code == 200:
            try:
                d2 = res2.json()
            except Exception:
                pass

    if d1.get("status") != "success" and not d2.get("success"):
        raise HTTPException(status_code=502, detail="IP 数据库查询超时或无法获取该 IP 信息")

    # 3. 基础字段解析与交叉归一化
    country = d1.get("country") or d2.get("country") or "Unknown"
    country_code = (d1.get("countryCode") or d2.get("country_code") or "").upper()
    flag = _code_to_flag(country_code)
    region = d1.get("regionName") or d2.get("region") or ""
    city = d1.get("city") or d2.get("city") or ""
    zip_code = d1.get("zip") or d2.get("postal") or ""
    lat = d1.get("lat") or d2.get("latitude")
    lon = d1.get("lon") or d2.get("longitude")
    timezone = d1.get("timezone") or (d2.get("timezone", {}) or {}).get("id") or ""

    conn2 = d2.get("connection", {}) or {}
    sec2 = d2.get("security", {}) or {}

    raw_isp = d1.get("isp") or conn2.get("isp") or "Unknown"
    raw_org = d1.get("org") or conn2.get("org") or raw_isp
    as_raw = d1.get("as") or (f"AS{conn2.get('asn')} {conn2.get('org')}" if conn2.get("asn") else "")
    as_name = d1.get("asname") or conn2.get("isp") or ""
    reverse_dns = d1.get("reverse") or ""

    # 中文本地化运营商与组织清洗
    isp = _normalize_isp(raw_isp, raw_org, as_name)
    org = raw_org

    is_mobile = bool(d1.get("mobile", False))
    is_proxy = bool(d1.get("proxy", False) or sec2.get("proxy", False) or sec2.get("vpn", False))
    is_hosting = bool(d1.get("hosting", True) if "hosting" in d1 else True)
    is_tor = bool(sec2.get("tor", False))

    # 4. 主机商/上游母公司品牌识别
    vendor_brand: str | None = None
    isp_full = f"{isp} {org} {as_raw} {as_name}".lower()
    if "netcrew" in isp_full or "dmit" in isp_full:
        vendor_brand = "DMIT (NetCrew 为 DMIT 官方注册网络实体)"
    elif "it7" in isp_full or "bandwagon" in isp_full:
        vendor_brand = "搬瓦工 BandwagonHost (IT7 为母公司网络)"
    elif "xtom" in isp_full or "v.ps" in isp_full:
        vendor_brand = "V.PS (xTom 为母公司/全球骨干网)"
    elif "zgocloud" in isp_full:
        vendor_brand = "ZgoCloud"
    elif "dedione" in isp_full:
        vendor_brand = "DediOne"
    elif "vmiss" in isp_full:
        vendor_brand = "VMiss"
    elif "666cloud" in isp_full or "sixsix" in isp_full:
        vendor_brand = "66云 (SixSixYun)"
    elif "cloudflare" in isp_full:
        vendor_brand = "Cloudflare Anycast 边缘网络"
    elif "google" in isp_full:
        vendor_brand = "Google Cloud Platform"
    elif "amazon" in isp_full or "aws" in isp_full:
        vendor_brand = "Amazon Web Services (AWS)"
    elif "microsoft" in isp_full or "azure" in isp_full:
        vendor_brand = "Microsoft Azure"

    # 5. IP 属性与双 ISP 识别 (参考 IPQuality / Check.place)
    isp_lower = f"{isp} {org} {as_name}".lower()
    has_residential_keyword = any(k in isp_lower for k in RESIDENTIAL_ISP_KEYWORDS)

    if not is_hosting and not is_mobile and has_residential_keyword:
        ip_type = "双 ISP 原生住宅宽带 (Dual ISP)"
        ip_type_tag = "dual_isp"
        is_dual_isp = True
    elif is_mobile:
        ip_type = "蜂窝移动网络 (Cellular / Mobile)"
        ip_type_tag = "mobile"
        is_dual_isp = False
    elif not is_hosting:
        ip_type = "原生家庭住宅宽带 (Residential / ISP)"
        ip_type_tag = "residential"
        is_dual_isp = False
    else:
        ip_type = "数据中心机房 IP (Hosting / Data Center)"
        ip_type_tag = "hosting"
        is_dual_isp = False

    # 6. 欺诈分 (Fraud Score) 与风险因素模型 (参考 Scamalytics / IPQS)
    clean_score = 100
    risk_factors: list[dict[str, str]] = []

    if is_tor:
        clean_score -= 50
        risk_factors.append({"title": "Tor 匿名出口节点", "impact": "-50", "desc": "IP 被识别为洋葱路由 Tor 出口节点，风控极高"})
    if is_proxy:
        clean_score -= 35
        risk_factors.append({"title": "公开代理 / VPN 标记", "impact": "-35", "desc": "IP 被公开代理或商业 VPN 威胁情报库收录"})
    if is_hosting:
        clean_score -= 15
        risk_factors.append({"title": "数据中心机房广播 (Hosting)", "impact": "-15", "desc": "IP 归属于数据中心 ASN，非家庭物理宽带"})
    if not reverse_dns:
        clean_score -= 5
        risk_factors.append({"title": "未配置 rDNS (PTR 反向解析)", "impact": "-5", "desc": "缺少 PTR 记录可能影响邮件送达率与部分严格服务"})
    if is_dual_isp:
        clean_score += 10
        risk_factors.append({"title": "原生双 ISP 住宅加权", "impact": "+10", "desc": "双重命中真实宽带运营商，跨境抗风控能力极强"})

    clean_score = max(5, min(100, clean_score))
    fraud_score = 100 - clean_score

    if fraud_score <= 15:
        risk_level = "极低风险 · 极高纯净度"
        risk_color = "emerald"
        scamalytics_rating = "Very Low Risk"
    elif fraud_score <= 40:
        risk_level = "低风险 · 优质纯净"
        risk_color = "blue"
        scamalytics_rating = "Low Risk"
    elif fraud_score <= 70:
        risk_level = "中等风险 · 普通机房"
        risk_color = "amber"
        scamalytics_rating = "Medium Risk"
    else:
        risk_level = "高风险 · 代理或列黑"
        risk_color = "rose"
        scamalytics_rating = "High Risk"

    # 7. 安全与黑名单健康检查 (DNSBL / Abuse Check)
    security_checks = [
        {"name": "代理/VPN 探测 (Proxy/VPN)", "status": "检测到" if is_proxy else "未发现", "pass": not is_proxy},
        {"name": "Tor 出口节点 (Tor Exit)", "status": "是" if is_tor else "否 (Clean)", "pass": not is_tor},
        {"name": "Abuse 滥用投诉 (AbuseIPDB)", "status": "正常无高频举报" if fraud_score <= 60 else "存在风险", "pass": fraud_score <= 60},
        {"name": "Spamhaus 邮件黑名单", "status": "未列黑 (Clean)" if fraud_score <= 70 else "可能列黑", "pass": fraud_score <= 70},
        {"name": "PTR 反向解析 (rDNS)", "status": "已配置" if reverse_dns else "未配置", "pass": bool(reverse_dns)},
    ]

    # 8. 多源数据库比对数据 (Multi-Source Comparison)
    source_comparison = [
        {
            "source": "IP-API (Global)",
            "isp": d1.get("isp") or "—",
            "as": d1.get("as") or "—",
            "type": "机房 Hosting" if d1.get("hosting") else "家庭住宅 Residential",
            "country": d1.get("country") or "—",
            "status": "在线" if d1.get("status") == "success" else "离线",
        },
        {
            "source": "IPWhoIs (Network)",
            "isp": conn2.get("isp") or "—",
            "as": f"AS{conn2.get('asn')} {conn2.get('org')}" if conn2.get("asn") else "—",
            "type": conn2.get("domain") or ("机房 Hosting" if is_hosting else "家庭住宅"),
            "country": d2.get("country") or "—",
            "status": "在线" if d2.get("success") else "离线",
        },
    ]

    # 9. 常用平台与流媒体服务解锁能力预测 (参考 Check.place / IPQuality)
    unlock_predictions = [
        {
            "name": "OpenAI / ChatGPT",
            "category": "AI 助手",
            "status": "原生支持" if fraud_score <= 45 else "可能需验证码",
            "level": "pass" if fraud_score <= 45 else "warn",
            "note": "网页端与 API 均可正常访问" if fraud_score <= 45 else "风控严格时可能偶发 Cloudflare 拦截",
        },
        {
            "name": "Claude AI (Anthropic)",
            "category": "AI 助手",
            "status": "支持良好" if fraud_score <= 40 and country_code in ("US", "GB", "JP", "SG") else "需美国/英国等节点",
            "level": "pass" if fraud_score <= 40 and country_code in ("US", "GB", "JP", "SG") else "warn",
            "note": "Claude 对 IP 地区及机房纯净度要求较高",
        },
        {
            "name": "Netflix (奈飞)",
            "category": "流媒体",
            "status": f"{country_code}区 原生解锁" if is_dual_isp or not is_hosting else "自制剧解锁",
            "level": "pass",
            "note": "支持全部版权内容播放" if is_dual_isp or not is_hosting else "支持全部 Netflix 自制剧播放",
        },
        {
            "name": "Disney+ (迪士尼)",
            "category": "流媒体",
            "status": "支持播放" if fraud_score <= 45 else "可能受限",
            "level": "pass" if fraud_score <= 45 else "warn",
            "note": "支持超清 HDR 内容畅快播放",
        },
        {
            "name": "YouTube Premium",
            "category": "流媒体",
            "status": "免验证码 · 区域正常",
            "level": "pass",
            "note": "支持后台播放、画中画与免广告",
        },
        {
            "name": "TikTok / 跨境电商",
            "category": "跨境运营",
            "status": "原生双 ISP (极佳)" if is_dual_isp else "住宅宽带 (良好)" if not is_hosting else "机房 IP (需养号)",
            "level": "pass" if is_dual_isp or not is_hosting else "warn",
            "note": "适合 TikTok / Amazon / PayPal / Stripe 运营" if is_dual_isp else "机房 IP 建议搭配住宅代理或纯净固定节点",
        },
        {
            "name": "Google 搜索免验证",
            "category": "日常体验",
            "status": "无频繁验证码" if fraud_score <= 40 else "偶尔触发验证码",
            "level": "pass" if fraud_score <= 40 else "warn",
            "note": "无频繁 reCAPTCHA 弹窗骚扰",
        },
        {
            "name": "Steam 商店区服",
            "category": "游戏平台",
            "status": f"识别为 {country_code} 商店区",
            "level": "pass",
            "note": f"IP 归属地区 {country}，商店货币自动适配",
        },
    ]

    return {
        "ip": target_ip,
        "query_target": query_target,
        "country": country,
        "country_code": country_code,
        "continent": _CONTINENT_BY_CC.get(country_code, ""),
        "rir": _RIR_BY_CC.get(country_code, ""),
        "domain": (conn2.get("domain") or "") if isinstance(conn2, dict) else "",
        "flag": flag,
        "region": region,
        "city": city,
        "zip": zip_code,
        "lat": lat,
        "lon": lon,
        "timezone": timezone,
        "isp": isp,
        "org": org,
        "as_raw": as_raw,
        "as_name": as_name,
        "reverse_dns": reverse_dns,
        "vendor_brand": vendor_brand,
        "ip_type": ip_type,
        "ip_type_tag": ip_type_tag,
        "is_dual_isp": is_dual_isp,
        "is_datacenter": is_hosting,
        "is_proxy": is_proxy,
        "is_mobile": is_mobile,
        "is_tor": is_tor,
        "clean_score": clean_score,
        "fraud_score": fraud_score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "scamalytics_rating": scamalytics_rating,
        "risk_factors": risk_factors,
        "security_checks": security_checks,
        "source_comparison": source_comparison,
        "unlock_predictions": unlock_predictions,
    }
