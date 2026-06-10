"""
SecureNet SOC — Demo Model Generator (v2)

Creates a synthetic ML model tuned for the standalone demo mode.
The feature ranges are calibrated to match what the extractor
actually produces at runtime (packets divided by 30s window).
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_engine.feature_engineering import FEATURE_COLUMNS


def generate_synthetic_data(n_benign=5000, n_attack=3000):
    """
    Generate realistic synthetic data calibrated to actual runtime values.

    The extractor computes features over a 30s window, so:
    - Benign: ~0-5 packets/sec, ~0-5000 bytes/sec
    - Attack: ~10-500+ packets/sec, ~10000-500000+ bytes/sec
    """
    np.random.seed(42)

    # --- Benign: low traffic, normal patterns ---
    benign = pd.DataFrame({
        "Flow Bytes/s":                  np.random.lognormal(7, 1.5, n_benign).clip(10, 50000),
        "Flow Packets/s":                np.random.lognormal(0.5, 0.8, n_benign).clip(0.1, 10),
        "Avg Packet Size":               np.random.normal(450, 200, n_benign).clip(50, 1500),
        "Flow Duration":                 np.random.exponential(50, n_benign),
        "Total Fwd Packets":             np.random.poisson(5, n_benign).astype(float).clip(1, 50),
        "Total Length of Fwd Packets":   np.random.lognormal(7, 2, n_benign).clip(100, 50000),
        "Fwd Packet Length Mean":        np.random.normal(500, 200, n_benign).clip(50, 1500),
        "Fwd Packet Length Std":         np.random.exponential(100, n_benign),
        "Flow IAT Mean":                np.random.exponential(2, n_benign),
        "Flow IAT Std":                 np.random.exponential(1.5, n_benign),
        "Small Packet Ratio":            np.random.beta(2, 5, n_benign).astype(float),
    })
    benign["Label"] = 0

    # --- Attack: high traffic bursts ---
    attack = pd.DataFrame({
        "Flow Bytes/s":                  np.random.lognormal(10, 1.5, n_attack).clip(5000, 1e7),
        "Flow Packets/s":                np.random.lognormal(2.5, 1, n_attack).clip(5, 5000),
        "Avg Packet Size":               np.random.normal(800, 400, n_attack).clip(40, 1500),
        "Flow Duration":                 np.random.exponential(15, n_attack),
        "Total Fwd Packets":             (np.random.poisson(200, n_attack) + 20).astype(float),
        "Total Length of Fwd Packets":   np.random.lognormal(12, 2, n_attack).clip(10000, 1e8),
        "Fwd Packet Length Mean":        np.random.normal(800, 400, n_attack).clip(40, 1500),
        "Fwd Packet Length Std":         np.random.exponential(300, n_attack),
        "Flow IAT Mean":                np.random.exponential(0.05, n_attack),
        "Flow IAT Std":                 np.random.exponential(0.03, n_attack),
        "Small Packet Ratio":            np.random.beta(5, 2, n_attack).astype(float),
    })
    attack["Label"] = 1

    df = pd.concat([benign, attack], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


def train_demo_model():
    output_dir = os.path.join(os.path.dirname(__file__), "models")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  SECURENET SOC - DEMO MODEL TRAINING (v2)")
    print("=" * 60)

    print("\n[1/3] Generating synthetic training data...")
    df = generate_synthetic_data()
    benign_n = (df["Label"] == 0).sum()
    attack_n = (df["Label"] == 1).sum()
    print(f"  Generated {len(df)} samples ({benign_n} benign, {attack_n} attack)")

    X = df[FEATURE_COLUMNS].values
    y = df["Label"].values
    X = np.nan_to_num(X, nan=0.0, posinf=1e10, neginf=-1e10)
    X_df = pd.DataFrame(X, columns=FEATURE_COLUMNS)

    print("\n[2/3] Training RandomForest model...")
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )),
    ])
    pipeline.fit(X_df, y)

    y_pred = pipeline.predict(X_df)
    accuracy = (y_pred == y).mean()
    print(f"  Training accuracy: {accuracy:.4f}")

    # Test with runtime-like features
    test_cases = [
        ("Benign (low traffic)", {
            "Flow Bytes/s": 500, "Flow Packets/s": 1.0, "Avg Packet Size": 450,
            "Flow Duration": 30, "Total Fwd Packets": 5, "Total Length of Fwd Packets": 2500,
            "Fwd Packet Length Mean": 450, "Fwd Packet Length Std": 100,
            "Flow IAT Mean": 2.0, "Flow IAT Std": 1.5, "Small Packet Ratio": 0.1,
        }),
        ("DDoS attack", {
            "Flow Bytes/s": 75000, "Flow Packets/s": 50.0, "Avg Packet Size": 1500,
            "Flow Duration": 10, "Total Fwd Packets": 500, "Total Length of Fwd Packets": 750000,
            "Fwd Packet Length Mean": 1500, "Fwd Packet Length Std": 0,
            "Flow IAT Mean": 0.02, "Flow IAT Std": 0.01, "Small Packet Ratio": 0.01,
        }),
        ("Port Scan", {
            "Flow Bytes/s": 2000, "Flow Packets/s": 40.0, "Avg Packet Size": 40,
            "Flow Duration": 10, "Total Fwd Packets": 400, "Total Length of Fwd Packets": 16000,
            "Fwd Packet Length Mean": 40, "Fwd Packet Length Std": 5,
            "Flow IAT Mean": 0.025, "Flow IAT Std": 0.01, "Small Packet Ratio": 0.95,
        }),
    ]

    print("\n  Validation:")
    for name, feat in test_cases:
        test_df = pd.DataFrame([feat])[FEATURE_COLUMNS]
        pred = pipeline.predict(test_df)[0]
        proba = pipeline.predict_proba(test_df)[0]
        label = "BENIGN" if pred == 0 else "MALICIOUS"
        print(f"    {name}: {label} (confidence={max(proba):.2%})")

    print("\n[3/3] Saving model artifacts...")
    model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = os.path.join(output_dir, "model.joblib")
    metadata_path = os.path.join(output_dir, "model_metadata.json")
    baseline_path = os.path.join(output_dir, "feature_baselines.json")

    joblib.dump(pipeline, model_path)

    # Compute and save feature baselines for drift detection
    try:
        from shared.drift_detector import DriftDetector
        baselines = DriftDetector.compute_baselines(X_df.values, FEATURE_COLUMNS)
        with open(baseline_path, "w") as f:
            json.dump(baselines, f, indent=2)
        print(f"  Baselines saved to: {baseline_path}")
    except Exception as e:
        print(f"  [!] Failed to save baselines: {e}")

    metadata = {
        "version": model_version,
        "algorithm": "RandomForest",
        "features": FEATURE_COLUMNS,
        "n_features": len(FEATURE_COLUMNS),
        "n_training_samples": len(X),
        "class_distribution": {"benign": int(benign_n), "attack": int(attack_n)},
        "training_accuracy": float(accuracy),
        "trained_at": datetime.now().isoformat(),
        "dataset": "synthetic_demo_v2",
        "pipeline_steps": ["scaler", "model"],
        "note": "Demo model v2 - calibrated for standalone demo runtime feature ranges",
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  Model saved to:    {model_path}")
    print(f"  Metadata saved to: {metadata_path}")
    print(f"  Version:           {model_version}")
    print(f"\n{'=' * 60}")
    print("  DEMO MODEL v2 READY")
    print(f"{'=' * 60}")

    return pipeline, metadata


if __name__ == "__main__":
    train_demo_model()
