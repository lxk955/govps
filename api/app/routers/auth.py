import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import EmailCode, User
from ..schemas import TokenOut
from ..services.notify import send_email
from ..services.client_ip import client_ip
from ..services.rate_limit import hit_rate_limited

router = APIRouter(prefix="/api/auth", tags=["auth"])

CODE_TTL_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5
# IP 限流（P7 #10 起 DB 滑动窗口计数）：防止用换邮箱的方式绕过 60 秒限制做邮件轰炸；
# 计数存 request_rate_events 表，多 worker / 重启后窗口仍连续。
IP_RATE_SECONDS = 60
IP_MAX_REQUESTS = 5


class RequestCodeIn(BaseModel):
    email: EmailStr


class VerifyIn(BaseModel):
    email: EmailStr
    code: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """SQLite 读回的 datetime 不带时区，统一视为 UTC。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _send_code_email(email: str, code: str) -> tuple[bool, str | None]:
    html = f"""
    <h2>VPS 雷达 登录验证码</h2>
    <p style="font-size:28px;font-weight:bold;letter-spacing:6px">{code}</p>
    <p>验证码 {CODE_TTL_MINUTES} 分钟内有效。如果这不是你的操作，请忽略本邮件。</p>
    """
    return send_email(email, "VPS 雷达 登录验证码", html)


@router.post("/request-code")
def request_code(payload: RequestCodeIn, request: Request, db: Session = Depends(get_db)):
    """发送 6 位登录验证码。同一邮箱 60 秒内只允许发一次；每 IP 每分钟最多 5 次。"""
    ip = client_ip(request)
    if hit_rate_limited(db, ip, window_seconds=IP_RATE_SECONDS, max_requests=IP_MAX_REQUESTS):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    email = str(payload.email).lower()
    existing = db.scalar(
        select(EmailCode)
        .where(EmailCode.email == email)
        .order_by(EmailCode.created_at.desc())
    )
    if existing:
        age = (_utcnow() - _as_aware(existing.created_at)).total_seconds()
        if age < RESEND_COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"发送太频繁，请 {RESEND_COOLDOWN_SECONDS - int(age)} 秒后重试",
            )

    code = f"{secrets.randbelow(1_000_000):06d}"
    # 每封邮箱只保留最新一条验证码
    db.execute(delete(EmailCode).where(EmailCode.email == email))
    db.add(
        EmailCode(
            email=email,
            code=code,
            expires_at=_utcnow() + timedelta(minutes=CODE_TTL_MINUTES),
        )
    )
    db.commit()

    mail_configured = bool(settings.RESEND_API_KEY)
    ok, err = _send_code_email(email, code)
    if not ok:
        # 安全：验证码绝不写入日志；未配置发信时经响应体 dev_code 下发（仅限本地开发）
        print(f"[auth] mail send failed (configured={mail_configured}): {err}")
        if mail_configured:
            raise HTTPException(status_code=503, detail="验证码发送失败，请稍后重试")
    # 仅在未配置发信时把验证码回给前端，方便本地开发；生产有 API key 时绝不下发
    return {"ok": True, "dev_code": None if mail_configured else code}


@router.post("/verify", response_model=TokenOut)
def verify(payload: VerifyIn, db: Session = Depends(get_db)):
    """校验验证码，换取长期 token（注册/登录合一）。"""
    email = str(payload.email).lower()
    record = db.scalar(
        select(EmailCode)
        .where(EmailCode.email == email)
        .order_by(EmailCode.created_at.desc())
    )
    if record is None or _as_aware(record.expires_at) < _utcnow():
        raise HTTPException(status_code=400, detail="验证码不存在或已过期，请重新获取")
    if record.attempts >= MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail="尝试次数过多，请重新获取验证码")

    if record.code != payload.code.strip():
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="验证码错误")

    db.execute(delete(EmailCode).where(EmailCode.email == email))

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, api_token=secrets.token_urlsafe(32))
        db.add(user)
    else:
        user.api_token = secrets.token_urlsafe(32)
    db.commit()
    return TokenOut(token=user.api_token)


class PreferenceIn(BaseModel):
    view_mode: str | None = None  # "card" | "list"
    currency_mode: str | None = None  # "CNY" | "USD" | "original"


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """当前登录用户信息及用户偏好设置。"""
    return {
        "email": user.email,
        "view_mode": user.view_mode or "card",
        "currency_mode": getattr(user, "currency_mode", None) or "CNY",
    }


@router.put("/preferences")
def update_preferences(
    payload: PreferenceIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新用户偏好设置（如视图模式卡片/列表、价格换算币种）。"""
    if payload.view_mode and payload.view_mode in ["card", "list"]:
        user.view_mode = payload.view_mode
    if payload.currency_mode and payload.currency_mode in ["CNY", "USD", "original"]:
        user.currency_mode = payload.currency_mode
    db.commit()
    return {
        "ok": True,
        "email": user.email,
        "view_mode": user.view_mode or "card",
        "currency_mode": getattr(user, "currency_mode", None) or "CNY",
    }
