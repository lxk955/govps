"""客户端真实 IP 解析（位于反向代理之后时取访客公网 IP）。

统一实现，供 auth（IP 限流）与 ipcheck（留空检测）共用。此前两处各写一套
且行为不一致——auth 会跳过内网地址，ipcheck 直接取 XFF 首段——同一请求在
不同端点可能解析出不同 IP。

注意：请求经 Next.js rewrite 转发时，本服务看到的 X-Forwarded-For 首段是
web 容器的出口 IP 而非访客 IP。因此 /api/ip/check 改由前端显式
传 ?ip=，这里的解析仅作为兜底。
"""

from fastapi import Request

# 内网 / 容器间代理地址段：XFF 中遇到就跳过，继续往后找公网地址
_PRIVATE_PREFIXES = (
    "127.",
    "10.",
    "192.168.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "::1",
    "localhost",
    "fc00:",
    "fe80:",
)


def client_ip(request: Request) -> str:
    """取客户端真实 IP：Cloudflare 注入优先，其次 x-real-ip，最后 XFF 首个公网地址。"""
    # 优先取 Cloudflare 注入的真实客户端公网 IP
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        for ip_str in parts:
            if not ip_str.startswith(_PRIVATE_PREFIXES):
                return ip_str
        # 全是内网地址时退回第一段，至少留下可追溯的值
        if parts:
            return parts[0]

    return request.client.host if request.client else "unknown"
