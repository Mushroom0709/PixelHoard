"""删 share 路由 — ticket #20。

行为:
- DB 删 share(级联删 share_tokens + user_grants + files)
- OBS 删 prefix PixelHoard/shares/{share_id}/
- 写 audit_logs
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit import log
from .config import settings
from .db import get_session
from .models import File, Share, ShareToken, User, UserGrant
from .obs_client import obs
from .routes_auth import require_user

router = APIRouter(prefix="/shares", tags=["share-delete"])


async def _delete_obs_prefix(share_id: int) -> int:
    """删 OBS 上 shares/{share_id}/ 全部对象。返回删除数量。"""
    prefix = f"{settings.OBS_WORKDIR}/shares/{share_id}/"

    # 列 prefix 下全部对象(可能分页)
    deleted = 0
    marker = None
    while True:
        kwargs = {
            "bucketName": settings.OBS_BUCKET,
            "prefix": prefix,
            "max_keys": 1000,
        }
        if marker:
            kwargs["marker"] = marker

        resp = obs.listObjects(**kwargs)
        if resp.status >= 300:
            raise RuntimeError(f"OBS list failed: {resp.errorCode}")

        contents = resp.body.contents or []
        if not contents:
            break

        # 批量删
        for obj in contents:
            try:
                obs.deleteObject(
                    bucketName=settings.OBS_BUCKET,
                    objectKey=obj.key,
                )
                deleted += 1
            except Exception:
                pass  # 继续

        if not resp.body.isTruncated:
            break
        marker = getattr(resp.body, "nextMarker", None)
        if not marker:
            break

    return deleted


@router.delete("/{slug}", status_code=204, response_class=Response)
async def delete_share(
    slug: str,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
) -> Response:
    """硬删 share。

    - DB: cascade 删 share_tokens / user_grants / files
    - OBS: 删 prefix PixelHoard/shares/{share_id}/
    - audit: 写 delete_share 行
    """
    # 1. 查 share
    stmt = select(Share).where(Share.slug == slug).where(Share.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="share not found")

    # 2. 权限:owner 或 admin
    if share.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="not owner")

    share_id = share.id

    # 3. DB 硬删 — FK CASCADE 自动处理 share_tokens/user_grants/files
    await db.execute(delete(Share).where(Share.id == share_id))
    await db.commit()

    # 4. OBS 删 prefix(异步,失败不阻塞 — 后续 cron 兜底)
    try:
        deleted_count = await asyncio.to_thread(_delete_obs_prefix, share_id)
    except Exception as e:
        # 记录到 audit 但不抛错(DB 已删,OBS 残留可后续清理)
        await log(
            "obs_delete_failed",
            user_id=user.id,
            share_id=share_id,
            target_type="share",
            target_id=share_id,
        )
        deleted_count = -1
        print(f"[delete_share] OBS cleanup failed for share {share_id}: {e}")

    # 5. 审计
    await log(
        "delete_share",
        user_id=user.id,
        share_id=share_id,
        target_type="share",
        target_id=share_id,
    )

    return Response(status_code=204)