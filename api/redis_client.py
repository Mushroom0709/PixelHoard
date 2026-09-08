"""Redis 客户端 + token 黑名单(token revocation)。

ticket #7: 登出 / refresh / admin 标记。
"""
from __future__ import annotations

from typing import Optional

from .config import settings


class _InMemoryFallback:
    """Redis 不可用时的兜底(单进程内存 dict)。

    多 worker / 多实例时不共享,但 ticket #7 v1 单实例 OK。
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        return True

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def delete(self, key: str) -> int:
        if key in self._store:
            del self._store[key]
            return 1
        return 0

    def exists(self, key: str) -> bool:
        return key in self._store


def _build_client():
    """构造 Redis 客户端,失败返 in-memory fallback。"""
    try:
        import redis  # type: ignore

        kwargs: dict = {
            "host": "redis",
            "port": 6379,
            "db": 0,
            "decode_responses": True,
        }
        if settings.REDIS_PASSWORD:
            kwargs["password"] = settings.REDIS_PASSWORD
        client = redis.Redis(**kwargs)
        client.ping()  # 试连接
        return client
    except Exception:
        return _InMemoryFallback()


redis_client = _build_client()


# ── Token 黑名单 API ─────────────────────────────────────
def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """把 token jti 加入黑名单,ttl_seconds 后自动过期。"""
    redis_client.set(f"blacklist:{jti}", "1", ex=ttl_seconds)


def is_blacklisted(jti: str) -> bool:
    """检查 token jti 是否在黑名单。"""
    return redis_client.exists(f"blacklist:{jti}")