"""Tests — JWT 工具(不需 DB)。"""
import time

import pytest

from api.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_token_safe,
)


def test_access_token_decode():
    token = create_access_token(user_id=42)
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_refresh_token_decode():
    token = create_refresh_token(user_id=42)
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"


def test_safe_decode_invalid():
    assert decode_token_safe("not-a-jwt") is None
    assert decode_token_safe("") is None
    assert decode_token_safe("xxx.yyy.zzz") is None


def test_token_extra_claims():
    token = create_access_token(user_id=1, extra={"is_admin": True})
    payload = decode_token(token)
    assert payload["is_admin"] is True


def test_token_expiry_present():
    token = create_access_token(user_id=1)
    payload = decode_token(token)
    assert "exp" in payload
    assert "iat" in payload