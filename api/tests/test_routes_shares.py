"""Tests — slug utils + share routes (ticket #8)。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.jwt_utils import create_access_token
from api.models import Share, User
from api.routes_auth import router as auth_router
from api.routes_shares import router as shares_router
from api.security import hash_password
from api.utils import normalize_slug, random_slug


# ── utils ──────────────────────────────────────────────
def test_random_slug_length():
    s = random_slug()
    assert len(s) == 8


def test_random_slug_alphabet():
    s = random_slug(20)
    allowed = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert set(s) <= allowed


def test_normalize_slug_basic():
    assert normalize_slug("My-Trip") == "my-trip"
    assert normalize_slug("hello world") == "hello-world"
    assert normalize_slug("UPPER lower") == "upper-lower"


def test_normalize_slug_strip_invalid():
    """非允许字符被剔除。"""
    assert normalize_slug("hello!@#world") == "helloworld"
    assert normalize_slug("___test___") == "test"


def test_normalize_slug_collapse_dashes():
    assert normalize_slug("a---b") == "a-b"
    assert normalize_slug("--leading--trailing--") == "leading-trailing"


# ── fixtures ───────────────────────────────────────────
def _make_user(id_: int = 1, is_admin: bool = False) -> User:
    return User(
        id=id_,
        email="alice@example.com",
        password_hash=hash_password("secret"),
        display_name="Alice",
        is_admin=is_admin,
        is_verified=False,
        created_at=datetime.now(timezone.utc),
    )


def _make_share(id_: int = 1, owner_id: int = 1, slug: str = "aaaa1111", title: str = "A") -> Share:
    return Share(
        id=id_,
        owner_id=owner_id,
        slug=slug,
        title=title,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
        obj.updated_at = datetime.now(timezone.utc)
        if hasattr(obj, "is_deleted") and obj.is_deleted is None:
            obj.is_deleted = False
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


def _auth(user_id: int = 1) -> dict:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


# ── POST /shares ───────────────────────────────────────
def test_create_share_201(client, mock_db):
    """新 share → 201,自动 8 位 slug。"""
    mock_db.get.return_value = _make_user()
    resp = client.post(
        "/shares",
        json={"title": "我的旅行相册"},
        headers=_auth(),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == "我的旅行相册"
    assert len(data["slug"]) == 8
    assert data["owner_id"] == 1


def test_create_share_with_custom_slug(client, mock_db):
    """用户给 slug → normalize 后使用。"""
    mock_db.get.return_value = _make_user()
    resp = client.post(
        "/shares",
        json={"title": "X", "slug": "my-trip-2024"},
        headers=_auth(),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["slug"] == "my-trip-2024"


def test_create_share_409_on_slug_collision(client, mock_db):
    """重复 slug → 409。"""

    async def fake_commit():
        from sqlalchemy.exc import IntegrityError
        raise IntegrityError("stmt", params=None, orig=Exception())
    mock_db.commit = fake_commit
    mock_db.rollback = AsyncMock()
    mock_db.get.return_value = _make_user()

    resp = client.post(
        "/shares",
        json={"title": "X", "slug": "taken-slug"},
        headers=_auth(),
    )
    assert resp.status_code == 409


def test_create_share_401_without_auth(client, mock_db):
    """无 token → 401。"""
    resp = client.post("/shares", json={"title": "X"})
    assert resp.status_code == 401


# ── GET /shares/me ─────────────────────────────────────
def test_list_my_shares(client, mock_db):
    """列自己创建的 share。"""
    mock_db.get.return_value = _make_user()

    # 让 execute 返回 2 个 share
    shares = [
        _make_share(id_=1, slug="aaaa1111", title="A"),
        _make_share(id_=2, slug="bbbb2222", title="B"),
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = shares

    resp = client.get("/shares/me", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "A"


# ── GET /shares/{slug} ─────────────────────────────────
def test_get_share_as_owner(client, mock_db):
    """owner 看自己的 share。"""
    mock_db.get.return_value = _make_user(id_=1, is_admin=False)
    share = _make_share(id_=1, owner_id=1, slug="myslug", title="X")
    mock_db.execute.return_value.scalar_one_or_none.return_value = share

    resp = client.get("/shares/myslug", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["slug"] == "myslug"


def test_get_share_as_admin(client, mock_db):
    """admin 看任何 share。"""
    mock_db.get.return_value = _make_user(id_=99, is_admin=True)
    share = _make_share(id_=1, owner_id=1, slug="others", title="X")
    mock_db.execute.return_value.scalar_one_or_none.return_value = share

    resp = client.get("/shares/others", headers=_auth())
    assert resp.status_code == 200


def test_get_share_403_for_non_owner(client, mock_db):
    """非 owner 非 admin → 403。"""
    mock_db.get.return_value = _make_user(id_=99, is_admin=False)
    share = _make_share(id_=1, owner_id=1, slug="others", title="X")
    mock_db.execute.return_value.scalar_one_or_none.return_value = share

    resp = client.get("/shares/others", headers=_auth())
    assert resp.status_code == 403


def test_get_share_404(client, mock_db):
    """不存在的 slug → 404。"""
    mock_db.get.return_value = _make_user()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    resp = client.get("/shares/notexist", headers=_auth())
    assert resp.status_code == 404

# ── ticket #15: 文件列表 ──────────────────────────────
from api.models import File as _FileModel
def test_list_files_empty(client, mock_db):
    """空 share → files=[], total=0"""
    mock_db.get.return_value = _make_user()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=_make_share())
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.get("/shares/aaa11111/files", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert data["files"] == []
    assert data["total"] == 0


def test_list_files_returns_files(client, mock_db):
    """返回 share 内文件列表。"""
    mock_db.get.return_value = _make_user()
    fake_file = _FileModel(
        id=1, share_id=1, original_filename="test.jpg", obs_key="x",
        size_bytes=12345, mime_type="image/jpeg", suffix="jpg",
        sha256="a" * 64, status="ready",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=_make_share())
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[fake_file])))
    mock_db.execute = AsyncMock(return_value=fake_result)

    resp = client.get("/shares/aaa11111/files", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["files"][0]["original_filename"] == "test.jpg"
