"""
SecureNet SOC — ML Engine Service (Refactored)

Consumes enriched features from stream:features, runs model inference,
and publishes malicious alerts to stream:alerts.

Changes from MVP:
- Redis Streams consumer (replaces FastAPI HTTP endpoint)
- 12-feature aligned input (replaces 2-feature model)
- Alert cooldown via Redis (prevents duplicate LLM calls)
- Blocked IP pre-filtering (skips already-blocked IPs)
- Prediction confidence scores
- Model metadata tracking
- Prometheus metrics + structured logging
"""

import os
import sys
import time
import json
import asyncio
import logging
from contextlib import asynccontextmanager

import joblib
import pandas as pd
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging, trace_id_ctx, get_trace_id
from shared.redis_client import redis_manager
from shared.validators import HealthResponse, PredictionResponse, PredictionFeatures
from pydantic import ValidationError
from shared.metrics import (
    PREDICTIONS_TOTAL, PREDICTION_LATENCY, QUEUE_DEPTH, STREAM_LAG, SYSTEM_DROPPED_MESSAGES,
    metrics_endpoint,
)
from ml_engine.feature_engineering import extractor_to_model_features, FEATURE_COLUMNS, EXTRACTOR_TO_CICIDS
from shared.chaos_engine import chaos
from shared.database import async_session, MLPrediction
from shared.drift_detector import DriftDetector
import hashlib

load_dotenv()

logger = setup_logging("ml_engine")

SERVICE_START_TIME = time.time()
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(os.path.dirname(__file__), "models", "model.joblib"))
METADATA_PATH = os.getenv("MODEL_METADATA_PATH", os.path.join(os.path.dirname(__file__), "models", "model_metadata.json"))
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN_SECONDS", "60"))

# ---------------------------------------------------------------------------
# Load model (with hot-reloading support)
# ---------------------------------------------------------------------------

model = None
model_metadata = {}
MODEL_VERSION = "unknown"
last_model_mtime = 0.0

def load_model_if_changed() -> None:
    """Load or reload model and metadata from disk if the model file is modified."""
    global model, model_metadata, MODEL_VERSION, last_model_mtime
    try:
        if os.path.exists(MODEL_PATH):
            mtime = os.path.getmtime(MODEL_PATH)
            if mtime > last_model_mtime:
                # Load the new model atomic-style to avoid intermediate failure state
                new_model = joblib.load(MODEL_PATH)
                new_metadata = {}
                if os.path.exists(METADATA_PATH):
                    with open(METADATA_PATH) as f:
                        new_metadata = json.load(f)

                model = new_model
                model_metadata = new_metadata
                MODEL_VERSION = model_metadata.get("version", "unknown")
                last_model_mtime = mtime
                logger.info(f"🔄 ML Model hot-reloaded successfully: version={MODEL_VERSION}")
        elif last_model_mtime == 0.0:
            # Fall back to legacy model path
            legacy_path = os.path.join(os.path.dirname(__file__), "model.joblib")
            if os.path.exists(legacy_path):
                model = joblib.load(legacy_path)
                MODEL_VERSION = "legacy"
                last_model_mtime = os.path.getmtime(legacy_path)
                logger.warning(f"Loaded legacy model from {legacy_path}")
            else:
                logger.error("No model found. Run: python ml_engine/train_production.py")
    except Exception as e:
        logger.error(f"Failed to load or reload model: {e}", exc_info=True)

# Initial load
load_model_if_changed()

async def model_watcher_loop() -> None:
    """Periodically check model file changes and trigger reload."""
    while True:
        try:
            load_model_if_changed()
        except Exception as e:
            logger.error(f"Error in model watcher loop: {e}")
        await asyncio.sleep(5)

# Drift detector
BASELINE_PATH = os.getenv(
    "DRIFT_BASELINE_PATH",
    os.path.join(os.path.dirname(__file__), "models", "feature_baselines.json"),
)
drift_detector = DriftDetector(baseline_path=BASELINE_PATH, window_size=1000)


def _compute_model_hash(path: str) -> str:
    """Compute SHA256 hash of model file for integrity verification."""
    if not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


MODEL_HASH = _compute_model_hash(MODEL_PATH)


async def log_prediction(
    src_ip: str, features: dict, prediction: str, confidence: float, latency_ms: float,
    tenant_id: str = None,
) -> None:
    """Persist ML prediction to PostgreSQL for performance tracking."""
    try:
        async with async_session() as session:
            record = MLPrediction(
                src_ip=src_ip,
                features=features,
                prediction=prediction,
                confidence=confidence,
                model_version=MODEL_VERSION,
                latency_ms=latency_ms,
                tenant_id=tenant_id,
            )
            session.add(record)
            await session.commit()
    except Exception as e:
        logger.error(f"Prediction logging failed: {e}")


# ---------------------------------------------------------------------------
# Core inference
# ---------------------------------------------------------------------------

async def process_features(data: dict) -> None:
    """
    Consumer handler: receive features, run inference, publish alerts.

    Args:
        data: Dict with feature values from the extractor (Redis stream message).
    """
    if model is None:
        logger.error("Model not loaded — skipping prediction")
        return

    src_ip = data.get("src_ip", "")
    tenant_id = data.get("tenant_id", None) or None  # Multi-tenancy
    if not src_ip or src_ip == "unknown":
        logger.warning("Feature message missing src_ip — skipping")
        return

    # Validate that key numeric fields can be parsed
    try:
        float(data.get("packets_per_sec", 0))
        float(data.get("bytes_per_sec", 0))
    except (ValueError, TypeError):
        logger.warning(f"Feature message has non-numeric fields — skipping", extra={"src_ip": src_ip})
        return

    # Skip already-blocked IPs (tenant-scoped)
    if await redis_manager.is_blocked(src_ip, tenant_id=tenant_id):
        return

    # Convert extractor features to model input format
    start_time = time.time()

    try:
        features_df = extractor_to_model_features(data)

        # Run inference
        prediction = model.predict(features_df)[0]

        # Get probability/confidence if available
        confidence = 0.0
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(features_df)[0]
            confidence = float(max(proba))

        latency_ms = (time.time() - start_time) * 1000

        # Map prediction to status
        # New model: 0=benign, 1=malicious
        # Legacy model: 1=benign, -1=malicious
        if MODEL_VERSION == "legacy":
            status = "benign" if prediction == 1 else "malicious"
        else:
            status = "benign" if prediction == 0 else "malicious"

        # Record metrics
        PREDICTIONS_TOTAL.labels(result=status, model_version=MODEL_VERSION).inc()
        PREDICTION_LATENCY.labels(model_version=MODEL_VERSION).observe(latency_ms / 1000)

        # Log prediction to PostgreSQL
        feature_dict = {k: v for k, v in data.items() if k not in ("src_ip", "trace_id", "tenant_id")}
        await log_prediction(src_ip, feature_dict, status, confidence, latency_ms, tenant_id=tenant_id)

        # Feed drift detector with mapped features matching baseline names
        mapped_dict = {}
        for k, v in feature_dict.items():
            try:
                mapped_dict[EXTRACTOR_TO_CICIDS.get(k, k)] = float(v)
            except (ValueError, TypeError):
                mapped_dict[EXTRACTOR_TO_CICIDS.get(k, k)] = 0.0
        drift_detector.add_sample(mapped_dict)

        logger.info(
            f"Prediction: {status}",
            extra={
                "src_ip": src_ip,
                "prediction": status,
                "confidence": round(confidence, 4),
                "latency_ms": round(latency_ms, 2),
                "model_version": MODEL_VERSION,
            },
        )

        # Handle malicious prediction
        if status == "malicious":
            # Check cooldown — avoid flooding the LLM
            if await redis_manager.should_alert(src_ip, ALERT_COOLDOWN, tenant_id=tenant_id):
                avg_size = float(data.get("avg_packet_size", 0))
                alert_data = {
                    "src_ip": src_ip,
                    "tenant_id": tenant_id or "",
                    "packets_per_sec": data.get("packets_per_sec", "0"),
                    "bytes_per_sec": data.get("bytes_per_sec", "0"),
                    "avg_packet_size": str(avg_size),
                    "prediction_confidence": str(round(confidence, 4)),
                    "model_version": MODEL_VERSION,
                    "features": json.dumps({
                        k: v for k, v in data.items() if k not in ("src_ip", "trace_id", "tenant_id")
                    }),
                    "trace_id": get_trace_id(),
                }
                await redis_manager.publish("stream:alerts", alert_data)
                logger.warning(
                    f"Alert published for {src_ip}",
                    extra={"src_ip": src_ip, "confidence": confidence},
                )
            else:
                logger.debug(f"Alert suppressed (cooldown active) for {src_ip}")

    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True, extra={"src_ip": src_ip})
        raise


# ---------------------------------------------------------------------------
# Consumer loop
# ---------------------------------------------------------------------------

_shutdown_event = asyncio.Event()


async def consumer_loop() -> None:
    """Main consumer loop — reads from stream:features."""
    logger.info("ML Engine consumer started — reading from stream:features")

    while not _shutdown_event.is_set():
        try:
            # Backpressure Check
            lag = await redis_manager.stream_length("stream:features")
            STREAM_LAG.labels(stream="stream:features", group="ml_engine_group").set(lag)
            if lag > 1000:
                logger.warning(f"Backpressure detected in stream:features! Lag: {lag}")

            await chaos.inject_redis_latency("stream:features", max_delay_ms=200)

            messages = await redis_manager.consume(
                stream="stream:features",
                group="ml_engine_group",
                consumer="ml_worker_1",
                count=20,
                block_ms=3000,
            )

            if messages:
                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        # Extract and propagate trace_id
                        msg_trace_id = data.get("trace_id")
                        if msg_trace_id:
                            trace_id_ctx.set(msg_trace_id)
                        else:
                            trace_id_ctx.set(get_trace_id()) # generate if missing

                        try:
                            # Chaos Drop
                            if chaos.should_drop_message(probability=0.01):
                                SYSTEM_DROPPED_MESSAGES.labels(service="ml_engine", reason="chaos_drop").inc()
                                await redis_manager.ack("stream:features", "ml_engine_group", msg_id)
                                continue

                            # Chaos Crash (Simulate)
                            chaos.simulate_crash(probability=0.0005)
                            try:
                                validated = PredictionFeatures(**data)
                            except ValidationError as e:
                                logger.warning(f"Validation error in stream:features for msg {msg_id}: {len(e.errors())} field errors")
                                await redis_manager.ack("stream:features", "ml_engine_group", msg_id)
                                continue

                            await process_features(data)
                            await redis_manager.ack("stream:features", "ml_engine_group", msg_id)
                        except Exception as e:
                            logger.error(f"Failed to process {msg_id}: {e}")

        except asyncio.CancelledError:
            logger.info("ML consumer loop cancelled — finishing")
            break
        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            await asyncio.sleep(3)


# ---------------------------------------------------------------------------
# FastAPI (health + metrics endpoints)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    consumer_task = asyncio.create_task(consumer_loop())

    # Start live model performance and drift monitoring
    from ml_engine.model_monitoring import monitor_loop
    monitor_interval = int(os.getenv("MODEL_MONITOR_INTERVAL_SECONDS", "60"))
    monitor_task = asyncio.create_task(monitor_loop(interval_sec=monitor_interval))

    # Start model file change hot-reload watcher
    watcher_task = asyncio.create_task(model_watcher_loop())

    logger.info(f"ML Engine service started (monitoring: {monitor_interval}s, hot-reloader: active)")
    yield
    _shutdown_event.set()
    consumer_task.cancel()
    monitor_task.cancel()
    watcher_task.cancel()
    try:
        await asyncio.gather(
            asyncio.wait_for(consumer_task, timeout=5),
            asyncio.wait_for(monitor_task, timeout=5),
            asyncio.wait_for(watcher_task, timeout=5),
            return_exceptions=True
        )
    except Exception:
        pass
    await redis_manager.close()


app = FastAPI(title="ML Detection Service", lifespan=lifespan)
app.add_route("/metrics", metrics_endpoint)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        service="ml_engine",
        uptime_seconds=round(time.time() - SERVICE_START_TIME, 1),
        version=MODEL_VERSION,
    )

@app.get("/ready")
async def ready():
    """Readiness check to verify Redis connectivity."""
    try:
        await redis_manager.client.ping()
        return {"status": "ready", "redis": "connected"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


@app.get("/model/info")
async def model_info():
    """Return current model metadata, hash, and drift status."""
    return {
        "version": MODEL_VERSION,
        "path": MODEL_PATH,
        "file_hash": MODEL_HASH,
        "features": FEATURE_COLUMNS,
        "drift_enabled": drift_detector.is_enabled,
        "drift_events": drift_detector.get_recent_drift_events(5),
    }


@app.post("/model/reload")
async def reload_model():
    """Hot-reload model from disk if the file has changed."""
    global model, model_metadata, MODEL_VERSION, MODEL_HASH
    new_hash = _compute_model_hash(MODEL_PATH)
    if new_hash == MODEL_HASH:
        return {"status": "unchanged", "hash": MODEL_HASH}
    try:
        model = joblib.load(MODEL_PATH)
        if os.path.exists(METADATA_PATH):
            with open(METADATA_PATH) as f:
                model_metadata = json.load(f)
            MODEL_VERSION = model_metadata.get("version", "unknown")
        MODEL_HASH = new_hash
        logger.info(f"Model hot-reloaded: v{MODEL_VERSION} hash={MODEL_HASH[:16]}")
        return {"status": "reloaded", "version": MODEL_VERSION, "hash": MODEL_HASH}
    except Exception as e:
        logger.error(f"Model reload failed: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    logger.info("Starting ML Engine on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002)
