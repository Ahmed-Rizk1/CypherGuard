"""
SecureNet SOC — Ingest Gateway Service

Receives packet data from remote sensors via authenticated API.
Validates sensor API keys, tags data with tenant_id, and publishes
to the existing pipeline (stream:raw_packets).

Endpoints:
  POST /v1/ingest/packets   — Submit batch of packets
  POST /v1/ingest/heartbeat — Sensor health check
  GET  /v1/ingest/config    — Fetch sensor configuration
  GET  /health              — Service health check
"""

import os
import sys
import time
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import bcrypt
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging
from shared.redis_client import redis_manager
from shared.database import async_session, Sensor
from shared.metrics import PACKETS_PROCESSED, metrics_endpoint
from ingest_gateway.auth import verify_sensor_key, SensorContext
from ingest_gateway.monitor import start_monitor, stop_monitor
from shared.rate_limiter import IngestRateLimiter

# Rate limiter: 5000 packets/min per sensor, 50000 packets/min per tenant
ingest_limiter = IngestRateLimiter(
    max_per_sensor=5000, max_per_tenant=50000, window_seconds=60,
)

load_dotenv()
logger = setup_logging("ingest_gateway")

SERVICE_START_TIME = time.time()


# ===================================================================
# Request Models
# ===================================================================

class PacketData(BaseModel):
    src_ip: str = Field(..., min_length=1, max_length=45)
    size: int = Field(..., ge=1, le=65535)
    protocol: str = Field(default="TCP", pattern="^(TCP|UDP|ICMP|OTHER)$")


class PacketBatch(BaseModel):
    packets: list[PacketData] = Field(..., min_length=1, max_length=1000)


class HeartbeatData(BaseModel):
    version: str = Field(default="unknown", max_length=50)
    uptime_seconds: float = Field(default=0, ge=0)
    packets_sent: int = Field(default=0, ge=0)
    system_info: dict = Field(default_factory=dict)


# ===================================================================
# App Setup
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    monitor_task = asyncio.create_task(start_monitor())
    logger.info("Ingest Gateway started")
    yield
    await stop_monitor()
    monitor_task.cancel()
    await redis_manager.close()

app = FastAPI(
    title="SecureNet Ingest Gateway",
    version="1.0.0",
    description="Authenticated packet ingestion from remote sensors.",
    lifespan=lifespan,
)
app.add_route("/metrics", metrics_endpoint)


# ===================================================================
# Packet Ingestion
# ===================================================================

@app.post("/v1/ingest/packets")
async def ingest_packets(
    batch: PacketBatch,
    sensor: SensorContext = Depends(verify_sensor_key),
):
    """
    Receive a batch of packets from a sensor.
    Tags each packet with tenant_id and sensor_id before publishing.
    Rate-limited per-sensor and per-tenant to prevent pipeline flooding.
    """
    # SECURITY: Rate limit before processing to prevent pipeline flooding
    await ingest_limiter.check(
        sensor_id=sensor.sensor_id,
        tenant_id=sensor.tenant_id,
        batch_size=len(batch.packets),
    )

    published = 0
    for pkt in batch.packets:
        await redis_manager.publish("stream:raw_packets", {
            "src_ip": pkt.src_ip,
            "size": str(pkt.size),
            "protocol": pkt.protocol,
            "tenant_id": str(sensor.tenant_id),
            "sensor_id": str(sensor.sensor_id),
        })
        published += 1

    PACKETS_PROCESSED.labels(service="ingest_gateway", status="accepted").inc(published)
    return {"status": "ok", "accepted": published}


# ===================================================================
# Heartbeat
# ===================================================================

@app.post("/v1/ingest/heartbeat")
async def heartbeat(
    data: HeartbeatData,
    sensor: SensorContext = Depends(verify_sensor_key),
):
    """Update sensor status and metadata."""
    try:
        async with async_session() as session:
            # SECURITY: Filter by BOTH sensor ID and tenant_id to prevent
            # a sensor key from updating another tenant's sensor record.
            result = await session.execute(
                select(Sensor).where(
                    Sensor.id == sensor.sensor_id,
                    Sensor.tenant_id == sensor.tenant_id,
                )
            )
            sensor_record = result.scalar_one_or_none()
            if sensor_record:
                sensor_record.status = "active"
                sensor_record.last_heartbeat = datetime.now(timezone.utc).replace(tzinfo=None)
                sensor_record.version = data.version
                await session.commit()
            else:
                logger.warning(
                    f"Heartbeat for unknown sensor/tenant: sensor={sensor.sensor_id} tenant={sensor.tenant_id}"
                )
    except Exception as e:
        logger.error(f"Heartbeat DB update failed: {e}")

    return {"status": "ok", "server_time": datetime.now(timezone.utc).isoformat()}


# ===================================================================
# Config
# ===================================================================

@app.get("/v1/ingest/config")
async def get_config(sensor: SensorContext = Depends(verify_sensor_key)):
    """Return sensor configuration from the platform."""
    try:
        async with async_session() as session:
            # SECURITY: Filter by tenant_id to prevent cross-tenant config access
            result = await session.execute(
                select(Sensor).where(
                    Sensor.id == sensor.sensor_id,
                    Sensor.tenant_id == sensor.tenant_id,
                )
            )
            sensor_record = result.scalar_one_or_none()
            config = sensor_record.config if sensor_record else {}
    except Exception:
        config = {}

    return {
        "heartbeat_interval": 30,
        "batch_size": 100,
        "batch_interval": 1.0,
        "custom": config,
    }


# ===================================================================
# Health
# ===================================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "ingest_gateway",
        "uptime_seconds": round(time.time() - SERVICE_START_TIME, 1),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)
