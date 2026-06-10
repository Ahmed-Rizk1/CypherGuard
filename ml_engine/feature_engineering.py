"""
SecureNet SOC — Feature Engineering Module

Defines the exact feature set used by the ML model and provides
bidirectional mapping between CICIDS2017 column names and the
extractor's runtime feature names.

CRITICAL: Any change to FEATURE_COLUMNS must be mirrored in the
training pipeline (train_production.py) AND the serving pipeline
(ml_engine/main.py). Always retrain after changing features.
"""

import pandas as pd
import numpy as np
from typing import Tuple


# ===================================================================
# Feature definitions
# ===================================================================

# These features are used for both training AND serving.
# They must match EXACTLY between train_production.py and main.py.
# NOTE: We intentionally exclude features that cannot be computed at serving time
# (e.g., Bwd Packet Length Mean requires bidirectional flow tracking).
FEATURE_COLUMNS = [
    "Flow Bytes/s",
    "Flow Packets/s",
    "Avg Packet Size",
    "Flow Duration",
    "Total Fwd Packets",
    "Total Length of Fwd Packets",
    "Fwd Packet Length Mean",
    "Fwd Packet Length Std",
    "Flow IAT Mean",
    "Flow IAT Std",
    "Small Packet Ratio",
]

# Mapping: extractor runtime names → training column names
EXTRACTOR_TO_CICIDS = {
    "bytes_per_sec":       "Flow Bytes/s",
    "packets_per_sec":     "Flow Packets/s",
    "avg_packet_size":     "Avg Packet Size",
    "flow_duration":       "Flow Duration",
    "packet_count":        "Total Fwd Packets",
    "total_bytes":         "Total Length of Fwd Packets",
    "fwd_pkt_len_mean":    "Fwd Packet Length Mean",
    "fwd_pkt_len_std":     "Fwd Packet Length Std",
    "flow_iat_mean":       "Flow IAT Mean",
    "flow_iat_std":        "Flow IAT Std",
    "small_packet_ratio":  "Small Packet Ratio",
}


# ===================================================================
# Training data preparation
# ===================================================================

def prepare_training_data(csv_path: str) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Load and prepare CICIDS2017 CSV data for model training.

    Handles:
    - Column name cleaning (strip whitespace)
    - Infinity/NaN removal
    - Missing column graceful handling
    - Binary label encoding (BENIGN=0, Attack=1)

    Args:
        csv_path: Path to the CICIDS2017 CSV file.

    Returns:
        Tuple of (X features DataFrame, y labels Series).
    """
    print(f"Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    print(f"  Raw shape: {df.shape}")
    print(f"  Columns: {list(df.columns[:10])}... ({len(df.columns)} total)")

    # Check which features are available
    available = [f for f in FEATURE_COLUMNS if f in df.columns]
    missing = set(FEATURE_COLUMNS) - set(available)

    if missing:
        print(f"  ⚠ Missing features (will fill with 0): {missing}")

    # Clean data: remove inf and NaN
    df_clean = df.replace([np.inf, -np.inf], np.nan)
    df_clean = df_clean.dropna(subset=[f for f in available if f in df_clean.columns] + ["Label"])

    print(f"  Clean shape: {df_clean.shape}")

    # Build feature matrix
    X = df_clean[available].copy()

    # Fill missing features with zeros
    for f in missing:
        X[f] = 0.0

    # Ensure correct column order (must match FEATURE_COLUMNS exactly)
    X = X[FEATURE_COLUMNS].astype(float)

    # Binary labels: 0 = benign, 1 = attack
    y = df_clean["Label"].apply(lambda label: 0 if label.strip() == "BENIGN" else 1)

    print(f"  Features: {len(FEATURE_COLUMNS)}")
    print(f"  Class distribution: Benign={int((y == 0).sum())}, Attack={int((y == 1).sum())}")
    print(f"  Attack ratio: {(y == 1).sum() / len(y) * 100:.1f}%")

    return X, y


# ===================================================================
# Serving: convert extractor output to model input
# ===================================================================

def extractor_to_model_features(extractor_data: dict) -> pd.DataFrame:
    """
    Convert extractor runtime feature names to CICIDS2017 column names
    expected by the trained model, applying sanitization and outlier clipping.

    Args:
        extractor_data: Dict with keys matching EXTRACTOR_TO_CICIDS keys.

    Returns:
        Single-row DataFrame with columns in FEATURE_COLUMNS order.
    """
    model_data = {}
    for ext_key, cicids_key in EXTRACTOR_TO_CICIDS.items():
        value = extractor_data.get(ext_key, 0.0)
        try:
            val_float = float(value)
            # Handle NaN / Inf
            if np.isnan(val_float) or np.isinf(val_float):
                val_float = 0.0
            
            # Robust outlier clipping and domain constraint enforcement
            if cicids_key == "Small Packet Ratio":
                val_float = max(0.0, min(1.0, val_float))
            elif cicids_key in ("Flow Bytes/s", "Flow Packets/s", "Total Length of Fwd Packets"):
                val_float = max(0.0, min(1e8, val_float))  # Cap extremely large peaks
            elif cicids_key == "Flow Duration":
                val_float = max(0.0, min(86400.0, val_float))  # Cap at 1 day
            elif cicids_key in ("Total Fwd Packets", "Avg Packet Size", "Fwd Packet Length Mean", "Fwd Packet Length Std", "Flow IAT Mean", "Flow IAT Std"):
                val_float = max(0.0, val_float)  # Must be non-negative
                
            model_data[cicids_key] = val_float
        except (ValueError, TypeError):
            model_data[cicids_key] = 0.0

    df = pd.DataFrame([model_data])

    # Ensure all columns present and in correct order
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0

    return df[FEATURE_COLUMNS]
