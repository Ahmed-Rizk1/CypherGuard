"""
SecureNet SOC — LLM Analyzer Service (Refactored)

Consumes alerts from stream:alerts, analyzes them via GPT-4o-mini,
and publishes block commands to stream:block_commands.

Changes from MVP:
- Redis Streams consumer (replaces HTTP endpoint)
- Traffic-profile caching (avoids repeated LLM calls for similar attacks)
- Circuit breaker (stops calling LLM after consecutive failures)
- Heuristic fallback (free classification when LLM is unavailable)
- PostgreSQL persistence (replaces dashboard_logs.json)
- Optimized prompt with system role + JSON response format
- Cost controls: cooldown already applied at ML Engine level
"""

import os
import sys
import time
import json
import hashlib
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging, trace_id_ctx, get_trace_id
from shared.redis_client import redis_manager
from shared.circuit_breaker import CircuitBreaker
from shared.database import async_session, Alert
from sqlalchemy import text
from shared.validators import HealthResponse, AlertData
from pydantic import ValidationError
from shared.metrics import (
    LLM_CALLS, LLM_LATENCY, ALERTS_GENERATED, CIRCUIT_BREAKER_STATE, STREAM_LAG,
    metrics_endpoint,
)
from shared.llm_config import (
    get_prompt, build_user_prompt_from_alert, validate_llm_response,
    LLM_PROMPT_VERSION,
)

load_dotenv()

logger = setup_logging("llm_analyzer")

SERVICE_START_TIME = time.time()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "15"))
CACHE_TTL = int(os.getenv("LLM_CACHE_TTL", "3600"))

# LLM Client (prefers Groq, falls back to OpenRouter)
if GROQ_API_KEY:
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
        timeout=LLM_TIMEOUT,
    )
    logger.info("LLM Client initialized with Groq API")
elif OPENROUTER_API_KEY:
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        timeout=LLM_TIMEOUT,
    )
    logger.info("LLM Client initialized with OpenRouter API")
else:
    client = None
    logger.warning("No LLM API keys provided. Running in heuristic fallback mode.")

# Circuit breaker for LLM calls
llm_circuit = CircuitBreaker(name="openrouter", failure_threshold=3, recovery_timeout=60)


# ===================================================================
# Prompt Engineering (delegated to shared.llm_config for versioning)
# ===================================================================

SYSTEM_PROMPT = get_prompt("system")


def build_user_prompt(alert: dict) -> str:
    return build_user_prompt_from_alert(alert)


# ===================================================================
# Caching
# ===================================================================

def _cache_key(alert: dict) -> str:
    """
    Generate cache key based on traffic profile buckets (not exact values).

    Bucketing increases cache hit rate — a DDoS at 5200 pps and one at 5400 pps
    will both map to the 5000 bucket.
    """
    pps = float(alert.get("packets_per_sec", 0))
    bps = float(alert.get("bytes_per_sec", 0))
    avg_size = float(alert.get("avg_packet_size", 0))

    pps_bucket = int(pps // 500) * 500
    bps_bucket = int(bps // 50000) * 50000
    size_bucket = int(avg_size // 200) * 200

    raw = f"{pps_bucket}:{bps_bucket}:{size_bucket}"
    tenant_prefix = alert.get("tenant_id", "")
    return f"t:{tenant_prefix}:llm_cache:{hashlib.md5(raw.encode()).hexdigest()}"


async def get_cached(alert: dict) -> dict | None:
    """Check Redis for a cached analysis matching this traffic profile."""
    key = _cache_key(alert)
    cached = await redis_manager.client.get(key)
    if cached:
        LLM_CALLS.labels(status="cache_hit").inc()
        logger.info("LLM cache hit", extra={"src_ip": alert.get("src_ip", "")})
        return json.loads(cached)
    return None


async def set_cached(alert: dict, analysis: dict) -> None:
    """Cache an LLM analysis in Redis."""
    key = _cache_key(alert)
    await redis_manager.client.set(key, json.dumps(analysis), ex=CACHE_TTL)


# ===================================================================
# Heuristic Fallback
# ===================================================================

def heuristic_fallback(alert: dict) -> dict:
    """
    Rule-based fallback classification when LLM is unavailable.

    Enhanced with feature-aware detection heuristics (Small Packet Ratio,
    bytes/sec) and per-attack-type explanations + recommendations.
    """
    pps = float(alert.get("packets_per_sec", 0))
    avg_size = float(alert.get("avg_packet_size", 0))

    # Extract additional features for smarter classification
    try:
        features_raw = alert.get("features", "{}")
        if isinstance(features_raw, str):
            feat_dict = json.loads(features_raw)
        else:
            feat_dict = features_raw
    except Exception:
        feat_dict = {}

    small_pkt_ratio = float(feat_dict.get("small_packet_ratio", 0.0) or feat_dict.get("Small Packet Ratio", 0.0))
    flow_bytes_sec = float(feat_dict.get("bytes_per_sec", 0.0) or feat_dict.get("Flow Bytes/s", 0.0))

    if avg_size > 1000 and pps > 1000:
        attack_type = "DDoS Volumetric Flood"
        severity = "critical"
        explanation = f"Detected high-rate volumetric flow ({pps:.0f} pkt/s, avg size {avg_size:.0f}B, {flow_bytes_sec/1e6:.2f} MB/s)."
        recommendation = "Deploy network-level rate limiting or route filtering; isolate targeted subnet."
    elif small_pkt_ratio > 0.8 and pps > 1500:
        attack_type = "SYN Flood / Port Scan"
        severity = "high"
        explanation = f"Detected extremely high ratio of small packets ({small_pkt_ratio:.1%} < 120 bytes) at high packet rate ({pps:.0f} pkt/s)."
        recommendation = "Enable SYN cookies, adjust TCP timeout thresholds, and block scanner IP."
    elif avg_size < 100 and pps > 1000:
        attack_type = "Fast Port Scan"
        severity = "high"
        explanation = f"High-speed transmission of small probe packets ({pps:.0f} pkt/s, average packet size {avg_size:.0f}B)."
        recommendation = "Block IP at perimeter firewall to prevent reconnaissance footprinting."
    elif 200 < avg_size < 600 and pps > 100:
        attack_type = "Brute Force Attack"
        severity = "medium"
        explanation = f"Low-to-medium rate interactive packets ({pps:.0f} pkt/s) with typical credential exchange payload sizes."
        recommendation = "Enforce adaptive account lockout thresholds and review auth logs."
    elif pps > 500:
        attack_type = "Anomalous High-Rate Traffic"
        severity = "high"
        explanation = f"Unusual traffic spike detected ({pps:.0f} pkt/s) exceeding normal baseline behavior."
        recommendation = "Analyze payload signatures and restrict traffic bandwidth for this source IP."
    else:
        attack_type = "Suspicious Traffic Pattern"
        severity = "medium"
        explanation = f"Unclassified anomalous flow detected. Traffic profile: {pps:.0f} pkt/s, avg size {avg_size:.0f}B."
        recommendation = "Monitor source IP closely and queue for further deep packet inspection."

    LLM_CALLS.labels(status="fallback").inc()

    return {
        "attack_type": attack_type,
        "severity": severity,
        "explanation": f"Heuristic classification (LLM unavailable). {explanation}",
        "recommendation": recommendation,
        "_source": "heuristic_fallback",
    }


# ===================================================================
# Core Analysis
# ===================================================================

async def analyze_alert(alert: dict) -> dict:
    """
    Analyze an alert using: Cache → LLM → Heuristic Fallback.

    Returns a dict with attack_type, severity, explanation, recommendation.
    """
    # 1. Check cache
    cached = await get_cached(alert)
    if cached:
        cached["_source"] = "cache"
        return cached

    # 2. Try LLM (with circuit breaker and provider fallback chain)
    if client and llm_circuit.can_execute():
        from shared.llm_config import MODEL_FALLBACK_CHAIN, get_model_for_attempt
        for attempt in range(len(MODEL_FALLBACK_CHAIN)):
            model_name = get_model_for_attempt(attempt)
            logger.info(f"Attempting LLM analysis using model: {model_name} (attempt {attempt + 1})")
            try:
                start = time.time()

                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(alert)},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )

                latency = time.time() - start
                LLM_LATENCY.observe(latency)

                # Parse and VALIDATE JSON response
                raw_text = response.choices[0].message.content.strip()
                analysis = validate_llm_response(raw_text)

                if analysis is None:
                    logger.error(f"LLM model {model_name} returned invalid response structure")
                    continue  # Try next model in fallback chain

                analysis["_source"] = "llm"
                analysis["_model"] = model_name
                analysis["_prompt_version"] = LLM_PROMPT_VERSION

                llm_circuit.record_success()
                LLM_CALLS.labels(status="success").inc()

                logger.info(
                    "LLM analysis complete",
                    extra={
                        "src_ip": alert.get("src_ip", ""),
                        "latency_ms": round(latency * 1000, 1),
                        "attack_type": analysis.get("attack_type"),
                        "model": model_name,
                    },
                )

                # Cache for future similar traffic
                await set_cached(alert, analysis)
                return analysis

            except Exception as e:
                logger.error(f"LLM model {model_name} call failed: {e}", extra={"src_ip": alert.get("src_ip", "")})
                # Try next model

        # If all models in the fallback chain failed:
        llm_circuit.record_failure()
        LLM_CALLS.labels(status="failure").inc()

    elif not llm_circuit.can_execute():
        LLM_CALLS.labels(status="circuit_open").inc()
        logger.warning("Circuit breaker OPEN — using heuristic fallback")

    # 3. Fallback to heuristics
    return heuristic_fallback(alert)


# ===================================================================
# Consumer
# ===================================================================

async def process_alert_message(data: dict) -> None:
    """Consumer handler for stream:alerts."""
    src_ip = data.get("src_ip", "unknown")

    # Run analysis (cache → LLM → fallback)
    analysis = await analyze_alert(data)

    # Record metrics
    ALERTS_GENERATED.labels(
        attack_type=analysis.get("attack_type", "unknown"),
        severity=analysis.get("severity", "unknown"),
    ).inc()

    tenant_id = data.get("tenant_id", None) or None  # Multi-tenancy

    # Persist to PostgreSQL
    alert_id = "unknown"
    try:
        async with async_session() as session:
            raw_features = {}
            try:
                raw_features = json.loads(data.get("features", "{}"))
            except (json.JSONDecodeError, TypeError):
                pass

            alert_record = Alert(
                src_ip=src_ip,
                tenant_id=tenant_id,
                attack_type=analysis.get("attack_type"),
                severity=analysis.get("severity"),
                confidence=float(data.get("prediction_confidence", 0)),
                explanation=analysis.get("explanation"),
                recommendation=analysis.get("recommendation"),
                raw_features=raw_features,
                llm_response=analysis,
            )
            session.add(alert_record)
            await session.commit()
            alert_id = str(alert_record.id)
    except Exception as e:
        logger.error(f"DB write failed: {e}", exc_info=True)

    # Publish to Decision Engine instead of Firewall directly
    await redis_manager.publish("stream:decisions_pending", {
        "src_ip": src_ip,
        "tenant_id": tenant_id or "",
        "reason": f"{analysis.get('attack_type', 'unknown')} - {analysis.get('severity', 'unknown')}",
        "alert_id": alert_id,
        "severity": analysis.get('severity', 'low'),
        "attack_type": analysis.get('attack_type', 'unknown'),
        "confidence": str(data.get("prediction_confidence", 0)),
        "trace_id": get_trace_id(),
    })

    # Push to recent alerts for dashboard (tenant-scoped)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "alert_id": alert_id,
        "src_ip": src_ip,
        "attack_type": analysis.get("attack_type", "Unknown"),
        "severity": analysis.get("severity", "medium"),
        "explanation": analysis.get("explanation", ""),
        "recommendation": analysis.get("recommendation", ""),
        "_source": analysis.get("_source", "unknown"),
    }
    await redis_manager.push_recent_alert(log_entry, tenant_id=tenant_id)

    logger.info(
        f"Alert processed: {analysis.get('attack_type')}",
        extra={"src_ip": src_ip, "attack_type": analysis.get("attack_type")},
    )


_shutdown_event = asyncio.Event()


async def consumer_loop() -> None:
    """Main consumer loop."""
    logger.info("LLM Analyzer consumer started — reading from stream:alerts")

    while not _shutdown_event.is_set():
        try:
            # Backpressure Check
            lag = await redis_manager.stream_length("stream:alerts")
            STREAM_LAG.labels(stream="stream:alerts", group="llm_analyzer_group").set(lag)
            if lag > 1000:
                logger.warning(f"Backpressure detected in stream:alerts! Lag: {lag}")

            messages = await redis_manager.consume(
                stream="stream:alerts",
                group="llm_analyzer_group",
                consumer="llm_worker_1",
                count=5,
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
                                validated = AlertData(**data)
                            except ValidationError as e:
                                logger.warning(f"Validation error in stream:alerts for msg {msg_id}: {len(e.errors())} field errors")
                                await redis_manager.ack("stream:alerts", "llm_analyzer_group", msg_id)
                                continue

                            await process_alert_message(data)
                            await redis_manager.ack("stream:alerts", "llm_analyzer_group", msg_id)
                        except Exception as e:
                            logger.error(f"Failed to process alert {msg_id}: {e}")

            # Update circuit breaker gauge
            state_map = {"closed": 0, "half_open": 1, "open": 2}
            CIRCUIT_BREAKER_STATE.labels(name="openrouter").set(
                state_map.get(llm_circuit.state.value, 0)
            )

        except asyncio.CancelledError:
            logger.info("LLM consumer loop cancelled — finishing")
            break
        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            await asyncio.sleep(5)


# ===================================================================
# FastAPI
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    consumer_task = asyncio.create_task(consumer_loop())
    logger.info("LLM Analyzer service started")
    yield
    _shutdown_event.set()
    consumer_task.cancel()
    try:
        await asyncio.wait_for(consumer_task, timeout=10)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    await redis_manager.close()


app = FastAPI(title="LLM Analysis Service", lifespan=lifespan)
app.add_route("/metrics", metrics_endpoint)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        service="llm_analyzer",
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


@app.get("/api/logs")
async def get_logs():
    """Returns recent AI threat analysis logs for the dashboard."""
    alerts = await redis_manager.get_recent_alerts(count=50)
    return {"logs": alerts}


if __name__ == "__main__":
    logger.info("Starting LLM Analyzer on port 8003...")
    uvicorn.run(app, host="0.0.0.0", port=8003)
