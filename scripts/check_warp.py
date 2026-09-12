#!/usr/bin/env python3
"""Cloudflare WARP 出口代理与节点连通性诊断工具。

用法：
    python3 scripts/check_warp.py [proxy_url]

默认检测 settings.WARP_PROXY 或 settings.CRAWLER_PROXY，也可以通过命令行参数传入代理地址：
    python3 scripts/check_warp.py socks5://127.0.0.1:40000
    python3 scripts/check_warp.py http://127.0.0.1:7897
"""

import os
import sys
from pathlib import Path

# 添加 api 目录到模块路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.config import settings
from app.crawler.base import make_client


def parse_trace(text: str) -> dict[str, str]:
    res = {}
    for line in text.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            res[k.strip()] = v.strip()
    return res


def run_check(proxy: str | None = None):
    target_proxy = proxy or settings.effective_warp_proxy or None

    print("=" * 60)
    print(" 🚀 GoVPS Cloudflare WARP 出口与反爬穿透诊断")
    print("=" * 60)
    print(f"[*] 目标出口代理: {target_proxy or '直连 (未配置代理)'}")

    # 1. 检测直连 Trace
    direct_trace = {}
    try:
        with make_client(timeout=10, proxy=None) as direct_client:
            r = direct_client.get("https://www.cloudflare.com/cdn-cgi/trace")
            if r.status_code == 200:
                direct_trace = parse_trace(r.text)
    except Exception as e:
        print(f"[!] 直连检测异常: {e}")

    # 2. 检测代理 Trace
    proxy_trace = {}
    if target_proxy:
        try:
            with make_client(timeout=10, proxy=target_proxy) as proxy_client:
                r = proxy_client.get("https://www.cloudflare.com/cdn-cgi/trace")
                if r.status_code == 200:
                    proxy_trace = parse_trace(r.text)
        except Exception as e:
            print(f"[!] 代理连接失败: {e}")
    else:
        proxy_trace = direct_trace

    print("-" * 60)
    if direct_trace:
        print(f"直连公网 IP:   {direct_trace.get('ip', 'unknown')} ({direct_trace.get('loc', '??')}) | 机房: {direct_trace.get('colo', '??')} | WARP: {direct_trace.get('warp', 'off')}")
    if proxy_trace and target_proxy:
        warp_status = proxy_trace.get("warp", "off")
        status_icon = "✅ [WARP 生效]" if warp_status in ("on", "plus") else "⚠️  [普通代理/WARP未开启]"
        print(f"代理出口 IP:   {proxy_trace.get('ip', 'unknown')} ({proxy_trace.get('loc', '??')}) | 机房: {proxy_trace.get('colo', '??')} | WARP: {warp_status} {status_icon}")

    print("-" * 60)
    print("[*] 商家端点 WAF 穿透测试:")

    targets = [
        ("VMiss 官网", "https://app.vmiss.com/index.php?rp=/store/us-los-angeles-cn2-gia"),
        ("V.PS 加购端点", "https://vps.hosting/?cmd=cart&action=add&id=148"),
        ("Bandwagon API", "https://api.64clouds.com/v1/getServiceInfo"),
        ("DMIT 官网", "https://www.dmit.io/cart.php"),
    ]

    for name, url in targets:
        try:
            with make_client(timeout=10, proxy=target_proxy) as client:
                r = client.get(url)
                status = r.status_code
                if status == 200:
                    badge = "✅ 200 OK (直通成功)"
                elif status == 403:
                    badge = "❌ 403 (被 Cloudflare 拦截)"
                else:
                    badge = f"ℹ️ {status}"
                print(f"  - {name:<14}: {badge}")
        except Exception as e:
            print(f"  - {name:<14}: ❌ 请求失败 ({e})")

    print("=" * 60)


if __name__ == "__main__":
    cli_proxy = sys.argv[1] if len(sys.argv) > 1 else None
    run_check(cli_proxy)
