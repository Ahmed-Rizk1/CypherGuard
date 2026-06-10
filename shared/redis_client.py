"""
Redis client for SecureNet SOC — unified state store and message broker (SaaS Multi-Tenant).

Provides:
- Redis Streams (publish/consume for the event-driven pipeline)
- Connection stats with sliding time window (replacing unbounded in-memory dict)
- Alert cooldown tracking (prevents duplicate LLM calls per IP)
- Blocked IPs cache (set operations) — per-tenant
- Live metrics for dashboard — per-tenant

All key-based operations support multi-tenancy via tenant_id parameter.
Keys are prefixed with `t:{tenant_id}:` when a tenant_id is provided.
Global keys (token blacklist, account lockout) remain unprefixed.

Usage:
    from shared.redis_client import redis_manager

    # At startup
    await redis_manager.connect()

    # Publish a message
    await redis_manager.publish("stream:raw_packets", {"src_ip": "1.2.3.4", ...})

    # Consume messages
    messages = await redis_manager.consume("stream:raw_packets", "extractor_group", "worker_1")

    # Tenant-scoped operations
    await redis_manager.add_blocked_ip("1.2.3.4", tenant_id="abc-123")
"""

import os
import time
import json
import logging
from typing import Optional, Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class RedisManager:
    """Async Redis client wrapper for all SOC operations."""

    def __init__(self):
        self.client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection pool."""
        self.client = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=5,
            socket_keepalive=True,
            retry_on_timeout=True,
        )
        # Verify connection
        await self.client.ping()
        logger.info("Redis connected", extra={"redis_url": REDIS_URL.split("@")[-1]})

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")

    async def config_set(self, name: str, value: str) -> None:
        """Set a Redis configuration parameter."""
        await self.client.config_set(name, value)
        
    async def execute_lua(self, script: str, keys: list = None, args: list = None) -> Any:
        """Execute a Lua script atomically."""
        return await self.client.eval(script, len(keys) if keys else 0, *(keys or []), *(args or []))

    # -------------------------------------------------------------------
    # Tenant key helper
    # -------------------------------------------------------------------

    @staticmethod
    def _tenant_key(base_key: str, tenant_id: str = None) -> str:
        """Prefix a key with tenant namespace if tenant_id is provided."""
        if tenant_id:
            return f"t:{tenant_id}:{base_key}"
        return base_key

    # -----------------------------------------------------------------------
    # Stream Operations (message broker)
    # -----------------------------------------------------------------------

    async def publish(self, stream: str, data: dict, maxlen: int = 10000) -> str:
        """
        Add a message to a Redis Stream.

        Args:
            stream: Stream name (e.g., "stream:raw_packets")
            data: Dict of string key-value pairs
            maxlen: Approximate max stream length (auto-trimmed)

        Returns:
            Message ID assigned by Redis.
        """
        # Redis Streams require all values to be strings
        str_data = {k: str(v) if not isinstance(v, str) else v for k, v in data.items()}
        msg_id = await self.client.xadd(stream, str_data, maxlen=maxlen, approximate=True)
        return msg_id

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list:
        """
        Read messages from a Redis Streams consumer group.

        Creates the consumer group on first call.
        Returns list of (stream_name, [(msg_id, data_dict), ...]) tuples.
        """
        # Ensure consumer group exists
        try:
            await self.client.xgroup_create(stream, group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        messages = await self.client.xreadgroup(
            group, consumer, {stream: ">"}, count=count, block=block_ms
        )
        return messages or []

    async def ack(self, stream: str, group: str, msg_id: str) -> None:
        """Acknowledge a processed message."""
        await self.client.xack(stream, group, msg_id)

    async def stream_length(self, stream: str) -> int:
        """Get the current length of a stream (for monitoring)."""
        try:
            return await self.client.xlen(stream)
        except Exception:
            return 0

    # -----------------------------------------------------------------------
    # Connection Stats (sliding window — tenant-scoped)
    # -----------------------------------------------------------------------

    async def update_conn_stats(self, ip: str, packet_size: int, ttl: int = 300, tenant_id: str = None) -> None:
        """
        Record a packet for an IP address using a Redis sorted set.

        Each entry is scored by timestamp (ms), enabling efficient sliding window
        queries. TTL ensures automatic cleanup of stale IPs.

        Args:
            ip: Source IP address
            packet_size: Packet size in bytes
            ttl: Time-to-live for the sorted set key (seconds)
            tenant_id: Tenant identifier for multi-tenancy
        """
        key = self._tenant_key(f"conn:{ip}:packets", tenant_id)
        now_ms = int(time.time() * 1000)
        member = f"{now_ms}:{packet_size}"

        pipe = self.client.pipeline()
        pipe.zadd(key, {member: now_ms})
        pipe.zremrangebyscore(key, 0, now_ms - (ttl * 1000))  # Trim old entries
        pipe.zremrangebyrank(key, 0, -10001)  # Cap at max 10,000 entries (prevents OOM on DDoS)
        pipe.expire(key, ttl + 60)  # Key expires after inactivity
        await pipe.execute()

    async def get_conn_features(self, ip: str, window_seconds: int = 30, tenant_id: str = None) -> dict:
        """
        Compute traffic features for an IP over a sliding time window.

        Returns a dict with the feature values that the ML model expects.
        """
        key = self._tenant_key(f"conn:{ip}:packets", tenant_id)
        now_ms = int(time.time() * 1000)
        window_start = now_ms - (window_seconds * 1000)

        # Get all entries within the window
        entries = await self.client.zrangebyscore(key, window_start, now_ms)

        if not entries:
            return {
                "packet_count": 0,
                "total_bytes": 0,
                "packets_per_sec": 0.0,
                "bytes_per_sec": 0.0,
                "avg_packet_size": 0.0,
                "flow_duration": 0.0,
                "fwd_pkt_len_mean": 0.0,
                "fwd_pkt_len_std": 0.0,
                "flow_iat_mean": 0.0,
                "flow_iat_std": 0.0,
                "small_packet_ratio": 0.0,
            }

        # Parse entries: "timestamp_ms:packet_size"
        sizes = []
        timestamps = []
        for entry in entries:
            parts = entry.split(":")
            if len(parts) >= 2:
                timestamps.append(int(parts[0]))
                sizes.append(int(parts[1]))

        packet_count = len(sizes)
        total_bytes = sum(sizes)
        avg_size = total_bytes / packet_count if packet_count > 0 else 0.0

        # Inter-arrival times
        iats = []
        if len(timestamps) > 1:
            sorted_ts = sorted(timestamps)
            iats = [(sorted_ts[i+1] - sorted_ts[i]) / 1000.0 for i in range(len(sorted_ts) - 1)]

        iat_mean = sum(iats) / len(iats) if iats else 0.0
        iat_std = (sum((x - iat_mean) ** 2 for x in iats) / len(iats)) ** 0.5 if iats else 0.0

        # Packet size statistics
        size_mean = avg_size
        size_std = (sum((s - size_mean) ** 2 for s in sizes) / len(sizes)) ** 0.5 if sizes else 0.0

        # Flow duration
        flow_duration = (max(timestamps) - min(timestamps)) / 1000.0 if len(timestamps) > 1 else 0.0

        # Small packet ratio (< 100 bytes, indicating scans)
        small_count = sum(1 for s in sizes if s < 100)
        small_ratio = small_count / packet_count if packet_count > 0 else 0.0

        return {
            "packet_count": packet_count,
            "total_bytes": total_bytes,
            "packets_per_sec": round(packet_count / window_seconds, 2),
            "bytes_per_sec": round(total_bytes / window_seconds, 2),
            "avg_packet_size": round(avg_size, 2),
            "flow_duration": round(flow_duration, 4),
            "fwd_pkt_len_mean": round(size_mean, 2),
            "fwd_pkt_len_std": round(size_std, 2),
            "flow_iat_mean": round(iat_mean, 6),
            "flow_iat_std": round(iat_std, 6),
            "small_packet_ratio": round(small_ratio, 4),
        }

    # -----------------------------------------------------------------------
    # Alert Cooldown (prevents duplicate LLM calls per IP — tenant-scoped)
    # -----------------------------------------------------------------------

    async def should_alert(self, ip: str, cooldown_seconds: int = 60, tenant_id: str = None) -> bool:
        """
        Check if this IP should trigger a new alert.

        Returns True if no alert was sent in the last `cooldown_seconds`.
        Uses Redis SET NX EX for atomic check-and-set.
        """
        key = self._tenant_key(f"cooldown:{ip}", tenant_id)
        result = await self.client.set(key, "1", nx=True, ex=cooldown_seconds)
        return result is not None  # True = key was set (no recent alert)

    # -----------------------------------------------------------------------
    # Blocked IPs Cache (tenant-scoped)
    # -----------------------------------------------------------------------

    async def add_blocked_ip(self, ip: str, tenant_id: str = None) -> None:
        """Add an IP to the active blocklist."""
        key = self._tenant_key("blocked_ips", tenant_id)
        await self.client.sadd(key, ip)

    async def remove_blocked_ip(self, ip: str, tenant_id: str = None) -> None:
        """Remove an IP from the active blocklist."""
        key = self._tenant_key("blocked_ips", tenant_id)
        await self.client.srem(key, ip)

    async def is_blocked(self, ip: str, tenant_id: str = None) -> bool:
        """Check if an IP is in the active blocklist."""
        key = self._tenant_key("blocked_ips", tenant_id)
        return await self.client.sismember(key, ip)

    async def get_blocked_ips(self, tenant_id: str = None) -> set:
        """Get all currently blocked IPs."""
        key = self._tenant_key("blocked_ips", tenant_id)
        return await self.client.smembers(key)

    # -----------------------------------------------------------------------
    # Live Metrics (for dashboard — tenant-scoped)
    # -----------------------------------------------------------------------

    async def set_live_metrics(self, metrics: dict, tenant_id: str = None) -> None:
        """Store current aggregate metrics for dashboard polling."""
        key = self._tenant_key("live_metrics", tenant_id)
        await self.client.set(key, json.dumps(metrics), ex=10)

    async def get_live_metrics(self, tenant_id: str = None) -> dict:
        """Retrieve current aggregate metrics."""
        key = self._tenant_key("live_metrics", tenant_id)
        raw = await self.client.get(key)
        if raw:
            return json.loads(raw)
        return {"packets_per_sec": 0, "bytes_per_sec": 0, "active_connections": 0}

    # -----------------------------------------------------------------------
    # Recent Alerts (for dashboard feed — tenant-scoped)
    # -----------------------------------------------------------------------

    async def push_recent_alert(self, alert: dict, max_alerts: int = 100, tenant_id: str = None) -> None:
        """Push an alert to the recent alerts list (newest first)."""
        key = self._tenant_key("recent_alerts", tenant_id)
        await self.client.lpush(key, json.dumps(alert))
        await self.client.ltrim(key, 0, max_alerts - 1)

    async def get_recent_alerts(self, count: int = 50, tenant_id: str = None) -> list[dict]:
        """Get the N most recent alerts."""
        key = self._tenant_key("recent_alerts", tenant_id)
        raw_list = await self.client.lrange(key, 0, count - 1)
        return [json.loads(item) for item in raw_list]


# Module-level singleton
redis_manager = RedisManager()
