"""Tests — 文件 URL 签发端点(登录)与游客 JSON API(share/files/url/delete)。

覆盖 2026-09-09 补全的"在线浏览/下载"核心功能:
- GET /shares/{slug}/files/{id}/url(owner/viewer/editor;陌生人 403)
- GET /guest/share/{slug}(游客 share+permission;无效 token 401)
- GET /guest/share/{slug}/files(游客列文件)
- GET /guest/files/{id}/url(游客取 URL;readwrite 才能删)
- DELETE /shares/{slug}/files/{id}(viewer 403)
- DELETE /guest/files/{id}(readonly token 403)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.models import File, Share, ShareToken, User, UserGrant

NOW = datetime.now(timezone.utc)


def _user(uid: int = 1, admin: bool = False) -> User:
    return User(id=uid, email=f"u{uid}@x.com", password_hash="x", display_name=f"u{uid}", is_admin=admin)


def _share(owner_id: int = 1) -> Share:
    return Share(id=1, owner_id=owner_id, slug="ab12cd34", title="相册", is_deleted=False, created_at=NOW, updated_at=NOW)


def _file(fid: int = 5, suffix: str = "jpg") -> File:
    return File(
        id=fid, share_id=1, uploaded_by=1, original_filename=f"p.{suffix}",
        obs_key=f"PixelHoard/shares/1/raw/2026/09/09/x_p.{suffix}",
        size_bytes=1024, mime_type="image/jpeg", suffix=suffix,
        sha256="0" * 64, status="ready",
        thumb_key=f"PixelHoard/shares/1/thumb/{fid}.jpg",
        preview_key=f"PixelHoard/shares/1/preview/{fid}.jpg",
        display_key=None,
        created_at=NOW,
    )


def _token(permission: str = "read") -> ShareToken:
    return ShareToken(id=3, share_id=1, token_code="tokabcd1", permission=permission, label=None, public_note=None, created_at=NOW)


class _DB:
    """可编程 fake db:execute 按顺序消费 push 的结果;get 返回当前 user。"""

    def __init__(self):
        self.results: list = []
        self.user: User | None = None
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.delete = AsyncMock()
        self.get = AsyncMock(side_effect=lambda model, pk: self.user)

    def set_user(self, u: User):
        self.user = u

    def push(self, obj):
        self.results.append(obj)

    async def execute(self, stmt):
        # 模拟 select(...).where(...) 链
        r = MagicMock()
        if not self.results:
            r.scalar_one_or_none = MagicMock(return_value=None)
            r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        else:
            first = self.results.pop(0)
            if isinstance(first, list):
                r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=first)))
                r.scalar_one_or_none = MagicMock(return_value=first[0] if first else None)
                r.all = MagicMock(return_value=first)
            else:
                r.scalar_one_or_none = MagicMock(return_value=first)
                r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=first if isinstance(first, list) else [])))
        return r

    def __call__(self, *a, **kw):
        return self


def _auth_header() -> dict:
    from api.jwt_utils import create_access_token
    return {"Authorization": f"Bearer {create_access_token(user_id=1)}"}


@pytest.fixture
def db():
    return _DB()


@pytest.fixture
def client(db):
    """独立 FastAPI(不触发 main.app 的 lifespan DB 探测)。"""
    from api.db import get_session
    from api.routes_auth import router as auth_router
    from api.routes_shares import router as shares_router
    from api.routes_guest import router as guest_router, legacy_router as legacy
    from api.routes_upload import router as upload_router
    from api.routes_delete import router as delete_router
    from api.routes_grants import router as grants_router

    app = FastAPI()
    for r in (auth_router, shares_router, guest_router, legacy, upload_router, delete_router, grants_router):
        app.include_router(r)

    async def _override():
        yield db

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── 登录:文件 URL ───────────────────────────────────────
def test_member_file_url_ok(client, db):
    """owner 请求文件 URL → 200 + 签名 URL(kind fallback raw)。"""
    db.set_user(_user(1))  # share.owner_id=1
    db.push(_share())
    db.push(_file())
    with patch("api.file_urls.sign_file_url", return_value={"url": "https://obs/signed", "kind": "raw", "filename": "p.jpg", "expires_in": 3600}) as mock_sign:
        r = client.get(
            "/shares/ab12cd34/files/5/url?kind=raw",
            headers=_auth_header(),
        )
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://obs/")


def test_member_file_url_403_stranger(client, db):
    """陌生人(无 grant)→ 403。"""
    db.set_user(_user(1))
    db.push(_share(owner_id=99))  # get_share_by_slug
    db.push(None)  # grant 查询 → None
    r = client.get(
        "/shares/ab12cd34/files/5/url?kind=raw",
        headers=_auth_header(),
    )
    assert r.status_code == 403, r.text


def test_guest_share_view_ok(client, db):
    """游客 share 视图 → 200 + permission。"""
    db.push(_share())
    db.push(_token("read"))
    r = client.get("/guest/share/ab12cd34?token=tokabcd1")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["share"]["slug"] == "ab12cd34"
    assert d["permission"] == "read"


def test_guest_share_view_401_bad_token(client, db):
    """游客 token 无效 → 401。"""
    db.push(_share())
    db.push(None)  # token 查询 None
    r = client.get("/guest/share/ab12cd34?token=WRONG")
    assert r.status_code == 401, r.text


def test_guest_files_ok(client, db):
    """游客列文件 → 200。"""
    db.push(_share())
    db.push(_token())
    db.push([_file()])
    r = client.get("/guest/share/ab12cd34/files?token=tokabcd1")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1


def test_guest_file_url_ok(client, db):
    """游客取文件 URL → 200。"""
    db.push(_share())
    db.push(_token())
    db.push(_file())
    with patch("api.file_urls.sign_file_url", return_value={"url": "https://obs/s2", "kind": "raw", "filename": "p.jpg", "expires_in": 3600}):
        r = client.get("/guest/files/5/url?share=ab12cd34&token=tokabcd1&kind=thumb")
    assert r.status_code == 200, r.text
    assert r.json()["url"] == "https://obs/s2"


def test_member_delete_file_viewer_forbidden(client, db):
    """viewer 删文件 → 403。"""
    db.set_user(_user(1))
    db.push(_share(owner_id=99))  # share 属于别人
    grant = MagicMock(spec=UserGrant)
    grant.role = "viewer"
    db.push(grant)
    r = client.delete("/shares/ab12cd34/files/5", headers=_auth_header())
    assert r.status_code == 403, r.text


def test_granted_shares_lists_shared(client, db):
    """GET /shares/granted 返回被授权的 share(带 role)。"""
    db.set_user(_user(1))
    # select(Share, UserGrant.role) → result.all() 行
    share = _share(owner_id=99)
    db.push([(share, "editor")])
    r = client.get("/shares/granted", headers=_auth_header())
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d) == 1
    assert d[0]["slug"] == "ab12cd34"
    assert d[0]["role"] == "editor"


def test_guest_delete_file_readonly_forbidden(client, db):
    """只读游客删文件 → 403。"""
    db.push(_share())
    db.push(_token("read"))
    r = client.delete("/guest/files/5?share=ab12cd34&token=tokabcd1")
    assert r.status_code == 403, r.text


def test_guest_delete_file_readwrite_ok(client, db):
    """读写游客删文件 → 204。"""
    db.push(_share())
    db.push(_token("readwrite"))
    db.push(_file())
    with patch("api.audit.log", new=AsyncMock()) as mock_log, \
         patch("api.obs_client.obs.deleteObject") as mock_del:
        mock_del.return_value = MagicMock(status=204)
        r = client.delete("/guest/files/5?share=ab12cd34&token=tokabcd1")
    assert r.status_code == 204, r.text
    mock_del.assert_called()