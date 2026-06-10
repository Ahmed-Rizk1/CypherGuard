"""
SecureNet Sensor Agent — Remote Network Monitoring

Deploys on customer networks to capture traffic and send to SecureNet platform.
Authenticates via API key, sends packets in batches, maintains heartbeat.

Environment Variables:
  SECURENET_API_KEY     — Sensor API key (sn_xxxxx)
  SECURENET_ENDPOINT    — Platform ingest URL (e.g., https://ingest.securenet.io)
  SENSOR_INTERFACE      — Network interface to sniff (default: auto-detect)
"""

import os
import sys
import time
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("securenet.sensor")

# Configuration
API_KEY = os.getenv("SECURENET_API_KEY", "")
ENDPOINT = os.getenv("SECURENET_ENDPOINT", "http://localhost:8007")
SENSOR_INTERFACE = os.getenv("SENSOR_INTERFACE", "")
BATCH_SIZE = int(os.getenv("SENSOR_BATCH_SIZE", "100"))
BATCH_INTERVAL = float(os.getenv("SENSOR_BATCH_INTERVAL", "1.0"))
HEARTBEAT_INTERVAL = int(os.getenv("SENSOR_HEARTBEAT_INTERVAL", "30"))

# Statistics
_start_time = time.time()
_packets_sent = 0
_packets_buffered = 0


class PacketBuffer:
    """Thread-safe buffer for batching packets before send."""
    
    def __init__(self, max_size: int = 1000):
        self.packets: list[dict] = []
        self.max_size = max_size
        self._lock = asyncio.Lock()
    
    async def add(self, packet: dict):
        async with self._lock:
            if len(self.packets) < self.max_size:
                self.packets.append(packet)
    
    async def flush(self) -> list[dict]:
        async with self._lock:
            batch = self.packets[:BATCH_SIZE]
            self.packets = self.packets[BATCH_SIZE:]
            return batch
    
    @property
    def size(self) -> int:
        return len(self.packets)


buffer = PacketBuffer()


async def send_batch(client: httpx.AsyncClient, packets: list[dict]) -> bool:
    """Send a batch of packets to the ingest gateway."""
    global _packets_sent
    try:
        resp = await client.post(
            f"{ENDPOINT}/v1/ingest/packets",
            json={"packets": packets},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            _packets_sent += len(packets)
            return True
        else:
            logger.error(f"Ingest failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Network error sending batch: {e}")
        return False


async def send_heartbeat(client: httpx.AsyncClient):
    """Send heartbeat to the platform."""
    try:
        resp = await client.post(
            f"{ENDPOINT}/v1/ingest/heartbeat",
            json={
                "version": "1.0.0",
                "uptime_seconds": time.time() - _start_time,
                "packets_sent": _packets_sent,
                "system_info": {
                    "platform": sys.platform,
                    "python_version": sys.version,
                },
            },
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            logger.debug("Heartbeat sent successfully")
        else:
            logger.warning(f"Heartbeat failed: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Heartbeat error: {e}")


async def capture_loop():
    """
    Capture packets from the network interface.
    
    Uses scapy if available, otherwise falls back to simulated traffic
    for testing/demo purposes.
    """
    try:
        from scapy.all import sniff, IP
        
        def packet_handler(pkt):
            if IP in pkt:
                asyncio.get_event_loop().call_soon_threadsafe(
                    asyncio.ensure_future,
                    buffer.add({
                        "src_ip": pkt[IP].src,
                        "size": len(pkt),
                        "protocol": pkt[IP].proto_name if hasattr(pkt[IP], 'proto_name') else "OTHER",
                    })
                )
        
        logger.info(f"Starting packet capture on {SENSOR_INTERFACE or 'default interface'}")
        sniff(
            iface=SENSOR_INTERFACE or None,
            prn=packet_handler,
            store=False,
        )
    except ImportError:
        logger.warning("Scapy not available — running in DEMO mode with simulated traffic")
        import random
        demo_ips = [f"192.168.1.{i}" for i in range(1, 255)]
        
        while True:
            await buffer.add({
                "src_ip": random.choice(demo_ips),
                "size": random.randint(64, 1500),
                "protocol": random.choice(["TCP", "UDP", "ICMP"]),
            })
            await asyncio.sleep(random.uniform(0.001, 0.05))


async def batch_sender_loop():
    """Periodically flush buffer and send batches."""
    async with httpx.AsyncClient() as client:
        while True:
            if buffer.size > 0:
                batch = await buffer.flush()
                if batch:
                    success = await send_batch(client, batch)
                    if not success:
                        # Re-add to buffer for retry
                        for pkt in batch:
                            await buffer.add(pkt)
            await asyncio.sleep(BATCH_INTERVAL)


async def heartbeat_loop():
    """Send periodic heartbeats."""
    async with httpx.AsyncClient() as client:
        while True:
            await send_heartbeat(client)
            await asyncio.sleep(HEARTBEAT_INTERVAL)


async def main():
    if not API_KEY:
        logger.error("SECURENET_API_KEY not set. Cannot start sensor.")
        sys.exit(1)
    
    logger.info(f"SecureNet Sensor starting — endpoint: {ENDPOINT}")
    
    # Run all tasks concurrently
    await asyncio.gather(
        capture_loop(),
        batch_sender_loop(),
        heartbeat_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
