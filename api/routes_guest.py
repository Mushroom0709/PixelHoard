"""游客访问 — ticket #11。

URL: /s/{slug}/{token} — 游客通过 token 进入分享(只读 + 可下载)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Share, ShareToken
from .redis_client import blacklist_token
from .schemas import ShareOut

router = APIRouter(prefix="/s", tags=["guest"])


def _now_ts() -> int:
    from datetime import datetime, timezone
    return int(datetime.now(timezone.utc).timestamp())


@router.get("/{slug}/{token_code}", response_model=ShareOut)
async def guest_view(
    slug: str,
    token_code: str,
    db: AsyncSession = Depends(get_session),
) -> ShareOut:
    """游客通过 token 访问 share。

    - token 必须存在、未撤销、未过期
    - 黑名单中的 token 拒绝
    - 游客永远只读,鉴权只用于"能否看",不看具体权限(read/readwrite)
    """
    # 1. 查 share
    stmt = select(Share).where(Share.slug == slug).where(Share.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="share not found")

    # 2. 查 token
    stmt2 = select(ShareToken).where(
        ShareToken.share_id == share.id,
        ShareToken.token_code == token_code,
    )
    result2 = await db.execute(stmt2)
    token = result2.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=401, detail="invalid token")

    # 3. 撤销?
    if token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="token revoked")

    # 4. 过期?
    if token.expires_at is not None:
        # expires_at 是 tz-aware datetime,token.expires_at.timestamp() 返 ts
        if token.expires_at.timestamp() < _now_ts():
            raise HTTPException(status_code=401, detail="token expired")

    # 5. 更新 last_used_at(非关键)
    from datetime import datetime, timezone
    token.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return ShareOut.model_validate(share)