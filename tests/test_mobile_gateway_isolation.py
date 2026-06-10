"""
Integration tests for the Mobile Gateway security boundaries and tenant isolation.
Runs against a local SQLite database with custom type overrides and transaction rollback safety.
"""

import os
import sys
import uuid
import time
import pytest
import bcrypt
import asyncio
import contextvars
from unittest.mock import AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

# Set test environment credentials
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-validation"
os.environ["INTERNAL_API_KEY"] = "test-internal-key-long-enough-for-validation"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ===================================================================
# SQLAlchemy PostgreSQL Type Overrides for SQLite Compatibility
# ===================================================================
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy.types import TypeDecorator, CHAR, JSON

class SQLiteUUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(str(value))

class SQLiteJSONB(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__()

# Inject custom classes into the postgresql dialect module so the DB models load them
pg.UUID = SQLiteUUID
pg.JSONB = SQLiteJSONB

# Now safe to import app and database modules
from mobile_gateway.main import app as mobile_app
from shared.database import User, Tenant, Alert, BlockedIP, Notification, Base
from shared.auth import create_access_token, create_refresh_token, decode_jwt, TokenPayload
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import with_loader_criteria, Session
from sqlalchemy import event
import datetime

# ===================================================================
# Database Transaction Rollback Fixture (using SQLite)
# ===================================================================

TEST_DB_FILE = "test_db_isolation.sqlite"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_FILE}", echo=False)

@event.listens_for(test_engine.sync_engine, "connect")
def configure_sqlite(dbapi_connection, connection_record):
    # Enable foreign keys
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    
    # Register NOW function
    dbapi_connection.create_function("now", 0, lambda: datetime.datetime.now().isoformat())

# Global ContextVar to scope tenant filtering
test_tenant_context = contextvars.ContextVar("test_tenant_context", default=None)

@event.listens_for(Session, "do_orm_execute")
def no_cross_tenant_queries(orm_execute_state):
    tid = test_tenant_context.get()
    if tid:
        if (
            (orm_execute_state.is_select or orm_execute_state.is_update or orm_execute_state.is_delete)
            and not orm_execute_state.is_column_load
            and not orm_execute_state.is_relationship_load
        ):
            stmt = orm_execute_state.statement
            for mapper in orm_execute_state.all_mappers:
                cls = mapper.class_
                if hasattr(cls, "tenant_id"):
                    t_uuid = uuid.UUID(str(tid)) if isinstance(tid, (str, uuid.UUID)) else tid
                    stmt = stmt.where(cls.tenant_id == t_uuid)
            orm_execute_state.statement = stmt

@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    # Remove any existing DB file
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass
            
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield
    
    await test_engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

@pytest.fixture
async def db_session():
    """
    Creates an SQLite connection and starts a transaction.
    Yields a session and rolls back the transaction at the end.
    """
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


@pytest.fixture(autouse=True)
async def override_db(db_session):
    """
    Patches async_session and tenant_session contexts inside the app
    to run all requests within the same transaction session.
    """
    @asynccontextmanager
    async def mock_async_session():
        yield db_session

    @asynccontextmanager
    async def mock_tenant_session(tenant_id: str):
        token = test_tenant_context.set(tenant_id)
        try:
            yield db_session
        finally:
            test_tenant_context.reset(token)

    # Patch modules that make DB sessions
    with patch("mobile_gateway.main.async_session", mock_async_session), \
         patch("mobile_gateway.main.tenant_session", mock_tenant_session), \
         patch("shared.database.async_session", mock_async_session), \
         patch("shared.database.tenant_session", mock_tenant_session):
        yield


# ===================================================================
# Redis Mock Fixture
# ===================================================================

@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis client interactions to prevent external Redis dependency in tests."""
    from shared.redis_client import redis_manager
    redis_manager.client = AsyncMock()
    redis_manager.client.get = AsyncMock(return_value=None)
    redis_manager.client.set = AsyncMock(return_value=True)
    redis_manager.client.exists = AsyncMock(return_value=0)
    redis_manager.client.hset = AsyncMock(return_value=1)
    redis_manager.client.hget = AsyncMock(return_value=None)
    redis_manager.get_live_metrics = AsyncMock(return_value={"cps": 0.0, "fps": 0.0})
    yield


# ===================================================================
# Helper Data Seed Functions
# ===================================================================

async def create_test_tenant(session, name: str, slug: str, status: str = "active") -> Tenant:
    tenant = Tenant(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        status=status,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def create_test_user(session, tenant_id: uuid.UUID, email: str, password: str, role: str = "analyst") -> User:
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=email,
        password_hash=pw_hash,
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def create_test_alert(session, tenant_id: uuid.UUID, src_ip: str, severity: str) -> Alert:
    alert = Alert(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        src_ip=src_ip,
        attack_type="DDoS",
        severity=severity,
        confidence=0.9,
        status="new",
    )
    session.add(alert)
    await session.flush()
    return alert


# ===================================================================
# TEST CASES
# ===================================================================

@pytest.mark.asyncio
async def test_health_public():
    """Public health check must return 200."""
    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_login_success(db_session):
    """Analyst login returns tokens on valid credentials."""
    tenant = await create_test_tenant(db_session, "Tenant A", "tenant-a")
    await create_test_user(db_session, tenant.id, "dev@tenant-a.com", "Password123!")

    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/v1/mobile/auth", json={
            "email": "dev@tenant-a.com",
            "password": "Password123!"
        })
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]


@pytest.mark.asyncio
async def test_login_invalid_password(db_session):
    """Login fails on invalid password."""
    tenant = await create_test_tenant(db_session, "Tenant A", "tenant-a")
    await create_test_user(db_session, tenant.id, "dev@tenant-a.com", "Password123!")

    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/v1/mobile/auth", json={
            "email": "dev@tenant-a.com",
            "password": "WrongPassword!"
        })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_suspended_tenant_rejected(db_session):
    """Users of suspended tenants are blocked from logging in."""
    tenant = await create_test_tenant(db_session, "Suspended Tenant", "suspended-t", status="suspended")
    await create_test_user(db_session, tenant.id, "dev@suspended.com", "Password123!")

    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/v1/mobile/auth", json={
            "email": "dev@suspended.com",
            "password": "Password123!"
        })
    assert response.status_code == 403
    assert "suspended" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_refresh_preserves_tid():
    """Token refresh preserves the tid (tenant ID) claim on the access token."""
    tid = str(uuid.uuid4())
    ref_token = create_refresh_token("user-123", "analyst", tenant_id=tid)

    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/v1/mobile/auth/refresh", json={
            "refresh_token": ref_token
        })
    assert response.status_code == 200
    new_acc = response.json()["data"]["access_token"]
    payload = decode_jwt(new_acc)
    assert payload.get("tid") == tid


@pytest.mark.asyncio
async def test_tenant_identity_bypass_rejections(db_session):
    """Any manual client tenant_id inputs in body, query, or header must be blocked with 403."""
    tenant = await create_test_tenant(db_session, "Tenant A", "tenant-a")
    user = await create_test_user(db_session, tenant.id, "dev@tenant-a.com", "Password123!")
    token = create_access_token(str(user.id), user.role, tenant_id=str(tenant.id))
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Reject Query Parameter Overrides
        res_query = await ac.get(f"/v1/mobile/alerts?tenant_id={uuid.uuid4()}", headers=headers)
        assert res_query.status_code == 403

        # 2. Reject HTTP Headers Overrides
        res_header = await ac.get("/v1/mobile/alerts", headers={
            **headers,
            "X-Tenant-ID": str(uuid.uuid4())
        })
        assert res_header.status_code == 403

        # 3. Reject Request JSON Body Overrides
        res_body = await ac.post("/v1/mobile/firewall/block", json={
            "ip_address": "1.1.1.1",
            "reason": "Test Override",
            "tenant_id": str(uuid.uuid4())
        }, headers=headers)
        assert res_body.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation_rls(db_session):
    """RLS ensures Tenant A user cannot see Tenant B alerts."""
    # Tenant A
    tenant_a = await create_test_tenant(db_session, "Tenant A", "tenant-a")
    user_a = await create_test_user(db_session, tenant_a.id, "dev@tenant-a.com", "Password123!")
    alert_a = await create_test_alert(db_session, tenant_a.id, "192.168.1.10", "critical")

    # Tenant B
    tenant_b = await create_test_tenant(db_session, "Tenant B", "tenant-b")
    alert_b = await create_test_alert(db_session, tenant_b.id, "10.0.0.50", "high")

    # Authenticate as Tenant A
    token_a = create_access_token(str(user_a.id), user_a.role, tenant_id=str(tenant_a.id))
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/mobile/alerts", headers=headers)
    
    assert response.status_code == 200
    items = response.json()["data"]
    # Should only return Alert A, never Alert B
    item_ids = [item["id"] for item in items]
    assert str(alert_a.id) in item_ids
    assert str(alert_b.id) not in item_ids


@pytest.mark.asyncio
async def test_block_ip_scoping(db_session):
    """Creating blocked IP scopes the record to the user's tenant_id."""
    tenant = await create_test_tenant(db_session, "Tenant A", "tenant-a")
    user = await create_test_user(db_session, tenant.id, "admin@tenant-a.com", "Password123!", role="admin")
    token = create_access_token(str(user.id), user.role, tenant_id=str(tenant.id))
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=mobile_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/v1/mobile/firewall/block", json={
            "ip_address": "8.8.8.8",
            "reason": "Integration Test Block"
        }, headers=headers)

    assert response.status_code == 201
    
    # Query database and verify scoping
    async with db_session.begin_nested() as _:
        result = await db_session.execute(
            select(BlockedIP).where(BlockedIP.ip_address == "8.8.8.8")
        )
        record = result.scalar_one_or_none()
    assert record is not None
    assert record.tenant_id == tenant.id
