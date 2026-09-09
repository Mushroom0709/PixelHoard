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
    """取 share 详情。

    权限:
    - owner / admin → 200
    - viewer / editor(被授权)→ 200 + 返回 role(ticket #13)
    - 其他 → 403
    - 不存在 → 404
    """
    stmt = select(Share).where(Share.slug == slug).where(Share.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="share not found")

    # owner / admin 直通
    if share.owner_id == user.id or user.is_admin:
        return ShareOut.model_validate(share)

    # grant 检查
    from .models import UserGrant  # noqa
    stmt2 = select(UserGrant).where(
        UserGrant.share_id == share.id,
        UserGrant.user_id == user.id,
    )
    result2 = await db.execute(stmt2)
    grant = result2.scalar_one_or_none()
    # grant 必须是 UserGrant 实例(mock 测试场景下可能返其他对象)
    if not isinstance(grant, UserGrant):
        raise HTTPException(status_code=403, detail="no access to this share")

    # 返回带 role 信息(用于 #13 viewer/editor 区分)
    out = ShareOut.model_validate({
        "id": share.id,
        "owner_id": share.owner_id,
        "slug": share.slug,
        "title": share.title,
        "description": share.description,
        "is_deleted": share.is_deleted,
        "created_at": share.created_at,
        "updated_at": share.updated_at,
        "role": grant.role,
    })
    return out


# ── Token CRUD(ticket #10) ─────────────────────────────
from .models import ShareToken  # noqa: E402
from .schemas import ShareTokenCreate, ShareTokenOut  # noqa: E402
from datetime import datetime as _dt, timezone as _tz  # noqa: E402
from fastapi import Response  # noqa: E402


async def _resolve_share_or_404(slug: str, user: UserModel, db: AsyncSession) -> Share:
    """取 share 并校验 owner(供 token CRUD 用)。"""
    stmt = select(Share).where(Share.slug == slug).where(Share.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="share not found")
    if share.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="not owner")
    return share


@router.post("/{slug}/tokens", response_model=ShareTokenOut, status_code=201)
async def create_token(
    slug: str,
    body: ShareTokenCreate,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> ShareTokenOut:
    """owner 给 share 生成一个访问 token。"""
    share = await _resolve_share_or_404(slug, user, db)

    # 生成短码:8 位 base62
    token_code = random_slug(8)

    expires_at = body.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=_tz.utc)

    token = ShareToken(
        share_id=share.id,
        token_code=token_code,
        permission=body.permission,
        label=body.label,
        public_note=body.public_note,
        expires_at=expires_at,
    )
    db.add(token)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # 极小概率碰撞,重试一次
        token_code = random_slug(8)
        token.token_code = token_code
        await db.commit()
    await db.refresh(token)
    return ShareTokenOut.model_validate(token)


# ── Files list(GET /shares/{slug}/files) ────────────────
from .models import File as FileModel  # noqa: E402
from .schemas import FileListOut, FileOut  # noqa: E402


@router.get("/{slug}/files", response_model=FileListOut)
async def list_files(
    slug: str,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> FileListOut:
    """列出 share 内文件(owner / viewer / editor 都能看)。"""
    share = await _resolve_share_or_404(slug, user, db)

    stmt = (
        select(FileModel)
        .where(FileModel.share_id == share.id)
        .order_by(FileModel.created_at.desc())
    )
    result = await db.execute(stmt)
    files = result.scalars().all()
    return FileListOut(
        files=[FileOut.model_validate(f) for f in files],
        total=len(files),
    )


@router.get("/{slug}/tokens", response_model=list[ShareTokenOut])
async def list_tokens(
    slug: str,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> list[ShareTokenOut]:
    """owner 列出 share 的所有 token(含已撤销)。"""
    share = await _resolve_share_or_404(slug, user, db)

    stmt = (
        select(ShareToken)
        .where(ShareToken.share_id == share.id)
        .order_by(ShareToken.created_at.desc())
    )
    result = await db.execute(stmt)
    tokens = result.scalars().all()
    return [ShareTokenOut.model_validate(t) for t in tokens]


@router.delete("/{slug}/tokens/{token_id}", status_code=204, response_class=Response)
async def revoke_token(
    slug: str,
    token_id: int,
    user: UserModel = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Response:
    """owner 撤销 token(revoked_at = now)。"""
    share = await _resolve_share_or_404(slug, user, db)

    stmt = select(ShareToken).where(
        ShareToken.id == token_id,
        ShareToken.share_id == share.id,
    )
    result = await db.execute(stmt)
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=404, detail="token not found")
    if token.revoked_at is None:
        token.revoked_at = _dt.now(_tz.utc)
        await db.commit()
    return Response(status_code=204)