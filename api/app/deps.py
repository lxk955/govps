from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """MVP 阶段的极简认证：Bearer token 即用户凭证。
    P1 再升级为邮箱验证码登录。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = db.scalar(select(User).where(User.api_token == token))
    if user is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return user


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """可选认证：携带有效 token 返回用户，否则返回 None（不抛错）。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return db.scalar(select(User).where(User.api_token == token))


def verify_task_token(x_task_token: str | None = Header(default=None)) -> str:
    from .config import settings
    if x_task_token != settings.TASK_TOKEN:
        raise HTTPException(status_code=403, detail="invalid task token")
    return x_task_token
