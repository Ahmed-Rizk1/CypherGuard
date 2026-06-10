"""
Per-IP and per-tenant rate limiting middleware for FastAPI.

Provides:
- RateLimiter: Original per-IP rate limiter (backward-compatible)
- TenantRateLimiter: Dual-key rate limiter (IP + tenant_id from JWT)
- IngestRateLimiter: Per-sensor rate limiter for the ingest gateway

All use Redis for distributed state, so they work across multiple workers.

Usage:
    from shared.rate_limiter import RateLimiter, TenantRateLimiter, IngestRateLimiter

    rate_limiter = TenantRateLimiter(max_per_ip=120, max_per_tenant=1000, window_seconds=60)
    ingest_limiter = IngestRateLimiter(max_per_sensor=5000, max_per_tenant=50000, window_seconds=60)

    @app.get("/api/alerts")
    async def get_alerts(dep=Depends(rate_limiter)):
        ...
"""

import time
import logging

from fastapi import HTTPException, Request
from shared.redis_client import redis_manager

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Distributed Redis-based per-IP rate limiter.
    
    Uses an atomic INCR + EXPIRE fixed-window approach.
    Horizontally scalable across multiple API workers.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        """FastAPI dependency — call on each request."""
        client_ip = request.client.host if request.client else "unknown"
        
        # Fallback to allow if Redis is not connected (fail-open for safety)
        if not redis_manager.client:
            return

        window_id = int(time.time() // self.window_seconds)
        key = f"rate_limit:{client_ip}:{window_id}"

        try:
            # Execute atomic INCR
            pipe = redis_manager.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window_seconds * 2) # double TTL for safety
            result = await pipe.execute()
            
            current_requests = result[0]

            if current_requests > self.max_requests:
                logger.warning(
                    f"Rate limit exceeded for {client_ip}: "
                    f"{self.max_requests}/{self.window_seconds}s",
                    extra={"src_ip": client_ip},
                )
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Rate limit exceeded: maximum {self.max_requests} requests "
                        f"per {self.window_seconds} seconds"
                    ),
                    headers={"Retry-After": str(self.window_seconds)},
                )
        except HTTPException:
            raise
        except Exception as e:
            # If Redis fails, log and fail-open to avoid breaking the API
            logger.error(f"RateLimiter Redis failure: {e}")

    def cleanup(self) -> int:
        """No-op. Redis automatically expires keys via TTL."""
        return 0


class TenantRateLimiter:
    """
    Dual-key rate limiter: per-IP AND per-tenant.

    Prevents:
    - Single IP abuse (standard rate limiting)
    - Noisy-neighbor effect (one tenant consuming all resources)

    Uses two Redis keys per window:
    - rate_limit:{ip}:{window}     — per-IP limit
    - rate_limit:t:{tid}:{window}  — per-tenant limit

    Both must be within limits for the request to proceed.
    """

    def __init__(
        self,
        max_per_ip: int = 120,
        max_per_tenant: int = 1000,
        window_seconds: int = 60,
    ):
        self.max_per_ip = max_per_ip
        self.max_per_tenant = max_per_tenant
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        """FastAPI dependency — checks both IP and tenant limits."""
        if not redis_manager.client:
            return

        client_ip = request.client.host if request.client else "unknown"
        window_id = int(time.time() // self.window_seconds)

        # Extract tenant_id from the request state (set by auth middleware)
        # If not available, fall back to IP-only limiting
        tenant_id = getattr(request.state, "tenant_id", None)

        try:
            pipe = redis_manager.client.pipeline()

            # 1. Per-IP rate limit
            ip_key = f"rate_limit:{client_ip}:{window_id}"
            pipe.incr(ip_key)
            pipe.expire(ip_key, self.window_seconds * 2)

            # 2. Per-tenant rate limit (if tenant context exists)
            if tenant_id:
                tenant_key = f"rate_limit:t:{tenant_id}:{window_id}"
                pipe.incr(tenant_key)
                pipe.expire(tenant_key, self.window_seconds * 2)

            results = await pipe.execute()

            ip_count = results[0]
            tenant_count = results[2] if tenant_id else 0

            if ip_count > self.max_per_ip:
                logger.warning(
                    f"IP rate limit exceeded: {client_ip} ({ip_count}/{self.max_per_ip})",
                    extra={"src_ip": client_ip, "tenant_id": tenant_id or ""},
                )
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(self.window_seconds)},
                )

            if tenant_id and tenant_count > self.max_per_tenant:
                logger.warning(
                    f"Tenant rate limit exceeded: {tenant_id} ({tenant_count}/{self.max_per_tenant})",
                    extra={"tenant_id": tenant_id},
                )
                raise HTTPException(
                    status_code=429,
                    detail="Tenant rate limit exceeded. Contact support for higher limits.",
                    headers={
                        "Retry-After": str(self.window_seconds),
                        "X-Upgrade-Required": "true",
                    },
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"TenantRateLimiter Redis failure: {e}")


class IngestRateLimiter:
    """
    Rate limiter for the ingest gateway (sensor packet submission).

    Enforces:
    - Per-sensor limit: prevents a single sensor from flooding
    - Per-tenant limit: prevents one tenant from consuming all pipeline capacity

    Uses Redis keys:
    - ingest_limit:s:{sensor_id}:{window}  — per-sensor
    - ingest_limit:t:{tenant_id}:{window}  — per-tenant
    """

    def __init__(
        self,
        max_per_sensor: int = 5000,
        max_per_tenant: int = 50000,
        window_seconds: int = 60,
    ):
        self.max_per_sensor = max_per_sensor
        self.max_per_tenant = max_per_tenant
        self.window_seconds = window_seconds

    async def check(self, sensor_id: str, tenant_id: str, batch_size: int = 1) -> None:
        """
        Check rate limits for a sensor ingestion request.

        Args:
            sensor_id: The sensor UUID making the request.
            tenant_id: The tenant UUID the sensor belongs to.
            batch_size: Number of packets in the batch (increments by this amount).

        Raises HTTPException 429 if limits are exceeded.
        """
        if not redis_manager.client:
            return

        window_id = int(time.time() // self.window_seconds)

        try:
            pipe = redis_manager.client.pipeline()

            sensor_key = f"ingest_limit:s:{sensor_id}:{window_id}"
            pipe.incrby(sensor_key, batch_size)
            pipe.expire(sensor_key, self.window_seconds * 2)

            tenant_key = f"ingest_limit:t:{tenant_id}:{window_id}"
            pipe.incrby(tenant_key, batch_size)
            pipe.expire(tenant_key, self.window_seconds * 2)

            results = await pipe.execute()

            sensor_count = results[0]
            tenant_count = results[2]

            if sensor_count > self.max_per_sensor:
                logger.warning(
                    f"Sensor ingest limit exceeded: {sensor_id} ({sensor_count}/{self.max_per_sensor})",
                    extra={"sensor_id": sensor_id, "tenant_id": tenant_id},
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Sensor rate limit exceeded: max {self.max_per_sensor} packets/{self.window_seconds}s",
                    headers={"Retry-After": str(self.window_seconds)},
                )

            if tenant_count > self.max_per_tenant:
                logger.warning(
                    f"Tenant ingest limit exceeded: {tenant_id} ({tenant_count}/{self.max_per_tenant})",
                    extra={"tenant_id": tenant_id},
                )
                raise HTTPException(
                    status_code=429,
                    detail="Tenant ingestion rate limit exceeded",
                    headers={"Retry-After": str(self.window_seconds)},
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"IngestRateLimiter Redis failure: {e}")

