"""
Tests for Phase 4 — Infrastructure & Observability.

Covers:
- Grafana dashboard JSON validity and required panels
- Prometheus alert rules YAML validity
- Docker compose file validity
- Alertmanager config validity
- Health check script structure
"""

import os
import json
import yaml
import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ===================================================================
# Grafana Dashboard Tests
# ===================================================================

class TestGrafanaDashboards:
    """Validate all Grafana dashboard JSON files."""

    @pytest.fixture
    def dashboard_dir(self):
        return os.path.join(PROJECT_ROOT, "grafana", "dashboards")

    def test_all_dashboards_valid_json(self, dashboard_dir):
        """Every .json file in grafana/dashboards must be valid JSON."""
        for fname in os.listdir(dashboard_dir):
            if fname.endswith(".json"):
                path = os.path.join(dashboard_dir, fname)
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)  # Will raise if invalid
                assert "panels" in data, f"{fname} missing 'panels' key"
                assert "title" in data, f"{fname} missing 'title' key"
                assert "uid" in data, f"{fname} missing 'uid' key"

    def test_ops_dashboard_has_key_panels(self, dashboard_dir):
        """Operations dashboard must have pipeline throughput and alert rate."""
        with open(os.path.join(dashboard_dir, "securenet-ops.json"), encoding='utf-8') as f:
            data = json.load(f)
        titles = {p["title"] for p in data["panels"]}
        assert "Pipeline Throughput" in titles
        assert "Alert Rate" in titles
        assert len(data["panels"]) >= 10

    def test_security_dashboard_exists(self, dashboard_dir):
        """Security dashboard must exist and have auth panels."""
        path = os.path.join(dashboard_dir, "securenet-security.json")
        assert os.path.exists(path)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        titles = " ".join(p["title"] for p in data["panels"])
        assert "Login" in titles or "Auth" in titles
        assert "Block" in titles or "Firewall" in titles

    def test_ml_dashboard_exists(self, dashboard_dir):
        """ML dashboard must exist and have prediction/drift panels."""
        path = os.path.join(dashboard_dir, "securenet-ml.json")
        assert os.path.exists(path)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        titles = " ".join(p["title"] for p in data["panels"])
        assert "Prediction" in titles or "ML" in titles
        assert "Drift" in titles

    def test_unique_dashboard_uids(self, dashboard_dir):
        """All dashboards must have unique UIDs."""
        uids = []
        for fname in os.listdir(dashboard_dir):
            if fname.endswith(".json"):
                with open(os.path.join(dashboard_dir, fname), encoding='utf-8') as f:
                    data = json.load(f)
                uids.append(data.get("uid"))
        assert len(uids) == len(set(uids)), "Duplicate dashboard UIDs found"


# ===================================================================
# Prometheus Tests
# ===================================================================

class TestPrometheusConfig:
    def test_prometheus_yml_valid(self):
        path = os.path.join(PROJECT_ROOT, "prometheus", "prometheus.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert "scrape_configs" in data
        jobs = {sc["job_name"] for sc in data["scrape_configs"]}
        assert "gateway" in jobs
        assert "ml_engine" in jobs
        assert "mobile_gateway" in jobs

    def test_alerts_yml_valid(self):
        path = os.path.join(PROJECT_ROOT, "prometheus", "alerts.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert "groups" in data
        group_names = {g["name"] for g in data["groups"]}
        assert "securenet_critical" in group_names
        assert "securenet_security" in group_names
        assert "securenet_infrastructure" in group_names

    def test_alerts_have_required_rules(self):
        path = os.path.join(PROJECT_ROOT, "prometheus", "alerts.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        all_alerts = []
        for group in data["groups"]:
            for rule in group["rules"]:
                all_alerts.append(rule["alert"])

        # Must have these critical alerts
        assert "ServiceDown" in all_alerts
        assert "AuthBruteForce" in all_alerts
        assert "QueueBacklog" in all_alerts
        assert "LLMCircuitOpen" in all_alerts

    def test_phase4_alerts_present(self):
        """Phase 4 should add drift, lockout, and latency alerts."""
        path = os.path.join(PROJECT_ROOT, "prometheus", "alerts.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        all_alerts = []
        for group in data["groups"]:
            for rule in group["rules"]:
                all_alerts.append(rule["alert"])

        assert "FeatureDriftDetected" in all_alerts
        assert "HighAPILatency" in all_alerts
        assert "DroppedMessagesHigh" in all_alerts

    def test_ml_alert_group_exists(self):
        """Phase 4 adds a dedicated ML alert group."""
        path = os.path.join(PROJECT_ROOT, "prometheus", "alerts.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        group_names = {g["name"] for g in data["groups"]}
        assert "securenet_ml" in group_names


# ===================================================================
# Docker Compose Tests
# ===================================================================

class TestDockerCompose:
    def test_base_compose_valid(self):
        path = os.path.join(PROJECT_ROOT, "docker-compose.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert "services" in data
        services = set(data["services"].keys())
        assert "redis" in services
        assert "postgres" in services
        assert "gateway" in services
        assert "ml-engine" in services

    def test_prod_override_exists(self):
        path = os.path.join(PROJECT_ROOT, "docker-compose.prod.yml")
        assert os.path.exists(path)
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert "services" in data

    def test_prod_has_sentinel(self):
        path = os.path.join(PROJECT_ROOT, "docker-compose.prod.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        services = set(data["services"].keys())
        assert "redis-sentinel-1" in services
        assert "redis-replica" in services

    def test_prod_has_resource_limits(self):
        path = os.path.join(PROJECT_ROOT, "docker-compose.prod.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        # ML engine should have memory limit
        ml = data["services"].get("ml-engine", {})
        assert "deploy" in ml


# ===================================================================
# Alertmanager Tests
# ===================================================================

class TestAlertmanager:
    def test_config_valid(self):
        path = os.path.join(PROJECT_ROOT, "alertmanager", "alertmanager.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert "route" in data
        assert "receivers" in data
        assert len(data["receivers"]) >= 2  # default + critical


# ===================================================================
# Traefik Tests
# ===================================================================

class TestTraefik:
    def test_config_valid(self):
        path = os.path.join(PROJECT_ROOT, "traefik", "traefik.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert "entryPoints" in data
        assert "websecure" in data["entryPoints"]
        assert "certificatesResolvers" in data

    def test_hsts_enabled(self):
        path = os.path.join(PROJECT_ROOT, "traefik", "traefik.yml")
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        headers = data["http"]["middlewares"]["security-headers"]["headers"]
        assert headers["stsSeconds"] >= 31536000
        assert headers["contentTypeNosniff"] is True


# ===================================================================
# Health Check Script Tests
# ===================================================================

class TestHealthCheckScript:
    def test_script_exists(self):
        path = os.path.join(PROJECT_ROOT, "scripts", "healthcheck.py")
        assert os.path.exists(path)

    def test_script_has_all_services(self):
        path = os.path.join(PROJECT_ROOT, "scripts", "healthcheck.py")
        with open(path, encoding='utf-8') as f:
            content = f.read()
        assert "Gateway" in content
        assert "ML Engine" in content
        assert "Mobile Gateway" in content
        assert "LLM Analyzer" in content


# ===================================================================
# Redis Sentinel Config Tests
# ===================================================================

class TestRedisSentinel:
    def test_sentinel_conf_exists(self):
        path = os.path.join(PROJECT_ROOT, "docker", "redis-sentinel.conf")
        assert os.path.exists(path)

    def test_sentinel_has_quorum(self):
        path = os.path.join(PROJECT_ROOT, "docker", "redis-sentinel.conf")
        with open(path) as f:
            content = f.read()
        assert "sentinel monitor mymaster" in content
        assert "down-after-milliseconds" in content
