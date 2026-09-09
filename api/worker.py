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

NATIVE_FORMATS = {"jpg", "jpeg", "png", "webp", "gif", "avif"}
THUMB_WIDTH = 200
PREVIEW_WIDTH = 800
JPEG_QUALITY = 85
VIDEO_FORMATS = {"mp4", "mov", "webm", "mkv", "avi", "m4v", "hevc"}
RAW_FORMATS = {"arw", "cr2", "cr3", "nef", "dng", "rw2", "orf", "raf"}
# HEIC/HEIF — 浏览器(除 iOS)不能原生显示,需要 display 兜底档
HEIC_FORMATS = {"heic", "heif"}


def _get_obs():
    """延迟 import — 测试可绕开。"""
    from .obs_client import obs
    return obs


def _download_obs(obs_key_str: str) -> bytes:
    """下载 OBS 对象内容。"""
    obs = _get_obs()
    # 必须 loadStreamInMemory=True — 否则 body.buffer 是 None(stream 模式)!
    resp = obs.getObject(
        bucketName=settings.OBS_BUCKET,
        objectKey=obs_key_str,
        loadStreamInMemory=True,
    )
    if resp.status >= 300:
        raise RuntimeError(f"OBS getObject failed: {resp.errorCode}")
    return resp.body.buffer


def _upload_obs(obs_key_str: str, data: bytes, content_type: str = "image/jpeg") -> None:
    """上传 bytes 到 OBS。"""
    obs = _get_obs()
    from obs import PutObjectHeader

    # 注意:putContent 没有 contentType 关键字参数,
    # content-type 必须走 PutObjectHeader(headers)!
    resp = obs.putContent(
        bucketName=settings.OBS_BUCKET,
        objectKey=obs_key_str,
        content=data,
        headers=PutObjectHeader(contentType=content_type),
    )
    if resp.status >= 300:
        raise RuntimeError(f"OBS putContent failed: {resp.errorCode}")


def obs_key_path(share_id: int, sub: str, filename: str) -> str:
    """统一 OBS key(避免 worker 顶层 import obs_client)。"""
    return f"{settings.OBS_WORKDIR}/shares/{share_id}/{sub}/{filename}"


async def _process_file(file_id: int) -> None:
    """处理单文件 — 路由到 image / video / arw 处理。"""
    async with async_session() as db:
        file_row = await db.get(File, file_id)
        if file_row is None or file_row.status != "processing":
            return
        share_id = file_row.share_id
        obs_raw_key = file_row.obs_key
        suffix = file_row.suffix or ""

    try:
        if _is_video(suffix):
            await _process_video(file_id, share_id, obs_raw_key)
            return
        if _is_raw(suffix):
            await _process_arw_file(file_id, share_id, obs_raw_key)
            return
        if _is_heic(suffix):
            await _process_heic_file(file_id, share_id, obs_raw_key)
            return
        if _is_image(suffix):
            await _process_image(file_id, share_id, obs_raw_key)
            return
        # 其他任意文件(文档/压缩包等)— 无需衍生档,直接 ready
        await _mark_ready_plain(file_id)
    except Exception as e:
        logger.error(f"process failed for file {file_id}: {e}")
        await _mark_failed(file_id, str(e))


async def _process_video(file_id: int, share_id: int, obs_raw_key: str) -> None:
    """处理视频:ffprobe + 抽帧 + 写 width/height/duration/codec/moov_at_head。"""
    info = await asyncio.to_thread(_probe_video, obs_raw_key)

    # 抽第一帧(原尺寸 JPEG)
    frame_jpeg, w, h, dur = await asyncio.to_thread(_generate_thumb_from_video, obs_raw_key)

    # 生成真正的 thumb(200) + preview(800),避免 4K 帧原尺寸存两份
    import io as _io
    from PIL import Image as _PIL

    _img = _PIL.open(_io.BytesIO(frame_jpeg))
    thumb_jpeg = await asyncio.to_thread(_resize_to_jpeg, _img, THUMB_WIDTH)
    preview_jpeg = await asyncio.to_thread(_resize_to_jpeg, _img, PREVIEW_WIDTH)

    thumb_key = obs_key_path(share_id, "thumb", f"{file_id}.jpg")
    preview_key = obs_key_path(share_id, "preview", f"{file_id}.jpg")
    await asyncio.to_thread(_upload_obs, thumb_key, thumb_jpeg, "image/jpeg")
    await asyncio.to_thread(_upload_obs, preview_key, preview_jpeg, "image/jpeg")

    async with async_session() as db:
        await db.execute(
            update(File)
            .where(File.id == file_id)
            .values(
                status="ready",
                thumb_key=thumb_key,
                preview_key=preview_key,
                width=info["width"] or w,
                height=info["height"] or h,
                duration_seconds=info["duration_seconds"],
                codec=info["codec"],
                moov_at_head=info["moov_at_head"],
            )
        )
        await db.commit()
    logger.info(f"video file {file_id} ready (moov_at_head={info['moov_at_head']})")


async def _process_arw_file(file_id: int, share_id: int, obs_raw_key: str) -> None:
    """处理 ARW/RAW:rawpy 解码 + 生成 thumb + preview。"""
    raw = await asyncio.to_thread(_download_obs, obs_raw_key)
    display_jpeg, w, h = await asyncio.to_thread(_process_arw, raw)

    # thumb 用 display 缩到 200
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(display_jpeg))
    thumb_jpeg = await asyncio.to_thread(_resize_to_jpeg, img, THUMB_WIDTH)

    # display 档 = preview 尺寸
    preview_jpeg = display_jpeg  # 已经是 800 宽

    thumb_key = obs_key_path(share_id, "thumb", f"{file_id}.jpg")
    preview_key = obs_key_path(share_id, "preview", f"{file_id}.jpg")
    display_key = obs_key_path(share_id, "display", f"{file_id}.jpg")
    await asyncio.to_thread(_upload_obs, thumb_key, thumb_jpeg, "image/jpeg")
    await asyncio.to_thread(_upload_obs, preview_key, preview_jpeg, "image/jpeg")
    await asyncio.to_thread(_upload_obs, display_key, preview_jpeg, "image/jpeg")

    async with async_session() as db:
        await db.execute(
            update(File)
            .where(File.id == file_id)
            .values(
                status="ready",
                thumb_key=thumb_key,
                preview_key=preview_key,
                display_key=display_key,
                width=w,
                height=h,
                has_exif=True,  # RAW 通常有
            )
        )
        await db.commit()
    logger.info(f"raw file {file_id} ready")


async def _process_image(file_id: int, share_id: int, obs_raw_key: str) -> None:
    """处理单张图片 — 生成 thumb + preview。"""
    # 下载
    try:
        raw_bytes = await asyncio.to_thread(_download_obs, obs_raw_key)
    except Exception as e:
        logger.error(f"download failed for file {file_id}: {e}")
        await _mark_failed(file_id, f"download: {e}")
        return

    try:
        from PIL import Image

        img = await asyncio.to_thread(Image.open, io.BytesIO(raw_bytes))
        img.load()  # 解码全部,失败抛

        thumb = await asyncio.to_thread(_resize_to_jpeg, img, THUMB_WIDTH)
        thumb_key = obs_key_path(share_id, "thumb", f"{file_id}.jpg")
        await asyncio.to_thread(_upload_obs, thumb_key, thumb, "image/jpeg")

        preview = await asyncio.to_thread(_resize_to_jpeg, img, PREVIEW_WIDTH)
        preview_key = obs_key_path(share_id, "preview", f"{file_id}.jpg")
        await asyncio.to_thread(_upload_obs, preview_key, preview, "image/jpeg")

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
        logger.info(f"file {file_id} ready")
    except Exception as e:
        logger.error(f"process failed for file {file_id}: {e}")
        await _mark_failed(file_id, str(e))


def _is_native(suffix: str) -> bool:
    return suffix.lower() in NATIVE_FORMATS


def _is_video(suffix: str) -> bool:
    return suffix.lower() in VIDEO_FORMATS


def _is_image(suffix: str) -> bool:
    return suffix.lower() in NATIVE_FORMATS or suffix.lower() in RAW_FORMATS


def _is_raw(suffix: str) -> bool:
    return suffix.lower() in RAW_FORMATS


async def _mark_ready_plain(file_id: int) -> None:
    """非媒体文件:直接 ready,无衍生档。"""
    async with async_session() as db:
        await db.execute(
            update(File)
            .where(File.id == file_id)
            .values(status="ready")
        )
        await db.commit()
    logger.info(f"plain file {file_id} ready (no derivates)")


def _is_heic(suffix: str) -> bool:
    return suffix.lower() in HEIC_FORMATS


def _decode_heic_to_jpeg(raw_bytes: bytes) -> tuple[bytes, int, int]:
    """HEIC/HEIF 解码 → preview JPEG。需要 pillow-heif。"""
    import io

    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    img = Image.open(io.BytesIO(raw_bytes))
    img.load()  # 解码,坏文件抛
    return _resize_to_jpeg(img, PREVIEW_WIDTH), img.width, img.height


async def _process_heic_file(file_id: int, share_id: int, obs_raw_key: str) -> None:
    """处理 HEIC/HEIF:解码 + thumb/preview/display 三档。"""
    raw = await asyncio.to_thread(_download_obs, obs_raw_key)
    display_jpeg, w, h = await asyncio.to_thread(_decode_heic_to_jpeg, raw)

    from PIL import Image
    import io

    img = Image.open(io.BytesIO(display_jpeg))
    thumb_jpeg = await asyncio.to_thread(_resize_to_jpeg, img, THUMB_WIDTH)

    thumb_key = obs_key_path(share_id, "thumb", f"{file_id}.jpg")
    preview_key = obs_key_path(share_id, "preview", f"{file_id}.jpg")
    display_key = obs_key_path(share_id, "display", f"{file_id}.jpg")
    await asyncio.to_thread(_upload_obs, thumb_key, thumb_jpeg, "image/jpeg")
    await asyncio.to_thread(_upload_obs, preview_key, display_jpeg, "image/jpeg")
    await asyncio.to_thread(_upload_obs, display_key, display_jpeg, "image/jpeg")

    async with async_session() as db:
        await db.execute(
            update(File)
            .where(File.id == file_id)
            .values(
                status="ready",
                thumb_key=thumb_key,
                preview_key=preview_key,
                display_key=display_key,
                width=w,
                height=h,
                has_exif=True,
            )
        )
        await db.commit()
    logger.info(f"heic file {file_id} ready")


def _process_arw(raw_bytes: bytes) -> tuple[bytes, int, int]:
    """ARW 解码 — 用 rawpy 返回 (jpeg_bytes, width, height)。"""
    import io

    import rawpy

    with rawpy.imread(io.BytesIO(raw_bytes)) as raw:
        rgb = raw.postprocess(
            use_auto_wb=True,
            no_auto_bright=False,
            output_bps=8,
        )
    from PIL import Image

    img = Image.fromarray(rgb)
    return _resize_to_jpeg(img, PREVIEW_WIDTH) + b"", img.width, img.height


def _probe_video(obs_key_str: str) -> dict:
    """用 ffprobe 探测视频信息(尺寸/时长/编码/moov 位置)。"""
    import json
    import subprocess
    import tempfile

    # 下载到本地临时文件 ffprobe 才能处理(也可以 stream 但实现复杂)
    raw = _download_obs(obs_key_str)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries",
                "stream=width,height,codec_name,codec_type:format=duration:format_tags=major_brand",
                "-print_format", "json",
                "-i", tmp_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        info = json.loads(result.stdout)

        # 检查 moov 在前头(粗略:扫描前 1MB 是否含 'moov' atom)
        moov_at_head = _check_moov_at_head(tmp_path)

        # 找视频流
        width = height = None
        codec = None
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                width = stream.get("width")
                height = stream.get("height")
                codec = stream.get("codec_name")
                break
        return {
            "width": width,
            "height": height,
            "duration_seconds": float(info.get("format", {}).get("duration", 0) or 0),
            "codec": codec,
            "moov_at_head": moov_at_head,
        }
    finally:
        import os
        os.unlink(tmp_path)


def _check_moov_at_head(local_path: str, head_bytes: int = 1024 * 1024) -> bool:
    """粗略:文件前 1MB 包含 'moov' 原子。"""
    with open(local_path, "rb") as f:
        head = f.read(head_bytes)
    return b"moov" in head


def _generate_thumb_from_video(obs_key_str: str) -> tuple[bytes, int, int, float]:
    """从视频中抽第一帧作为 thumb。"""
    import subprocess
    import tempfile

    raw = _download_obs(obs_key_str)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(raw)
        src_path = tmp.name
    out_path = src_path + ".jpg"

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "00:00:00.5", "-i", src_path,
                "-frames:v", "1", "-q:v", "3", out_path,
            ],
            capture_output=True, timeout=30,
        )
        with open(out_path, "rb") as f:
            jpeg_data = f.read()
        from PIL import Image
        img = Image.open(out_path)
        return jpeg_data, img.width, img.height, 0.5
    finally:
        import os
        os.unlink(src_path)
        if os.path.exists(out_path):
            os.unlink(out_path)


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
                await _process_file(fid)
        except Exception as e:
            logger.exception(f"poll error: {e}")
        await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        sys.exit(0)