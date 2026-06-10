"""
SecureNet SOC — Firewall Controller Service (Refactored)

Consumes block commands from stream:block_commands, validates IPs,
blocks them in Redis (immediate effect), optionally blocks via iptables,
and persists the record to PostgreSQL.

Changes from MVP:
- Redis Streams consumer (replaces HTTP endpoint for ingestion)
- Safe iptables integration via subprocess (no shell injection)
- IP validation with loopback/link-local/private protection
- PostgreSQL persistence with audit trail
- Loads existing blocks from DB on startup
- Structured logging + Prometheus metrics
"""

import os
import sys
import time
import ipaddress
import platform
import subprocess
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Depends
from dotenv import load_dotenv
from sqlalchemy import select, text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging, trace_id_ctx, get_trace_id
from shared.redis_client import redis_manager
from shared.database import async_session, BlockedIP
from shared.validators import HealthResponse, BlockRequest
from pydantic import ValidationError
from shared.metrics import FIREWALL_BLOCKS, BLOCKED_IPS_COUNT, STREAM_LAG, metrics_endpoint

load_dotenv()

logger = setup_logging("firewall")

SERVICE_START_TIME = time.time()
ENABLE_OS_FIREWALL = os.getenv("ENABLE_OS_FIREWALL", "0") == "1"
IS_LINUX = platform.system() == "Linux"


# ===================================================================
# IP Validation
# ===================================================================

def validate_ip_strict(ip_str: str) -> str:
    """
    Validate and return a normalized IP address.

    Rejects:
    - Non-IP strings (prevents injection)
    - Loopback addresses (127.x.x.x)
    - Link-local addresses (169.254.x.x)
    """
    try:
        addr = ipaddress.ip_address(ip_str.strip())
    except ValueError as e:
        raise ValueError(f"Invalid IP address '{ip_str}': {e}")

    if addr.is_loopback:
        raise ValueError(f"Cannot block loopback address: {addr}")
    if addr.is_link_local:
        raise ValueError(f"Cannot block link-local address: {addr}")

    return str(addr)


# ===================================================================
# OS-Level Firewall (iptables)
# ===================================================================

def block_ip_iptables(ip: str) -> bool:
    """
    Safely block an IP via iptables (Linux only).

    Security: Uses subprocess with list arguments — completely immune
    to shell injection. The IP is validated before reaching this function.
    """
    if not IS_LINUX:
        logger.debug("OS firewall not available on this platform")
        return False

    validated_ip = validate_ip_strict(ip)  # Double-validate

    try:
        # Check if rule already exists
        check = subprocess.run(
            ["iptables", "-C", "INPUT", "-s", validated_ip, "-j", "DROP"],
            capture_output=True, timeout=5,
        )

        if check.returncode == 0:
            logger.info(f"iptables rule already exists for {validated_ip}")
            return True

        # Add the DROP rule
        result = subprocess.run(
            ["iptables", "-A", "INPUT", "-s", validated_ip, "-j", "DROP"],
            capture_output=True, text=True, timeout=5,
        )

        if result.returncode == 0:
            logger.info(f"iptables: Blocked {validated_ip}")
            return True
        else:
            logger.error(f"iptables failed: {result.stderr.strip()}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"iptables command timed out for {validated_ip}")
        return False
    except PermissionError:
        logger.error("Insufficient permissions for iptables (need root/CAP_NET_ADMIN)")
        return False
    except FileNotFoundError:
        logger.error("iptables binary not found")
        return False


def unblock_ip_iptables(ip: str) -> bool:
    """Remove an iptables DROP rule for an IP."""
    if not IS_LINUX:
        return False

    validated_ip = validate_ip_strict(ip)

    try:
        result = subprocess.run(
            ["iptables", "-D", "INPUT", "-s", validated_ip, "-j", "DROP"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Failed to unblock {validated_ip} in iptables: {e}")
        return False


# ===================================================================
# Consumer
# ===================================================================

async def process_block_command(data: dict) -> None:
    """Consumer handler for stream:block_commands."""
    raw_ip = data.get("src_ip", "")
    reason = data.get("reason", "automated")[:500]  # Enforce max length
    alert_id = data.get("alert_id")
    tenant_id = data.get("tenant_id", None) or None  # Multi-tenancy

    if not raw_ip:
        logger.warning("Block command missing src_ip — skipping")
        return

    # Validate IP
    try:
        validated_ip = validate_ip_strict(raw_ip)
    except ValueError as e:
        logger.error(f"Invalid IP rejected: {e}")
        return

    # Skip if already blocked (tenant-scoped)
    if await redis_manager.is_blocked(validated_ip, tenant_id=tenant_id):
        logger.debug(f"IP {validated_ip} already blocked — skipping")
        return

    # 1. Block in Redis (immediate effect for the pipeline, tenant-scoped)
    await redis_manager.add_blocked_ip(validated_ip, tenant_id=tenant_id)

    # 2. Block in OS firewall (if enabled and on Linux)
    os_blocked = False
    if ENABLE_OS_FIREWALL:
        os_blocked = block_ip_iptables(validated_ip)
    else:
        logger.info(f"OS firewall disabled — soft-block only for {validated_ip}")

    # 3. Persist to PostgreSQL
    try:
        async with async_session() as session:
            record = BlockedIP(
                ip_address=validated_ip,
                reason=reason,
                tenant_id=tenant_id,
                alert_id=alert_id if alert_id and alert_id != "unknown" else None,
            )
            session.add(record)
            await session.commit()
    except Exception as e:
        logger.error(f"DB write failed for blocked IP {validated_ip}: {e}")

    # 4. Update metrics
    FIREWALL_BLOCKS.labels(source="automated").inc()
    blocked_count = len(await redis_manager.get_blocked_ips(tenant_id=tenant_id))
    BLOCKED_IPS_COUNT.set(blocked_count)

    logger.warning(
        f"🚨 IP BLOCKED: {validated_ip}",
        extra={
            "src_ip": validated_ip,
            "reason": reason,
            "os_firewall": os_blocked,
            "tenant_id": tenant_id,
        },
    )


_shutdown_event = asyncio.Event()


async def consumer_loop() -> None:
    """Main consumer loop."""
    logger.info("Firewall consumer started — reading from stream:block_commands")

    while not _shutdown_event.is_set():
        try:
            # Backpressure Check
            lag = await redis_manager.stream_length("stream:block_commands")
            STREAM_LAG.labels(stream="stream:block_commands", group="firewall_group").set(lag)
            if lag > 1000:
                logger.warning(f"Backpressure detected in stream:block_commands! Lag: {lag}")

            messages = await redis_manager.consume(
                stream="stream:block_commands",
                group="firewall_group",
                consumer="fw_worker_1",
                count=10,
                block_ms=5000,
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
                            try:
                                validated = BlockRequest(**data)
                            except ValidationError as e:
                                logger.warning(f"Validation error in stream:block_commands for msg {msg_id}: {len(e.errors())} field errors")
                                await redis_manager.ack("stream:block_commands", "firewall_group", msg_id)
                                continue

                            await process_block_command(data)
                            await redis_manager.ack(
                                "stream:block_commands", "firewall_group", msg_id
                            )
                        except Exception as e:
                            logger.error(f"Block command failed for {msg_id}: {e}")

        except asyncio.CancelledError:
            logger.info("Firewall consumer loop cancelled — finishing")
            break
        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            await asyncio.sleep(5)


# ===================================================================
# Startup: load existing blocks from DB into Redis
# ===================================================================

async def load_blocks_from_db() -> None:
    """Load active blocked IPs from PostgreSQL into Redis cache (tenant-scoped)."""
    try:
        async with async_session() as session:
            result = await session.execute(
                text("SELECT ip_address, tenant_id FROM blocked_ips WHERE is_active = TRUE")
            )
            count = 0
            for row in result:
                tenant_id = str(row[1]) if row[1] else None
                await redis_manager.add_blocked_ip(str(row[0]), tenant_id=tenant_id)
                count += 1

            BLOCKED_IPS_COUNT.set(count)
            logger.info(f"Loaded {count} blocked IPs from database into Redis")
    except Exception as e:
        logger.warning(f"Could not load blocked IPs from DB: {e}")


# ===================================================================
# FastAPI
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    await load_blocks_from_db()
    consumer_task = asyncio.create_task(consumer_loop())
    logger.info("Firewall Controller service started")
    yield
    _shutdown_event.set()
    consumer_task.cancel()
    try:
        await asyncio.wait_for(consumer_task, timeout=10)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    await redis_manager.close()


app = FastAPI(title="Firewall Controller", lifespan=lifespan)
app.add_route("/metrics", metrics_endpoint)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        service="firewall",
        uptime_seconds=round(time.time() - SERVICE_START_TIME, 1),
    )


@app.get("/ready")
async def ready():
    """Readiness check to verify Redis and DB connectivity."""
    status = {"status": "ready", "redis": "connected", "db": "connected"}
    try:
        await redis_manager.client.ping()
    except Exception as e:
        status["status"] = "not_ready"
        status["redis"] = f"error: {e}"

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        status["status"] = "not_ready"
        status["db"] = f"error: {e}"
        
    return status


@app.get("/api/firewall/status")
async def get_status():
    """Returns the current blocklist (for dashboard)."""
    blocked = list(await redis_manager.get_blocked_ips())
    return {"blocked_ips": blocked, "count": len(blocked)}


if __name__ == "__main__":
    logger.info("Starting Firewall Controller on port 8004...")
    uvicorn.run(app, host="0.0.0.0", port=8004)
