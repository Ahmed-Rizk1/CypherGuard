"""
Tests for Phase 5 — Documentation & Final Polish.

Covers:
- All required documentation files exist and have content
- README completeness
- OpenAPI/Swagger enabled on gateways
- .dockerignore exists
- CHANGELOG exists and has all phases
"""

import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ===================================================================
# Documentation Completeness Tests
# ===================================================================

class TestDocumentationExists:
    """Every required doc file must exist and have substantive content."""

    REQUIRED_DOCS = [
        ("docs/architecture.md", ["Architecture", "mermaid", "Data Flow"]),
        ("docs/database_erd.md", ["erDiagram", "users", "alerts", "audit_log"]),
        ("docs/mobile_integration_guide.md", ["Authentication", "Alerts", "WebSocket", "Firewall"]),
        ("docs/websocket_protocol.md", ["WebSocket", "ping", "pong", "Heartbeat"]),
        ("docs/ml_model.md", ["Random Forest", "Feature", "Drift", "hot-reload"]),
        ("docs/environment_setup.md", ["Docker", "PostgreSQL", "Redis", "Environment Variables"]),
        ("docs/deployment_runbook.md", ["Prerequisites", "Rolling Update", "Rollback", "Backup"]),
        ("docs/incident_response.md", ["Severity", "Playbook", "P0", "P1"]),
    ]

    @pytest.mark.parametrize("path,keywords", REQUIRED_DOCS)
    def test_doc_exists_and_has_content(self, path, keywords):
        full_path = os.path.join(PROJECT_ROOT, path)
        assert os.path.exists(full_path), f"Missing documentation: {path}"

        with open(full_path, encoding="utf-8") as f:
            content = f.read()

        assert len(content) > 500, f"{path} is too short ({len(content)} bytes)"

        for keyword in keywords:
            assert keyword in content, f"{path} missing expected keyword: '{keyword}'"


class TestReadme:
    """README.md must be comprehensive and production-ready."""

    def test_readme_exists(self):
        path = os.path.join(PROJECT_ROOT, "README.md")
        assert os.path.exists(path)

    def test_readme_has_architecture(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
            content = f.read()
        assert "Architecture" in content
        assert "Sniffer" in content or "Pipeline" in content

    def test_readme_has_quick_start(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
            content = f.read()
        assert "Quick Start" in content or "Getting Started" in content

    def test_readme_has_api_docs(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
            content = f.read()
        assert "/docs" in content
        assert "Swagger" in content or "OpenAPI" in content or "redoc" in content

    def test_readme_has_testing_section(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
            content = f.read()
        assert "pytest" in content or "Testing" in content

    def test_readme_has_security_section(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
            content = f.read()
        assert "Security" in content
        assert "JWT" in content

    def test_readme_has_project_structure(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
            content = f.read()
        assert "Project Structure" in content or "Structure" in content
        assert "gateway/" in content
        assert "shared/" in content

    def test_readme_is_substantial(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 3000, "README is too short for a production project"


class TestChangelog:
    """CHANGELOG must document all phases."""

    def test_changelog_exists(self):
        path = os.path.join(PROJECT_ROOT, "CHANGELOG.md")
        assert os.path.exists(path)

    def test_changelog_has_all_phases(self):
        with open(os.path.join(PROJECT_ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
            content = f.read()
        assert "Phase 1" in content
        assert "Phase 2" in content
        assert "Phase 3" in content
        assert "Phase 4" in content
        assert "Phase 5" in content

    def test_changelog_has_versions(self):
        with open(os.path.join(PROJECT_ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
            content = f.read()
        assert "[1.0.0]" in content
        assert "[1.4.0]" in content


# ===================================================================
# OpenAPI Tests
# ===================================================================

class TestOpenAPIDocs:
    """Both gateways must have Swagger/ReDoc enabled."""

    def test_gateway_has_docs_enabled(self):
        from gateway.main import app as gw_app
        assert gw_app.docs_url == "/docs"
        assert gw_app.redoc_url == "/redoc"
        assert gw_app.title == "SecureNet SOC API Gateway"

    def test_gateway_has_tags(self):
        from gateway.main import app as gw_app
        assert gw_app.openapi_tags is not None
        tag_names = {t["name"] for t in gw_app.openapi_tags}
        assert "Auth" in tag_names
        assert "Alerts" in tag_names

    def test_gateway_version_current(self):
        from gateway.main import app as gw_app
        assert gw_app.version == "1.4.0"

    def test_mobile_gateway_has_docs_enabled(self):
        from mobile_gateway.main import app as mg_app
        assert mg_app.docs_url == "/docs"
        assert mg_app.redoc_url == "/redoc"
        assert mg_app.title == "SecureNet Mobile SOC Gateway"

    def test_mobile_gateway_has_tags(self):
        from mobile_gateway.main import app as mg_app
        assert mg_app.openapi_tags is not None
        tag_names = {t["name"] for t in mg_app.openapi_tags}
        assert "Auth" in tag_names
        assert "Decisions" in tag_names
        assert "Devices" in tag_names

    def test_mobile_gateway_version_current(self):
        from mobile_gateway.main import app as mg_app
        assert mg_app.version == "1.4.0"


# ===================================================================
# Build Optimization Tests
# ===================================================================

class TestDockerIgnore:
    def test_dockerignore_exists(self):
        path = os.path.join(PROJECT_ROOT, ".dockerignore")
        assert os.path.exists(path)

    def test_dockerignore_excludes_critical(self):
        with open(os.path.join(PROJECT_ROOT, ".dockerignore"), encoding="utf-8") as f:
            content = f.read()
        assert ".env" in content
        assert "tests/" in content
        assert "__pycache__" in content
        assert "node_modules" in content
        assert ".git" in content
