"""数据库 — SQLAlchemy 异步引擎(占位,后续 ticket #4 展开 model)。"""
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config import settings


def _make_url(url: str) -> str:
    """postgresql:// → postgresql+asyncpg://。"""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine: AsyncEngine = create_async_engine(
    _make_url(settings.DATABASE_URL),
    echo=False,
    pool_pre_ping=True,
)