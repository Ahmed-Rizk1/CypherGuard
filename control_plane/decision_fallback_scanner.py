"""
SecureNet SOC — Decision Fallback Scanner (SaaS Multi-Tenant)

Acts as a safety net for Redis Keyspace Notifications.
Periodically scans tenant-scoped `decision_expiry_index` Sorted Sets for expired decisions.
Uses the same Lua atomic execution to guarantee idempotency.
"""

import os
import sys
import json
import time
import asyncio
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging, trace_id_ctx, get_trace_id
from shared.redis_client import redis_manager
from shared.metrics import MOBILE_TIMEOUT_FALLBACKS, SCANNER_PROCESSED_ITEMS
from shared.lua_scripts import LUA_EXECUTE_DECISION, get_execute_decision_keys

load_dotenv()
logger = setup_logging("fallback_scanner")

SCANNER_INTERVAL = float(os.getenv("FALLBACK_SCANNER_INTERVAL", "10.0"))


async def process_expired_alert(alert_id: str, tenant_id: str = None):
    """Attempt atomic fallback execution on an expired alert."""
    try:
        prefix = f"t:{tenant_id}:" if tenant_id else ""
        payloads_key = f"{prefix}decision_payloads"
        
        # Fetch payload from hash
        payload_str = await redis_manager.client.hget(payloads_key, alert_id)
        if not payload_str:
            # Already processed and removed
            return False

        payload = json.loads(payload_str)
        
        # We need a new trace ID for the fallback execution
        execution_trace = get_trace_id()

        # Atomic Lua execution (tenant-scoped keys)
        result = await redis_manager.execute_lua(
            LUA_EXECUTE_DECISION,
            keys=get_execute_decision_keys(alert_id, tenant_id=tenant_id),
            args=[alert_id, "BLOCK", "timeout", execution_trace, "system", str(time.time())]
        )

        if result == 1:
            logger.warning(f"[Scanner] Timeout reached for {alert_id}. Executing fallback.", extra={"alert_id": alert_id})
            
            block_command = {
                "src_ip": payload.get("ip"),
                "reason": payload.get("reason", "unknown"),
                "alert_id": alert_id,
                "tenant_id": tenant_id or "",
                "trace_id": execution_trace
            }
            
            await redis_manager.publish("stream:block_commands", block_command)
            MOBILE_TIMEOUT_FALLBACKS.inc()
            return True
            
        return False

    except Exception as e:
        logger.error(f"[Scanner] Failed to process {alert_id}: {e}", exc_info=True)
        return False


async def scan_tenant_index(index_key: str, tenant_id: str = None):
    """Scan a single tenant's expiry index for expired alerts."""
    now = time.time()
    
    expired_alerts = await redis_manager.client.zrangebyscore(index_key, 0, now)
    
    if not expired_alerts:
        return 0
    
    logger.debug(f"[Scanner] Found {len(expired_alerts)} expired alerts in {index_key}")
    
    processed_count = 0
    for alert_id in expired_alerts:
        success = await process_expired_alert(alert_id, tenant_id=tenant_id)
        if success:
            processed_count += 1
    
    SCANNER_PROCESSED_ITEMS.inc(processed_count)
    
    # Cleanup the index
    await redis_manager.client.zrem(index_key, *expired_alerts)
    
    return processed_count


async def scanner_loop():
    logger.info(f"Decision Fallback Scanner started (Interval: {SCANNER_INTERVAL}s)")
    
    while True:
        try:
            # Scan all tenant expiry indexes using pattern matching
            # Pattern: t:*:decision_expiry_index
            cursor = 0
            while True:
                cursor, keys = await redis_manager.client.scan(
                    cursor=cursor, match="t:*:decision_expiry_index", count=100
                )
                for key in keys:
                    # Extract tenant_id from key: t:{tenant_id}:decision_expiry_index
                    parts = key.split(":", 2)
                    tenant_id = parts[1] if len(parts) >= 3 else None
                    await scan_tenant_index(key, tenant_id=tenant_id)
                
                if cursor == 0:
                    break
            
            # Also scan legacy (non-tenanted) index
            legacy_exists = await redis_manager.client.exists("decision_expiry_index")
            if legacy_exists:
                await scan_tenant_index("decision_expiry_index", tenant_id=None)
                
        except Exception as e:
            logger.error(f"[Scanner] Loop error: {e}", exc_info=True)
            
        await asyncio.sleep(SCANNER_INTERVAL)


async def main():
    await redis_manager.connect()
    
    try:
        await scanner_loop()
    except KeyboardInterrupt:
        logger.info("Fallback scanner stopped.")
    finally:
        await redis_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
