"""Worker — 后台生成衍生档(ticket #17 thumb/preview)。

简单的 polling 模式:
- 每 2s 查 files 表 status='processing' 的 file
- 调 Pillow 生成 thumb (200px) + preview (800px) JPEG
- 上传到 OBS 的 thumb/ + preview/ 路径
- 更新 files.status='ready' + thumb_key + preview_key

OBS client 在函数内延迟 import — 本机测试无 obs 包也能跑纯 Pillow 测试。
"""
from __future__ import annotations

import asyncio
import io
import logging
import sys
from typing import Optional

from sqlalchemy import select, update

from .config import settings
from .db import async_session
from .models import File

logger = logging.getLogger("pixelhoard.worker")
logging.basicConfig(level=logging.INFO)

NATIVE_FORMATS = {"jpg", "jpeg", "png", "webp", "gif", "avif", "heic", "heif"}
THUMB_WIDTH = 200
PREVIEW_WIDTH = 800
JPEG_QUALITY = 85


def _get_obs():
    """延迟 import — 测试可绕开。"""
    from .obs_client import obs
    return obs


def _download_obs(obs_key_str: str) -> bytes:
    """下载 OBS 对象内容。"""
    obs = _get_obs()
    resp = obs.getObject(bucketName=settings.OBS_BUCKET, objectKey=obs_key_str)
    if resp.status >= 300:
        raise RuntimeError(f"OBS getObject failed: {resp.errorCode}")
    return resp.body.buffer


def _upload_obs(obs_key_str: str, data: bytes, content_type: str = "image/jpeg") -> None:
    """上传 bytes 到 OBS。"""
    obs = _get_obs()
    resp = obs.putContent(
        bucketName=settings.OBS_BUCKET,
        objectKey=obs_key_str,
        content=data,
        contentType=content_type,
    )
    if resp.status >= 300:
        raise RuntimeError(f"OBS putContent failed: {resp.errorCode}")


def obs_key_path(share_id: int, sub: str, filename: str) -> str:
    """统一 OBS key(避免 worker 顶层 import obs_client)。"""
    return f"{settings.OBS_WORKDIR}/shares/{share_id}/{sub}/{filename}"


async def _process_image(file_id: int, suffix: str) -> None:
    """处理单张图片 — 生成 thumb + preview。"""
    async with async_session() as db:
        file_row = await db.get(File, file_id)
        if file_row is None or file_row.status != "processing":
            return
        if not file_row.suffix:
            file_row.suffix = suffix
        share_id = file_row.share_id
        obs_raw_key = file_row.obs_key

    # 下载
    try:
        raw_bytes = await asyncio.to_thread(_download_obs, obs_raw_key)
    except Exception as e:
        logger.error(f"download failed for file {file_id}: {e}")
        await _mark_failed(file_id, f"download: {e}")
        return

    # 生成衍生档
    try:
        from PIL import Image

        img = await asyncio.to_thread(Image.open, io.BytesIO(raw_bytes))
        img.load()  # 解码全部,失败抛

        # thumb
        thumb = await asyncio.to_thread(_resize_to_jpeg, img, THUMB_WIDTH)
        thumb_key = obs_key_path(share_id, "thumb", f"{file_id}.jpg")
        await asyncio.to_thread(_upload_obs, thumb_key, thumb, "image/jpeg")

        # preview
        preview = await asyncio.to_thread(_resize_to_jpeg, img, PREVIEW_WIDTH)
        preview_key = obs_key_path(share_id, "preview", f"{file_id}.jpg")
        await asyncio.to_thread(_upload_obs, preview_key, preview, "image/jpeg")

        # 更新 DB
        async with async_session() as db:
            await db.execute(
                update(File)
                .where(File.id == file_id)
                .values(
                    status="ready",
                    thumb_key=thumb_key,
                    preview_key=preview_key,
                    width=img.width,
                    height=img.height,
                    has_exif=bool(img.info.get("exif")),
                )
            )
            await db.commit()
        logger.info(f"file {file_id} ready (suffix={suffix})")
    except Exception as e:
        logger.error(f"process failed for file {file_id}: {e}")
        await _mark_failed(file_id, str(e))


def _resize_to_jpeg(img, target_width: int) -> bytes:
    """Pillow 同步 resize + JPEG 编码。"""
    from PIL import Image

    img = img.copy()
    if img.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA"):
            bg.paste(img, mask=img.split()[-1])
        else:
            bg.paste(img.convert("RGBA"))
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if img.width > target_width:
        ratio = target_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((target_width, new_height), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


async def _mark_failed(file_id: int, reason: str) -> None:
    async with async_session() as db:
        await db.execute(
            update(File)
            .where(File.id == file_id)
            .values(status="failed", failure_reason=reason[:500])
        )
        await db.commit()


async def poll_loop() -> None:
    """每 2s 扫一次 processing 文件。"""
    logger.info("worker started")
    while True:
        try:
            async with async_session() as db:
                stmt = (
                    select(File)
                    .where(File.status == "processing")
                    .order_by(File.created_at)
                    .limit(5)
                )
                result = await db.execute(stmt)
                files = result.scalars().all()
                ids = [(f.id, f.suffix or "") for f in files]

            for fid, suf in ids:
                await _process_image(fid, suf)
        except Exception as e:
            logger.exception(f"poll error: {e}")
        await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        sys.exit(0)