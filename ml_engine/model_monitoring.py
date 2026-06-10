"""
SecureNet SOC — Live Model Monitoring & Alerting

Periodically queries recent predictions, matches them against analyst alerts
to estimate real-time model accuracy/F1/latency, and calculates feature drift.
Exposes these statistics as Prometheus metrics.

MULTI-TENANT SAFETY:
    This is a platform-level background job that runs GLOBALLY across all tenants.
    It calculates system-wide model quality metrics (accuracy, F1, latency, drift).
    This is INTENTIONALLY global because:
    1. The ML model itself is shared infrastructure (not per-tenant)
    2. Model quality metrics are platform operational concerns
    3. No per-tenant data is exposed through API routes from this module
    4. All Prometheus metrics are global aggregates (not tenant-specific)
    5. Audit log entries use tenant_id=None to indicate system-level events
"""

import os
import sys
import time
import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy import select, desc

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import async_session, MLPrediction, Alert, write_audit_log
from shared.metrics import (
    MODEL_ACCURACY_RECENT, MODEL_F1_RECENT, MODEL_LATENCY_P95, PREDICTION_DRIFT_SCORE
)
from shared.drift_detector import DriftDetector
from ml_engine.auto_retrain import map_extractor_to_cicids

logger = logging.getLogger("model_monitoring")

BASELINE_PATH = os.getenv(
    "DRIFT_BASELINE_PATH",
    os.path.join(os.path.dirname(__file__), "models", "feature_baselines.json"),
)

async def run_monitoring_cycle() -> None:
    """Run one cycle of ML model monitoring."""
    logger.info("Running live model monitoring check...")
    try:
        async with async_session() as session:
            # 1. Fetch last 1000 predictions
            stmt = select(MLPrediction).order_by(desc(MLPrediction.created_at)).limit(1000)
            result = await session.execute(stmt)
            predictions = result.scalars().all()

            if not predictions:
                logger.info("No predictions found in the database. Skipping cycle.")
                return

            # 2. Compute p95 latency
            latencies = [p.latency_ms for p in predictions if p.latency_ms is not None]
            p95_latency = float(np.percentile(latencies, 95)) if latencies else 0.0
            MODEL_LATENCY_P95.set(p95_latency)

            # 3. Fetch alerts in the same time range to get analyst feedback (ground truth)
            oldest_time = min(p.created_at for p in predictions)
            alert_stmt = select(Alert).where(Alert.created_at >= oldest_time - timedelta(seconds=60))
            alert_result = await session.execute(alert_stmt)
            alerts = alert_result.scalars().all()

            # 4. Match predictions with alerts and compute confusion matrix
            tp = 0
            fp = 0
            tn = 0
            fn = 0

            for p in predictions:
                pred_label = p.prediction  # "malicious" or "benign"

                # Find matching alert
                matching_alert = None
                closest_diff = float("inf")
                for a in alerts:
                    if a.src_ip == p.src_ip:
                        diff = abs((a.created_at - p.created_at).total_seconds())
                        if diff < 15 and diff < closest_diff:
                            closest_diff = diff
                            matching_alert = a

                if pred_label == "malicious":
                    if matching_alert and matching_alert.status == "false_positive":
                        fp += 1
                    else:
                        tp += 1
                else:  # benign
                    if matching_alert and matching_alert.status not in ("false_positive", "new"):
                        # Benign prediction, but there is a resolved or investigating alert for the same IP
                        fn += 1
                    else:
                        tn += 1

            total = tp + fp + tn + fn
            accuracy = (tp + tn) / total if total > 0 else 1.0
            precision = tp / (tp + fp) if tp + fp > 0 else 1.0
            recall = tp / (tp + fn) if tp + fn > 0 else 1.0
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0

            # Update gauges
            MODEL_ACCURACY_RECENT.set(accuracy)
            MODEL_F1_RECENT.set(f1)

            # 5. Compute drift score (maximum KL divergence)
            max_kl = 0.0
            if os.path.exists(BASELINE_PATH):
                try:
                    features_list = [p.features for p in predictions]
                    mapped_features = [map_extractor_to_cicids(f) for f in features_list]
                    detector = DriftDetector(baseline_path=BASELINE_PATH, window_size=len(mapped_features))
                    detector.buffer = mapped_features
                    detector._check_drift()
                    
                    for event in detector.drift_events:
                        max_kl = max(max_kl, event.get("kl_divergence", 0.0))
                except Exception as e:
                    logger.error(f"Failed to calculate drift score: {e}")
            PREDICTION_DRIFT_SCORE.set(max_kl)

            logger.info(
                f"Monitoring metrics calculated: Accuracy={accuracy:.4f}, F1={f1:.4f}, "
                f"p95_latency={p95_latency:.2f}ms, MaxDrift={max_kl:.4f} "
                f"(TP={tp}, FP={fp}, TN={tn}, FN={fn})"
            )

            # 6. Check degradation alerts
            degraded = False
            reasons = []
            if accuracy < 0.95:
                degraded = True
                severity = "warning" if accuracy >= 0.90 else "critical"
                reasons.append(f"Accuracy dropped to {accuracy:.2%}")
            if p95_latency > 500:
                degraded = True
                severity = "warning"
                reasons.append(f"p95 latency reached {p95_latency:.1f}ms")
            
            if degraded:
                alert_msg = f"🔔 [ML Model Monitor Warning] {', '.join(reasons)}"
                logger.warning(alert_msg)
                print(alert_msg)
                
                await write_audit_log(
                    action="model_degradation_alert",
                    actor="system",
                    resource_type="model",
                    details={
                        "accuracy": accuracy,
                        "f1": f1,
                        "p95_latency_ms": p95_latency,
                        "max_drift": max_kl,
                        "reasons": reasons,
                        "severity": severity,
                    }
                )
    except Exception as e:
        logger.error(f"Error during run_monitoring_cycle: {e}", exc_info=True)

async def monitor_loop(interval_sec: int = 600) -> None:
    """Background monitor loop running every interval_sec."""
    logger.info(f"Starting ML model monitoring daemon loop (interval: {interval_sec}s)...")
    while True:
        try:
            await run_monitoring_cycle()
        except Exception as e:
            logger.error(f"Error in model monitoring loop: {e}", exc_info=True)
        await asyncio.sleep(interval_sec)
