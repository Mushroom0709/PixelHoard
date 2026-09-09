"""上传路由 — ticket #14 upload-init / #15 前端分片(直传 OBS) / #16 upload-complete。"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .models import File, Share, ShareToken, User, UserGrant
from .obs_client import obs, obs_key
from .redis_client import redis_client
from .schemas import (
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadInitRequest,
    UploadInitResponse,
)

# 注意:前端走 /api/shares/{slug}/upload-*,nginx 把 /api/ 前缀去掉转发给 api
# 所以这里 prefix 用 /shares,而不是 /s
router = APIRouter(prefix="/shares", tags=["upload"])

PART_SIZE = 5 * 1024 * 1024  # 5MB
UPLOAD_META_TTL = 3600 * 6  # 6h — 比预签名 URL 长


async def _resolve_share(slug: str, db: AsyncSession) -> Share:
    stmt = select(Share).where(Share.slug == slug).where(Share.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="share not found")
    return share


async def _can_write(
    share: Share,
    user: User | None,
    token: ShareToken | None,
    db: AsyncSession,
) -> bool:
    """校验写权限(owner / editor / readwrite token)。"""
    # 用户登录路径
    if user is not None:
        if share.owner_id == user.id or user.is_admin:
            return True
        # grant 检查
        stmt = select(UserGrant).where(
            UserGrant.share_id == share.id,
            UserGrant.user_id == user.id,
        )
        result = await db.execute(stmt)
        grant = result.scalar_one_or_none()
        if isinstance(grant, UserGrant) and grant.role == "editor":
            return True
        return False
    # 游客路径:用 token
    if token is not None and token.share_id == share.id:
        if token.revoked_at is not None:
            return False
        if token.expires_at and token.expires_at.timestamp() < datetime.now(timezone.utc).timestamp():
            return False
        return token.permission == "readwrite"
    return False


# ── POST /s/{slug}/upload-init ──────────────────────────
@router.post("/{slug}/upload-init", response_model=UploadInitResponse)
async def upload_init(
    slug: str,
    body: UploadInitRequest,
    user: User | None = Depends(__import__("api.routes_auth", fromlist=["get_current_user"]).get_current_user),
    token: str | None = None,  # token 通过 query param 传入(游客路径)
    db: AsyncSession = Depends(get_session),
) -> UploadInitResponse:
    """签 OBS Multipart Init URL。

    - 校验写权限(owner / editor / readwrite token)
    - 计算 part 数 = ceil(size / PART_SIZE)
    - 调用 OBS initiateMultipartUpload
    - 生成预签名 URL 用于每个 part 上传
    - DB 不写 row(完成时才写 — ticket #16)
    """
    share = await _resolve_share(slug, db)

    # 解析 token(若 query 提供)
    share_token = None
    if token:
        stmt = select(ShareToken).where(
            ShareToken.share_id == share.id,
            ShareToken.token_code == token,
        )
        result = await db.execute(stmt)
        share_token = result.scalar_one_or_none()

    if not await _can_write(share, user, share_token, db):
        raise HTTPException(status_code=403, detail="no write permission")

    # 校验 size
    if body.size > 5 * 1024 * 1024 * 1024:  # 5GB
        raise HTTPException(status_code=413, detail="file too large")

    # 生成 upload_id
    upload_id = secrets.token_urlsafe(16)

    # 计算 part 数
    n_parts = (body.size + PART_SIZE - 1) // PART_SIZE
    if n_parts > 10000:
        raise HTTPException(status_code=413, detail="too many parts")

    # OBS initiate multipart
    object_key = obs_key(
        share.id,
        "raw",
        f"{datetime.now(timezone.utc):%Y/%m/%d}/{upload_id}_{body.filename}",
    )

    try:
        resp = obs.initiateMultipartUpload(
            bucketName=settings.OBS_BUCKET,
            objectKey=object_key,
            contentType=body.mime_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OBS initiate failed: {e}")

    if resp.status < 300:
        obs_upload_id = resp.body.uploadId
    else:
        raise HTTPException(status_code=500, detail=f"OBS initiate failed: {resp.errorCode}")

    # 签每个 part 的预签名 URL
    part_urls = []
    expires_in = 3600  # 1h
    for part_num in range(1, int(n_parts) + 1):
        try:
            url_resp = obs.createSignedUrl(
                method="PUT",
                bucketName=settings.OBS_BUCKET,
                objectKey=object_key,
                expires=expires_in,
                specialParam=f"partNumber={part_num}&uploadId={obs_upload_id}",
            )
            part_urls.append(url_resp.signedUrl)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OBS sign failed: {e}")

    # 暂存 metadata(完成时用)— Redis 中
    meta = {
        "share_id": share.id,
        "obs_upload_id": obs_upload_id,
        "obs_key": object_key,
        "filename": body.filename,
        "size": body.size,
        "mime": body.mime_type,
        "sha256": body.sha256,
        "suffix": (body.filename.rsplit(".", 1)[-1] if "." in body.filename else "").lower(),
        "uploaded_by": user.id if user else None,
        "n_parts": int(n_parts),
    }
    redis_client.set(f"upload:{upload_id}", json.dumps(meta), ex=UPLOAD_META_TTL)

    return UploadInitResponse(
        upload_id=upload_id,
        part_urls=part_urls,
        part_size=PART_SIZE,
        complete_url=f"/api/shares/{slug}/upload-complete",
        expires_in=expires_in,
    )


# ── POST /s/{slug}/upload-complete ──────────────────────
@router.post("/{slug}/upload-complete", response_model=UploadCompleteResponse, status_code=201)
async def upload_complete(
    slug: str,
    body: UploadCompleteRequest,
    user: User | None = Depends(
        __import__("api.routes_auth", fromlist=["get_current_user"]).get_current_user
    ),
    db: AsyncSession = Depends(get_session),
) -> UploadCompleteResponse:
    """验证所有 part ETag + CompleteMultipart + 写 file row(processing)。

    ticket #16 核心:
    - 从 Redis 取 upload metadata
    - 调 OBS completeMultipartUpload(parts 列表)
    - 写 files row, status='processing'(等 worker 衍生档生成)
    - 返回 file_id
    """
    share = await _resolve_share(slug, db)

    meta_raw = redis_client.get(f"upload:{body.upload_id}")
    if not meta_raw:
        raise HTTPException(status_code=404, detail="upload not found or expired")
    meta = json.loads(meta_raw)

    # 校验 share 一致
    if meta["share_id"] != share.id:
        raise HTTPException(status_code=400, detail="share mismatch")

    # 调 OBS complete
    parts = [
        {"partNumber": p.part_number, "etag": p.etag}
        for p in body.parts
    ]

    try:
        resp = obs.completeMultipartUpload(
            bucketName=settings.OBS_BUCKET,
            objectKey=meta["obs_key"],
            uploadId=meta["obs_upload_id"],
            parts=parts,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OBS complete failed: {e}")

    if resp.status >= 300:
        raise HTTPException(status_code=500, detail=f"OBS complete failed: {resp.errorCode}")

    # 写 file row
    file_row = File(
        share_id=share.id,
        uploaded_by=meta.get("uploaded_by"),
        original_filename=meta["filename"],
        obs_key=meta["obs_key"],
        size_bytes=meta["size"],
        mime_type=meta["mime"],
        suffix=meta["suffix"],
        sha256=meta["sha256"],
        status="processing",
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)

    # 清理 Redis meta
    redis_client.delete(f"upload:{body.upload_id}")

    return UploadCompleteResponse(file_id=file_row.id, status="processing")