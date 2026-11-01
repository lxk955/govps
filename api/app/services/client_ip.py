"""客户端真实 IP 解析（位于反向代理之后时取访客公网 IP，并防范伪造请求头绕过限流）。

统一实现，供 auth（IP 限流）、ipcheck（留空检测）、track（PV 限流）与 go/click（点击统计）共用。

拓扑与信任链规则：
1. 生产环境流量经 Cloudflare → Caddy → FastAPI，Caddy 总是将 TCP 对端地址覆写到 `X-Real-IP`。
   - 当 `X-Real-IP` 属于 Cloudflare 官方回源网段时，信任 `CF-Connecting-IP`；
   - 当 `X-Real-IP` 是非 Cloudflare 公网地址（例如攻击者绕过 CDN 直连源站 80/443）时，
     忽略客户端可伪造的 `CF-Connecting-IP` 与 `X-Forwarded-For`，直接采用 `X-Real-IP`。
2. 若本服务被公网直接访问（TCP 对端本身即为公网 IP），仅在对端属于 Cloudflare 网段时才信任
   `CF-Connecting-IP`，否则直接返回 TCP 对端 IP。
3. 本地开发 / 单元测试（对端为回环、容器内网或 `testclient`，且无公网 `X-Real-IP`）时，
   按 `CF-Connecting-IP` → `X-Forwarded-For` 首个公网地址 → `X-Real-IP` → 对端地址兜底。
"""

import ipaddress

from fastapi import Request

# Cloudflare 官方回源网段（https://www.cloudflare.com/ips-v4 & ips-v6）
_CLOUDFLARE_NETS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        # IPv4
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        # IPv6
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)

# 本地回环与容器/局域网私网段（仅当对端位于这些网段或 testclient 时，才视为受信任的本地反代）
_LOCAL_PROXY_NETS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "100.64.0.0/10",
        "0.0.0.0/8",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "::/128",
    )
)

_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _parse_ip(raw: str | None) -> _IPAddress | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def _is_local_ip(addr: _IPAddress) -> bool:
    return any(addr in net for net in _LOCAL_PROXY_NETS)


def is_cloudflare_ip(addr: _IPAddress | str | None) -> bool:
    parsed = _parse_ip(addr) if isinstance(addr, str) or addr is None else addr
    if parsed is None:
        return False
    return any(parsed in net for net in _CLOUDFLARE_NETS)


def client_ip(request: Request) -> str:
    """取客户端真实 IP，校验反向代理与 Cloudflare 回源信任链，防范请求头伪造。"""
    peer_host = request.client.host.strip() if (request.client and request.client.host) else ""
    peer_ip = _parse_ip(peer_host)
    cf_ip = _parse_ip(request.headers.get("cf-connecting-ip"))

    # 1. TCP 对端本身已是非内网外部地址（未经过本地反代容器）
    if peer_ip is not None and not _is_local_ip(peer_ip):
        if is_cloudflare_ip(peer_ip) and cf_ip is not None:
            return str(cf_ip)
        return str(peer_ip)

    # 2. TCP 对端是本地/内网反代（如 Caddy 容器）：以反代注入的 X-Real-IP 判定上游身份
    real_raw = request.headers.get("x-real-ip")
    real_ip = _parse_ip(real_raw)
    if real_ip is not None and not _is_local_ip(real_ip):
        if is_cloudflare_ip(real_ip):
            return str(cf_ip) if cf_ip is not None else str(real_ip)
        # 绕过 Cloudflare 直连源站公网端口：忽略伪造的 CF-Connecting-IP / XFF
        return str(real_ip)

    # 3. 本地开发 / 测试环境（无外部 X-Real-IP）兜底
    if cf_ip is not None:
        return str(cf_ip)

    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        for part in parts:
            parsed = _parse_ip(part)
            if parsed is not None and not _is_local_ip(parsed):
                return str(parsed)
        if real_ip is not None:
            return str(real_ip)
        if parts:
            first_parsed = _parse_ip(parts[0])
            return str(first_parsed) if first_parsed is not None else parts[0]

    if real_ip is not None:
        return str(real_ip)
    if real_raw and real_raw.strip():
        return real_raw.strip()

    return str(peer_ip) if peer_ip is not None else (peer_host or "unknown")
