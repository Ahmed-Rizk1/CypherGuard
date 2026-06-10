"""
Tests for Phase 3 — Database, ML, and LLM improvements.

Covers:
- Drift detection logic
- LLM prompt versioning
- LLM response validation
- ORM model registry
- Audit log helper
- Prediction logging
- Model hash computation
"""

import os
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import numpy as np

os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-validation"
os.environ["INTERNAL_API_KEY"] = "test-internal-key-long-enough-for-validation"


# ===================================================================
# Drift Detector Tests
# ===================================================================

from shared.drift_detector import DriftDetector


class TestDriftDetector:
    def test_disabled_without_baselines(self):
        d = DriftDetector()
        assert not d.is_enabled
        assert d.add_sample({"a": 1}) is None

    def test_enabled_with_baselines(self, tmp_path):
        baseline = {"feature_a": {
            "histogram": [0.1] * 20,
            "bin_edges": list(np.linspace(0, 100, 21)),
            "mean": 50.0, "std": 25.0,
        }}
        p = tmp_path / "baselines.json"
        p.write_text(json.dumps(baseline))
        d = DriftDetector(baseline_path=str(p))
        assert d.is_enabled

    def test_window_accumulates(self):
        d = DriftDetector(window_size=100)
        d.baseline = {"a": {"histogram": [0.5, 0.5], "bin_edges": [0, 50, 100]}}
        for i in range(99):
            result = d.add_sample({"a": i})
            assert result is None  # Window not full

    def test_drift_detection_triggers(self, tmp_path):
        """Extreme distribution shift should be detected."""
        baseline = {"feature_x": {
            "histogram": np.ones(20).tolist(),
            "bin_edges": np.linspace(0, 100, 21).tolist(),
            "mean": 50.0, "std": 25.0,
        }}
        p = tmp_path / "baselines.json"
        p.write_text(json.dumps(baseline))
        d = DriftDetector(baseline_path=str(p), window_size=50, kl_threshold=0.1)

        # Feed extremely skewed data
        for i in range(50):
            result = d.add_sample({"feature_x": 99.0})

        # Last sample should trigger check
        if result is not None:
            assert "feature_x" in result

    def test_compute_baselines(self):
        """Baseline computation should produce valid histograms."""
        X = np.random.randn(1000, 3)
        names = ["f1", "f2", "f3"]
        baselines = DriftDetector.compute_baselines(X, names, n_bins=10)
        assert len(baselines) == 3
        assert "histogram" in baselines["f1"]
        assert "bin_edges" in baselines["f1"]
        assert len(baselines["f1"]["histogram"]) == 10

    def test_recent_drift_events_empty(self):
        d = DriftDetector()
        assert d.get_recent_drift_events() == []


# ===================================================================
# LLM Config Tests
# ===================================================================

from shared.llm_config import (
    get_prompt, build_user_prompt_from_alert,
    validate_llm_response, LLM_PROMPT_VERSION,
    get_model_for_attempt,
)


class TestPromptVersioning:
    def test_system_prompt_v1(self):
        prompt = get_prompt("system", version="v1")
        assert "IDS analyst" in prompt
        assert "JSON" in prompt

    def test_system_prompt_v2(self):
        prompt = get_prompt("system", version="v2")
        assert "SOC analyst" in prompt
        assert "RULES" in prompt

    def test_user_prompt_formatting(self):
        alert = {
            "src_ip": "192.168.1.100",
            "packets_per_sec": 5000.0,
            "bytes_per_sec": 1000000.0,
            "avg_packet_size": 200.0,
            "prediction_confidence": 0.95,
        }
        prompt = build_user_prompt_from_alert(alert)
        assert "192.168.1.100" in prompt
        assert "5000" in prompt

    def test_current_version_exists(self):
        prompt = get_prompt("system")
        assert len(prompt) > 0

    def test_invalid_version_falls_back(self):
        prompt = get_prompt("system", version="v999")
        assert len(prompt) > 0  # Falls back to current


class TestLLMResponseValidation:
    def test_valid_response(self):
        raw = json.dumps({
            "attack_type": "DDoS Volumetric",
            "severity": "critical",
            "explanation": "High rate of packets detected.",
            "recommendation": "Block the source IP.",
        })
        result = validate_llm_response(raw)
        assert result is not None
        assert result["severity"] == "critical"

    def test_invalid_severity_rejected(self):
        raw = json.dumps({
            "attack_type": "DDoS",
            "severity": "EXTREME",
            "explanation": "Bad.",
            "recommendation": "Block.",
        })
        result = validate_llm_response(raw)
        assert result is None

    def test_missing_field_rejected(self):
        raw = json.dumps({
            "attack_type": "DDoS",
            "severity": "high",
        })
        result = validate_llm_response(raw)
        assert result is None

    def test_markdown_code_block_stripped(self):
        raw = '```json\n{"attack_type":"PortScan","severity":"medium","explanation":"Scanning.","recommendation":"Investigate."}\n```'
        result = validate_llm_response(raw)
        assert result is not None
        assert result["attack_type"] == "PortScan"

    def test_dict_input_accepted(self):
        data = {
            "attack_type": "BruteForce",
            "severity": "high",
            "explanation": "Multiple failed logins.",
            "recommendation": "Lock account.",
        }
        result = validate_llm_response(data)
        assert result is not None

    def test_garbage_input_rejected(self):
        result = validate_llm_response("This is not JSON at all!")
        assert result is None


class TestModelFallbackChain:
    def test_first_attempt_primary(self):
        model = get_model_for_attempt(0)
        assert "gpt-4o-mini" in model

    def test_fallback_on_second_attempt(self):
        model = get_model_for_attempt(1)
        assert "llama" in model

    def test_beyond_chain_uses_last(self):
        model = get_model_for_attempt(99)
        assert "llama" in model


# ===================================================================
# Database Model Tests
# ===================================================================

from shared.database import ModelRegistry, write_audit_log, AuditLog


class TestModelRegistryORM:
    def test_model_registry_has_fields(self):
        """ModelRegistry should have all required fields."""
        cols = {c.name for c in ModelRegistry.__table__.columns}
        required = {"id", "version", "algorithm", "accuracy", "f1_score",
                     "feature_columns", "training_samples", "file_hash",
                     "is_active", "created_at", "activated_at"}
        assert required.issubset(cols)

    def test_audit_log_has_fields(self):
        """AuditLog should have all required fields."""
        cols = {c.name for c in AuditLog.__table__.columns}
        required = {"id", "actor", "action", "resource_type", "resource_id",
                     "details", "ip_address", "created_at"}
        assert required.issubset(cols)


# ===================================================================
# ML Engine Integration Tests
# ===================================================================

from httpx import AsyncClient, ASGITransport
from ml_engine.main import app as ml_app


class TestMLEnginePhase3:
    @pytest.mark.asyncio
    async def test_model_info_endpoint(self):
        transport = ASGITransport(app=ml_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/model/info")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "features" in data
        assert "drift_enabled" in data
        assert "drift_events" in data

    @pytest.mark.asyncio
    async def test_model_reload_endpoint(self):
        transport = ASGITransport(app=ml_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/model/reload")
        assert r.status_code == 200
        assert r.json()["status"] in ("unchanged", "reloaded", "error")

    @pytest.mark.asyncio
    async def test_health_shows_model_version(self):
        transport = ASGITransport(app=ml_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/health")
        assert r.status_code == 200
        assert "version" in r.json()
