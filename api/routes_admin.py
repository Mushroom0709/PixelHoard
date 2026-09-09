"""Admin 路由 — 管理员管理用户(需求 1:管理员负责管理用户)。

- GET    /admin/users        列全部用户(仅 admin)
- PATCH  /admin/users/{id}   设置/取消 is_admin(仅 admin,不能改自己)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import User
from .routes_auth import require_user

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: Optional[str] = None
    is_admin: bool
    is_verified: bool
    created_at: datetime


class AdminUserPatch(BaseModel):
    is_admin: Optional[bool] = None
    is_verified: Optional[bool] = None


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin only")


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> list[AdminUserOut]:
    """列全部用户(按创建倒序)。"""
    _require_admin(user)
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [AdminUserOut.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def patch_user(
    user_id: int,
    body: AdminUserPatch,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> AdminUserOut:
    """改用户 is_admin / is_verified。不能操作自己(防止锁死)。"""
    _require_admin(user)
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot modify yourself")

    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")

    if body.is_admin is not None:
        target.is_admin = body.is_admin
    if body.is_verified is not None:
        target.is_verified = body.is_verified
    await db.commit()
    await db.refresh(target)
    return AdminUserOut.model_validate(target)
