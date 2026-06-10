"""
SecureNet SOC — Decision Timeout Listener (SaaS Multi-Tenant)

Subscribes to Redis Keyspace Notifications for expired pending_decision keys.
Implements atomic fallback (fail-secure) using Lua scripting to prevent 
race conditions with mobile approvals.

Multi-tenancy: Keys follow pattern t:{tenant_id}:pending_decision:{alert_id}
"""

import os
import sys
import json
import time
import asyncio
import logging
from dotenv import load_dotenv

import redis.asyncio as aioredis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging, trace_id_ctx, get_trace_id
from shared.redis_client import redis_manager
from shared.metrics import MOBILE_TIMEOUT_FALLBACKS
from shared.lua_scripts import LUA_EXECUTE_DECISION, get_execute_decision_keys

load_dotenv()
logger = setup_logging("timeout_listener")


def _parse_tenant_key(key: str):
    """
    Parse a tenant-scoped pending_decision key.
    
    Formats:
      - t:{tenant_id}:pending_decision:{alert_id}
      - pending_decision:{alert_id}  (legacy, no tenant)
    
    Returns (tenant_id, alert_id) tuple.
    """
    if key.startswith("t:"):
        # t:{tenant_id}:pending_decision:{alert_id}
        parts = key.split(":", 3)  # ['t', tenant_id, 'pending_decision', alert_id]
        if len(parts) >= 4 and parts[2] == "pending_decision":
            return parts[1], parts[3]
    
    if key.startswith("pending_decision:"):
        return None, key.split(":", 1)[1]
    
    return None, None


async def handle_expiration(tenant_id: str, alert_id: str):
    """Triggered when a pending_decision key expires."""
    try:
        prefix = f"t:{tenant_id}:" if tenant_id else ""
        payloads_key = f"{prefix}decision_payloads"
        
        # 1. Fetch the payload from the hash
        payload_str = await redis_manager.client.hget(payloads_key, alert_id)
        if not payload_str:
            # Payload missing or already processed
            return

        payload = json.loads(payload_str)
        
        # 2. We need a new trace ID for the fallback execution
        execution_trace = get_trace_id()

        # 3. Attempt atomic execution via Lua (tenant-scoped keys)
        result = await redis_manager.execute_lua(
            LUA_EXECUTE_DECISION,
            keys=get_execute_decision_keys(alert_id, tenant_id=tenant_id),
            args=[alert_id, "BLOCK", "timeout", execution_trace, "system", str(time.time())]
        )

        if result == 1:
            logger.warning(f"Timeout reached for alert {alert_id}. Executing fallback (FAIL-SECURE).", extra={"alert_id": alert_id})
            
            block_command = {
                "src_ip": payload.get("ip"),
                "reason": payload.get("reason", "unknown"),
                "alert_id": alert_id,
                "tenant_id": tenant_id or "",
                "trace_id": execution_trace
            }
            
            # Publish to firewall
            await redis_manager.publish("stream:block_commands", block_command)
            MOBILE_TIMEOUT_FALLBACKS.inc()
            logger.info(f"Fallback executed for alert {alert_id}")
        else:
            logger.debug(f"Timeout ignored for {alert_id}: Decision was already made by mobile.")

    except Exception as e:
        logger.error(f"Error handling expiration for {alert_id}: {e}", exc_info=True)


async def main():
    await redis_manager.connect()
    
    # Needs a dedicated pubsub connection
    pubsub = redis_manager.client.pubsub()
    await pubsub.psubscribe("__keyevent@0__:expired")
    
    logger.info("Decision Timeout Listener started — waiting for key expirations...")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                key = message["data"]
                # Match both tenant-scoped and legacy keys
                tenant_id, alert_id = _parse_tenant_key(key)
                if alert_id:
                    # Process in background to avoid blocking the listener
                    asyncio.create_task(handle_expiration(tenant_id, alert_id))
    except asyncio.CancelledError:
        logger.info("Listener cancelled")
    finally:
        await pubsub.close()
        await redis_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
