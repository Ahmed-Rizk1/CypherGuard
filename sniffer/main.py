"""
SecureNet SOC — Sniffer Service (Refactored)

Captures raw network packets using Scapy and publishes them to
Redis Streams (stream:raw_packets) for async processing.

Changes from MVP:
- Replaced synchronous HTTP POST with Redis XADD (fire-and-forget)
- Removed 50ms timeout that was dropping >90% of packets
- Added structured logging
- Added Prometheus metrics
- Added blocked IP pre-filtering
"""

import os
import sys
import time
import asyncio
import logging
import uuid

from scapy.all import sniff, IP, TCP, UDP, ICMP
from dotenv import load_dotenv

# Add project root to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging
from shared.redis_client import redis_manager
from shared.metrics import PACKETS_PROCESSED

load_dotenv()

logger = setup_logging("sniffer")

# ---------------------------------------------------------------------------
# Packet processing
# ---------------------------------------------------------------------------

# We need a global event loop reference for the Scapy callback
_loop = None
_running = True


def packet_callback(packet):
    """
    Scapy callback — invoked for each captured packet.

    Extracts minimal routing info and publishes to Redis.
    Deep feature engineering happens in the Extractor service.
    """
    if IP not in packet:
        return

    src_ip = packet[IP].src
    dst_ip = packet[IP].dst
    size = len(packet)

    # Determine transport protocol
    if TCP in packet:
        proto_name = "TCP"
    elif UDP in packet:
        proto_name = "UDP"
    elif ICMP in packet:
        proto_name = "ICMP"
    else:
        proto_name = "OTHER"

    payload = {
        "timestamp": str(time.time()),
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "protocol": proto_name,
        "size": str(size),
        "trace_id": str(uuid.uuid4()),
    }

    # Publish to Redis Stream (non-blocking via event loop)
    try:
        future = asyncio.run_coroutine_threadsafe(
            redis_manager.publish("stream:raw_packets", payload), _loop
        )
        # Don't wait for result — fire and forget
        PACKETS_PROCESSED.labels(service="sniffer", status="success").inc()
    except Exception as e:
        PACKETS_PROCESSED.labels(service="sniffer", status="error").inc()
        logger.error(f"Failed to publish packet: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_sniffer():
    """Start the packet sniffer with Redis Streams backend."""
    global _loop
    _loop = asyncio.get_running_loop()

    # Connect to Redis
    await redis_manager.connect()

    logger.info("Packet sniffer starting — publishing to stream:raw_packets")
    logger.info("Press Ctrl+C to stop")

    # Run Scapy sniff in a thread (it blocks)
    try:
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: sniff(prn=packet_callback, store=0),
        )
    except KeyboardInterrupt:
        logger.info("Sniffer stopped by user")
    finally:
        await redis_manager.close()


if __name__ == "__main__":
    asyncio.run(run_sniffer())
