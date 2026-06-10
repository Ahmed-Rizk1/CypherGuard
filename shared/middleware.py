"""
Tenant middleware for SecureNet SOC.

Provides:
- get_current_tenant: Extracts tenant_id from JWT (required)
- get_optional_tenant: Extracts tenant_id or empty string (optional)
- require_active_tenant: Validates tenant is active/trial (cached in Redis)

SECURITY: require_active_tenant() should be used on all protected endpoints
to prevent suspended/cancelled tenants from accessing the API.
"""

import logging
from fastapi import Depends, HTTPException, Request
from shared.auth import verify_jwt, TokenPayload
from shared.redis_client import redis_manager

logger = logging.getLogger(__name__)

# Valid tenant statuses that allow API access
_ACTIVE_STATUSES = {"trial", "active"}
# Redis cache TTL for tenant status (seconds)
_STATUS_CACHE_TTL = 30


async def get_current_tenant(
    token: TokenPayload = Depends(verify_jwt),
) -> str:
    """
    FastAPI dependency that extracts and returns the tenant_id from the JWT.

    Raises HTTPException 403 if no tenant_id is present in the token.
    """
    if not token.tid:
        raise HTTPException(
            status_code=403,
            detail="No tenant context. Please contact support."
        )
    return token.tid


async def get_optional_tenant(
    token: TokenPayload = Depends(verify_jwt),
) -> str:
    """
    FastAPI dependency that returns tenant_id or empty string.
    Used for backward compatibility during migration.
    """
    return token.tid or ""


async def require_active_tenant(
    tenant_id: str = Depends(get_current_tenant),
) -> str:
    """
    FastAPI dependency that validates the tenant's account status.

    Checks that the tenant status is 'trial' or 'active'. Uses Redis
    caching (30s TTL) to avoid a DB query on every request.

    SECURITY: This prevents users from suspended/cancelled tenants from
    accessing any protected API endpoint, even with a valid JWT.

    Usage:
        @app.get("/api/data")
        async def get_data(tenant_id: str = Depends(require_active_tenant)):
            ...

    Raises HTTPException 403 if the tenant is suspended/cancelled/not found.
    """
    cache_key = f"tenant_status:{tenant_id}"

    try:
        # Check Redis cache first
        if redis_manager.client:
            cached_status = await redis_manager.client.get(cache_key)
            if cached_status:
                if cached_status in _ACTIVE_STATUSES:
                    return tenant_id
                raise HTTPException(
                    status_code=403,
                    detail=f"Tenant account is {cached_status}. Contact support.",
                )
    except HTTPException:
        raise
    except Exception:
        # Redis failure — fall through to DB lookup
        pass

    # Cache miss or Redis down — check the database
    try:
        from shared.database import async_session, Tenant
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(
                select(Tenant.status).where(Tenant.id == tenant_id)
            )
            status = result.scalar_one_or_none()

        if not status:
            raise HTTPException(
                status_code=403,
                detail="Tenant not found. Contact support.",
            )

        # Cache the status in Redis
        try:
            if redis_manager.client:
                await redis_manager.client.set(
                    cache_key, status, ex=_STATUS_CACHE_TTL
                )
        except Exception:
            pass  # Non-critical

        if status not in _ACTIVE_STATUSES:
            logger.warning(
                f"API access denied: tenant {tenant_id} status={status}",
                extra={"tenant_id": tenant_id},
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant account is {status}. Contact support.",
            )

        return tenant_id

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify tenant status: {e}")
        # FAIL-OPEN: If both Redis and DB are down, allow the request.
        # The tenant isolation is still enforced by RLS.
        return tenant_id

