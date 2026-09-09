"""共享权限辅助 — share 访问解析(owner/granted/guest-token)与文件 URL 签发。

避免每个路由文件重复实现 get_share 的 owner/viewer/editor/token 判定。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Share, ShareToken, User, UserGrant


async def get_share_by_slug(slug: str, db: AsyncSession) -> Share:
    """按 slug 取未删除 share,不存在 → 404。"""
    stmt = (
        select(Share)
        .where(Share.slug == slug)
        .where(Share.is_deleted == False)  # noqa: E712
    )
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="share not found")
    return share


async def resolve_share_role(
    share: Share, user: User, db: AsyncSession
) -> Optional[str]:
    """返回登录用户对 share 的角色。

    - owner / admin → None(与既有 API 约定一致:role=None 表示 owner)
    - viewer/editor grant → 对应 role
    - 无权限 → 403
    """
    if share.owner_id == user.id or user.is_admin:
        return None

    stmt = select(UserGrant).where(
        UserGrant.share_id == share.id,
        UserGrant.user_id == user.id,
    )
    result = await db.execute(stmt)
    grant = result.scalar_one_or_none()
    if not isinstance(grant, UserGrant):
        raise HTTPException(status_code=403, detail="no access to this share")
    return grant.role


async def require_share_read_access(
    share: Share, user: User, db: AsyncSession
) -> Optional[str]:
    """读访问(share 可见 + 列文件)。owner/admin/granted(read 或 editor)→ role。"""
    return await resolve_share_role(share, user, db)


async def require_share_write_access(
    share: Share, user: User, db: AsyncSession
) -> None:
    """写访问(上传/删除文件)。owner/admin/editor grant。viewer → 403。"""
    role = await resolve_share_role(share, user, db)
    if role == "viewer":
        raise HTTPException(status_code=403, detail="readonly: viewer cannot write")


async def resolve_guest_token(
    share: Share, token_code: str, db: AsyncSession
) -> ShareToken:
    """游客 token 校验:存在 + 未撤销 + 未过期。失败 → 401。"""
    stmt = select(ShareToken).where(
        ShareToken.share_id == share.id,
        ShareToken.token_code == token_code,
    )
    result = await db.execute(stmt)
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=401, detail="invalid token")
    if token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="token revoked")
    if token.expires_at is not None:
        if token.expires_at.timestamp() < datetime.now(timezone.utc).timestamp():
            raise HTTPException(status_code=401, detail="token expired")
    return token


def file_url_kind_keys(file) -> dict:
    """file row → 各 kind 的 OBS key 映射(含 fallback 链)。"""
    keys = {}
    for kind, attr in (
        ("raw", "obs_key"),
        ("display", "display_key"),
        ("preview", "preview_key"),
        ("thumb", "thumb_key"),
    ):
        v = getattr(file, attr, None)
        if v:
            keys[kind] = v
    return keys
