"""Tests — UserGrant CRUD (ticket #12) + viewer/editor role (ticket #13)。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.jwt_utils import create_access_token
from api.models import Share, User, UserGrant
from api.routes_auth import router as auth_router
from api.routes_grants import router as grants_router
from api.routes_shares import router as shares_router
from api.security import hash_password


def _make_user(id_=1, email="alice@example.com", is_admin=False) -> User:
    return User(
        id=id_, email=email,
        password_hash=hash_password("x"),
        display_name="A",
        is_admin=is_admin, is_verified=False,
        created_at=datetime.now(timezone.utc),
    )


def _make_share(id_=1, owner_id=1, slug="aaa11111") -> Share:
    return Share(
        id=id_, owner_id=owner_id, slug=slug, title="X",
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_grant(id_=1, share_id=1, user_id=99, role="viewer") -> UserGrant:
    return UserGrant(
        id=id_, share_id=share_id, user_id=user_id, role=role,
        granted_by=1,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()
    db.delete = AsyncMock()
    db.rollback = AsyncMock()

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    db.execute = AsyncMock(return_value=fake_result)

    async def fake_refresh(obj):
        obj.id = 1
        obj.created_at = datetime.now(timezone.utc)
    db.refresh.side_effect = fake_refresh
    return db


@pytest.fixture
def app(mock_db):
    from api.db import get_session

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(shares_router)
    app.include_router(grants_router)

    async def _override():
        yield mock_db

    app.dependency_overrides[get_session] = _override
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _auth(uid=1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id=uid)}"}


# ── POST /shares/{slug}/grants ──────────────────────────
def test_create_grant_201(client, mock_db):
    """owner 给用户授权 → 201。"""
    share = _make_share()
    target = _make_user(id_=99, email="bob@example.com")

    # 第一次 execute → share,第二次 → target user
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[share, target])
    mock_db.execute = AsyncMock(return_value=fake_result)
    mock_db.get.return_value = _make_user(id_=1)

    resp = client.post(
        "/shares/aaa11111/grants",
        json={"user_email": "bob@example.com", "role": "viewer"},
        headers=_auth(),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "viewer"


def test_create_grant_404_user_not_found(client, mock_db):
    """目标用户不存在 → 404。"""
    share = _make_share()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[share, None])  # target missing
    mock_db.execute = AsyncMock(return_value=fake_result)
    mock_db.get.return_value = _make_user(id_=1)

    resp = client.post(
        "/shares/aaa11111/grants",
        json={"user_email": "nobody@example.com", "role": "viewer"},
        headers=_auth(),
    )
    assert resp.status_code == 404


def test_create_grant_400_cannot_grant_to_owner(client, mock_db):
    """给自己授权 → 400。"""
    share = _make_share(owner_id=1)
    target = _make_user(id_=1, email="alice@example.com")  # same as owner
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[share, target])
    mock_db.execute = AsyncMock(return_value=fake_result)
    mock_db.get.return_value = _make_user(id_=1)

    resp = client.post(
        "/shares/aaa11111/grants",
        json={"user_email": "alice@example.com", "role": "editor"},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_create_grant_409_duplicate(client, mock_db):
    """重复授权 → 409。"""
    share = _make_share()
    target = _make_user(id_=99)

    async def fake_commit():
        from sqlalchemy.exc import IntegrityError
        raise IntegrityError("stmt", params=None, orig=Exception())
    mock_db.commit = fake_commit
    mock_db.rollback = AsyncMock()

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[share, target])
    mock_db.execute = AsyncMock(return_value=fake_result)
    mock_db.get.return_value = _make_user(id_=1)

    resp = client.post(
        "/shares/aaa11111/grants",
        json={"user_email": "bob@example.com", "role": "viewer"},
        headers=_auth(),
    )
    assert resp.status_code == 409


# ── GET /shares/{slug}/grants ───────────────────────────
def test_list_grants(client, mock_db):
    mock_db.get.return_value = _make_user(id_=1)
    grants = [_make_grant(id_=1), _make_grant(id_=2, role="editor")]
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=_make_share())
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=grants)))
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.get("/shares/aaa11111/grants", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[1]["role"] == "editor"


# ── DELETE /shares/{slug}/grants/{user_id} ─────────────
def test_revoke_grant_204(client, mock_db):
    mock_db.get.return_value = _make_user(id_=1)
    grant = _make_grant()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[_make_share(), grant])
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.delete("/shares/aaa11111/grants/99", headers=_auth())
    assert resp.status_code == 204


def test_revoke_grant_404(client, mock_db):
    mock_db.get.return_value = _make_user(id_=1)
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[_make_share(), None])
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.delete("/shares/aaa11111/grants/999", headers=_auth())
    assert resp.status_code == 404


# ── ticket #13: viewer/editor 区分 ────────────────────
def test_get_share_as_viewer_returns_role(client, mock_db):
    """viewer 访问 → 200 + role=viewer。"""
    mock_db.get.return_value = _make_user(id_=99, is_admin=False)
    grant = _make_grant(user_id=99, role="viewer")

    # share lookup → grant lookup
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[_make_share(owner_id=1), grant])
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.get("/shares/aaa11111", headers=_auth(uid=99))
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "viewer"


def test_get_share_as_editor_returns_role(client, mock_db):
    """editor 访问 → 200 + role=editor。"""
    mock_db.get.return_value = _make_user(id_=99)
    grant = _make_grant(user_id=99, role="editor")
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(side_effect=[_make_share(owner_id=1), grant])
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.get("/shares/aaa11111", headers=_auth(uid=99))
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


def test_get_share_owner_role_admin(client, mock_db):
    """owner 访问 → role=None(自己拥有,不需要 grant)。"""
    mock_db.get.return_value = _make_user(id_=1, is_admin=False)
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=_make_share(owner_id=1))
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.get("/shares/aaa11111", headers=_auth(uid=1))
    assert resp.status_code == 200
    assert resp.json()["role"] is None