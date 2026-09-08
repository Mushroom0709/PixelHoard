"""认证路由 — ticket #5 (#6 login, #7 logout/refresh 在此基础上加)。"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import async_session, get_session
from .jwt_utils import create_access_token, create_refresh_token, decode_token
from .models import User
from .schemas import TokenOut, UserCreate, UserLogin, UserOut
from .security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# 用于 FastAPI 的 OAuth2 流(后续 ticket 视情况启用)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> User | None:
    """从 Authorization: Bearer <token> 取当前用户。

    失败返 None(由路由决定 401 / 403)。
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:
        return None
    if payload.get("type") != "access":
        return None
    try:
        uid = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = await db.get(User, uid)
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


# ── POST /auth/login(占位 — ticket #6 完善) ─────────────
@router.post("/login", response_model=TokenOut)
async def login(body: UserLogin, db: AsyncSession = Depends(get_session)) -> TokenOut:
    """登录:ticket #6 完善。"""
    # 先占位 — ticket #6 实现具体逻辑
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="login not implemented yet (ticket #6)")