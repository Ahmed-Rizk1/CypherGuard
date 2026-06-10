"""
Sensor API key authentication for the Ingest Gateway.

SECURITY: Verifies API key format, bcrypt hash, sensor status,
AND tenant status. Sensors from suspended/cancelled tenants are rejected.
"""

import logging
from pydantic import BaseModel

import bcrypt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from shared.database import async_session, Sensor, Tenant

logger = logging.getLogger(__name__)
security_scheme = HTTPBearer(auto_error=True)


class SensorContext(BaseModel):
    """Authenticated sensor context."""
    sensor_id: str
    tenant_id: str
    sensor_name: str


async def verify_sensor_key(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> SensorContext:
    """
    FastAPI dependency that validates a sensor API key.
    
    The API key format is: sn_{48 hex chars}
    The key prefix (first 11 chars) is used to look up the sensor,
    then bcrypt verify is used to check the full key.

    SECURITY CHECKS:
    1. Key format validation (sn_ prefix + minimum length)
    2. Sensor lookup by prefix (active or pending status only)
    3. Tenant status check (must be trial or active)
    4. Full bcrypt key verification
    """
    raw_key = credentials.credentials
    
    if not raw_key.startswith("sn_") or len(raw_key) < 20:
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    key_prefix = raw_key[:11]
    
    async with async_session() as session:
        result = await session.execute(
            select(Sensor).where(
                Sensor.api_key_prefix == key_prefix,
                Sensor.status.in_(["active", "pending"]),
            )
        )
        sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    
    # SECURITY: Check tenant status — reject sensors from suspended/cancelled tenants.
    # This prevents data ingestion for tenants that have been deactivated.
    async with async_session() as session:
        tenant_result = await session.execute(
            select(Tenant.status).where(Tenant.id == sensor.tenant_id)
        )
        tenant_status = tenant_result.scalar_one_or_none()
    
    if tenant_status not in ("trial", "active"):
        logger.warning(
            f"Sensor auth rejected: tenant {sensor.tenant_id} status={tenant_status}",
            extra={"sensor_id": str(sensor.id), "tenant_id": str(sensor.tenant_id)},
        )
        raise HTTPException(
            status_code=403,
            detail="Tenant account is suspended or inactive. Contact support.",
        )
    
    # Verify the full key against the bcrypt hash
    if not bcrypt.checkpw(raw_key.encode(), sensor.api_key_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return SensorContext(
        sensor_id=str(sensor.id),
        tenant_id=str(sensor.tenant_id),
        sensor_name=sensor.name,
    )

