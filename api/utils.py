"""工具函数 — slug 生成、base62 等。"""
import secrets
import string


_BASE62_ALPHABET = string.digits + string.ascii_letters  # 0-9 a-z A-Z
_BASE62_LEN = 8


def random_slug(length: int = _BASE62_LEN) -> str:
    """8 位 base62 短码。"""
    return "".join(secrets.choice(_BASE62_ALPHABET) for _ in range(length))


def normalize_slug(s: str) -> str:
    """normalize user-provided slug to ^[a-z0-9-]{3,32}$。"""
    s = s.lower().strip()
    # 把空格换成 -
    s = s.replace(" ", "-")
    # 移除非允许字符
    s = "".join(c for c in s if c.isalnum() or c == "-")
    # 合并多个 -
    while "--" in s:
        s = s.replace("--", "-")
    s = s.strip("-")
    return s