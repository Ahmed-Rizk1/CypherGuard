"""
SecureNet SOC — Feature Extractor Service (Refactored)

Consumes raw packets from stream:raw_packets, computes sliding-window 
behavioral features using Redis, and publishes enriched features to 
stream:features for ML classification.

Changes from MVP:
- Redis Streams consumer (replaces FastAPI HTTP endpoint for ingestion)
- Still exposes FastAPI for /metrics and /health endpoints
- Sliding window feature computation via Redis sorted sets (replaces unbounded dict)
- Computes 12 aligned features (matching ML training pipeline)
- Periodically publishes aggregated live metrics for the dashboard
- Structured logging, Prometheus metrics
"""

import os
import sys
import time
import json
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging, trace_id_ctx, get_trace_id
from shared.redis_client import redis_manager
from shared.validators import MetricsResponse, HealthResponse
from shared.metrics import (
    PACKETS_PROCESSED, ACTIVE_CONNECTIONS, QUEUE_DEPTH, STREAM_LAG, SYSTEM_DROPPED_MESSAGES,
    metrics_endpoint,
)
from shared.chaos_engine import chaos

load_dotenv()

logger = setup_logging("extractor")

SERVICE_START_TIME = time.time()
FEATURE_WINDOW_SECONDS = int(os.getenv("FEATURE_WINDOW_SECONDS", "30"))
METRICS_PUBLISH_INTERVAL = float(os.getenv("METRICS_PUBLISH_INTERVAL", "1.0"))
MAX_ACTIVE_IPS = 5000  # Cap to prevent unbounded memory growth under DDoS

# Track recently active IPs (for metrics aggregation)
_active_ips: set = set()
_shutdown_event = asyncio.Event()


# ---------------------------------------------------------------------------
# Consumer: process raw packets
# ---------------------------------------------------------------------------

async def process_packet(data: dict) -> None:
    """
    Process a single raw packet from stream:raw_packets.

    1. Validate incoming data
    2. Update the sliding window stats for the source IP in Redis
    3. Compute features over the window
    4. Publish features to stream:features
    """
    # Validate required fields (lightweight — full Pydantic is too heavy per-packet)
    src_ip = data.get("src_ip", "")
    raw_size = data.get("size", "0")
    protocol = data.get("protocol", "OTHER")
    tenant_id = data.get("tenant_id", None)  # Multi-tenancy

    if not src_ip:
        logger.warning("Packet missing src_ip — skipping")
        PACKETS_PROCESSED.labels(service="extractor", status="invalid").inc()
        return

    try:
        size = int(raw_size)
    except (ValueError, TypeError):
        logger.warning(f"Packet has invalid size '{raw_size}' — skipping")
        PACKETS_PROCESSED.labels(service="extractor", status="invalid").inc()
        return

    if size <= 0 or size > 65535:
        logger.warning(f"Packet size out of range ({size}) — skipping")
        PACKETS_PROCESSED.labels(service="extractor", status="invalid").inc()
        return

    if protocol not in ("TCP", "UDP", "ICMP", "OTHER"):
        protocol = "OTHER"

    # Skip already-blocked IPs to save processing (tenant-scoped)
    if await redis_manager.is_blocked(src_ip, tenant_id=tenant_id):
        return

    # 1. Record the packet in the sliding window (tenant-scoped)
    await redis_manager.update_conn_stats(src_ip, size, ttl=300, tenant_id=tenant_id)

    # Track this IP as recently active (with cap to prevent OOM under DDoS)
    if len(_active_ips) < MAX_ACTIVE_IPS:
        _active_ips.add(src_ip)

    # 2. Compute features over the window (tenant-scoped)
    features = await redis_manager.get_conn_features(src_ip, FEATURE_WINDOW_SECONDS, tenant_id=tenant_id)

    # 3. Publish enriched features to the ML engine (with tenant context)
    feature_payload = {
        "src_ip": src_ip,
        "protocol": protocol,
        "tenant_id": tenant_id or "",
        "trace_id": get_trace_id(),
        **{k: str(v) for k, v in features.items()},
    }

    await redis_manager.publish("stream:features", feature_payload)
    PACKETS_PROCESSED.labels(service="extractor", status="success").inc()



async def consumer_loop() -> None:
    """Main consumer loop — reads from stream:raw_packets. Exits on shutdown signal."""
    logger.info("Extractor consumer started — reading from stream:raw_packets")

    while not _shutdown_event.is_set():
        try:
            # Backpressure Check
            lag = await redis_manager.stream_length("stream:raw_packets")
            STREAM_LAG.labels(stream="stream:raw_packets", group="extractor_group").set(lag)
            if lag > 1000:
                logger.warning(f"Backpressure detected in stream:raw_packets! Lag: {lag}")

            await chaos.inject_redis_latency("stream:raw_packets", max_delay_ms=100)

            messages = await redis_manager.consume(
                stream="stream:raw_packets",
                group="extractor_group",
                consumer="extractor_worker_1",
                count=50,    # Process in batches for efficiency
                block_ms=2000,
            )

            if messages:
                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        # Extract and propagate trace_id
                        msg_trace_id = data.get("trace_id")
                        if msg_trace_id:
                            trace_id_ctx.set(msg_trace_id)
                        else:
                            trace_id_ctx.set(get_trace_id())

                        try:
                            # Chaos Drop
                            if chaos.should_drop_message(probability=0.01):
                                SYSTEM_DROPPED_MESSAGES.labels(service="extractor", reason="chaos_drop").inc()
                                await redis_manager.ack("stream:raw_packets", "extractor_group", msg_id)
                                continue

                            # Chaos Crash (Simulate)
                            chaos.simulate_crash(probability=0.0005)

                            await process_packet(data)
                            await redis_manager.ack(
                                "stream:raw_packets", "extractor_group", msg_id
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to process packet {msg_id}: {e}",
                                exc_info=True,
                            )

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled — finishing")
            break
        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            await asyncio.sleep(2)


# ---------------------------------------------------------------------------
# Metrics publisher: aggregate and push live metrics for dashboard
# ---------------------------------------------------------------------------

async def metrics_publisher_loop() -> None:
    """Periodically aggregate and publish live traffic metrics."""
    global _active_ips

    while True:
        try:
            total_pps = 0.0
            total_bps = 0.0
            active_count = 0

            # Compute per-IP metrics for all recently active IPs
            stale_ips = set()
            for ip in list(_active_ips):
                features = await redis_manager.get_conn_features(ip, FEATURE_WINDOW_SECONDS)
                if features["packet_count"] > 0:
                    total_pps += features["packets_per_sec"]
                    total_bps += features["bytes_per_sec"]
                    active_count += 1
                else:
                    stale_ips.add(ip)

            # Remove stale IPs
            _active_ips -= stale_ips

            # Publish to Redis for dashboard consumption
            metrics_data = {
                "packets_per_sec": round(total_pps, 2),
                "bytes_per_sec": round(total_bps, 2),
                "active_connections": active_count,
            }
            await redis_manager.set_live_metrics(metrics_data)

            # Update Prometheus gauges
            ACTIVE_CONNECTIONS.set(active_count)

        except Exception as e:
            logger.error(f"Metrics publisher error: {e}")

        await asyncio.sleep(METRICS_PUBLISH_INTERVAL)


# ---------------------------------------------------------------------------
# FastAPI app (for /health, /metrics, and /api/metrics endpoints)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, clean up on shutdown."""
    await redis_manager.connect()

    # Start consumer and metrics publisher as background tasks
    consumer_task = asyncio.create_task(consumer_loop())
    metrics_task = asyncio.create_task(metrics_publisher_loop())

    logger.info("Extractor service started")
    yield

    # Graceful shutdown: signal loops to stop, then wait for completion
    _shutdown_event.set()
    consumer_task.cancel()
    metrics_task.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(consumer_task, metrics_task, return_exceptions=True), timeout=10)
    except asyncio.TimeoutError:
        logger.warning("Shutdown timeout — forcing exit")
    await redis_manager.close()
    logger.info("Extractor service stopped")


app = FastAPI(title="Feature Extractor Service", lifespan=lifespan)

# Prometheus metrics endpoint
app.add_route("/metrics", metrics_endpoint)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        service="extractor",
        uptime_seconds=round(time.time() - SERVICE_START_TIME, 1),
    )


@app.get("/ready")
async def ready():
    """Readiness check to verify Redis connectivity."""
    try:
        await redis_manager.client.ping()
        return {"status": "ready", "redis": "connected"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_live_metrics():
    """Returns aggregated traffic metrics for the dashboard."""
    data = await redis_manager.get_live_metrics()
    return MetricsResponse(**data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Feature Extractor on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
