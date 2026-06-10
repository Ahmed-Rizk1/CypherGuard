"""
SecureNet SOC — Auto-Retrain on Data Drift

1. Create monitor loop:
   - Every hour: query last 1000 predictions
   - Calculate feature statistics (mean, std)
   - Compare to baseline (existing DriftDetector class)
   - If drift > 0.1: trigger retrain

2. Retraining flow:
   - Call train_production.py with recent data
   - Auto-promote if F1_new > F1_old
   - Log event to audit_log
   - Send notification

3. CLI interface:
   python ml_engine/auto_retrain.py --check-drift
   python ml_engine/auto_retrain.py --force-retrain

MULTI-TENANT SAFETY:
    This is a platform-level CLI/daemon tool that operates GLOBALLY.
    It is INTENTIONALLY global because:
    1. The ML model is shared infrastructure (single model serves all tenants)
    2. Drift detection needs cross-tenant prediction data for statistical significance
    3. Retraining is a platform operational task, not a tenant action
    4. No per-tenant data is exposed — only aggregated feature statistics
    5. Audit log entries use tenant_id=None to indicate system-level events
"""
# [ignoring loop detection]

import os
import sys
import json
import asyncio
import logging
import argparse
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import select, desc

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import async_session, MLPrediction, write_audit_log, MLExperiment
from shared.drift_detector import DriftDetector
from ml_engine.feature_engineering import FEATURE_COLUMNS, EXTRACTOR_TO_CICIDS
from ml_engine.train_production import train_and_evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("auto_retrain")

BASELINE_PATH = os.getenv(
    "DRIFT_BASELINE_PATH",
    os.path.join(os.path.dirname(__file__), "models", "feature_baselines.json"),
)
DEFAULT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
)

def map_extractor_to_cicids(features: dict) -> dict:
    """Map extractor keys to training/baseline feature names."""
    mapped = {}
    for k, v in features.items():
        cicids_key = EXTRACTOR_TO_CICIDS.get(k, k)
        mapped[cicids_key] = v
    return mapped

async def get_recent_predictions(limit: int = 1000) -> list[dict]:
    """Retrieve last N predictions from database."""
    async with async_session() as session:
        result = await session.execute(
            select(MLPrediction).order_by(desc(MLPrediction.created_at)).limit(limit)
        )
        predictions = result.scalars().all()
        return [p.features for p in predictions]

async def check_drift_and_retrain(force: bool = False, csv_path: str = DEFAULT_CSV):
    """Check data drift and trigger retraining if threshold crossed."""
    logger.info("Starting drift detection check...")
    
    if force:
        logger.info("Force-retrain flag set. Skipping drift check.")
        await trigger_retraining(csv_path, drift_detected=False, drift_details={"forced": True})
        return

    features_list = await get_recent_predictions(1000)
    if not features_list:
        logger.warning("No predictions found in the database. Cannot check drift.")
        return

    logger.info(f"Retrieved {len(features_list)} predictions for drift checking.")

    # Load baseline
    if not os.path.exists(BASELINE_PATH):
        logger.error(f"Baseline file not found at {BASELINE_PATH}. Please run train_production.py first.")
        return

    # Map keys to match baseline names
    mapped_features = [map_extractor_to_cicids(f) for f in features_list]

    # Calculate runtime stats for logging
    logger.info("Feature statistics (Mean | Std):")
    df_runtime = pd.DataFrame(mapped_features)
    for col in FEATURE_COLUMNS:
        if col in df_runtime.columns:
            mean = df_runtime[col].mean()
            std = df_runtime[col].std()
            logger.info(f"  {col:<30}: Mean={mean:.4f}, Std={std:.4f}")

    # Use DriftDetector to calculate KL divergence
    detector = DriftDetector(baseline_path=BASELINE_PATH, kl_threshold=0.1, window_size=len(mapped_features))
    detector.buffer = mapped_features
    drifted_features = detector._check_drift()

    if drifted_features:
        logger.warning(f"Drift detected in features: {drifted_features}")
        drift_details = {
            "drifted_features": drifted_features,
            "events": detector.get_recent_drift_events(len(drifted_features))
        }
        await trigger_retraining(csv_path, drift_detected=True, drift_details=drift_details)
    else:
        logger.info("No significant drift detected (KL divergence <= 0.1 for all features).")

async def trigger_retraining(csv_path: str, drift_detected: bool, drift_details: dict):
    """Run model retraining and auto-promote if performance improves."""
    logger.info(f"Triggering model retraining using dataset: {csv_path}")

    # Get the F1 score of the current best/active model before retraining
    f1_old = 0.0
    try:
        async with async_session() as session:
            result = await session.execute(
                select(MLExperiment).where(MLExperiment.is_best == True).order_by(desc(MLExperiment.created_at)).limit(1)
            )
            best_exp = result.scalar()
            if best_exp:
                f1_old = best_exp.f1_score or 0.0
    except Exception as e:
        logger.warning(f"Could not retrieve old F1 score: {e}")

    # Run the training pipeline
    try:
        pipeline, metadata, exp_id, promoted = train_and_evaluate(csv_path)
        f1_new = metadata.get("full_training_metrics", {}).get("f1", 0.0)
        
        logger.info(f"Retraining complete. New F1: {f1_new:.4f} (Old F1: {f1_old:.4f})")
        logger.info(f"Auto-promoted: {promoted}")

        # Log event to audit_log
        audit_details = {
            "experiment_id": str(exp_id) if exp_id else None,
            "old_f1": f1_old,
            "new_f1": f1_new,
            "promoted": promoted,
            "drift_detected": drift_detected,
            "drift_details": drift_details,
            "dataset": csv_path,
        }
        
        await write_audit_log(
            action="model_auto_retrain",
            actor="system",
            resource_type="model",
            resource_id=metadata.get("version", "unknown"),
            details=audit_details,
        )
        
        # Send Notification (logger and standard output)
        notification_msg = (
            f"🔔 [Auto-Retrain Notification] Model retrained successfully!\n"
            f"  - Promotion Status: {'PROMOTED' if promoted else 'NOT PROMOTED (existing model is better)'}\n"
            f"  - New F1 Score: {f1_new:.4f} | Old F1 Score: {f1_old:.4f}\n"
            f"  - Triggered by drift: {drift_detected}"
        )
        logger.info(notification_msg)
        print(notification_msg)

        # Trigger hot-reload on the ml-engine container if promoted
        if promoted:
            ml_engine_url = os.getenv("ML_ENGINE_URL", "http://ml-engine:8002")
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"{ml_engine_url}/model/reload",
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_data = json.loads(response.read().decode())
                    logger.info(f"Triggered ML engine reload: {res_data}")
            except Exception as reload_err:
                logger.error(f"Failed to trigger ML engine reload: {reload_err}")

    except Exception as e:
        logger.error(f"Retraining failed: {e}", exc_info=True)
        await write_audit_log(
            action="model_auto_retrain_failed",
            actor="system",
            resource_type="model",
            details={"error": str(e), "drift_detected": drift_detected},
        )

async def monitor_loop(csv_path: str):
    """Daemon monitor loop that runs every hour."""
    logger.info("Starting auto-retrain daemon monitor loop (interval: 1 hour)...")
    while True:
        try:
            await check_drift_and_retrain(force=False, csv_path=csv_path)
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}", exc_info=True)
        # Sleep for 1 hour (3600 seconds)
        await asyncio.sleep(3600)

def main():
    parser = argparse.ArgumentParser(description="SecureNet SOC Auto-Retrain Daemon")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check-drift", action="store_true", help="Check data drift and retrain if necessary")
    group.add_argument("--force-retrain", action="store_true", help="Force retraining immediately without drift check")
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV, help="Path to training CSV dataset")
    parser.add_argument("--daemon", action="store_true", help="Run as a daemon monitoring loop every hour")
    
    args = parser.parse_args()

    if args.daemon:
        asyncio.run(monitor_loop(args.csv))
    elif args.force_retrain:
        asyncio.run(check_drift_and_retrain(force=True, csv_path=args.csv))
    elif args.check_drift:
        asyncio.run(check_drift_and_retrain(force=False, csv_path=args.csv))
    else:
        # Default behavior: run check-drift once
        asyncio.run(check_drift_and_retrain(force=False, csv_path=args.csv))

if __name__ == "__main__":
    main()
