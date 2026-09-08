"""Smoke tests — Pydantic schemas + ORM models 字段验证。

ticket #4: import 通过 + 字段测试。

不在 ticket 范围内的事(需要 DB)用 pytest.skip()。
"""
import pytest
from pydantic import ValidationError

from api import models
from api import schemas


# ── models.py import 通过 ─────────────────────────────
def test_models_module_imports():
    """验证 7 个 ORM 模型可 import。"""
    assert hasattr(models, "User")
    assert hasattr(models, "Share")
    assert hasattr(models, "ShareToken")
    assert hasattr(models, "UserGrant")
    assert hasattr(models, "File")
    assert hasattr(models, "AuditLog")
    assert hasattr(models, "QuotaConfig")
    assert hasattr(models, "Base")


# ── schemas.py import 通过 ─────────────────────────────
def test_schemas_module_imports():
    """验证主要 Pydantic schema 可 import。"""
    assert hasattr(schemas, "UserCreate")
    assert hasattr(schemas, "UserOut")
    assert hasattr(schemas, "UserLogin")
    assert hasattr(schemas, "TokenOut")
    assert hasattr(schemas, "ShareCreate")
    assert hasattr(schemas, "ShareOut")
    assert hasattr(schemas, "ShareTokenCreate")
    assert hasattr(schemas, "ShareTokenOut")
    assert hasattr(schemas, "UserGrantCreate")
    assert hasattr(schemas, "UserGrantOut")
    assert hasattr(schemas, "FileOut")
    assert hasattr(schemas, "FileListOut")
    assert hasattr(schemas, "UploadInitRequest")
    assert hasattr(schemas, "UploadInitResponse")
    assert hasattr(schemas, "UploadCompleteRequest")
    assert hasattr(schemas, "UploadedPart")
    assert hasattr(schemas, "UploadCompleteResponse")
    assert hasattr(schemas, "AuditLogOut")


# ── UserCreate 验证 ───────────────────────────────────
def test_user_create_valid():
    u = schemas.UserCreate(email="test@example.com", password="12345678")
    assert u.email == "test@example.com"
    assert len(u.password) == 8


def test_user_create_short_password():
    with pytest.raises(ValidationError):
        schemas.UserCreate(email="t@e.com", password="short")


def test_user_create_invalid_email():
    with pytest.raises(ValidationError):
        schemas.UserCreate(email="not-an-email", password="12345678")


# ── ShareCreate 验证 ───────────────────────────────────
def test_share_create_default_slug_none():
    s = schemas.ShareCreate(title="My Trip")
    assert s.title == "My Trip"
    assert s.slug is None
    assert s.description is None


def test_share_create_with_slug():
    s = schemas.ShareCreate(title="X", slug="my-trip-2024")
    assert s.slug == "my-trip-2024"


def test_share_create_invalid_slug_pattern():
    """slug 必须 ^[a-z0-9-]{3,32}$"""
    with pytest.raises(ValidationError):
        schemas.ShareCreate(title="X", slug="My_Trip")  # 大写+下划线非法
    with pytest.raises(ValidationError):
        schemas.ShareCreate(title="X", slug="ab")  # 太短


# ── ShareTokenCreate 验证 ─────────────────────────────
def test_share_token_create_read():
    t = schemas.ShareTokenCreate(permission="read", label="给小明")
    assert t.permission == "read"


def test_share_token_create_readwrite():
    t = schemas.ShareTokenCreate(permission="readwrite", public_note="可上传可下载")
    assert t.permission == "readwrite"
    assert t.public_note == "可上传可下载"


def test_share_token_create_invalid_permission():
    with pytest.raises(ValidationError):
        schemas.ShareTokenCreate(permission="admin")  # type: ignore[arg-type]


# ── UserGrantCreate 验证 ──────────────────────────────
def test_user_grant_editor():
    g = schemas.UserGrantCreate(user_email="u@e.com", role="editor")
    assert g.role == "editor"


def test_user_grant_invalid_role():
    with pytest.raises(ValidationError):
        schemas.UserGrantCreate(user_email="u@e.com", role="admin")  # type: ignore[arg-type]


# ── UploadInitRequest 验证 ─────────────────────────────
def test_upload_init_valid_sha256():
    sha = "a" * 64
    u = schemas.UploadInitRequest(filename="x.jpg", size=1024, mime_type="image/jpeg", sha256=sha)
    assert u.size == 1024
    assert u.sha256 == sha


def test_upload_init_bad_sha():
    with pytest.raises(ValidationError):
        schemas.UploadInitRequest(filename="x.jpg", size=1024, mime_type="image/jpeg", sha256="tooshort")


# ── ORM model 字段存在性验证 ───────────────────────────
def test_user_model_fields():
    cols = {c.name for c in models.User.__table__.columns}
    assert "id" in cols
    assert "email" in cols
    assert "password_hash" in cols
    assert "is_admin" in cols


def test_share_model_fields():
    cols = {c.name for c in models.Share.__table__.columns}
    assert {"id", "owner_id", "slug", "title", "is_deleted"} <= cols


def test_share_token_model_fields():
    cols = {c.name for c in models.ShareToken.__table__.columns}
    assert {"id", "share_id", "token_code", "permission"} <= cols


def test_file_model_fields():
    cols = {c.name for c in models.File.__table__.columns}
    expected = {
        "id", "share_id", "original_filename", "obs_key", "size_bytes",
        "mime_type", "suffix", "sha256", "status",
    }
    assert expected <= cols