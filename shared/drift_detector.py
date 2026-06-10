"""
Feature drift detection for SecureNet ML pipeline.

Monitors runtime feature distributions against training baselines
using KL divergence. Raises alerts when distributions shift beyond
configurable thresholds, indicating potential model accuracy degradation.

Usage:
    from shared.drift_detector import DriftDetector

    detector = DriftDetector(baseline_path="ml_engine/models/feature_baselines.json")

    # In inference loop:
    detector.add_sample(features_dict)
"""

import os
import json
import logging
import numpy as np
from typing import Optional
from scipy.stats import entropy

logger = logging.getLogger(__name__)

# Prometheus metric for drift alerts (lazy import to avoid circular deps)
_drift_counter = None


def _get_drift_counter():
    global _drift_counter
    if _drift_counter is None:
        from prometheus_client import Counter
        _drift_counter = Counter(
            "securenet_feature_drift_detected_total",
            "Number of feature drift events detected",
            ["feature"],
        )
    return _drift_counter


from collections import deque

class DriftDetector:
    """
    Detects feature drift by comparing runtime distributions to training baselines.

    Uses KL divergence with configurable window size and threshold.
    """

    def __init__(
        self,
        baseline_path: str = "",
        window_size: int = 1000,
        kl_threshold: float = 0.5,
        n_bins: int = 20,
    ):
        self.window_size = window_size
        self.kl_threshold = kl_threshold
        self.n_bins = n_bins
        self.buffer: list[dict] = []
        self.baseline: dict = {}
        self.drift_events = deque(maxlen=1000)

        if baseline_path and os.path.exists(baseline_path):
            with open(baseline_path) as f:
                self.baseline = json.load(f)
            logger.info(f"Loaded {len(self.baseline)} feature baselines from {baseline_path}")
        else:
            logger.warning("No feature baselines loaded — drift detection disabled")

    @property
    def is_enabled(self) -> bool:
        return bool(self.baseline)

    def add_sample(self, features: dict) -> Optional[list[str]]:
        """
        Add a feature sample to the buffer. Returns list of drifted features
        if window is full and drift is detected, otherwise None.
        """
        if not self.is_enabled:
            return None

        self.buffer.append(features)

        if len(self.buffer) >= self.window_size:
            drifted = self._check_drift()
            self.buffer = []
            return drifted if drifted else None

        return None

    def _check_drift(self) -> list[str]:
        """Compare buffered runtime distribution against baselines."""
        drifted_features = []

        for feature_name, baseline_data in self.baseline.items():
            try:
                runtime_values = [
                    float(s.get(feature_name, 0))
                    for s in self.buffer
                    if feature_name in s
                ]

                if len(runtime_values) < 10:
                    continue

                baseline_hist = np.array(baseline_data.get("histogram", []))
                if len(baseline_hist) == 0:
                    continue

                # Compute runtime histogram with same bin edges
                bin_edges = baseline_data.get("bin_edges")
                if bin_edges:
                    runtime_hist, _ = np.histogram(
                        runtime_values, bins=bin_edges, density=True
                    )
                else:
                    runtime_hist, _ = np.histogram(
                        runtime_values, bins=self.n_bins, density=True
                    )

                # Add smoothing to avoid division by zero
                runtime_hist = runtime_hist.astype(float) + 1e-10
                baseline_hist = baseline_hist.astype(float) + 1e-10

                # Normalize
                runtime_hist = runtime_hist / runtime_hist.sum()
                baseline_hist = baseline_hist / baseline_hist.sum()

                kl_div = float(entropy(runtime_hist, baseline_hist))

                if kl_div > self.kl_threshold:
                    logger.warning(
                        f"DRIFT DETECTED on '{feature_name}': KL={kl_div:.4f} "
                        f"(threshold={self.kl_threshold})"
                    )
                    _get_drift_counter().labels(feature=feature_name).inc()
                    drifted_features.append(feature_name)

                    self.drift_events.append({
                        "feature": feature_name,
                        "kl_divergence": round(kl_div, 4),
                        "threshold": self.kl_threshold,
                        "samples": len(runtime_values),
                    })

            except Exception as e:
                logger.debug(f"Drift check failed for {feature_name}: {e}")

        return drifted_features

    def get_recent_drift_events(self, n: int = 10) -> list[dict]:
        """Return the N most recent drift events."""
        return list(self.drift_events)[-n:]

    @staticmethod
    def compute_baselines(X, feature_names: list[str], n_bins: int = 20) -> dict:
        """
        Compute feature baselines from training data for later drift detection.

        Args:
            X: Training feature matrix (numpy array or DataFrame).
            feature_names: List of feature column names.
            n_bins: Number of histogram bins.

        Returns:
            Dict of {feature_name: {histogram, bin_edges, mean, std}}.
        """
        baselines = {}
        X_arr = np.array(X)

        for i, name in enumerate(feature_names):
            values = X_arr[:, i]
            values = values[np.isfinite(values)]

            hist, bin_edges = np.histogram(values, bins=n_bins, density=True)

            baselines[name] = {
                "histogram": hist.tolist(),
                "bin_edges": bin_edges.tolist(),
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
            }

        return baselines
