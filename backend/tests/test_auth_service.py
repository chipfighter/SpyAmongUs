"""
Unit tests for AuthService (JWT token lifecycle).
"""

import time
from datetime import datetime, timedelta

import jwt
import pytest

from services.auth_service import AuthService


@pytest.fixture
def auth():
    return AuthService()


# ── Token creation ────────────────────────────────────────────────────────

class TestCreateTokens:

    def test_returns_two_strings(self, auth):
        access, refresh = auth.create_tokens("usr_abc", "alice")
        assert isinstance(access, str)
        assert isinstance(refresh, str)
        assert access != refresh

    def test_access_token_payload(self, auth):
        access, _ = auth.create_tokens("usr_abc", "alice")
        payload = jwt.decode(access, auth.secret_key, algorithms=[auth.algorithm])
        assert payload["sub"] == "usr_abc"
        assert payload["username"] == "alice"
        assert payload["type"] == "access"

    def test_refresh_token_payload(self, auth):
        _, refresh = auth.create_tokens("usr_abc", "alice")
        payload = jwt.decode(refresh, auth.secret_key, algorithms=[auth.algorithm])
        assert payload["type"] == "refresh"

    def test_access_token_expiry_is_in_the_future(self, auth):
        access, _ = auth.create_tokens("usr_abc", "alice")
        payload = jwt.decode(access, auth.secret_key, algorithms=[auth.algorithm])
        assert payload["exp"] > time.time()


# ── Token verification ────────────────────────────────────────────────────

class TestVerifyToken:

    def test_valid_access_token(self, auth):
        access, _ = auth.create_tokens("usr_abc", "alice")
        ok, payload = auth.verify_token(access, "access")
        assert ok is True
        assert payload["sub"] == "usr_abc"

    def test_valid_refresh_token(self, auth):
        _, refresh = auth.create_tokens("usr_abc", "alice")
        ok, payload = auth.verify_token(refresh, "refresh")
        assert ok is True

    def test_wrong_token_type_rejected(self, auth):
        access, _ = auth.create_tokens("usr_abc", "alice")
        ok, payload = auth.verify_token(access, "refresh")
        assert ok is False
        assert payload is None

    def test_tampered_token_rejected(self, auth):
        access, _ = auth.create_tokens("usr_abc", "alice")
        ok, _ = auth.verify_token(access + "x", "access")
        assert ok is False

    def test_expired_token_rejected(self, auth):
        expired_payload = {
            "sub": "usr_abc",
            "username": "alice",
            "type": "access",
            "exp": datetime.utcnow() - timedelta(seconds=10),
            "iat": datetime.utcnow() - timedelta(minutes=30),
        }
        token = jwt.encode(expired_payload, auth.secret_key, algorithm=auth.algorithm)
        ok, _ = auth.verify_token(token, "access")
        assert ok is False

    def test_garbage_string_rejected(self, auth):
        ok, _ = auth.verify_token("not.a.jwt", "access")
        assert ok is False


# ── Refresh access token ──────────────────────────────────────────────────

class TestRefreshAccessToken:

    def test_returns_new_access_token(self, auth):
        _, refresh = auth.create_tokens("usr_abc", "alice")
        new_access = auth.refresh_access_token(refresh)
        assert new_access is not None
        ok, payload = auth.verify_token(new_access, "access")
        assert ok is True
        assert payload["sub"] == "usr_abc"

    def test_invalid_refresh_returns_none(self, auth):
        assert auth.refresh_access_token("bad.token") is None

    def test_access_token_cannot_refresh(self, auth):
        access, _ = auth.create_tokens("usr_abc", "alice")
        assert auth.refresh_access_token(access) is None


# ── Rotate refresh token ─────────────────────────────────────────────────

class TestRotateRefreshToken:

    def test_returns_new_refresh_token(self, auth):
        _, refresh = auth.create_tokens("usr_abc", "alice")
        new_refresh = auth.rotate_refresh_token(refresh)
        assert new_refresh is not None
        ok, payload = auth.verify_token(new_refresh, "refresh")
        assert ok is True
        assert payload["sub"] == "usr_abc"

    def test_invalid_token_returns_none(self, auth):
        assert auth.rotate_refresh_token("garbage") is None


# ── Extract user id ───────────────────────────────────────────────────────

class TestGetUserIdFromToken:

    def test_extracts_user_id(self, auth):
        access, _ = auth.create_tokens("usr_xyz", "zara")
        assert auth.get_user_id_from_token(access) == "usr_xyz"

    def test_invalid_token_returns_none(self, auth):
        assert auth.get_user_id_from_token("nope") is None

    def test_wrong_type_returns_none(self, auth):
        _, refresh = auth.create_tokens("usr_xyz", "zara")
        assert auth.get_user_id_from_token(refresh, "access") is None
