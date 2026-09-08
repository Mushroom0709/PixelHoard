"""Auth route 集成测试 — 用 in-memory mock 跑 FastAPI。

ticket #6: 验证 /auth/login + /auth/me 行为。
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.models import User
from api.routes_auth import router as auth_router
from api.security import hash_password


def _make_user(id_: int = 1, email: str = "alice@example.com") -> User:
    u = User(
        id=id_,
        email=email,
        password_hash=hash_password("secret123"),
        display_name="Alice",
        is_admin=False,
        is_verified=False,
        created_at=datetime.now(timezone.utc),
    )
    return u


@pytest.fixture
def mock_db():
    """Mock AsyncSession — 用 MagicMock 模拟 get / execute / commit / refresh。"""
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()

    # execute() 返 AsyncResult,需要 chainable 的 scalar_one_or_none()
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
    """构造一个最小 FastAPI app,覆盖 get_session 依赖。"""
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


# ── /auth/register ─────────────────────────────────────
def test_register_201_returns_tokens(client, mock_db):
    """新邮箱 → 201 + access/refresh token。"""

    # execute() 不会在 register 路径里被调用,IntegrityError 也不会触发
    resp = client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "new@example.com"


def test_register_422_on_short_password(client, mock_db):
    """密码太短 → 422(Pydantic 验证)。"""
    resp = client.post(
        "/auth/register",
        json={"email": "t@e.com", "password": "abc"},  # < 8 字符
    )
    assert resp.status_code == 422


# ── /auth/login ────────────────────────────────────────
def test_login_success(client, mock_db):
    """正确邮箱密码 → 200 + tokens。"""
    user = _make_user()
    mock_db.execute.return_value.scalar_one_or_none.return_value = user

    resp = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "alice@example.com"


def test_login_wrong_password(client, mock_db):
    """错密码 → 401。"""
    user = _make_user()
    mock_db.execute.return_value.scalar_one_or_none.return_value = user

    resp = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_login_unknown_email(client, mock_db):
    """未知邮箱 → 401(不区分用户存在 / 错密码,防 enumeration)。"""
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    resp = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


def test_register_409_on_duplicate(client, mock_db):
    """重复邮箱 → 409。"""
    async def fake_commit():
        from sqlalchemy.exc import IntegrityError
        raise IntegrityError("stmt", params=None, orig=Exception("dup"))
    mock_db.commit = fake_commit
    mock_db.rollback = AsyncMock()

    resp = client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


# ── /auth/me ───────────────────────────────────────────
def test_me_with_valid_token(client, mock_db):
    """带正确 token → 200 + user info。"""
    from api.security import hash_password

    user = _make_user(id_=42)
    mock_db.get.return_value = user

    # 生成真实 token
    from api.jwt_utils import create_access_token
    token = create_access_token(user_id=42)

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["id"] == 42


def test_me_without_token_401(client):
    """无 token → 401。"""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_garbage_token_401(client):
    """无效 token → 401。"""
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_me_with_refresh_token_rejected_401(client):
    """refresh token 不能用于 /auth/me(必须 access)。"""
    from api.jwt_utils import create_refresh_token
    token = create_refresh_token(user_id=1)

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401