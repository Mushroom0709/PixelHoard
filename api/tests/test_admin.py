"""Tests — admin 用户管理端点。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.jwt_utils import create_access_token
from api.models import User

NOW = datetime.now(timezone.utc)


def _user(uid=1, admin=False):
    return User(id=uid, email=f"u{uid}@x.com", password_hash="x", display_name=f"u{uid}", is_admin=admin, is_verified=False, created_at=NOW)


@pytest.fixture
def db():
    d = MagicMock()
    d.commit = AsyncMock()
    d.refresh = AsyncMock()
    d.rollback = AsyncMock()
    users = []
    d.users = users

    async def execute(stmt):
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=users[0] if users else None)
        r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=list(users))))
        return r

    d.execute = AsyncMock(side_effect=execute)
    d.get = AsyncMock(side_effect=lambda model, pk: users[0] if users else None)
    return d


@pytest.fixture
def client(db):
    from api.db import get_session
    from api.routes_admin import router

    app = FastAPI()
    app.include_router(router)

    async def _override():
        yield db

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _auth(uid=1):
    return {"Authorization": f"Bearer {create_access_token(user_id=uid)}"}


def test_admin_list_users_403_non_admin(client, db):
    db.users.append(_user(1, admin=False))
    r = client.get("/admin/users", headers=_auth(1))
    assert r.status_code == 403, r.text


def test_admin_list_users_ok(client, db):
    db.users.append(_user(1, admin=True))
    db.users.append(_user(2, admin=False))
    r = client.get("/admin/users", headers=_auth(1))
    assert r.status_code == 200, r.text
    assert len(r.json()) == 2


def test_admin_patch_user_ok(client, db):
    db.users.append(_user(1, admin=True))
    db.users.append(_user(2, admin=False))
    r = client.patch("/admin/users/2", json={"is_admin": True}, headers=_auth(1))
    assert r.status_code == 200, r.text
    assert r.json()["is_admin"] is True


def test_admin_patch_self_forbidden(client, db):
    db.users.append(_user(1, admin=True))
    r = client.patch("/admin/users/1", json={"is_admin": False}, headers=_auth(1))
    assert r.status_code == 400, r.text
