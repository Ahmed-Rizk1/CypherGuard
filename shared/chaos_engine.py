"""
Chaos Engineering Module for SecureNet SOC.

Simulates production failures (network latency, message drops, consumer crashes).
Strictly controlled by the CHAOS_MODE environment variable. Safely defaults to OFF.

Usage:
    from shared.chaos_engine import chaos

    await chaos.inject_redis_latency("stream:features")
    if chaos.should_drop_message(probability=0.01):
        continue
"""

import os
import time
import random
import asyncio
import logging

logger = logging.getLogger(__name__)


class ChaosEngine:
    """Singleton Chaos Engine."""
    
    def __init__(self):
        # Cache environment variable at startup. NEVER check per message.
        self.is_enabled = os.getenv("CHAOS_MODE", "false").lower() == "true"
        if self.is_enabled:
            logger.critical("⚠️ CHAOS_MODE is ENABLED. System is running with simulated failures. ⚠️")

    async def inject_redis_latency(self, stream_name: str, max_delay_ms: int = 500) -> None:
        """Inject random async delay to simulate Redis or network slowness."""
        if not self.is_enabled:
            return
            
        delay_ms = random.randint(0, max_delay_ms)
        if delay_ms > 50: # Only log noticeable delays
            logger.warning(f"[CHAOS] Injecting {delay_ms}ms latency into {stream_name} read")
        
        await asyncio.sleep(delay_ms / 1000.0)

    def should_drop_message(self, probability: float = 0.01) -> bool:
        """Return True if the message should be dropped (simulating packet loss)."""
        if not self.is_enabled:
            return False
            
        should_drop = random.random() < probability
        if should_drop:
            logger.warning(f"[CHAOS] Dropping message (probability={probability})")
        return should_drop

    def simulate_crash(self, probability: float = 0.001) -> None:
        """Simulate an unhandled exception crashing the current processing loop."""
        if not self.is_enabled:
            return
            
        if random.random() < probability:
            logger.critical(f"[CHAOS] Simulating fatal consumer crash (probability={probability})")
            raise RuntimeError("ChaosEngine injected fatal crash")

# Global singleton
chaos = ChaosEngine()
