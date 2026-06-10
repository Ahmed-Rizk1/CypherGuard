"""
Gateway API integration tests (updated for Phase 2 versioned routes).
"""

import pytest
from httpx import AsyncClient, ASGITransport
from gateway.main import app


@pytest.mark.asyncio
async def test_metrics_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/metrics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_alerts_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/alerts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_firewall_status_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/firewall/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_public():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_logout_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/auth/logout")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_v1_user_profile_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/api/users/me")
    assert response.status_code == 401
