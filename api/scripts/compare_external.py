#!/usr/bin/env python3
"""多源 VPS 数据对比与准确性验证脚本。

比对源：
1. 本地 GoVPS 爬虫（CRAWLERS）
2. https://d-vps.com/ （通过 WASM 签名解密请求 /api/stock/products?provider=...）
3. https://monitor.vpszk.com/ （/api/plans）
4. https://vpsoso.com/ （HTML 页面）
"""

import base64
import ctypes
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import httpx
from selectolax.parser import HTMLParser
from wasmtime import Instance, Module, Store

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from app.crawler.base import RawProduct, make_client
from app.crawler.registry import CRAWLERS

# ──────────────────────────────────
# 1. d-vps.com 客户端
# ──────────────────────────────────
class DvpsClient:
    def __init__(self, wasm_path: Path):
        self.store = Store()
        with open(wasm_path, "rb") as f:
            module = Module(self.store.engine, f.read())
        self.instance = Instance(self.store, module, [])
        self.memory = self.instance.exports(self.store)["memory"]
        self.io_ptr_fn = self.instance.exports(self.store)["io_ptr"]
        self.sign_fn = self.instance.exports(self.store)["sign"]
        self.resp_decrypt_fn = self.instance.exports(self.store)["resp_decrypt"]

        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        fp_obj = {
            "wd": False,
            "gl": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)",
            "ua": self.ua,
            "ch": True,
            "lang": "zh-CN",
            "hc": 8,
            "cdp": False,
        }
        self.fp_str = json.dumps(fp_obj, separators=(",", ":"))
        self.fp_bytes = self.fp_str.encode("utf-8")
        self.fp_header = base64.urlsafe_b64encode(self.fp_bytes).decode("ascii").rstrip("=")
        self.http = httpx.Client(headers={"User-Agent": self.ua}, timeout=20.0)

    def request(self, path: str):
        ch_resp = self.http.post("https://d-vps.com/api/stock/challenge", headers={"X-VP-FP": self.fp_header})
        ch_resp.raise_for_status()
        ch_data = ch_resp.json()
        ch_id = ch_data["id"]
        seed_bytes = bytes.fromhex(ch_data["seed"])
        pow_bits = ch_data["pow_bits"]

        ts_str = str(int(time.time() * 1000))
        ts_bytes = ts_str.encode("utf-8")
        path_bytes = path.split("?")[0].encode("utf-8")

        ptr = self.io_ptr_fn(self.store)
        mem_addr = ctypes.cast(self.memory.data_ptr(self.store), ctypes.c_void_p).value

        offset = ptr
        ctypes.memmove(mem_addr + offset, seed_bytes, len(seed_bytes))
        offset += len(seed_bytes)
        ctypes.memmove(mem_addr + offset, self.fp_bytes, len(self.fp_bytes))
        offset += len(self.fp_bytes)
        ctypes.memmove(mem_addr + offset, ts_bytes, len(ts_bytes))
        offset += len(ts_bytes)
        ctypes.memmove(mem_addr + offset, path_bytes, len(path_bytes))

        res_len = self.sign_fn(self.store, len(seed_bytes), len(self.fp_bytes), len(ts_bytes), len(path_bytes), pow_bits)
        out_bytes = ctypes.string_at(mem_addr + ptr, res_len)
        nonce_hex = out_bytes[:8].hex()
        sig_hex = out_bytes[8:24].hex()

        headers = {
            "X-VP-CH": ch_id,
            "X-VP-TS": ts_str,
            "X-VP-FP": self.fp_header,
            "X-VP-PN": nonce_hex,
            "X-VP-SG": sig_hex,
        }
        resp = self.http.get("https://d-vps.com" + path, headers=headers)
        resp.raise_for_status()
        if resp.headers.get("X-VP-ENC") == "1":
            raw_enc = resp.content
            ctypes.memmove(mem_addr + ptr, seed_bytes, len(seed_bytes))
            ctypes.memmove(mem_addr + ptr + len(seed_bytes), self.fp_bytes, len(self.fp_bytes))
            ctypes.memmove(mem_addr + ptr + len(seed_bytes) + len(self.fp_bytes), raw_enc, len(raw_enc))
            dec_len = self.resp_decrypt_fn(self.store, len(seed_bytes), len(self.fp_bytes), len(raw_enc))
            dec_bytes = ctypes.string_at(mem_addr + ptr + len(seed_bytes) + len(self.fp_bytes), dec_len)
            return json.loads(dec_bytes.decode("utf-8"))
        return resp.json()

    def get_providers(self):
        return self.request("/api/stock/providers").get("providers", [])

    def get_products(self, provider: str):
        return self.request(f"/api/stock/products?provider={provider}").get("products", [])


# ──────────────────────────────────
# 2. vpszk.com 客户端
# ──────────────────────────────────
def fetch_vpszk_plans(client: httpx.Client) -> list[dict]:
    try:
        r = client.get("https://monitor.vpszk.com/api/plans?pageSize=1000", timeout=20.0)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        print(f"[vpszk] error: {e}")
        return []


# ──────────────────────────────────
# 3. vpsoso.com 抓取
# ──────────────────────────────────
def fetch_vpsoso_plans(client: httpx.Client, slug: str) -> list[dict]:
    url_map = {
        "bandwagon": "https://vpsoso.com/vps/bwh",
        "dmit": "https://vpsoso.com/vps/dmit",
        "gomami": "https://vpsoso.com/vps/gomami",
        "evoxt": "https://vpsoso.com/vps/evoxt",
        "vmrack": "https://vpsoso.com/vps/vmrack",
    }
    url = url_map.get(slug)
    if not url:
        return []
    try:
        r = client.get(url, timeout=15.0)
        if r.status_code != 200:
            return []
        tree = HTMLParser(r.text)
        items = []
        for row in tree.css("tbody tr"):
            cells = [c.text(separator=" ", strip=True) for c in row.css("td")]
            if len(cells) < 8:
                continue
            name = cells[1].replace("推荐", "").strip()
            loc = cells[2]
            line = cells[4]
            conf = cells[5]
            bw = cells[6]
            price = cells[7]
            link = row.css_first("a[href]")
            href = link.attributes.get("href", "") if link else ""
            stock_cells = [c for c in cells if any(k in c for k in ("有货", "缺货", "无货", "售完"))]
            in_stock = bool(stock_cells) and "有货" in stock_cells[-1]
            items.append({
                "name": name,
                "location": loc,
                "line": line,
                "config": conf,
                "bandwidth": bw,
                "price": price,
                "href": href,
                "in_stock": in_stock,
            })
        return items
    except Exception as e:
        print(f"[vpsoso] {slug} error: {e}")
        return []


def main():
    dvps = DvpsClient(API_DIR / "app" / "crawler" / "dvps.wasm")
    print("Fetching d-vps providers...")
    d_provs = dvps.get_providers()
    print(f"d-vps providers count: {len(d_provs)}")
    d_prov_map = {p["provider"].lower(): p for p in d_provs}
    for p in d_provs:
        print(f"  {p['provider']}: {p['display_name']}")

    with make_client(30.0) as client:
        print("\nFetching vpszk plans...")
        vpszk_all = fetch_vpszk_plans(client)
        print(f"vpszk total plans: {len(vpszk_all)}")


if __name__ == "__main__":
    main()
