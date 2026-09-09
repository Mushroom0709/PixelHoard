"""文件访问 URL 签发(登录/游客共用)。

kind 选择与 fallback:
- raw:     原文件(下载 / 视频流 / 原生可显示图片)
- thumb:   200px 缩略图
- preview: 800px 预览
- display: RAW/HEIC 专用 display 兜底档

请求的 kind 不存在时按展示目的 fallback:
- 图片/视频预览: display → preview → raw(native 可看) → 404
- 缩略图: thumb 缺失时 preview(小图够用)→ raw → 404
- 下载: 必须 raw(原画)
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from .config import settings
from .obs_client import obs

# 图片/视频原生浏览器可显示的 kind(RAW/HEIC 等必须 display 档)
DISPLAYABLE_RAW = {"jpg", "jpeg", "png", "webp", "gif", "avif"}
# RAW/HEIC worker 会生成 display 档
NON_DISPLAYABLE_RAW = {"arw", "cr2", "cr3", "nef", "dng", "rw2", "orf", "raf", "heic", "heif"}
VIDEO_SUFFIXES = {"mp4", "mov", "webm", "mkv", "m4v", "avi", "hevc", "ts"}
URL_EXPIRES = 3600  # 1h


def _key_for_kind(file, kind: str) -> Optional[str]:
    attr = {
        "raw": "obs_key",
        "thumb": "thumb_key",
        "preview": "preview_key",
        "display": "display_key",
    }.get(kind)
    if not attr:
        return None
    return getattr(file, attr, None)


def pick_key(file, kind: str) -> tuple[str, str]:
    """按 kind 挑 OBS key,带 fallback。返回 (key, actual_kind)。"""
    suffix = (file.suffix or "").lower()

    if kind == "raw":
        if file.obs_key:
            return file.obs_key, "raw"
        raise HTTPException(status_code=404, detail="raw file missing")

    if kind == "thumb":
        for k in ("thumb", "preview", "raw"):
            key = _key_for_kind(file, k)
            if key:
                return key, k
        raise HTTPException(status_code=404, detail="no preview available")

    if kind in ("preview", "display"):
        want_display = kind == "display"
        # display 只用于 RAW/HEIC;普通图片直接 raw 就够
        if want_display:
            # 先 display_key,没有则按后缀回退到 raw(浏览器原生可看)
            for k in ("display",):
                key = _key_for_kind(file, k)
                if key:
                    return key, k
            if suffix in DISPLAYABLE_RAW and file.obs_key:
                return file.obs_key, "raw"
            # RAW/HEIC 还没生成 display → preview/raw 都没有意义,给 preview 尝试
            for k in ("preview",):
                key = _key_for_kind(file, k)
                if key:
                    return key, k
            raise HTTPException(status_code=404, detail="display not ready yet")
        else:
            for k in ("preview", "display", "raw"):
                key = _key_for_kind(file, k)
                if key and not (k == "raw" and suffix in NON_DISPLAYABLE_RAW):
                    return key, k
            if suffix in DISPLAYABLE_RAW and file.obs_key:
                return file.obs_key, "raw"
            raise HTTPException(status_code=404, detail="preview not available")

    raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")


def sign_file_url(file, kind: str, download: bool = False, expires: int = URL_EXPIRES) -> dict:
    """为 file 签一个访问 URL。返回 {url, kind(actual), filename, expires_in}。"""
    key, actual = pick_key(file, kind)

    # 文件名(URL 编码放 query;OBS 解码后作为 attachment 名)
    filename = file.original_filename or "file"
    query: dict = {}
    if download:
        # 触发浏览器下载而非内联
        query["response-content-disposition"] = (
            f'attachment; filename="{filename}"'
        )

    try:
        resp = obs.createSignedUrl(
            method="GET",
            bucketName=settings.OBS_BUCKET,
            objectKey=key,
            expires=expires,
            queryParams=query or None,
        )
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"OBS sign failed: {e}")

    return {
        "url": resp.signedUrl,
        "kind": actual,
        "filename": filename,
        "expires_in": expires,
    }
