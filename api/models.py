"""SQLAlchemy ORM models — 6 张表对应 ADR-0005 schema。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Real,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── 用户 ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("idx_users_email", "email"),)


# ── 分享 ──────────────────────────────────────────────
class Share(Base):
    __tablename__ = "shares"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped[User] = relationship(back_populates="shares")

    __table_args__ = (
        Index("idx_shares_slug", "slug"),
        Index("idx_shares_owner", "owner_id"),
        Index("idx_shares_deleted", "is_deleted", "deleted_at"),
    )


# User ↔ Share 反向引用
User.shares = relationship("Share", back_populates="owner", cascade="all, delete-orphan")


# ── Share Tokens ───────────────────────────────────────
class ShareToken(Base):
    __tablename__ = "share_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    share_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shares.id", ondelete="CASCADE"), nullable=False
    )
    token_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    permission: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(Text)
    public_note: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    share: Mapped[Share] = relationship()

    __table_args__ = (
        CheckConstraint("permission IN ('read', 'readwrite')", name="ck_token_permission"),
        Index("idx_tokens_code", "token_code"),
        Index("idx_tokens_share", "share_id"),
        Index("idx_tokens_active", "share_id", "revoked_at", "expires_at"),
    )


# ── User Grants ────────────────────────────────────────
class UserGrant(Base):
    __tablename__ = "user_grants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    share_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shares.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    granted_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    share: Mapped[Share] = relationship()
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    granter: Mapped[User] = relationship(foreign_keys=[granted_by])

    __table_args__ = (
        UniqueConstraint("share_id", "user_id", name="uq_grant_share_user"),
        CheckConstraint("role IN ('viewer', 'editor')", name="ck_grant_role"),
        Index("idx_grants_user", "user_id"),
        Index("idx_grants_share", "share_id"),
    )


# ── Files ──────────────────────────────────────────────
class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    share_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shares.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    uploaded_via_token: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("share_tokens.id")
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    obs_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    suffix: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    thumb_key: Mapped[Optional[str]] = mapped_column(Text)
    preview_key: Mapped[Optional[str]] = mapped_column(Text)
    display_key: Mapped[Optional[str]] = mapped_column(Text)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Real)
    codec: Mapped[Optional[str]] = mapped_column(Text)
    moov_at_head: Mapped[Optional[bool]] = mapped_column(Boolean)
    has_exif: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    share: Mapped[Share] = relationship()
    uploader: Mapped[Optional[User]] = relationship(foreign_keys=[uploaded_by])

    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name="ck_file_status"
        ),
        Index("idx_files_share", "share_id", "created_at"),
        Index("idx_files_status", "status"),
        Index("idx_files_sha256", "sha256"),
    )


# ── Audit Logs ─────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    share_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("shares.id")
    )
    token_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("share_tokens.id")
    )
    file_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("files.id")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(Text)
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_audit_occurred", "occurred_at"),
        Index("idx_audit_user", "user_id", "occurred_at"),
        Index("idx_audit_share", "share_id", "occurred_at"),
    )


# ── Quota Configs ──────────────────────────────────────
class QuotaConfig(Base):
    __tablename__ = "quota_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    scope_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    max_shares: Mapped[Optional[int]] = mapped_column(Integer)
    max_files_per_share: Mapped[Optional[int]] = mapped_column(Integer)
    max_file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    max_total_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (CheckConstraint("scope IN ('user','share','global')", name="ck_quota_scope"),)