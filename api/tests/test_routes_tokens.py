"""Tests — token CRUD (ticket #10)。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.jwt_utils import create_access_token
from api.models import Share, ShareToken, User
from api.routes_auth import router as auth_router
from api.routes_shares import router as shares_router
from api.security import hash_password


def _make_user(id_: int = 1, is_admin: bool = False) -> User:
    return User(
        id=id_, email="alice@example.com",
        password_hash=hash_password("x"), display_name="A",
        is_admin=is_admin, is_verified=False,
        created_at=datetime.now(timezone.utc),
    )


def _make_share(id_: int = 1, owner_id: int = 1, slug: str = "aaa11111") -> Share:
    return Share(
        id=id_, owner_id=owner_id, slug=slug, title="X",
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_token(id_: int = 1, share_id: int = 1, code: str = "aB7xK2Lm") -> ShareToken:
    return ShareToken(
        id=id_, share_id=share_id, token_code=code,
        permission="read", label="test", public_note=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()
    db.rollback = AsyncMock()

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    db.execute = AsyncMock(return_value=fake_result)

    async def fake_refresh(obj):
        obj.id = 1
        obj.created_at = datetime.now(timezone.utc)
        if hasattr(obj, "revoked_at"):
            pass  # 默认 None
    db.refresh.side_effect = fake_refresh
    return db


@pytest.fixture
def app(mock_db):
    from api.db import get_session

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(shares_router)

    async def _override():
        yield mock_db

    app.dependency_overrides[get_session] = _override
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _auth(uid: int = 1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id=uid)}"}


def _setup_share_owner(mock_db, owner_id=1):
    mock_db.get.return_value = _make_user(id_=owner_id)
    # execute 返 share(twice for owner lookup in token CRUD)
    share = _make_share(owner_id=owner_id)
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=share)
    mock_db.execute = AsyncMock(return_value=fake_result)


# ── POST /shares/{slug}/tokens ──────────────────────────
def test_create_token_201(client, mock_db):
    """owner 创建 token → 201,8 位 base62 code。"""
    _setup_share_owner(mock_db)
    resp = client.post(
        "/shares/aaa11111/tokens",
        json={"permission": "read", "label": "给小明"},
        headers=_auth(),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["permission"] == "read"
    assert data["label"] == "给小明"


def test_create_token_403_for_non_owner(client, mock_db):
    """非 owner → 403。"""
    mock_db.get.return_value = _make_user(id_=99)
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=_make_share(owner_id=1))
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.post(
        "/shares/aaa11111/tokens",
        json={"permission": "read"},
        headers=_auth(uid=99),
    )
    assert resp.status_code == 403


def test_create_token_401_unauth(client, mock_db):
    resp = client.post(
        "/shares/aaa11111/tokens",
        json={"permission": "read"},
    )
    assert resp.status_code == 401


# ── GET /shares/{slug}/tokens ───────────────────────────
def test_list_tokens(client, mock_db):
    """owner 列出 token。"""
    _setup_share_owner(mock_db)
    # 让 scalars() 返回 2 个
    tokens = [_make_token(id_=1, code="aaaa1111"), _make_token(id_=2, code="bbbb2222")]
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=_make_share())
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=tokens)))
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.get("/shares/aaa11111/tokens", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# ── DELETE /shares/{slug}/tokens/{token_id} ─────────────
def test_revoke_token_204(client, mock_db):
    """撤销 token → 204。"""
    _setup_share_owner(mock_db)
    token = _make_token(id_=42)
    token.revoked_at = None

    # execute 第一次返 share,第二次返 token
    results = [_make_share(), token]
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=lambda: results.pop(0))
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.delete("/shares/aaa11111/tokens/42", headers=_auth())
    assert resp.status_code == 204
    # token.revoked_at 已被设置
    assert token.revoked_at is not None


def test_revoke_token_404(client, mock_db):
    """token 不存在 → 404。"""
    _setup_share_owner(mock_db)
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[_make_share(), None])
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.delete("/shares/aaa11111/tokens/9999", headers=_auth())
    assert resp.status_code == 404