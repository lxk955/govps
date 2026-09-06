"""d-vps.com 冗余数据源客户端。

通过 WebAssembly 动态签名与加密解密，访问 https://d-vps.com/api/stock/products。
作为 GoVPS 对 DMIT / V.PS / VMiss 等全站 Cloudflare 强防护商家的优质辅助与实时库存校准源。
"""

import base64
import ctypes
import json
import logging
import re
import time
from decimal import Decimal
from pathlib import Path

import httpx

from .base import (
    RawProduct,
    extract_line_tags,
    normalize_line_tags,
    normalize_location,
    parse_specs,
)

logger = logging.getLogger(__name__)

WASM_PATH = Path(__file__).resolve().parent / "dvps.wasm"

_CYCLE_MAP = {
    "monthly": "monthly",
    "quarterly": "quarterly",
    "semiannually": "semi-annually",
    "semi_annually": "semi-annually",
    "annually": "annually",
    "biennially": "biennially",
    "triennially": "triennially",
}


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_FP_DICT = {
    "wd": False,
    "gl": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)",
    "ua": _UA,
    "ch": True,
    "lang": "zh-CN",
    "hc": 8,
    "cdp": False,
}
_FP_BYTES = json.dumps(_FP_DICT, separators=(",", ":")).encode("utf-8")
_FP_HEADER = base64.urlsafe_b64encode(_FP_BYTES).decode("ascii").rstrip("=")

_SHARED_ENGINE = None
_SHARED_MODULE = None


class DvpsSource:
    """d-vps.com 数据抓取器（含 WASM PoW 签名与响应解密）。"""

    def __init__(self, wasm_file: Path = WASM_PATH):
        self.wasm_file = wasm_file
        self._store = None
        self._instance = None
        self._initialized = False

    def _init_wasm(self):
        if self._initialized:
            return
        if not self.wasm_file.exists():
            raise FileNotFoundError(f"WASM file not found: {self.wasm_file}")
        try:
            global _SHARED_ENGINE, _SHARED_MODULE
            from wasmtime import Engine, Instance, Module, Store

            if _SHARED_ENGINE is None:
                _SHARED_ENGINE = Engine()
                with open(self.wasm_file, "rb") as f:
                    _SHARED_MODULE = Module(_SHARED_ENGINE, f.read())

            self._store = Store(_SHARED_ENGINE)
            self._instance = Instance(self._store, _SHARED_MODULE, [])
            self._memory = self._instance.exports(self._store)["memory"]
            self._io_ptr = self._instance.exports(self._store)["io_ptr"]
            self._sign = self._instance.exports(self._store)["sign"]
            self._resp_decrypt = self._instance.exports(self._store)["resp_decrypt"]
            self._initialized = True
        except Exception as e:
            logger.warning(f"[dvps_source] Failed to initialize WASM engine: {e}")
            raise

    def fetch_products(self, provider_slug: str, client: httpx.Client | None = None) -> list[RawProduct]:
        """抓取指定商家的产品列表并转为统一 RawProduct。出错时静默返回空列表。"""
        http_client = client or httpx.Client(headers={"User-Agent": _UA}, timeout=15.0)
        try:
            # 1. 获取挑战（快速失败，避免在离线或测试时加载 WASM）
            ch_resp = http_client.post(
                "https://d-vps.com/api/stock/challenge",
                headers={"X-VP-FP": _FP_HEADER},
            )
            if ch_resp.status_code != 200:
                print(f"[dvps_source] challenge failed: {ch_resp.status_code}")
                return []
            ch_data = ch_resp.json()
            ch_id = ch_data["id"]
            seed_bytes = bytes.fromhex(ch_data["seed"])
            pow_bits = ch_data["pow_bits"]

            # 2. 挑战成功后初始化 WASM 执行环境
            self._init_wasm()

            # 2. 签名
            path = f"/api/stock/products?provider={provider_slug}"
            target_path = path.split("?")[0]
            ts_str = str(int(time.time() * 1000))
            ts_bytes = ts_str.encode("utf-8")
            path_bytes = target_path.encode("utf-8")

            ptr = self._io_ptr(self._store)
            mem_addr = ctypes.cast(self._memory.data_ptr(self._store), ctypes.c_void_p).value

            offset = ptr
            ctypes.memmove(mem_addr + offset, seed_bytes, len(seed_bytes))
            offset += len(seed_bytes)
            ctypes.memmove(mem_addr + offset, _FP_BYTES, len(_FP_BYTES))
            offset += len(_FP_BYTES)
            ctypes.memmove(mem_addr + offset, ts_bytes, len(ts_bytes))
            offset += len(ts_bytes)
            ctypes.memmove(mem_addr + offset, path_bytes, len(path_bytes))

            res_len = self._sign(
                self._store,
                len(seed_bytes),
                len(_FP_BYTES),
                len(ts_bytes),
                len(path_bytes),
                pow_bits,
            )
            out_bytes = ctypes.string_at(mem_addr + ptr, res_len)
            nonce_hex = out_bytes[:8].hex()
            sig_hex = out_bytes[8:24].hex()

            headers = {
                "X-VP-CH": ch_id,
                "X-VP-TS": ts_str,
                "X-VP-FP": _FP_HEADER,
                "X-VP-PN": nonce_hex,
                "X-VP-SG": sig_hex,
            }
            resp = http_client.get(f"https://d-vps.com{path}", headers=headers)
            if resp.status_code != 200:
                print(f"[dvps_source] get products failed: {resp.status_code}")
                return []

            if resp.headers.get("X-VP-ENC") == "1":
                raw_enc = resp.content
                ctypes.memmove(mem_addr + ptr, seed_bytes, len(seed_bytes))
                ctypes.memmove(mem_addr + ptr + len(seed_bytes), _FP_BYTES, len(_FP_BYTES))
                ctypes.memmove(
                    mem_addr + ptr + len(seed_bytes) + len(_FP_BYTES),
                    raw_enc,
                    len(raw_enc),
                )
                dec_len = self._resp_decrypt(
                    self._store, len(seed_bytes), len(_FP_BYTES), len(raw_enc)
                )
                dec_bytes = ctypes.string_at(
                    mem_addr + ptr + len(seed_bytes) + len(_FP_BYTES), dec_len
                )
                data = json.loads(dec_bytes.decode("utf-8"))
            else:
                data = resp.json()

            raw_items = data.get("products", [])
            return [self._convert_product(p, provider_slug) for p in raw_items if p]
        except Exception as e:
            print(f"[dvps_source] fetch error for {provider_slug}: {e}")
            return []

    def _convert_product(self, p: dict, provider_slug: str) -> RawProduct:
        pid = str(p.get("pid") or p.get("pid_str") or "")
        name = p.get("name") or f"Product {pid}"
        currency = p.get("currency") or "USD"

        # 解析多周期价格
        cycles = p.get("cycles") or []
        price_options = []
        for c in cycles:
            c_key = c.get("cycle", "").lower()
            c_name = _CYCLE_MAP.get(c_key)
            if not c_name:
                continue
            total = c.get("total_usd") or c.get("total") or 0
            price_options.append({
                "billing_cycle": c_name,
                "price": float(total),
                "currency": currency,
                "purchase_url": p.get("affiliate_url") or "",
            })

        # 基准价格与周期：优先遵循 d-vps 提供的 price_cycle
        p_cycle_str = str(p.get("price_cycle") or "").lower()
        pref_cycle = _CYCLE_MAP.get(p_cycle_str)
        if price_options:
            base_opt = None
            if pref_cycle:
                base_opt = next((o for o in price_options if o["billing_cycle"] == pref_cycle), None)
            if not base_opt:
                base_opt = next((o for o in price_options if o["billing_cycle"] == "monthly"), None)
            if not base_opt:
                base_opt = next((o for o in price_options if o["billing_cycle"] == "annually"), price_options[0])
            price = Decimal(str(base_opt["price"]))
            billing_cycle = base_opt["billing_cycle"]
        else:
            p_val = p.get("list_price_usd") or p.get("annual_price_usd") or 0
            price = Decimal(str(p_val))
            billing_cycle = "monthly" if p.get("list_price_usd") else "annually"

        # 硬件配置
        cpu = None
        if cpu_str := str(p.get("cpu") or ""):
            if m := re.search(r"(\d+)", cpu_str):
                cpu = int(m.group(1))

        ram_gb = None
        if ram_str := str(p.get("ram") or ""):
            if "gb" in ram_str.lower():
                if m := re.search(r"(\d+(?:\.\d+)?)", ram_str):
                    ram_gb = Decimal(m.group(1))
            elif "mb" in ram_str.lower():
                if m := re.search(r"(\d+)", ram_str):
                    ram_gb = (Decimal(m.group(1)) / 1024).quantize(Decimal("0.1"))

        disk_gb = None
        if disk_str := str(p.get("disk") or ""):
            if m := re.search(r"(\d+)", disk_str):
                v = int(m.group(1))
                disk_gb = v * 1000 if "tb" in disk_str.lower() else v

        bw_gb = None
        if bw_str := str(p.get("transfer") or ""):
            if "unmetered" in bw_str.lower() or "unlimited" in bw_str.lower():
                bw_gb = -1
            elif "tb" in bw_str.lower():
                if m := re.search(r"(\d+(?:\.\d+)?)", bw_str):
                    bw_gb = int(float(m.group(1)) * 1000)
            elif "gb" in bw_str.lower():
                if m := re.search(r"(\d+)", bw_str):
                    bw_gb = int(m.group(1))

        port_mbps = None
        if port_str := str(p.get("port_speed") or ""):
            if m := re.search(r"(\d+(?:\.\d+)?)", port_str):
                pv = float(m.group(1))
                port_mbps = int(pv * 1000) if "gbps" in port_str.lower() or "g口" in port_str.lower() else int(pv)

        # 机房与线路
        dc_text = p.get("datacenter") or ""
        location = normalize_location(dc_text) or normalize_location(name)
        line_tags = normalize_line_tags(f"{name} {' '.join(p.get('lines', []))} {dc_text}")

        in_stock = p.get("status") == "in_stock"

        raw_p = RawProduct(
            external_id=pid if not pid.startswith(f"{provider_slug}-") else pid,
            name=name[:250],
            price=price,
            currency=currency,
            billing_cycle=billing_cycle,
            price_options=price_options,
            purchase_url=p.get("affiliate_url") or "",
            in_stock=in_stock,
            location=location,
            line_tags=line_tags,
            cpu_cores=cpu,
            ram_gb=ram_gb,
            disk_gb=disk_gb,
            bandwidth_gb=bw_gb,
            port_mbps=port_mbps,
            stock_verified=True,
        )
        return raw_p
