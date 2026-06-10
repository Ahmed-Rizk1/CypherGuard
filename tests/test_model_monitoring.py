"""
Tests for live model monitoring & alerting in ml_engine/model_monitoring.py.
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import MLPrediction, Alert
from ml_engine.model_monitoring import run_monitoring_cycle


@pytest.mark.asyncio
@patch("ml_engine.model_monitoring.async_session")
@patch("ml_engine.model_monitoring.MODEL_ACCURACY_RECENT")
@patch("ml_engine.model_monitoring.MODEL_F1_RECENT")
@patch("ml_engine.model_monitoring.MODEL_LATENCY_P95")
@patch("ml_engine.model_monitoring.PREDICTION_DRIFT_SCORE")
@patch("ml_engine.model_monitoring.write_audit_log")
@patch("ml_engine.model_monitoring.os.path.exists")
async def test_run_monitoring_cycle_metrics(
    mock_exists,
    mock_write_audit_log,
    mock_drift_gauge,
    mock_latency_gauge,
    mock_f1_gauge,
    mock_accuracy_gauge,
    mock_async_session,
):
    """Test metrics calculation and gauge updates under normal conditions."""
    mock_exists.return_value = False  # Skip drift check for now
    mock_write_audit_log.return_value = AsyncMock()

    # Mock predictions
    base_time = datetime.now()
    mock_predictions = [
        MLPrediction(
            src_ip="192.168.1.10",
            prediction="malicious",
            latency_ms=120.0,
            created_at=base_time,
        ),
        MLPrediction(
            src_ip="192.168.1.11",
            prediction="benign",
            latency_ms=80.0,
            created_at=base_time - timedelta(seconds=2),
        ),
        MLPrediction(
            src_ip="192.168.1.12",
            prediction="malicious",
            latency_ms=250.0,
            created_at=base_time - timedelta(seconds=5),
        ),
    ]

    # Mock corresponding alerts to simulate:
    # 1. 192.168.1.10: prediction "malicious", alert "resolved" (True Positive)
    # 2. 192.168.1.11: prediction "benign", no alerts (True Negative)
    # 3. 192.168.1.12: prediction "malicious", alert "false_positive" (False Positive)
    mock_alerts = [
        Alert(src_ip="192.168.1.10", status="resolved", created_at=base_time),
        Alert(src_ip="192.168.1.12", status="false_positive", created_at=base_time - timedelta(seconds=5)),
    ]

    # Configure session mocks
    mock_session = AsyncMock()
    mock_async_session.return_value.__aenter__.return_value = mock_session

    # Mock predictions query execution
    mock_predictions_result = MagicMock()
    mock_predictions_result.scalars.return_value.all.return_value = mock_predictions

    # Mock alerts query execution
    mock_alerts_result = MagicMock()
    mock_alerts_result.scalars.return_value.all.return_value = mock_alerts

    # Set side_effect to return predictions result first, then alerts result
    mock_session.execute.side_effect = [mock_predictions_result, mock_alerts_result]

    # Run one cycle
    await run_monitoring_cycle()

    # Check metrics:
    # TP = 1 (192.168.1.10)
    # TN = 1 (192.168.1.11)
    # FP = 1 (192.168.1.12 - since status is false_positive)
    # FN = 0
    # Total = 3
    # Accuracy = (1 + 1) / 3 = 0.6667
    # Precision = 1 / (1 + 1) = 0.5
    # Recall = 1 / (1 + 0) = 1.0
    # F1 = (2 * 0.5 * 1.0) / (0.5 + 1.0) = 0.6667

    # Verify gauge updates
    mock_accuracy_gauge.set.assert_called_once_with(pytest.approx(0.6667, 0.001))
    mock_f1_gauge.set.assert_called_once_with(pytest.approx(0.6667, 0.001))

    # Verify latency gauge update (p95 of [120, 80, 250] is 237.0)
    mock_latency_gauge.set.assert_called_once_with(pytest.approx(237.0, 0.01))

    # Verify model degradation alert (since accuracy 66.67% < 95%)
    mock_write_audit_log.assert_called_once()
    args, kwargs = mock_write_audit_log.call_args
    assert kwargs["action"] == "model_degradation_alert"
    assert kwargs["details"]["severity"] == "critical"
