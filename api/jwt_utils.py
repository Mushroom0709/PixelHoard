"""JWT 签发 / 校验。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt

from .config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, extra: Optional[dict[str, Any]] = None) -> str:
    """签发 access token(短期)。"""
    import secrets
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.JWT_ACCESS_TTL_MIN),
        "jti": secrets.token_urlsafe(16),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    """签发 refresh token(长期)。"""
    import secrets
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": _now(),
        "exp": _now() + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """解码 + 校验 JWT;失败抛 JWTError。"""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])


def decode_token_safe(token: str) -> Optional[dict[str, Any]]:
    """安全解码 — 失败返 None 不抛。"""
    try:
        return decode_token(token)
    except JWTError:
        return None