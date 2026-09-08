"""Tests — guest access via token (ticket #11)。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.models import Share, ShareToken
from api.routes_guest import router as guest_router


def _make_share(slug: str = "aaa11111") -> Share:
    return Share(
        id=1, owner_id=2, slug=slug, title="公开相册",
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_token(
    code: str = "tok12345",
    permission: str = "read",
    expires_at=None,
    revoked_at=None,
) -> ShareToken:
    return ShareToken(
        id=10, share_id=1, token_code=code, permission=permission,
        label=None, public_note=None,
        expires_at=expires_at, revoked_at=revoked_at,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=fake_result)
    return db


@pytest.fixture
def app(mock_db):
    from api.db import get_session
    app = FastAPI()
    app.include_router(guest_router)
    async def _override():
        yield mock_db
    app.dependency_overrides[get_session] = _override
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _setup_share_and_token(mock_db, share, token, *, share_missing=False, token_missing=False):
    results = []
    if share_missing:
        results.append(None)
    else:
        results.append(share)
    if token_missing:
        results.append(None)
    else:
        results.append(token)
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=lambda: results.pop(0))
    mock_db.execute = AsyncMock(return_value=fake_result)


# ── 200 路径 ────────────────────────────────────────────
def test_guest_view_200(client, mock_db):
    """正确 slug + token → 200 + share 详情。"""
    share = _make_share()
    token = _make_token()
    _setup_share_and_token(mock_db, share, token)

    resp = client.get("/s/aaa11111/tok12345")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["slug"] == "aaa11111"
    assert data["title"] == "公开相册"


# ── 401 路径 ────────────────────────────────────────────
def test_guest_view_401_token_missing(client, mock_db):
    """token 不存在 → 401。"""
    share = _make_share()
    _setup_share_and_token(mock_db, share, None, token_missing=True)

    resp = client.get("/s/aaa11111/nonexistent")
    assert resp.status_code == 401


def test_guest_view_401_token_revoked(client, mock_db):
    """token 已撤销 → 401。"""
    share = _make_share()
    token = _make_token(revoked_at=datetime.now(timezone.utc))
    _setup_share_and_token(mock_db, share, token)

    resp = client.get("/s/aaa11111/tok12345")
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower()


def test_guest_view_401_token_expired(client, mock_db):
    """token 过期 → 401。"""
    share = _make_share()
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    token = _make_token(expires_at=expired)
    _setup_share_and_token(mock_db, share, token)

    resp = client.get("/s/aaa11111/tok12345")
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_guest_view_401_token_unexpired(client, mock_db):
    """token 未过期 → 200(确保上面的过期逻辑没误伤)。"""
    share = _make_share()
    future = datetime.now(timezone.utc) + timedelta(days=7)
    token = _make_token(expires_at=future)
    _setup_share_and_token(mock_db, share, token)

    resp = client.get("/s/aaa11111/tok12345")
    assert resp.status_code == 200


# ── 404 ─────────────────────────────────────────────────
def test_guest_view_404_share_missing(client, mock_db):
    """share 不存在 → 404。"""
    _setup_share_and_token(mock_db, None, None, share_missing=True, token_missing=True)

    resp = client.get("/s/notexist/tok12345")
    assert resp.status_code == 404


# ── read / readwrite 都能访问(游客只看不论权限) ─────────
def test_guest_view_readwrite_permission_also_works(client, mock_db):
    """readwrite token 游客也能用(只是不暴露写权限)。"""
    share = _make_share()
    token = _make_token(permission="readwrite")
    _setup_share_and_token(mock_db, share, token)

    resp = client.get("/s/aaa11111/tok12345")
    assert resp.status_code == 200
    # 响应里不暴露 token 的写权限(游客永远是只读视角)
    # 这里只是验证 200,无敏感字段泄露