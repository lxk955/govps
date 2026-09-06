#!/usr/bin/env python3
"""详细对比审计脚本：全量比对 GoVPS 爬虫与 d-vps.com, monitor.vpszk.com, vpsoso.com 的数据差异。"""

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(API_DIR / "scripts"))

from compare_external import DvpsClient, fetch_vpsoso_plans, fetch_vpszk_plans
from app.crawler.base import make_client
from app.crawler.registry import CRAWLERS


def compare_plans(merchant_name, govps_raws, dvps_raws, vpszk_items, vpsoso_items, get_dvps_pid=lambda x: str(x.get("pid", ""))):
    print("\n" + "=" * 70)
    print(f"【{merchant_name} 数据准确性审计】")
    print("=" * 70)

    # 1. 基础汇总
    govps_by_id = {}
    for p in govps_raws:
        pid = p.external_id
        # 仅针对 DMIT 剥离 dmit- 前缀以便与聚合源对齐
        clean_pid = re.sub(r"^dmit-", "", pid) if pid.startswith("dmit-") else pid
        govps_by_id[clean_pid] = p

    dvps_by_id = {}
    for p in dvps_raws:
        pid = get_dvps_pid(p)
        if pid:
            dvps_by_id[pid] = p

    vpszk_by_id = {}
    for p in vpszk_items:
        pid = str(p.get("externalId") or p.get("id") or "")
        clean_pid = re.sub(r"^[a-zA-Z0-9]+-", "", pid) if "-" in pid else pid
        if clean_pid:
            vpszk_by_id[clean_pid] = p

    print(f"GoVPS 款数: {len(govps_by_id)}, 在售: {sum(1 for p in govps_raws if p.in_stock)}")
    print(f"d-vps 款数: {len(dvps_by_id)}, 在售: {sum(1 for p in dvps_raws if p.get('status') == 'in_stock')}")
    if vpszk_items:
        print(f"vpszk 款数: {len(vpszk_by_id)}, 在售: {sum(1 for p in vpszk_items if p.get('stock') == 'in')}")
    if vpsoso_items:
        print(f"vpsoso 款数: {len(vpsoso_items)}, 在售: {sum(1 for p in vpsoso_items if p.get('in_stock'))}")

    # 2. 覆盖面差异分析 (d-vps vs GoVPS)
    common_pids = set(govps_by_id.keys()) & set(dvps_by_id.keys())
    missing_in_govps = set(dvps_by_id.keys()) - set(govps_by_id.keys())
    missing_in_dvps = set(govps_by_id.keys()) - set(dvps_by_id.keys())

    print(f"\n[覆盖率] 共同 PID 款数: {len(common_pids)}")
    print(f"[覆盖率] d-vps 有但 GoVPS 缺失: {len(missing_in_govps)} 款")
    missing_in_stock = [pid for pid in missing_in_govps if dvps_by_id[pid].get("status") == "in_stock"]
    print(f"  其中 d-vps 处于在售状态的: {len(missing_in_stock)} 款")
    for pid in missing_in_stock[:8]:
        dp = dvps_by_id[pid]
        dc_str = str(dp.get('datacenter') or '')
        print(f"    - PID {pid}: {dp.get('name')} | ${dp.get('annual_price_usd') or dp.get('list_price_usd')} | {dc_str[:40]}")

    print(f"[覆盖率] GoVPS 有但 d-vps 缺失: {len(missing_in_dvps)} 款")
    for pid in list(missing_in_dvps)[:5]:
        gp = govps_by_id[pid]
        print(f"    - PID {pid}: {gp.name} | 在售:{gp.in_stock} | {gp.currency} {gp.price}/{gp.billing_cycle}")

    # 3. 共同款核验（库存、价格、硬件规格、机房、线路）
    stock_mismatches = []
    price_mismatches = []
    cpu_mismatches = []
    ram_mismatches = []
    disk_mismatches = []
    bw_mismatches = []
    line_mismatches = []

    for pid in sorted(list(common_pids), key=lambda x: int(x) if x.isdigit() else str(x)):
        gp = govps_by_id[pid]
        dp = dvps_by_id[pid]

        # 库存
        dp_in_stock = (dp.get("status") == "in_stock")
        if gp.in_stock != dp_in_stock:
            stock_mismatches.append({
                "pid": pid,
                "name": gp.name,
                "govps": gp.in_stock,
                "dvps": dp_in_stock,
            })

        # 价格比对：找年付或月付
        dp_annual = dp.get("annual_price_usd")
        dp_monthly = dp.get("monthly_price_usd")
        dp_cycles = dp.get("cycles", [])

        # 线路对比
        dp_lines = dp.get("lines", []) or []
        gp_lines = gp.line_tags or []
        # 如果 d-vps 标有 CN2 GIA/9929/CMIN2，GoVPS 却标为 普通BGP 或 国际线路
        premium_tags = {"CN2 GIA", "9929", "CMIN2", "4837", "软银", "CMI"}
        dp_premium = set(dp_lines) & premium_tags
        gp_premium = set(gp_lines) & premium_tags
        if dp_premium and not gp_premium:
            line_mismatches.append({
                "pid": pid,
                "name": gp.name,
                "govps_lines": gp_lines,
                "dvps_lines": dp_lines,
            })

        # 规格对比
        # CPU
        dp_cpu_str = str(dp.get("cpu") or "")
        dp_cpu = int(re.search(r"\d+", dp_cpu_str).group(0)) if re.search(r"\d+", dp_cpu_str) else None
        if dp_cpu and gp.cpu_cores and dp_cpu != gp.cpu_cores:
            if not (dp_cpu == 7663 and gp.cpu_cores == 56):
                cpu_mismatches.append({"pid": pid, "name": gp.name, "govps": gp.cpu_cores, "dvps": dp_cpu})

        # 内存
        dp_ram_str = str(dp.get("ram") or "")
        dp_ram = None
        if "gb" in dp_ram_str.lower():
            if m := re.search(r"(\d+(?:\.\d+)?)", dp_ram_str):
                dp_ram = Decimal(m.group(1))
        elif "mb" in dp_ram_str.lower():
            if m := re.search(r"(\d+)", dp_ram_str):
                dp_ram = (Decimal(m.group(1)) / 1024).quantize(Decimal("0.1"))
        if dp_ram and gp.ram_gb and abs(float(dp_ram) - float(gp.ram_gb)) > 0.05:
            ram_mismatches.append({"pid": pid, "name": gp.name, "govps": float(gp.ram_gb), "dvps": float(dp_ram)})

        # 流量
        dp_bw_str = str(dp.get("transfer") or "")
        dp_bw = None
        if "tb" in dp_bw_str.lower():
            if m := re.search(r"(\d+(?:\.\d+)?)", dp_bw_str):
                dp_bw = int(float(m.group(1)) * 1000)
        elif "gb" in dp_bw_str.lower():
            if m := re.search(r"(\d+)", dp_bw_str):
                dp_bw = int(m.group(1))
        if dp_bw and gp.bandwidth_gb and gp.bandwidth_gb > 0:
            # 允许千进制与1024微小差异(如 1000 vs 1024)
            if abs(dp_bw - gp.bandwidth_gb) > 50:
                bw_mismatches.append({"pid": pid, "name": gp.name, "govps": gp.bandwidth_gb, "dvps": dp_bw})

    print(f"\n[共同款差异分析]")
    print(f"- 库存差异: {len(stock_mismatches)} 款")
    for s in stock_mismatches[:5]:
        print(f"  PID {s['pid']} ({s['name']}): GoVPS={s['govps']} vs d-vps={s['dvps']}")

    print(f"- 线路归类降级差异 (d-vps有精品网而GoVPS没有): {len(line_mismatches)} 款")
    for l in line_mismatches[:5]:
        print(f"  PID {l['pid']} ({l['name']}): GoVPS={l['govps_lines']} vs d-vps={l['dvps_lines']}")

    print(f"- CPU 差异: {len(cpu_mismatches)} 款")
    for c in cpu_mismatches[:3]:
        print(f"  PID {c['pid']} ({c['name']}): GoVPS={c['govps']}C vs d-vps={c['dvps']}C")

    print(f"- RAM 差异: {len(ram_mismatches)} 款")
    for r in ram_mismatches[:3]:
        print(f"  PID {r['pid']} ({r['name']}): GoVPS={r['govps']}G vs d-vps={r['dvps']}G")

    print(f"- 流量差异: {len(bw_mismatches)} 款")
    for b in bw_mismatches[:3]:
        print(f"  PID {b['pid']} ({b['name']}): GoVPS={b['govps']}G vs d-vps={b['dvps']}G")

    return {
        "merchant": merchant_name,
        "govps_count": len(govps_by_id),
        "dvps_count": len(dvps_by_id),
        "common_count": len(common_pids),
        "stock_mismatches": stock_mismatches,
        "line_mismatches": line_mismatches,
        "missing_in_govps": list(missing_in_govps),
        "missing_in_stock": missing_in_stock,
        "cpu_mismatches": cpu_mismatches,
        "ram_mismatches": ram_mismatches,
        "bw_mismatches": bw_mismatches,
    }


def main():
    dvps = DvpsClient(API_DIR / "app" / "crawler" / "dvps.wasm")
    with make_client(30.0) as client:
        vpszk_all = fetch_vpszk_plans(client)

        merchant_configs = [
            ("BandwagonHost", "bandwagon", "bandwagonhost", "bandwagonhost", "bwh"),
            ("DMIT", "dmit", "dmit", "dmit", "dmit"),
            ("V.PS", "vps", "vps", "vps", None),
            ("VMiss", "vmiss", "vmiss", "vmiss", None),
            ("DediOne", "dedione", "dedione", "dedione", None),
            ("66云", "66yun", "liuliuyun", "66yun", None),
            ("ZgoCloud", "zgocloud", "zgovps", "zgo", None),
            ("GoMami", "gomami", "gomami", "gomami", "gomami"),
            ("Evoxt", "evoxt", "evoxt", "evoxt", "evoxt"),
        ]

        all_results = {}
        for m_name, govps_slug, dvps_prov, vpszk_slug, vpsoso_slug in merchant_configs:
            crawler = next((c for c in CRAWLERS if c.slug == govps_slug), None)
            if not crawler:
                continue
            govps_raws = crawler.fetch(client)
            dvps_raws = dvps.get_products(dvps_prov)
            vpszk_items = [p for p in vpszk_all if p.get("providerSlug") == vpszk_slug]
            vpsoso_items = fetch_vpsoso_plans(client, vpsoso_slug) if vpsoso_slug else []

            res = compare_plans(m_name, govps_raws, dvps_raws, vpszk_items, vpsoso_items)
            all_results[govps_slug] = res

        with open(API_DIR / "audit_report.json", "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"\n[audit] Full report written to {API_DIR / 'audit_report.json'}")


if __name__ == "__main__":
    main()
