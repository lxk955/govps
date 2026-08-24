"""汇率服务（P5）：自动抓取 + 每日快照 + 人工覆盖。

原则（refactor-plan §3 P5 / 验收标准）：
- 汇率独立存储于 exchange_rates / exchange_rate_snapshots，任何路径不回写产品价格；
- 自动源异常（请求失败/字段缺失/数值非法/漂移过大）时拒绝写入并保留旧值，
  绝不静默产生错误数据；人工覆盖不受漂移守卫限制（source=manual）;
- 快照 unique(code, date)，当日重复更新幂等覆盖；
- USD 恒为 1.0，统一换算币种。
"""

import datetime
import math
from datetime import date, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ExchangeRate, ExchangeRateSnapshot

# 站点在售币种全集（crawler 产出）；USD 恒为 1.0
SUPPORTED_CODES = ("USD", "CNY", "EUR", "CAD")
BASE_CODE = "USD"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(timezone.utc)


def fetch_rates(client: httpx.Client) -> tuple[dict[str, float] | None, str | None]:
    """从主/备数据源拉取 base=USD 报价。两个源的响应格式均已核实：
    er-api: {"result": "ok", "rates": {"CNY": ...}}；frankfurter: {"rates": {...}}。
    全部失败返回 (None, 错误说明)，由调用方决定降级。"""
    urls = [settings.EXCHANGE_RATE_API_URL, settings.EXCHANGE_RATE_FALLBACK_API_URL]
    last_err: str | None = None
    for url in urls:
        try:
            resp = client.get(url)
        except httpx.HTTPError as e:
            last_err = f"{url}: {e}"
            continue
        if resp.status_code != 200:
            last_err = f"{url}: HTTP {resp.status_code}"
            continue
        try:
            data = resp.json()
            rates = data["rates"]
            parsed: dict[str, float] = {}
            for code in SUPPORTED_CODES:
                if code == BASE_CODE:
                    parsed[code] = 1.0
                    continue
                v = float(rates[code])
                if not math.isfinite(v) or v <= 0:
                    raise ValueError(f"{code} 非法数值 {v}")
                parsed[code] = v
            return parsed, None
        except (KeyError, TypeError, ValueError) as e:
            last_err = f"{url}: 响应格式或数值异常 ({e})"
            continue
    return None, last_err


def _deviation_ok(stored: ExchangeRate | None, new_rate: float) -> bool:
    """自动源漂移守卫：相对当前存量值变动超过阈值视为异常（首次写入不设限）。"""
    if stored is None:
        return True
    old = float(stored.units_per_usd)
    if old <= 0:
        return True
    return abs(new_rate - old) / old <= settings.EXCHANGE_RATE_MAX_DEVIATION


def update_rates(
    db: Session,
    client: httpx.Client | None = None,
    overrides: dict[str, float] | None = None,
) -> dict:
    """更新汇率并写当日快照。

    - 无 overrides：走自动源；任一币种校验失败/缺失则该币种保留旧值；
      整体拉取失败返回 ok=False 且完全不动库（断源沿用旧值并标记 updated_at 不变）。
    - 有 overrides：人工覆盖，跳过漂移守卫，source=manual。
    幂等：同日快照覆盖更新；rates 行 upsert。"""
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=settings.EXCHANGE_RATE_TIMEOUT)

    today = date.today()
    result: dict = {"ok": False, "updated": [], "skipped": [], "source": "manual" if overrides else "auto"}
    source_reachable = False

    try:
        if overrides:
            # 人工覆盖：仅写入提供的币种（未提供的自然保留旧值），跳过漂移守卫
            fetched = {}
            for c, v in overrides.items():
                if c not in SUPPORTED_CODES:
                    result["skipped"].append(f"{c}: 不支持的币种")
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    result["skipped"].append(f"{c}: 数值非法")
                    continue
                if c != BASE_CODE and (not math.isfinite(fv) or fv <= 0):
                    result["skipped"].append(f"{c}: 数值非法（须为正数）")
                    continue
                fetched[c] = 1.0 if c == BASE_CODE else fv
        else:
            fetched, err = fetch_rates(client)  # type: ignore[arg-type]
            if fetched is None:
                # 断源降级：保留旧值，明确报告失败原因
                result["error"] = f"全部汇率源不可用: {err}"
                return result
            source_reachable = True

        for code in SUPPORTED_CODES:
            rate = fetched.get(code)
            if rate is None:
                result["skipped"].append(f"{code}: 本次未提供，保留旧值")
                continue
            stored = db.scalar(select(ExchangeRate).where(ExchangeRate.code == code))
            if overrides is None and not _deviation_ok(stored, rate):
                # 自动源异常守卫：疑似坏数据，拒绝静默写入
                result["skipped"].append(
                    f"{code}: 漂移超限({stored.units_per_usd} → {rate})，需人工确认"
                )
                continue

            if stored is None:
                stored = ExchangeRate(code=code)
                db.add(stored)
            stored.units_per_usd = rate
            stored.source = "manual" if overrides else "auto"
            stored.updated_at = _utcnow()

            snap = db.scalar(
                select(ExchangeRateSnapshot).where(
                    ExchangeRateSnapshot.code == code,
                    ExchangeRateSnapshot.date == today,
                )
            )
            if snap is None:
                db.add(ExchangeRateSnapshot(code=code, date=today, units_per_usd=rate))
            else:
                snap.units_per_usd = rate
                snap.created_at = _utcnow()
            result["updated"].append(code)

        db.commit()
        result["ok"] = True if overrides else source_reachable
        return result
    finally:
        if own_client:
            client.close()  # type: ignore[union-attr]


def current_rates_map(db: Session) -> dict[str, float]:
    """当前汇率 → {code: units_per_usd}（换算展示用，单次请求加载一次）。
    USD 金额 = 外币金额 ÷ units_per_usd。"""
    rows = db.scalars(select(ExchangeRate)).all()
    m = {r.code: float(r.units_per_usd) for r in rows}
    m.setdefault(BASE_CODE, 1.0)
    return m


def snapshot_map_for_days(db: Session, days: int = 90) -> dict[str, dict[str, float]]:
    """近 N 天快照 → {iso_date: {code: units_per_usd}}，供历史价格按日期匹配。"""
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(ExchangeRateSnapshot).where(ExchangeRateSnapshot.date >= since)
    ).scalars()
    out: dict[str, dict[str, float]] = {}
    for s in rows:
        out.setdefault(s.date.isoformat(), {})[s.code] = float(s.units_per_usd)
    return out


def convert_historical(
    amount: float,
    currency: str,
    on_date: str,
    snapshots: dict[str, dict[str, float]],
    current: dict[str, float],
) -> float | None:
    """历史外币金额 → USD：USD = 金额 ÷ 该日期的 units_per_usd。
    只使用「该日期当日或之前最近」的快照。

    找不到（如快照体系上线前的历史数据）返回 None——宁缺毋滥，
    绝不退回当前汇率造成「历史价格错误使用当前汇率」。"""
    if currency == BASE_CODE:
        return amount
    try:
        d = date.fromisoformat(on_date[:10])
    except ValueError:
        return None
    for _ in range(31):  # 最多回看 30 天，覆盖长假期/抓取中断窗口
        day = snapshots.get(d.isoformat())
        if day and currency in day and day[currency] > 0:
            return amount / day[currency]
        d -= timedelta(days=1)
    return None
