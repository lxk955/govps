"""管理后台可改的站点配置：库里有值则覆盖 .env 默认。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import SiteSetting

# key -> (kind, env default, min, max)  min/max 仅 int
SPEC: dict[str, tuple] = {
    "event_dedup_minutes": ("int", settings.EVENT_DEDUP_MINUTES, 1, 10080),
    "daily_mail_cap": ("int", settings.DAILY_MAIL_CAP, 0, 1000),
    "indexnow_enabled": ("bool", settings.INDEXNOW_ENABLED, None, None),
}


def _row(db: Session, key: str) -> SiteSetting | None:
    return db.scalar(select(SiteSetting).where(SiteSetting.key == key))


def get_str(db: Session, key: str, default: str) -> str:
    row = _row(db, key)
    if row is None or row.value is None or row.value == "":
        return default
    return row.value


def get_int(db: Session, key: str, default: int) -> int:
    raw = get_str(db, key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_bool(db: Session, key: str, default: bool) -> bool:
    raw = get_str(db, key, "1" if default else "0").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def public_settings(db: Session) -> dict:
    return {
        "event_dedup_minutes": get_int(db, "event_dedup_minutes", settings.EVENT_DEDUP_MINUTES),
        "daily_mail_cap": get_int(db, "daily_mail_cap", settings.DAILY_MAIL_CAP),
        "indexnow_enabled": get_bool(db, "indexnow_enabled", settings.INDEXNOW_ENABLED),
    }


def upsert_settings(db: Session, payload: dict) -> dict:
    for key, spec in SPEC.items():
        if key not in payload or payload[key] is None:
            continue
        kind, default, lo, hi = spec
        if kind == "int":
            try:
                n = int(payload[key])
            except (TypeError, ValueError):
                continue
            if lo is not None and n < lo:
                n = lo
            if hi is not None and n > hi:
                n = hi
            value = str(n)
        else:
            value = "1" if bool(payload[key]) else "0"
        row = _row(db, key)
        if row is None:
            db.add(SiteSetting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return public_settings(db)
