"""Share 路由 — ticket #8 创建/列表 / #9 详情 / #10 token CRUD / #11 游客 / #12-13 grant。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Share
from .models import User as UserModel
from .routes_auth import require_user
from .schemas import ShareCreate, ShareOut
from .utils import normalize_slug, random_slug

router = APIRouter(prefix="/shares", tags=["shares"])


# ── POST /shares ────────────────────────────────────────
@router.post("", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
async def create_share(
    body: ShareCreate,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> ShareOut:
    """创建 share — 自动生成 8 位 base62 slug(或用户自定义)。"""
    # 处理 slug
    if body.slug:
        slug = normalize_slug(body.slug)
        if not (3 <= len(slug) <= 32):
            raise HTTPException(status_code=422, detail="slug must be 3-32 chars after normalization")
    else:
        slug = random_slug()

    share = Share(
        owner_id=user.id,
        slug=slug,
        title=body.title.strip(),
        description=body.description,
    )
    db.add(share)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"slug '{slug}' already exists",
        )
    await db.refresh(share)
    return ShareOut.model_validate(share)


# ── GET /shares/me ──────────────────────────────────────
@router.get("/me", response_model=list[ShareOut])
async def list_my_shares(
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> list[ShareOut]:
    """列出我创建的 share。"""
    stmt = (
        select(Share)
        .where(Share.owner_id == user.id)
        .where(Share.is_deleted == False)  # noqa: E712
        .order_by(Share.created_at.desc())
    )
    result = await db.execute(stmt)
    shares = result.scalars().all()
    return [ShareOut.model_validate(s) for s in shares]


# ── GET /shares/{slug} ──────────────────────────────────
@router.get("/{slug}", response_model=ShareOut)
async def get_share(
    slug: str,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> ShareOut:
    """取 share 详情(owner 视角)。"""
    stmt = select(Share).where(Share.slug == slug).where(Share.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="share not found")
    # owner / grant / admin 才能看(后续 ticket #11/12/13 细分)
    if share.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="no access to this share")
    return ShareOut.model_validate(share)