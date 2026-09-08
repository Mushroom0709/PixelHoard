"""Tests — logout / refresh / admin (ticket #7)。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.jwt_utils import create_access_token, create_refresh_token
from api.models import User
from api.redis_client import _InMemoryFallback  # noqa
from api.routes_auth import router as auth_router
from api.security import hash_password


# 用 in-memory redis(避免真 Redis 依赖)— 替换全局 client
from api import redis_client as rc_module

rc_module.redis_client = _InMemoryFallback()


def _make_user(id_: int = 1, is_admin: bool = False) -> User:
    u = User(
        id=id_,
        email="alice@example.com",
        password_hash=hash_password("secret123"),
        display_name="Alice",
        is_admin=is_admin,
        is_verified=False,
        created_at=datetime.now(timezone.utc),
    )
    return u


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()
    db.rollback = AsyncMock()

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=fake_result)

    async def fake_refresh(obj):
        obj.id = 1
        obj.created_at = datetime.now(timezone.utc)
        obj.is_admin = False
        obj.is_verified = False
    db.refresh.side_effect = fake_refresh
    return db


@pytest.fixture
def app(mock_db):
    from api.db import get_session

    app = FastAPI()
    app.include_router(auth_router)

    async def _override():
        yield mock_db

    app.dependency_overrides[get_session] = _override
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ── logout ──────────────────────────────────────────────
def test_logout_with_token_blacklists(client, mock_db):
    """带 token logout → ok,黑名单生效。"""
    user = _make_user()
    mock_db.get.return_value = user
    token = create_access_token(user_id=1)

    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_logout_without_token_401(client):
    """无 token → 401。"""
    resp = client.post("/auth/logout")
    assert resp.status_code == 401


def test_logged_out_token_rejected_on_me(client, mock_db):
    """登出后再访问 /me → 401(token 在黑名单)。"""
    user = _make_user()
    mock_db.get.return_value = user
    token = create_access_token(user_id=1)

    # 先 logout
    client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    # 再访问 /me
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ── refresh ─────────────────────────────────────────────
def test_refresh_returns_new_tokens(client, mock_db):
    """refresh token → 新 access + refresh。"""
    user = _make_user()
    mock_db.get.return_value = user
    refresh_token = create_refresh_token(user_id=1)

    resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # 新 refresh 应与旧的不同
    assert data["refresh_token"] != refresh_token


def test_refresh_with_access_token_rejected_401(client, mock_db):
    """用 access token 当 refresh → 401。"""
    user = _make_user()
    mock_db.get.return_value = user
    access_token = create_access_token(user_id=1)

    resp = client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


def test_refresh_with_garbage_401(client):
    """无效 token → 401。"""
    resp = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert resp.status_code == 401


def test_refresh_after_revoke_401(client, mock_db):
    """被 revoke 的 refresh → 401。"""
    user = _make_user()
    mock_db.get.return_value = user
    refresh_token = create_refresh_token(user_id=1)

    # 用 refresh 一次(会自动 rotate,把旧的加黑名单)
    r1 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r1.status_code == 200

    # 再用同一个旧 refresh → 401
    r2 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 401


# ── me/role (admin 标记) ────────────────────────────────
def test_me_role_returns_admin_flag(client, mock_db):
    """GET /me/role 返回 is_admin。"""
    user = _make_user(is_admin=True)
    mock_db.get.return_value = user
    token = create_access_token(user_id=1)

    resp = client.get("/auth/me/role", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_admin"] is True
    assert data["email"] == "alice@example.com"


def test_me_role_non_admin(client, mock_db):
    """非 admin 用户 is_admin=false。"""
    user = _make_user(is_admin=False)
    mock_db.get.return_value = user
    token = create_access_token(user_id=1)

    resp = client.get("/auth/me/role", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False