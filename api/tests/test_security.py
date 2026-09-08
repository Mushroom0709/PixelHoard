"""Tests — auth/security 单元(不需 DB)。"""
import pytest

from api.security import hash_password, verify_password


def test_hash_password_not_plain():
    """确保密码不被明文存。"""
    h = hash_password("hello1234")
    assert h != "hello1234"
    assert len(h) > 50  # bcrypt hash 60 字符


def test_hash_password_format():
    """bcrypt hash 以 $2b$ 开头。"""
    h = hash_password("test")
    assert h.startswith(("$2a$", "$2b$", "$2y$"))


def test_hash_password_unique_salt():
    """同一密码两次 hash 应不同(盐)。"""
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


def test_verify_password_correct():
    h = hash_password("correct")
    assert verify_password("correct", h) is True


def test_verify_password_wrong():
    h = hash_password("correct")
    assert verify_password("wrong", h) is False


def test_verify_password_garbage_hash():
    """坏 hash 应安全失败,不应抛。"""
    assert verify_password("anything", "not-a-bcrypt-hash") is False