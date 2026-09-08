"""UserGrant 路由 — ticket #12 创建/列表/撤销 / #13 viewer/editor 区分。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Share, User as UserModel, UserGrant
from .routes_auth import require_user
from .routes_shares import _resolve_share_or_404
from .schemas import UserGrantCreate, UserGrantOut

router = APIRouter(prefix="/shares", tags=["grants"])


@router.post("/{slug}/grants", response_model=UserGrantOut, status_code=201)
async def create_grant(
    slug: str,
    body: UserGrantCreate,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> UserGrantOut:
    """owner 把 share 授权给某用户(viewer / editor)。"""
    share = await _resolve_share_or_404(slug, user, db)

    # 查目标用户
    stmt = select(UserModel).where(UserModel.email == body.user_email.lower().strip())
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    if target.id == share.owner_id:
        raise HTTPException(status_code=400, detail="cannot grant to owner")

    grant = UserGrant(
        share_id=share.id,
        user_id=target.id,
        role=body.role,
        granted_by=user.id,
    )
    db.add(grant)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="grant already exists")
    await db.refresh(grant)
    return UserGrantOut.model_validate(grant)


@router.get("/{slug}/grants", response_model=list[UserGrantOut])
async def list_grants(
    slug: str,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> list[UserGrantOut]:
    """owner 列出 share 的所有授权。"""
    share = await _resolve_share_or_404(slug, user, db)
    stmt = (
        select(UserGrant)
        .where(UserGrant.share_id == share.id)
        .order_by(UserGrant.created_at.desc())
    )
    result = await db.execute(stmt)
    grants = result.scalars().all()
    return [UserGrantOut.model_validate(g) for g in grants]


@router.delete("/{slug}/grants/{user_id}", status_code=204, response_class=__import__("fastapi").Response)
async def revoke_grant(
    slug: str,
    user_id: int,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """owner 撤销某个用户的授权。"""
    from fastapi import Response

    share = await _resolve_share_or_404(slug, user, db)

    stmt = select(UserGrant).where(
        UserGrant.share_id == share.id,
        UserGrant.user_id == user_id,
    )
    result = await db.execute(stmt)
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail="grant not found")
    await db.delete(grant)
    await db.commit()
    return Response(status_code=204)