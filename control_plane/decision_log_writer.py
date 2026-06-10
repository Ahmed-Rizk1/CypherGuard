"""
SecureNet SOC — Async Decision Log Writer

Consumes decision execution records from `stream:decision_logs` in batches.
Performs bulk `ON CONFLICT DO NOTHING` inserts into PostgreSQL.
Only after DB confirmation, deletes the original payload from Redis `decision_payloads`.
"""

import os
import sys
import json
import time
import asyncio
import logging
from typing import List

from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging
from shared.redis_client import redis_manager
from shared.database import async_session, DecisionLog
from shared.metrics import (
    DECISIONS_EXECUTED, DECISION_DB_WRITE_LATENCY, DECISION_QUEUE_SIZE
)

load_dotenv()
logger = setup_logging("decision_writer")

BATCH_SIZE = int(os.getenv("DECISION_LOG_BATCH_SIZE", "100"))
BATCH_TIMEOUT = float(os.getenv("DECISION_LOG_BATCH_TIMEOUT", "1.0"))

_shutdown_event = asyncio.Event()

async def process_batch(records: List[dict], msg_ids: List[str]):
    """Write batch to DB, then remove from Redis payload hash."""
    if not records:
        return

    start_time = time.time()
    success = False
    
    # 1. Bulk Database Insert
    try:
        async with async_session() as session:
            # We use Postgres 'ON CONFLICT DO NOTHING' for pure idempotency
            stmt = insert(DecisionLog).values([
                {
                    "alert_id": r["alert_id"],
                    "action": r["action"],
                    "source": r["source"],
                    "trace_id": r["trace_id"],
                    "tenant_id": r.get("tenant_id") or None,
                }
                for r in records
            ]).on_conflict_do_nothing(index_elements=["alert_id"])
            
            await session.execute(stmt)
            await session.commit()
            success = True
            
            # Record latency
            DECISION_DB_WRITE_LATENCY.observe(time.time() - start_time)
            
            for r in records:
                DECISIONS_EXECUTED.labels(source=r["source"]).inc()
                
            logger.info(f"Successfully bulk inserted {len(records)} decision logs.")
    except Exception as e:
        logger.error(f"Failed DB bulk insert (will retry via consumer group): {e}", exc_info=True)
        # We do NOT ack, allowing the consumer group to re-deliver these messages
        return

    # 2. Redis Cleanup (Only runs if DB insert succeeds)
    if success:
        try:
            # Group by tenant for cleanup
            by_tenant: dict[str, list[str]] = {}
            for r in records:
                tid = r.get("tenant_id", "")
                prefix = f"t:{tid}:" if tid else ""
                key = f"{prefix}decision_payloads"
                if key not in by_tenant:
                    by_tenant[key] = []
                by_tenant[key].append(r["alert_id"])
            
            for payloads_key, alert_ids in by_tenant.items():
                if alert_ids:
                    await redis_manager.client.hdel(payloads_key, *alert_ids)
                
            # Ack messages from stream
            if msg_ids:
                await redis_manager.client.xack("stream:decision_logs", "writer_group", *msg_ids)
        except Exception as e:
            logger.error(f"Failed to cleanup Redis after DB write: {e}")
            # Even if cleanup fails, it's safe because the DB is idempotent

async def consumer_loop():
    logger.info("Decision Log Writer started — reading from stream:decision_logs")
    
    # Ensure group exists
    try:
        await redis_manager.client.xgroup_create("stream:decision_logs", "writer_group", mkstream=True)
    except Exception:
        pass
        
    while not _shutdown_event.is_set():
        try:
            lag = await redis_manager.client.xlen("stream:decision_logs")
            DECISION_QUEUE_SIZE.set(lag)
            
            messages = await redis_manager.consume(
                stream="stream:decision_logs",
                group="writer_group",
                consumer="writer_1",
                count=BATCH_SIZE,
                block_ms=int(BATCH_TIMEOUT * 1000),
            )
            
            if messages:
                batch_records = []
                batch_msg_ids = []
                
                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        batch_msg_ids.append(msg_id)
                        batch_records.append({
                            "alert_id": data.get("alert_id"),
                            "action": data.get("action"),
                            "source": data.get("source"),
                            "trace_id": data.get("trace_id"),
                            "tenant_id": data.get("tenant_id", "") or None,
                        })
                
                if batch_records:
                    await process_batch(batch_records, batch_msg_ids)
                    
        except asyncio.CancelledError:
            logger.info("Decision Log Writer cancelled")
            break
        except Exception as e:
            logger.error(f"Writer loop error: {e}", exc_info=True)
            await asyncio.sleep(5)

async def main():
    await redis_manager.connect()
    
    writer_task = asyncio.create_task(consumer_loop())
    
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        _shutdown_event.set()
        writer_task.cancel()
        await redis_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
