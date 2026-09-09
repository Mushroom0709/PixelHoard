"""Admin bootstrap — alembic 第二版 migration,在 users 表为空时自动 seed admin。

启动 admin 用户(从 .env 读 ADMIN_EMAIL + ADMIN_PASSWORD,缺省:
  admin@pixelhoard.local / admin123!change-me)
"""
import os

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_admin_bootstrap"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """始终保证 admin 账号存在(upsert)。"""
    conn = op.get_bind()

    # 从 env 读,缺省值
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@pixelhoard.com").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123!change-me")
    admin_display = os.environ.get("ADMIN_DISPLAY_NAME", "PixelHoard Admin")

    # bcrypt hash
    import bcrypt

    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(admin_password.encode("utf-8"), salt).decode("utf-8")

    # upsert: 如果 admin_email 不存在 → INSERT;存在 → 设为 admin + 重置密码
    conn.execute(
        sa.text(
            """
            INSERT INTO users (email, password_hash, display_name, is_admin, is_verified, created_at)
            VALUES (:email, :hash, :display, true, true, NOW())
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                is_admin = true,
                is_verified = true,
                display_name = EXCLUDED.display_name
            """
        ),
        {
            "email": admin_email,
            "hash": hashed,
            "display": admin_display,
        },
    )


def downgrade() -> None:
    """降级 = 把 admin 降级为普通用户(保留账号)。"""
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE users SET is_admin = false WHERE email = :email"),
        {"email": os.environ.get("ADMIN_EMAIL", "admin@pixelhoard.com").lower().strip()},
    )