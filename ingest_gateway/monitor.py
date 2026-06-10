"""
Sensor health monitor for the Ingest Gateway.

Background task that detects offline sensors (no heartbeat for 5 minutes)
and updates their status in the database.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_

from shared.database import async_session, Sensor, Notification

logger = logging.getLogger(__name__)

MONITOR_INTERVAL = 60  # Check every 60 seconds
OFFLINE_THRESHOLD = timedelta(minutes=5)

_shutdown = asyncio.Event()


async def start_monitor():
    """Background task to detect offline sensors."""
    logger.info("Sensor monitor started")
    
    while not _shutdown.is_set():
        try:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - OFFLINE_THRESHOLD
            
            async with async_session() as session:
                # Find active sensors that haven't sent a heartbeat recently
                result = await session.execute(
                    select(Sensor).where(
                        and_(
                            Sensor.status == "active",
                            Sensor.last_heartbeat < cutoff,
                        )
                    )
                )
                stale_sensors = list(result.scalars().all())
                
                for sensor in stale_sensors:
                    sensor.status = "offline"
                    logger.warning(
                        f"Sensor '{sensor.name}' marked offline "
                        f"(last heartbeat: {sensor.last_heartbeat})"
                    )
                    
                    # Create notification for tenant
                    notification = Notification(
                        tenant_id=sensor.tenant_id,
                        type="sensor",
                        title=f"Sensor '{sensor.name}' is offline",
                        message=(
                            f"Sensor '{sensor.name}' hasn't sent a heartbeat in 5 minutes. "
                            f"Check the sensor's network connection and ensure it is running."
                        ),
                        data={"sensor_id": str(sensor.id), "sensor_name": sensor.name},
                    )
                    session.add(notification)
                
                if stale_sensors:
                    await session.commit()
                    logger.info(f"Marked {len(stale_sensors)} sensor(s) as offline")
                    
        except Exception as e:
            logger.error(f"Sensor monitor error: {e}")
        
        await asyncio.sleep(MONITOR_INTERVAL)


async def stop_monitor():
    """Signal the monitor to stop."""
    _shutdown.set()
