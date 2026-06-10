"""
Tests for Phase 2 — API completeness, response envelopes, and pagination.

Covers:
- Standard response envelope format
- Cursor pagination logic
- ORM-to-dict conversions
- Mobile gateway endpoint structure
- Gateway endpoint structure
"""

import os
import uuid
from datetime import datetime, timezone

import pytest

os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-validation"
os.environ["INTERNAL_API_KEY"] = "test-internal-key-long-enough-for-validation"

from shared.responses import (
    success_response, paginated_response, error_response,
    alert_to_dict, blocked_ip_to_dict, decision_to_dict, user_to_dict,
)


# ===================================================================
# Response Envelope Tests
# ===================================================================

class TestSuccessResponse:
    def test_basic_success(self):
        resp = success_response(data={"key": "value"})
        body = resp.body
        import json
        data = json.loads(body)
        assert data["success"] is True
        assert data["data"]["key"] == "value"
        assert resp.status_code == 200

    def test_custom_status_code(self):
        resp = success_response(data=None, status_code=201)
        assert resp.status_code == 201

    def test_custom_message(self):
        import json
        resp = success_response(message="Created")
        data = json.loads(resp.body)
        assert data["message"] == "Created"


class TestPaginatedResponse:
    def test_structure(self):
        import json
        resp = paginated_response(
            data=[{"id": "1"}, {"id": "2"}],
            cursor="2026-01-01T00:00:00",
            per_page=20,
            has_next=True,
        )
        body = json.loads(resp.body)
        assert body["success"] is True
        assert len(body["data"]) == 2
        assert body["meta"]["cursor"] == "2026-01-01T00:00:00"
        assert body["meta"]["per_page"] == 20
        assert body["meta"]["has_next"] is True

    def test_no_cursor_when_empty(self):
        import json
        resp = paginated_response(data=[], cursor=None, per_page=20, has_next=False)
        body = json.loads(resp.body)
        assert body["meta"]["cursor"] is None
        assert body["meta"]["has_next"] is False

    def test_optional_total(self):
        import json
        resp = paginated_response(data=[], cursor=None, per_page=20, has_next=False, total=42)
        body = json.loads(resp.body)
        assert body["meta"]["total"] == 42


class TestErrorResponse:
    def test_error_structure(self):
        import json
        resp = error_response("AUTH_TOKEN_EXPIRED", "Token has expired", 401)
        body = json.loads(resp.body)
        assert body["success"] is False
        assert body["error"]["code"] == "AUTH_TOKEN_EXPIRED"
        assert body["error"]["message"] == "Token has expired"
        assert resp.status_code == 401

    def test_error_with_details(self):
        import json
        resp = error_response("VALIDATION_ERROR", "Bad input", 400, details={"field": "email"})
        body = json.loads(resp.body)
        assert body["error"]["details"]["field"] == "email"


# ===================================================================
# ORM-to-Dict Conversion Tests
# ===================================================================

class MockAlert:
    def __init__(self):
        self.id = uuid.uuid4()
        self.src_ip = "192.168.1.100"
        self.attack_type = "DDoS"
        self.severity = "critical"
        self.confidence = 0.95
        self.explanation = "High packet rate"
        self.recommendation = "Block IP"
        self.status = "new"
        self.analyst_notes = None
        self.created_at = datetime(2026, 5, 16, tzinfo=timezone.utc)
        self.resolved_at = None
        self.resolved_by = None

class MockBlockedIP:
    def __init__(self):
        self.id = uuid.uuid4()
        self.ip_address = "10.0.0.1"
        self.reason = "DDoS"
        self.blocked_by = "system"
        self.is_active = True
        self.created_at = datetime(2026, 5, 16, tzinfo=timezone.utc)
        self.expires_at = None
        self.unblocked_at = None

class MockDecision:
    def __init__(self):
        self.id = uuid.uuid4()
        self.alert_id = "alert-123"
        self.action = "APPROVE"
        self.source = "mobile"
        self.trace_id = "trace-456"
        self.created_at = datetime(2026, 5, 16, tzinfo=timezone.utc)

class MockUser:
    def __init__(self):
        self.id = uuid.uuid4()
        self.email = "admin@securenet.local"
        self.role = "admin"
        self.is_active = True
        self.created_at = datetime(2026, 5, 16, tzinfo=timezone.utc)
        self.last_login = datetime(2026, 5, 16, tzinfo=timezone.utc)


class TestAlertToDict:
    def test_contains_all_fields(self):
        d = alert_to_dict(MockAlert())
        required = ["id", "src_ip", "attack_type", "severity", "confidence",
                     "explanation", "recommendation", "status", "created_at"]
        for field in required:
            assert field in d

    def test_id_is_string(self):
        d = alert_to_dict(MockAlert())
        assert isinstance(d["id"], str)

    def test_dates_are_iso_strings(self):
        d = alert_to_dict(MockAlert())
        assert "2026-05-16" in d["created_at"]

    def test_none_resolved_at(self):
        d = alert_to_dict(MockAlert())
        assert d["resolved_at"] is None

    def test_no_password_hash(self):
        """Alert dict must never contain password-related fields."""
        d = alert_to_dict(MockAlert())
        assert "password" not in str(d).lower()


class TestBlockedIPToDict:
    def test_contains_all_fields(self):
        d = blocked_ip_to_dict(MockBlockedIP())
        required = ["id", "ip_address", "reason", "blocked_by", "is_active", "created_at"]
        for field in required:
            assert field in d


class TestDecisionToDict:
    def test_contains_all_fields(self):
        d = decision_to_dict(MockDecision())
        required = ["id", "alert_id", "action", "source", "trace_id", "created_at"]
        for field in required:
            assert field in d


class TestUserToDict:
    def test_contains_safe_fields(self):
        d = user_to_dict(MockUser())
        required = ["id", "email", "role", "is_active", "created_at", "last_login"]
        for field in required:
            assert field in d

    def test_no_password_hash(self):
        """User dict must NEVER contain password hash."""
        d = user_to_dict(MockUser())
        assert "password" not in str(d).lower()
        assert "hash" not in str(d).lower()


# ===================================================================
# Gateway API Tests (httpx ASGITransport)
# ===================================================================

from httpx import AsyncClient, ASGITransport
from gateway.main import app as gateway_app


class TestGatewayPhase2Endpoints:
    @pytest.mark.asyncio
    async def test_health(self):
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_v1_alerts_requires_auth(self):
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/v1/api/alerts")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_v1_dashboard_requires_auth(self):
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/v1/api/dashboard/summary")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_v1_logout_requires_auth(self):
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/v1/auth/logout")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_legacy_alerts_still_works(self):
        """Backward compat: /api/alerts should still exist."""
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/alerts")
        assert r.status_code == 401  # Auth required, but route exists


class TestMobileGatewayPhase2Endpoints:
    @pytest.mark.asyncio
    async def test_health(self):
        from mobile_gateway.main import app as mobile_app
        transport = ASGITransport(app=mobile_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_v1_alerts_requires_auth(self):
        from mobile_gateway.main import app as mobile_app
        transport = ASGITransport(app=mobile_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/v1/mobile/alerts")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_v1_profile_requires_auth(self):
        from mobile_gateway.main import app as mobile_app
        transport = ASGITransport(app=mobile_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/v1/mobile/users/me")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_v1_firewall_requires_auth(self):
        from mobile_gateway.main import app as mobile_app
        transport = ASGITransport(app=mobile_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/v1/mobile/firewall")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_v1_dashboard_requires_auth(self):
        from mobile_gateway.main import app as mobile_app
        transport = ASGITransport(app=mobile_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/v1/mobile/dashboard/summary")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_v1_decisions_requires_auth(self):
        from mobile_gateway.main import app as mobile_app
        transport = ASGITransport(app=mobile_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/v1/mobile/decisions")
        assert r.status_code == 401
