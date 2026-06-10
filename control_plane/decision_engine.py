"""
SecureNet SOC — Control Plane Decision Engine

Consumes alerts from stream:decisions_pending (published by LLM Analyzer).
Routes alerts to either AUTO_EXECUTE (stream:block_commands) or 
SEND_TO_MOBILE (stream:mobile_notifications) based on severity.

Implements a watchdog for fail-secure timeout fallbacks.
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
from shared.metrics import (
    MOBILE_ALERTS_SENT, MOBILE_TIMEOUT_FALLBACKS, STREAM_LAG, metrics_endpoint
)

load_dotenv()
logger = setup_logging("decision_engine")

DECISION_TIMEOUT_SECONDS = int(os.getenv("MOBILE_DECISION_TIMEOUT", "60"))

# ===================================================================
# Routing Logic
# ===================================================================

async def route_alert(data: dict) -> None:
    """Route the LLM analysis to either Auto Execute or Mobile."""
    src_ip = data.get("src_ip", "unknown")
    reason = data.get("reason", "unknown")
    alert_id = data.get("alert_id", "unknown")
    severity = data.get("severity", "low").lower()
    tenant_id = data.get("tenant_id", None) or None  # Multi-tenancy
    
    prefix = f"t:{tenant_id}:" if tenant_id else ""
    
    block_payload = {
        "src_ip": src_ip,
        "reason": reason,
        "alert_id": alert_id,
        "tenant_id": tenant_id or "",
        "trace_id": get_trace_id()
    }
    
    if severity in ["high", "critical"]:
        # SEND_TO_MOBILE
        pending_key = f"{prefix}pending_decision:{alert_id}"
        
        now = time.time()
        # Create structured JSON for the pending decision
        pending_payload = {
            "alert_id": alert_id,
            "ip": src_ip,
            "action": "BLOCK",
            "severity": severity,
            "tenant_id": tenant_id or "",
            "trace_id": get_trace_id(),
            "created_at": str(now),
            "expires_at": str(now + DECISION_TIMEOUT_SECONDS),
            "status": "pending",
            "reason": reason
        }
        
        # Store pending decision payload in a hash so it survives expiration
        payloads_key = f"{prefix}decision_payloads"
        await redis_manager.client.hset(payloads_key, alert_id, json.dumps(pending_payload))
        
        # Store the volatile key that triggers the expiration event
        await redis_manager.client.set(pending_key, "1", ex=DECISION_TIMEOUT_SECONDS)
        
        # Add to the Sorted Set index for the fallback scanner
        expiry_key = f"{prefix}decision_expiry_index"
        await redis_manager.client.zadd(expiry_key, {alert_id: float(pending_payload["expires_at"])})
        
        # Publish to mobile gateway
        mobile_payload = {
            "trace_id": get_trace_id(),
            "alert_id": alert_id,
            "tenant_id": tenant_id or "",
            "attack_type": data.get("attack_type", "Unknown"),
            "confidence": data.get("confidence", "0.0"),
            "severity": severity.upper(),
            "recommended_action": "BLOCK_IP",
            "ip": src_ip
        }
        await redis_manager.publish("stream:mobile_notifications", mobile_payload)
        MOBILE_ALERTS_SENT.labels(severity=severity).inc()
        
        logger.info(f"Routed alert {alert_id} to Mobile Gateway", extra={"alert_id": alert_id})
        
    else:
        # AUTO_EXECUTE
        await redis_manager.publish("stream:block_commands", block_payload)
        logger.info(f"Auto-executed alert {alert_id} (Low Severity)", extra={"alert_id": alert_id})

# ===================================================================
# Consumer
# ===================================================================

_shutdown_event = asyncio.Event()

async def consumer_loop() -> None:
    """Main consumer loop reading from stream:decisions_pending."""
    logger.info("Decision Engine started — reading from stream:decisions_pending")

    while not _shutdown_event.is_set():
        try:
            lag = await redis_manager.stream_length("stream:decisions_pending")
            STREAM_LAG.labels(stream="stream:decisions_pending", group="decision_group").set(lag)
            if lag > 1000:
                logger.warning(f"Backpressure detected! Lag: {lag}")

            messages = await redis_manager.consume(
                stream="stream:decisions_pending",
                group="decision_group",
                consumer="decision_worker_1",
                count=10,
                block_ms=5000,
            )

            if messages:
                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        msg_trace_id = data.get("trace_id")
                        if msg_trace_id:
                            trace_id_ctx.set(msg_trace_id)
                        else:
                            trace_id_ctx.set(get_trace_id())

                        try:
                            await route_alert(data)
                            await redis_manager.ack("stream:decisions_pending", "decision_group", msg_id)
                        except Exception as e:
                            logger.error(f"Failed to route alert {msg_id}: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled")
            break
        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            await asyncio.sleep(5)

# ===================================================================
# FastAPI Wrapper
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    
    # Enable Keyspace Notifications for expired events
    try:
        await redis_manager.config_set("notify-keyspace-events", "Ex")
        logger.info("Enabled Redis keyspace notifications for expirations (Ex)")
    except Exception as e:
        logger.error(f"Failed to set notify-keyspace-events: {e}")
        
    consumer_task = asyncio.create_task(consumer_loop())
    logger.info("Decision Engine service started")
    yield
    _shutdown_event.set()
    consumer_task.cancel()
    try:
        await asyncio.wait_for(consumer_task, timeout=10)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    await redis_manager.close()

app = FastAPI(title="Control Plane Decision Engine", lifespan=lifespan)
app.add_route("/metrics", metrics_endpoint)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "decision_engine"}

@app.get("/ready")
async def ready():
    try:
        await redis_manager.client.ping()
        return {"status": "ready", "redis": "connected"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}

if __name__ == "__main__":
    logger.info("Starting Decision Engine on port 8006...")
    uvicorn.run(app, host="0.0.0.0", port=8006)
