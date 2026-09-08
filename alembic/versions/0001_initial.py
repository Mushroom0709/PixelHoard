"""initial schema: 6 tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-09

对应 ADR-0005 schema。6 张表:users, shares, share_tokens, user_grants,
files, audit_logs, quota_configs(实际 7 张,quota 算上)。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_users_email", "users", ["email"])

    # shares
    op.create_table(
        "shares",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_shares_slug", "shares", ["slug"])
    op.create_index("idx_shares_owner", "shares", ["owner_id"])
    op.create_index("idx_shares_deleted", "shares", ["is_deleted", "deleted_at"])

    # share_tokens
    op.create_table(
        "share_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("share_id", sa.BigInteger(), sa.ForeignKey("shares.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_code", sa.Text(), nullable=False, unique=True),
        sa.Column("permission", sa.Text(), nullable=False),
        sa.Column("label", sa.Text()),
        sa.Column("public_note", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("permission IN ('read', 'readwrite')", name="ck_token_permission"),
    )
    op.create_index("idx_tokens_code", "share_tokens", ["token_code"])
    op.create_index("idx_tokens_share", "share_tokens", ["share_id"])
    op.create_index("idx_tokens_active", "share_tokens", ["share_id", "revoked_at", "expires_at"])

    # user_grants
    op.create_table(
        "user_grants",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("share_id", sa.BigInteger(), sa.ForeignKey("shares.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("share_id", "user_id", name="uq_grant_share_user"),
        sa.CheckConstraint("role IN ('viewer', 'editor')", name="ck_grant_role"),
    )
    op.create_index("idx_grants_user", "user_grants", ["user_id"])
    op.create_index("idx_grants_share", "user_grants", ["share_id"])

    # files
    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("share_id", sa.BigInteger(), sa.ForeignKey("shares.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("uploaded_via_token", sa.BigInteger(), sa.ForeignKey("share_tokens.id")),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("obs_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("suffix", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("thumb_key", sa.Text()),
        sa.Column("preview_key", sa.Text()),
        sa.Column("display_key", sa.Text()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("codec", sa.Text()),
        sa.Column("moov_at_head", sa.Boolean()),
        sa.Column("has_exif", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("status IN ('processing', 'ready', 'failed')", name="ck_file_status"),
    )
    op.create_index("idx_files_share", "files", ["share_id", "created_at"])
    op.create_index("idx_files_status", "files", ["status"])
    op.create_index("idx_files_sha256", "files", ["sha256"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("share_id", sa.BigInteger(), sa.ForeignKey("shares.id")),
        sa.Column("token_id", sa.BigInteger(), sa.ForeignKey("share_tokens.id")),
        sa.Column("file_id", sa.BigInteger(), sa.ForeignKey("files.id")),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text()),
        sa.Column("target_id", sa.BigInteger()),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_audit_occurred", "audit_logs", ["occurred_at"])
    op.create_index("idx_audit_user", "audit_logs", ["user_id", "occurred_at"])
    op.create_index("idx_audit_share", "audit_logs", ["share_id", "occurred_at"])

    # quota_configs
    op.create_table(
        "quota_configs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.BigInteger()),
        sa.Column("max_shares", sa.Integer()),
        sa.Column("max_files_per_share", sa.Integer()),
        sa.Column("max_file_size_bytes", sa.BigInteger()),
        sa.Column("max_total_bytes", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("scope IN ('user','share','global')", name="ck_quota_scope"),
    )


def downgrade() -> None:
    # 倒序删除(注意 FK CASCADE 会自动处理)
    op.drop_table("quota_configs")
    op.drop_table("audit_logs")
    op.drop_table("files")
    op.drop_table("user_grants")
    op.drop_table("share_tokens")
    op.drop_table("shares")
    op.drop_table("users")