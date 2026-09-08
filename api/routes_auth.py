"""认证路由 — ticket #5 (注册) / #6 (登录/me) / #7 (logout/refresh/admin)。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import async_session, get_session
from .jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from .models import User
from .redis_client import blacklist_token, is_blacklisted
from .schemas import TokenOut, UserCreate, UserLogin, UserOut
from .security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# 用于 FastAPI 的 OAuth2 流(后续 ticket 视情况启用)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
) -> User | None:
    """从 Authorization: Bearer <token> 取当前用户。

    失败返 None(由路由决定 401 / 403)。
    """
    if not authorization:
        return None
    # 兼容 "Bearer xxx" 与直接 "xxx"
    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    try:
        payload = decode_token(token)
    except Exception:
        return None
    if payload.get("type") != "access":
        return None
    # 检查黑名单
    jti = payload.get("jti")
    if jti and is_blacklisted(jti):
        return None
    try:
        uid = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = await db.get(User, uid)
    return user


async def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    """强制要求登录 — 401 if not。"""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ── POST /auth/register ────────────────────────────────
@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_session)) -> TokenOut:
    """注册:邮箱 + 密码 → 写 users → 返 access + refresh。

    重复邮箱 → 409。
    """
    user = User(
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )
    await db.refresh(user)

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
    )


# ── POST /auth/login ───────────────────────────────────
@router.post("/login", response_model=TokenOut)
async def login(body: UserLogin, db: AsyncSession = Depends(get_session)) -> TokenOut:
    """登录:邮箱 + 密码 → 返 access + refresh。

    错密码 / 不存在邮箱 → 401(统一信息,防 enumeration)。
    """
    stmt = select(User).where(User.email == body.email.lower().strip())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 更新 last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
    )


# ── GET /auth/me ────────────────────────────────────────
@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(require_user)) -> UserOut:
    """当前用户。401 if missing/invalid token。"""
    return UserOut.model_validate(user)


# ── POST /auth/logout ───────────────────────────────────
class LogoutOut(BaseModel):
    ok: bool = True


class RefreshIn(BaseModel):
    refresh_token: str


class RefreshOut(BaseModel):
    access_token: str
    refresh_token: str


@router.post("/logout", response_model=LogoutOut)
async def logout(
    authorization: str | None = Header(default=None),
    user: User | None = Depends(get_current_user),
) -> LogoutOut:
    """登出 — 把当前 access token 的 jti 加黑名单。

    客户端应同时丢弃 refresh token(否则通过 /refresh 仍可换 access)。
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")

    jti = payload.get("jti")
    if jti:
        exp = payload.get("exp", 0)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        ttl = max(60, int(exp - now_ts))  # 至少 60s
        ttl = min(ttl, 30 * 24 * 3600)  # 不超过 30d
        blacklist_token(jti, ttl)
    return LogoutOut()


# ── POST /auth/refresh ──────────────────────────────────
@router.post("/refresh", response_model=RefreshOut)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_session)) -> RefreshOut:
    """refresh token → 新 access + refresh(轮换)。

    黑名单中的 jti 拒绝。
    """
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="not a refresh token")

    jti = payload.get("jti")
    if jti and is_blacklisted(jti):
        raise HTTPException(status_code=401, detail="refresh token revoked")

    try:
        uid = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="malformed token")

    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")

    # 旧 refresh 也进黑名单(rotation)
    if jti:
        exp = payload.get("exp", 0)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        ttl = max(60, int(exp - now_ts))
        blacklist_token(jti, ttl)

    return RefreshOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


# ── GET /auth/me/role(admin 标记) ───────────────────────
@router.get("/me/role", response_model=dict)
async def me_role(user: User = Depends(require_user)) -> dict:
    """返回当前用户角色(便于前端区分 admin UI)。"""
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
    }