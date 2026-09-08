"""数据库 — SQLAlchemy 异步引擎 + ORM Base。"""
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    """ORM 基类(供 models + alembic 引用)。"""
    pass


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

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖 — 异步生成器。"""
    async with async_session() as s:
        yield s