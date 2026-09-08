"""Pydantic schemas — API 请求/响应模型。

ticket #4: 在 SQLAlchemy models 之上补 DTO 层。
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── User ────────────────────────────────────────────────
class UserCreate(BaseModel):
    """POST /register body."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=100)


class UserOut(BaseModel):
    """用户响应(不含密码哈希)。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: Optional[str] = None
    is_admin: bool = False
    is_verified: bool = False
    created_at: datetime


class UserLogin(BaseModel):
    """POST /login body."""

    email: EmailStr
    password: str


class TokenOut(BaseModel):
    """登录返回(access + refresh)。"""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


# ── Share ───────────────────────────────────────────────
class ShareCreate(BaseModel):
    """POST /shares body。"""

    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    slug: Optional[str] = Field(default=None, max_length=32, pattern=r"^[a-z0-9-]{3,32}$")


class ShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    slug: str
    title: str
    description: Optional[str] = None
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime


# ── Share Token ─────────────────────────────────────────
class ShareTokenCreate(BaseModel):
    """POST /shares/{slug}/tokens body。"""

    permission: Literal["read", "readwrite"]
    label: Optional[str] = Field(default=None, max_length=100)
    public_note: Optional[str] = Field(default=None, max_length=500)
    expires_at: Optional[datetime] = None


class ShareTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    share_id: int
    permission: str
    label: Optional[str] = None
    public_note: Optional[str] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime


# ── UserGrant ───────────────────────────────────────────
class UserGrantCreate(BaseModel):
    """POST /shares/{slug}/grants body。"""

    user_email: EmailStr
    role: Literal["viewer", "editor"]


class UserGrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    share_id: int
    user_id: int
    role: str
    granted_by: int
    created_at: datetime


# ── File ────────────────────────────────────────────────
class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    share_id: int
    original_filename: str
    size_bytes: int
    mime_type: str
    suffix: str
    status: str
    failure_reason: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    codec: Optional[str] = None
    moov_at_head: Optional[bool] = None
    has_exif: Optional[bool] = None
    created_at: datetime


class FileListOut(BaseModel):
    """GET /shares/{slug}/files 响应。"""

    files: list[FileOut]
    total: int


# ── Upload Init ─────────────────────────────────────────
class UploadInitRequest(BaseModel):
    """POST /shares/{slug}/upload-init body。"""

    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    mime_type: str = Field(min_length=1, max_length=100)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]+$")


class UploadInitResponse(BaseModel):
    upload_id: str
    part_urls: list[str]
    part_size: int
    complete_url: str
    expires_in: int  # 秒


# ── Upload Complete ─────────────────────────────────────
class UploadCompleteRequest(BaseModel):
    upload_id: str
    parts: list["UploadedPart"]


class UploadedPart(BaseModel):
    part_number: int = Field(ge=1, le=10000)
    etag: str = Field(min_length=1, max_length=100)
    size: int = Field(gt=0)


class UploadCompleteResponse(BaseModel):
    file_id: int
    status: Literal["processing", "ready", "failed"]


# ── Audit ───────────────────────────────────────────────
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    share_id: Optional[int] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    occurred_at: datetime