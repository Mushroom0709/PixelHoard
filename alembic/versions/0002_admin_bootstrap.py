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
    """如果 users 表为空,seed 一个 admin 用户。"""
    conn = op.get_bind()

    count = conn.execute(sa.text("SELECT count(*) FROM users")).scalar() or 0
    if count > 0:
        # 已有用户,不重复 seed
        return

    # 从 env 读,缺省值(生产 .env 必填)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@pixelhoard.local").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123!change-me")
    admin_display = os.environ.get("ADMIN_DISPLAY_NAME", "PixelHoard Admin")

    # bcrypt hash(同步,本机用)
    import bcrypt

    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(admin_password.encode("utf-8"), salt).decode("utf-8")

    conn.execute(
        sa.text(
            """
            INSERT INTO users (email, password_hash, display_name, is_admin, is_verified, created_at)
            VALUES (:email, :hash, :display, true, true, NOW())
            """
        ),
        {
            "email": admin_email,
            "hash": hashed,
            "display": admin_display,
        },
    )


def downgrade() -> None:
    """降级 = 删 admin 用户。"""
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email AND is_admin = true"),
        {"email": os.environ.get("ADMIN_EMAIL", "admin@pixelhoard.local").lower().strip()},
    )