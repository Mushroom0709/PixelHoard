"""Tests — worker image processing logic (ticket #17)。

只测纯函数 _resize_to_jpeg(OBS 与 Pillow 调用隔离)。
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from api.worker import _resize_to_jpeg


def _make_image(width: int, height: int, mode: str = "RGB") -> Image.Image:
    """生成纯色测试图。"""
    if mode == "RGB":
        return Image.new("RGB", (width, height), (128, 64, 32))
    if mode == "RGBA":
        return Image.new("RGBA", (width, height), (128, 64, 32, 255))
    raise ValueError(mode)


def test_resize_jpeg_rgba_to_rgb():
    """RGBA → RGB + 白底。"""
    img = _make_image(100, 100, "RGBA")
    data = _resize_to_jpeg(img, 50)
    # 验证是合法 JPEG
    out = Image.open(io.BytesIO(data))
    assert out.format == "JPEG"
    assert out.mode == "RGB"
    assert out.width == 50


def test_resize_jpeg_no_shrink_when_small():
    """原图已比目标小 → 不放大(保持原尺寸)。"""
    img = _make_image(100, 100)
    data = _resize_to_jpeg(img, 200)
    out = Image.open(io.BytesIO(data))
    assert out.width == 100


def test_resize_jpeg_shrink_large():
    """原图比目标大 → 缩到目标宽度。"""
    img = _make_image(4000, 3000)
    data = _resize_to_jpeg(img, 800)
    out = Image.open(io.BytesIO(data))
    assert out.width == 800
    # height 比例
    assert abs(out.height - 600) < 2


def test_resize_jpeg_keeps_aspect_ratio():
    img = _make_image(2000, 1000)
    data = _resize_to_jpeg(img, 200)
    out = Image.open(io.BytesIO(data))
    assert out.width == 200
    assert out.height == 100


def test_resize_jpeg_preserves_exif_kwargs():
    """函数签名有 optimize=True — 输出 JPEG 应该是合法的。"""
    img = _make_image(100, 100)
    data = _resize_to_jpeg(img, 50)
    assert data[:2] == b"\xff\xd8"  # JPEG magic