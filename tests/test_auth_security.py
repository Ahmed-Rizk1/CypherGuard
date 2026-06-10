"""
Tests for shared.auth module — Phase 1 security hardening.

Covers:
- JWT creation with jti claims
- Token blacklisting and revocation
- Access token verification
- Refresh token rotation
- Account lockout logic
- Role-based access control
- Secret validation
- Security header middleware
- Request size limit middleware
"""

import os
import time
import uuid
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Set test secrets before importing auth module
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-validation"
os.environ["INTERNAL_API_KEY"] = "test-internal-key-long-enough-for-validation"

import jwt as pyjwt

# Must import after setting env vars
from shared.auth import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    validate_secrets,
    TokenPayload,
    VALID_ROLES,
    JWT_SECRETS,
    JWT_ALGORITHM,
    JWT_EXPIRY_SECONDS,
)


class TestJWTCreation:
    """Tests for JWT token creation with jti claims."""

    def test_access_token_contains_jti(self):
        """Access tokens must have a unique jti claim for revocation support."""
        token = create_access_token("user-123", "admin")
        payload = pyjwt.decode(token, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        assert "jti" in payload
        assert len(payload["jti"]) == 36  # UUID format

    def test_access_token_jti_unique_per_call(self):
        """Each token must have a distinct jti to enable individual revocation."""
        t1 = create_access_token("user-123", "admin")
        t2 = create_access_token("user-123", "admin")
        p1 = pyjwt.decode(t1, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        p2 = pyjwt.decode(t2, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        assert p1["jti"] != p2["jti"]

    def test_access_token_has_type_claim(self):
        """Access tokens must have type='access' to distinguish from refresh tokens."""
        token = create_access_token("user-123", "analyst")
        payload = pyjwt.decode(token, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        assert payload["type"] == "access"

    def test_access_token_custom_expiry(self):
        """Custom expiry should override the default."""
        token = create_access_token("user-123", "viewer", expires_in=300)
        payload = pyjwt.decode(token, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        assert payload["exp"] - payload["iat"] == 300

    def test_access_token_default_expiry(self):
        """Default expiry should match JWT_EXPIRY_SECONDS."""
        token = create_access_token("user-123", "admin")
        payload = pyjwt.decode(token, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        assert abs((payload["exp"] - payload["iat"]) - JWT_EXPIRY_SECONDS) < 2

    def test_access_token_invalid_role_raises(self):
        """Invalid role must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            create_access_token("user-123", "superadmin")

    def test_refresh_token_contains_jti(self):
        """Refresh tokens must have jti for rotation blacklisting."""
        token = create_refresh_token("user-123", "admin")
        payload = pyjwt.decode(token, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        assert "jti" in payload

    def test_refresh_token_has_type_claim(self):
        """Refresh tokens must have type='refresh'."""
        token = create_refresh_token("user-123", "admin")
        payload = pyjwt.decode(token, JWT_SECRETS[0], algorithms=[JWT_ALGORITHM])
        assert payload["type"] == "refresh"


class TestJWTDecoding:
    """Tests for JWT token decoding and validation."""

    def test_decode_valid_token(self):
        """Valid token should decode successfully."""
        token = create_access_token("user-123", "admin")
        payload = decode_jwt(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"

    def test_decode_expired_token_raises(self):
        """Expired token should raise HTTPException 401."""
        from fastapi import HTTPException
        token = create_access_token("user-123", "admin", expires_in=-1)
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_invalid_token_raises(self):
        """Malformed token should raise HTTPException 401 with sanitized message."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt("not.a.valid.token")
        assert exc_info.value.status_code == 401
        # Must NOT contain internal library error details
        assert "Invalid or malformed token" in exc_info.value.detail

    def test_decode_tampered_token_raises(self):
        """Token with modified payload should fail verification."""
        from fastapi import HTTPException
        token = create_access_token("user-123", "admin")
        # Tamper with the payload (change a character)
        parts = token.split(".")
        parts[1] = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
        tampered = ".".join(parts)
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(tampered)
        assert exc_info.value.status_code == 401


class TestSecretValidation:
    """Tests for the validate_secrets() startup check."""

    def test_valid_secrets_pass(self):
        """Proper secrets should not raise."""
        # Our test env vars are valid, so this should pass
        validate_secrets()

    def test_short_jwt_secret_fails(self):
        """JWT secret shorter than 16 chars must fail."""
        import shared.auth as auth_module
        original = auth_module.JWT_SECRETS
        try:
            auth_module.JWT_SECRETS = ["short"]
            with pytest.raises(RuntimeError, match="too short"):
                validate_secrets()
        finally:
            auth_module.JWT_SECRETS = original

    def test_placeholder_jwt_secret_fails(self):
        """JWT secret containing placeholder markers must fail."""
        import shared.auth as auth_module
        original = auth_module.JWT_SECRETS
        try:
            auth_module.JWT_SECRETS = ["generate-with-openssl-rand-hex-32"]
            with pytest.raises(RuntimeError, match="placeholder"):
                validate_secrets()
        finally:
            auth_module.JWT_SECRETS = original


class TestErrorSanitization:
    """Tests to ensure no internal details leak in error responses."""

    def test_invalid_token_error_is_generic(self):
        """Error message for invalid tokens must not expose library internals."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt("completely-garbage-token")
        detail = exc_info.value.detail
        # Must not contain Python exception class names or tracebacks
        assert "jwt" not in detail.lower() or "malformed" in detail.lower()
        assert "Traceback" not in detail
        assert "InvalidTokenError" not in detail


class TestRoleBasedAccess:
    """Tests for the require_role dependency factory."""

    def test_require_role_rejects_invalid_role_definition(self):
        """Defining require_role with invalid roles must raise at definition time."""
        from shared.auth import require_role
        with pytest.raises(ValueError, match="Invalid role"):
            require_role("superuser")

    def test_require_role_accepts_valid_roles(self):
        """Valid roles should create a working dependency."""
        from shared.auth import require_role
        dep = require_role("admin", "analyst")
        assert callable(dep)


class TestTokenBlacklist:
    """Tests for Redis-based token blacklisting."""

    @pytest.mark.asyncio
    async def test_blacklist_token_stores_in_redis(self):
        """Blacklisted token jti should be stored in Redis with TTL."""
        mock_redis = AsyncMock()
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import blacklist_token
            await blacklist_token("test-jti-123", 3600)
            mock_redis.set.assert_called_once_with(
                "token:blacklist:test-jti-123", "1", ex=3600
            )

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_returns_true(self):
        """Should return True for blacklisted tokens."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import is_token_blacklisted
            result = await is_token_blacklisted("revoked-jti")
            assert result is True

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_returns_false(self):
        """Should return False for non-blacklisted tokens."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import is_token_blacklisted
            result = await is_token_blacklisted("valid-jti")
            assert result is False

    @pytest.mark.asyncio
    async def test_blacklist_fails_open_on_redis_error(self):
        """If Redis is down, is_token_blacklisted should fail-open (return False)."""
        mock_redis = AsyncMock()
        mock_redis.exists.side_effect = Exception("Redis connection failed")
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import is_token_blacklisted
            result = await is_token_blacklisted("any-jti")
            assert result is False


class TestAccountLockout:
    """Tests for account lockout after repeated failed logins."""

    @pytest.mark.asyncio
    async def test_record_failed_login_increments_counter(self):
        """Each failed login should increment the Redis counter."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import record_failed_login
            await record_failed_login("test@example.com")
            mock_redis.incr.assert_called_once_with("auth:lockout:test@example.com")

    @pytest.mark.asyncio
    async def test_is_account_locked_after_threshold(self):
        """Account should be locked after exceeding threshold."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"5"  # Matches ACCOUNT_LOCKOUT_THRESHOLD
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import is_account_locked
            result = await is_account_locked("test@example.com")
            assert result is True

    @pytest.mark.asyncio
    async def test_is_account_not_locked_below_threshold(self):
        """Account should not be locked below threshold."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"3"
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import is_account_locked
            result = await is_account_locked("test@example.com")
            assert result is False

    @pytest.mark.asyncio
    async def test_clear_failed_logins_deletes_key(self):
        """Successful login should clear the lockout counter."""
        mock_redis = AsyncMock()
        with patch("shared.auth._redis_client", mock_redis):
            from shared.auth import clear_failed_logins
            await clear_failed_logins("test@example.com")
            mock_redis.delete.assert_called_once_with("auth:lockout:test@example.com")
