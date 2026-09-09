"""游客访问 API。

设计(2026-09-09 重构):
- 游客分享链接 `/s/{slug}/{token}` 由 nginx 交给 web SPA 渲染页面,
  页面数据从本 router 的 JSON API 拿(token 走 query param):
    GET /api/guest/share/{slug}?token=CODE        → GuestShareView(share + permission)
    GET /api/guest/share/{slug}/files?token=CODE   → FileListOut
    GET /api/guest/files/{file_id}/url?token=CODE&share={slug}&kind=&download= → FileUrlOut
- 旧路径式端点 GET /s/{slug}/{token_code}(返 ShareOut)保留给 API 客户端。

游客能力(既定决策):
- token 唯一凭证,纯无状态;可预览 / 下载 / ZIP 打包 / EXIF(read 与 readwrite 都行)
- readwrite token 的游客也可上传/删除文件(前端据 permission 显示)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .access import get_share_by_slug, resolve_guest_token
from .db import get_session
from .models import File as FileModel
from .models import Share, ShareToken
from .schemas import (
    FileListOut,
    FileOut,
    FileUrlOut,
    GuestShareView,
    ShareOut,
)

router = APIRouter(prefix="/guest", tags=["guest"])
legacy_router = APIRouter(prefix="/s", tags=["guest"])


# ── 游客 API ────────────────────────────────────────────
@router.get("/share/{slug}", response_model=GuestShareView)
async def guest_share_view(
    slug: str,
    token: str,
    db: AsyncSession = Depends(get_session),
) -> GuestShareView:
    """游客取 share 元数据 + token 权限。"""
    share = await get_share_by_slug(slug, db)
    st = await resolve_guest_token(share, token, db)

    out = ShareOut.model_validate({
        "id": share.id,
        "owner_id": share.owner_id,
        "slug": share.slug,
        "title": share.title,
        "description": share.description,
        "is_deleted": share.is_deleted,
        "created_at": share.created_at,
        "updated_at": share.updated_at,
        # role=None 表示 owner — 但游客不是 owner;前端看 permission 字段
        "role": None,
    })
    return GuestShareView(
        share=out,
        permission=st.permission,
        token_public_note=st.public_note,
    )


@router.get("/share/{slug}/files", response_model=FileListOut)
async def guest_share_files(
    slug: str,
    token: str,
    db: AsyncSession = Depends(get_session),
) -> FileListOut:
    """游客列文件(read/readwrite token 均可)。"""
    share = await get_share_by_slug(slug, db)
    await resolve_guest_token(share, token, db)

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


@router.get("/files/{file_id}/url", response_model=FileUrlOut)
async def guest_file_url(
    file_id: int,
    token: str,
    share: str,
    kind: str = "raw",
    download: bool = False,
    db: AsyncSession = Depends(get_session),
) -> FileUrlOut:
    """游客取文件访问 URL(签名 GET,短时效)。"""
    share_row = await get_share_by_slug(share, db)
    await resolve_guest_token(share_row, token, db)

    stmt = select(FileModel).where(
        FileModel.id == file_id,
        FileModel.share_id == share_row.id,
    )
    result = await db.execute(stmt)
    file_row = result.scalar_one_or_none()
    if file_row is None:
        raise HTTPException(status_code=404, detail="file not found")

    from .file_urls import sign_file_url

    return FileUrlOut(**sign_file_url(file_row, kind, download=download))


@router.delete("/files/{file_id}", status_code=204)
async def guest_delete_file(
    file_id: int,
    token: str,
    share: str,
    db: AsyncSession = Depends(get_session),
) -> Response:
    """游客删除文件 — 仅 readwrite token。"""
    share_row = await get_share_by_slug(share, db)
    st = await resolve_guest_token(share_row, token, db)
    if st.permission != "readwrite":
        raise HTTPException(status_code=403, detail="readonly token cannot delete files")

    stmt = select(FileModel).where(
        FileModel.id == file_id,
        FileModel.share_id == share_row.id,
    )
    result = await db.execute(stmt)
    file_row = result.scalar_one_or_none()
    if file_row is None:
        raise HTTPException(status_code=404, detail="file not found")

    from .routes_shares import delete_file_row

    await delete_file_row(file_row, None, db, "guest")
    return Response(status_code=204)


# ── 旧路径式端点(API 客户端用)──────────────────────────
@legacy_router.get("/{slug}/{token_code}", response_model=ShareOut)
async def guest_view(
    slug: str,
    token_code: str,
    db: AsyncSession = Depends(get_session),
) -> ShareOut:
    """游客通过 token 访问 share(元数据;files 走 /api/guest 端点)。"""
    share = await get_share_by_slug(slug, db)
    st = await resolve_guest_token(share, token_code, db)
    # 更新 last_used_at(非关键)
    from datetime import datetime, timezone

    st.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return ShareOut.model_validate(share)
