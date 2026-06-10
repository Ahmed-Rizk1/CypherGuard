"""
Authentication and authorization for SecureNet SOC (SaaS Multi-Tenant).

Provides:
- JWT token creation and verification with jti (JWT ID) and tid (tenant ID) claims
- Redis-based token blacklisting for logout / revocation
- Refresh token rotation (one-time use)
- Account lockout after repeated failures
- Internal API key verification for service-to-service calls
- Role-based access control (owner, admin, analyst, viewer)
- Security header middleware
- Login-specific rate limiting

Usage:
    from shared.auth import verify_jwt, require_role, create_access_token

    # Protect a dashboard endpoint (JWT required)
    @app.get("/api/alerts")
    async def get_alerts(token: TokenPayload = Depends(verify_jwt)):
        ...

    # Protect an admin-only endpoint
    @app.post("/api/users")
    async def create_user(token: TokenPayload = Depends(require_role("admin"))):
        ...

    # Protect an internal service endpoint (API key)
    @app.post("/internal/predict")
    async def predict(dep = Depends(verify_internal_api_key)):
        ...
"""

import os
import time
import uuid
import logging
import hmac
from typing import Optional

import jwt
from fastapi import HTTPException, Security, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

raw_secrets = os.getenv("JWT_SECRET", "")
JWT_SECRETS: list[str] = [s.strip() for s in raw_secrets.split(",") if s.strip()]
if not JWT_SECRETS:
    JWT_SECRETS = [""]
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_SECONDS: int = int(os.getenv("JWT_EXPIRY_SECONDS", "3600"))
INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

# Account lockout settings
ACCOUNT_LOCKOUT_THRESHOLD: int = int(os.getenv("ACCOUNT_LOCKOUT_THRESHOLD", "5"))
ACCOUNT_LOCKOUT_DURATION: int = int(os.getenv("ACCOUNT_LOCKOUT_DURATION", "900"))  # 15 min

_UNSAFE_MARKERS = {"CHANGE-ME", "REPLACE_ME", "changeme", "replace_me", "your-", "generate-with"}


def validate_secrets() -> None:
    """Fail fast if critical secrets are missing or still set to placeholder values."""
    errors: list[str] = []

    for i, secret in enumerate(JWT_SECRETS):
        if not secret or len(secret) < 16:
            errors.append(f"JWT_SECRET[{i}] is missing or too short (min 16 chars)")
        elif any(marker in secret.lower() for marker in _UNSAFE_MARKERS):
            errors.append(f"JWT_SECRET[{i}] still contains a placeholder value")

    if not INTERNAL_API_KEY or len(INTERNAL_API_KEY) < 16:
        errors.append("INTERNAL_API_KEY is missing or too short (min 16 chars)")
    elif any(marker in INTERNAL_API_KEY.lower() for marker in _UNSAFE_MARKERS):
        errors.append("INTERNAL_API_KEY still contains a placeholder value")

    if errors:
        for err in errors:
            logger.critical(f"SECRET VALIDATION FAILED: {err}")
        raise RuntimeError(
            "FATAL: Insecure secrets detected. Set proper values in .env before starting.\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


security_scheme = HTTPBearer(auto_error=True)

# Updated RBAC hierarchy: owner > admin > analyst > viewer
VALID_ROLES = {"owner", "admin", "analyst", "viewer"}


# ---------------------------------------------------------------------------
# Token models
# ---------------------------------------------------------------------------

class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str        # user ID
    tid: str = ""   # tenant ID ← NEW for multi-tenancy
    role: str       # owner | admin | analyst | viewer
    exp: float      # expiration timestamp (epoch)
    iat: float = 0  # issued-at timestamp
    jti: str = ""   # unique token ID for revocation


class TokenResponse(BaseModel):
    """Login response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    role: str


# ---------------------------------------------------------------------------
# Token Blacklist (Redis-based)
# ---------------------------------------------------------------------------

_redis_client = None  # Lazily bound to redis_manager.client


async def _get_redis():
    """Get the Redis client, lazily importing to avoid circular imports."""
    global _redis_client
    if _redis_client is None:
        from shared.redis_client import redis_manager
        _redis_client = redis_manager.client
    return _redis_client


async def blacklist_token(jti: str, remaining_ttl: int) -> None:
    """Add a token's jti to the Redis blacklist with auto-expiry matching the token's TTL."""
    if not jti or remaining_ttl <= 0:
        return
    try:
        redis = await _get_redis()
        await redis.set(f"token:blacklist:{jti}", "1", ex=remaining_ttl)
    except Exception as e:
        logger.error(f"Failed to blacklist token {jti}: {e}")


async def is_token_blacklisted(jti: str) -> bool:
    """Check if a token's jti has been revoked."""
    if not jti:
        return False
    try:
        redis = await _get_redis()
        return await redis.exists(f"token:blacklist:{jti}") > 0
    except Exception:
        # Fail-open: if Redis is down, allow the token (rate limiter still protects)
        return False


# ---------------------------------------------------------------------------
# Account Lockout (Redis-based)
# ---------------------------------------------------------------------------

async def record_failed_login(email: str) -> None:
    """Record a failed login attempt and lock account if threshold exceeded."""
    try:
        redis = await _get_redis()
        key = f"auth:lockout:{email}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, ACCOUNT_LOCKOUT_DURATION)
    except Exception as e:
        logger.error(f"Failed to record login failure: {e}")


async def clear_failed_logins(email: str) -> None:
    """Clear failed login counter on successful login."""
    try:
        redis = await _get_redis()
        await redis.delete(f"auth:lockout:{email}")
    except Exception:
        pass


async def is_account_locked(email: str) -> bool:
    """Check if an account is locked due to too many failed attempts."""
    try:
        redis = await _get_redis()
        count = await redis.get(f"auth:lockout:{email}")
        if count and int(count) >= ACCOUNT_LOCKOUT_THRESHOLD:
            return True
    except Exception:
        pass  # Fail-open
    return False


# ---------------------------------------------------------------------------
# Token creation (updated with tenant_id support)
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    role: str,
    tenant_id: str = "",
    expires_in: Optional[int] = None,
) -> str:
    """
    Create a signed JWT access token with jti and tid (tenant) claims.

    Args:
        user_id: Unique user identifier (UUID string or email).
        role: One of 'owner', 'admin', 'analyst', 'viewer'.
        tenant_id: Tenant UUID string for multi-tenancy.
        expires_in: Token lifetime in seconds. Defaults to JWT_EXPIRY_SECONDS.

    Returns:
        Encoded JWT string.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

    expiry = expires_in or JWT_EXPIRY_SECONDS
    now = time.time()

    payload = {
        "sub": user_id,
        "tid": tenant_id,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expiry,
    }

    # Always sign with the newest (first) secret in the list
    return jwt.encode(payload, JWT_SECRETS[0], algorithm=JWT_ALGORITHM)


REFRESH_TOKEN_EXPIRY: int = int(os.getenv("REFRESH_TOKEN_EXPIRY", "604800"))  # 7 days


def create_refresh_token(user_id: str, role: str, tenant_id: str = "") -> str:
    """
    Create a long-lived refresh token (7 days) with a unique jti.

    Refresh tokens contain a 'type: refresh' claim and CANNOT be used
    as access tokens. They can only be exchanged for a new access token
    via the /auth/refresh endpoint.
    """
    now = time.time()
    payload = {
        "sub": user_id,
        "tid": tenant_id,
        "role": role,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + REFRESH_TOKEN_EXPIRY,
    }
    return jwt.encode(payload, JWT_SECRETS[0], algorithm=JWT_ALGORITHM)


async def refresh_access_token(refresh_token: str) -> dict:
    """
    Exchange a valid refresh token for a new access token AND a new refresh token.

    Implements refresh token rotation: the old refresh token is blacklisted
    and a new one is issued, preventing replay attacks.

    Returns:
        Dict with new access_token, refresh_token, and expires_in.

    Raises HTTPException if the token is invalid, expired, blacklisted, or not a refresh token.
    """
    payload = decode_jwt(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    # Check if this refresh token has already been used (rotation check)
    jti = payload.get("jti", "")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    user_id = payload.get("sub")
    role = payload.get("role")
    tenant_id = payload.get("tid", "")

    if role not in VALID_ROLES:
        raise HTTPException(status_code=401, detail="Invalid role in refresh token")

    # Blacklist the old refresh token (one-time use / rotation)
    remaining_ttl = int(payload.get("exp", 0) - time.time())
    await blacklist_token(jti, remaining_ttl)

    # Issue new tokens (with tenant_id preserved)
    new_access = create_access_token(user_id, role, tenant_id=tenant_id)
    new_refresh = create_refresh_token(user_id, role, tenant_id=tenant_id)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRY_SECONDS,
    }


# ---------------------------------------------------------------------------
# JWT verification (for dashboard/external API)
# ---------------------------------------------------------------------------

def decode_jwt(token: str) -> dict:
    """Decodes and validates a JWT token string."""
    payload = None
    last_error = None

    for secret in JWT_SECRETS:
        try:
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
            break  # Success!
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            last_error = e
            continue  # Try next secret

    if not payload:
        # Sanitized error message — never expose internal JWT library details
        raise HTTPException(status_code=401, detail="Invalid or malformed token")

    return payload


async def verify_jwt(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> TokenPayload:
    """
    FastAPI dependency that extracts and validates a JWT Bearer token.

    Checks:
    1. Token is syntactically valid and not expired
    2. Token type is 'access' (prevents refresh token misuse)
    3. Token has not been blacklisted (logout/revocation)
    4. Token contains a valid role

    SECURITY: Without the type check, a 7-day refresh token could be
    used as a Bearer token on any protected endpoint, bypassing the
    shorter access token expiry window.

    Raises HTTPException 401 if the token is missing, expired, blacklisted, or invalid.
    """
    token = credentials.credentials
    payload = decode_jwt(token)

    # SECURITY: Reject refresh tokens used as access tokens.
    # Refresh tokens have type="refresh" and a 7-day expiry.
    # Without this check, they could bypass the 1-hour access token window.
    token_type = payload.get("type", "")
    if token_type != "access":
        raise HTTPException(
            status_code=401,
            detail="Invalid token type. Use an access token, not a refresh token.",
        )

    # Check if token has been revoked
    jti = payload.get("jti", "")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    if payload.get("role") not in VALID_ROLES:
        raise HTTPException(status_code=401, detail="Token contains invalid role")

    return TokenPayload(**payload)


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory that enforces role-based access.

    Usage:
        @app.delete("/api/alert/{id}")
        async def delete_alert(token = Depends(require_role("admin", "analyst"))):
            ...
    """
    for r in allowed_roles:
        if r not in VALID_ROLES:
            raise ValueError(f"Invalid role in require_role: {r}")

    async def _check_role(
        token: TokenPayload = Depends(verify_jwt),
    ) -> TokenPayload:
        if token.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions",
            )
        return token

    return _check_role


# ---------------------------------------------------------------------------
# Internal API key verification (for service-to-service calls)
# ---------------------------------------------------------------------------

async def verify_internal_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> None:
    """
    FastAPI dependency that validates an internal API key in the Bearer header.

    Uses constant-time comparison to prevent timing attacks.
    """
    if not hmac.compare_digest(credentials.credentials, INTERNAL_API_KEY):
        logger.warning("Invalid internal API key attempt")
        raise HTTPException(status_code=403, detail="Invalid API key")


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------

async def security_headers_middleware(request: Request, call_next) -> Response:
    """Add security headers to all responses (OWASP best practices)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    # HSTS only added when behind TLS (Traefik adds this in production)
    return response


# ---------------------------------------------------------------------------
# Request Size Limit Middleware
# ---------------------------------------------------------------------------

MAX_REQUEST_BODY_SIZE: int = int(os.getenv("MAX_REQUEST_BODY_SIZE", str(1024 * 1024)))  # 1MB


async def request_size_limit_middleware(request: Request, call_next) -> Response:
    """Reject requests exceeding the configured body size limit."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
        raise HTTPException(status_code=413, detail="Request body too large")
    return await call_next(request)
