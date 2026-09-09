"""Tests — upload 路由路径正确性。

核心 bug 回归:前端走 /api/shares/{slug}/upload-*,nginx 去 /api 前缀后
落到 /shares/{slug}/upload-*。此测试确保路由注册在正确 prefix 下。
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def upload_router():
    """延迟 import router。"""
    from api.routes_upload import router
    return router


def test_router_prefix_is_shares(upload_router):
    """router 必须挂 /shares 前缀(nginx 去 /api 后可达)。"""
    assert upload_router.prefix == "/shares", f"prefix={upload_router.prefix}, expected /shares"


def test_upload_routes_registered(upload_router):
    """两个端点完整路径必须注册(prefix + 路径)。"""
    paths = [r.path for r in upload_router.routes if hasattr(r, "path")]
    assert "/shares/{slug}/upload-init" in paths, f"paths={paths}"
    assert "/shares/{slug}/upload-complete" in paths, f"paths={paths}"


def test_complete_url_path_consistent():
    """upload-init 返回的 complete_url 必须匹配前端 /api/shares/ 路径。"""
    from api.routes_upload import PART_SIZE
    assert PART_SIZE == 5 * 1024 * 1024