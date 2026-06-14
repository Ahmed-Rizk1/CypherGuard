"""
PostgreSQL database layer for SecureNet SOC (SaaS Multi-Tenant).

Uses SQLAlchemy 2.0 async ORM with asyncpg driver.
Provides persistent storage for:
- Tenant organizations and billing
- User accounts and authentication
- Alert records and audit trail
- Blocked IP history
- ML prediction logs
- Sensor management
- API keys
- Notifications

Multi-tenancy is enforced via:
1. `tenant_id` column on all data tables
2. PostgreSQL Row-Level Security (RLS) policies
3. `tenant_session()` context manager that sets `app.tenant_id` per session

Usage:
    from shared.database import tenant_session, Alert, BlockedIP

    async with tenant_session(tenant_id) as session:
        alert = Alert(src_ip="1.2.3.4", attack_type="DDoS", severity="critical")
        session.add(alert)
        await session.commit()
"""

import os
import uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from sqlalchemy import String, Float, Boolean, Text, ForeignKey, text, Integer
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://securenet:securenet@localhost:5432/securenet",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,            # Verify connections are alive
    pool_recycle=300,               # Recycle connections every 5 min
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Default tenant ID for backward compatibility and migration
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tenant & Organization Models (NEW for SaaS)
# ---------------------------------------------------------------------------

class Tenant(Base):
    """SaaS tenant (organization/company)."""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", use_alter=True), nullable=True
    )
    plan: Mapped[str] = mapped_column(String(50), default="free")  # free|pro|business|enterprise
    status: Mapped[str] = mapped_column(String(20), default="trial")  # trial|active|suspended|cancelled
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    max_sensors: Mapped[int] = mapped_column(Integer, default=1)
    max_users: Mapped[int] = mapped_column(Integer, default=1)
    max_ai_analyses_monthly: Mapped[int] = mapped_column(Integer, default=50)
    ai_analyses_used: Mapped[int] = mapped_column(Integer, default=0)
    ai_analyses_reset_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # MSSP future support
    parent_tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tenants.id"), nullable=True
    )
    mssp_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class Sensor(Base):
    """Deployed sensor agents on customer networks."""
    __tablename__ = "sensors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt hash
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)  # first 8 chars for display
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|active|offline|revoked
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class APIKey(Base):
    """API keys for programmatic access."""
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    scopes: Mapped[dict] = mapped_column(JSONB, default=lambda: {"read": True, "write": False})
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class Subscription(Base):
    """Stripe subscription state mirror."""
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), unique=True, nullable=False
    )
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False)  # free|pro|business|enterprise
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # active|past_due|canceled|trialing
    current_period_start: Mapped[datetime] = mapped_column(nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class UsageRecord(Base):
    """Tracks AI analysis usage for usage-based billing."""
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ai_analysis, sensor_hours
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(nullable=False)
    reported_to_stripe: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class Notification(Base):
    """In-app notifications for tenants/users."""
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )  # nullable = tenant-wide notification
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # alert|sensor|billing|system
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    read_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


# ---------------------------------------------------------------------------
# ORM Models (Updated with tenant_id)
# ---------------------------------------------------------------------------

class User(Base):
    """SOC dashboard user accounts."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="viewer"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()")
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class Alert(Base):
    """Detected threat alerts — permanent audit log."""
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    attack_type: Mapped[Optional[str]] = mapped_column(String(100))
    severity: Mapped[Optional[str]] = mapped_column(String(20))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)
    raw_features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    llm_response: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    analyst_notes: Mapped[Optional[str]] = mapped_column(Text)
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"), index=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class DecisionLog(Base):
    """Immutable audit log of all human and automated SOC decisions."""
    __tablename__ = "decision_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    alert_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False) # e.g., BLOCK, ALLOW, ESCALATE
    source: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., mobile, timeout, auto
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()")
    )


class BlockedIP(Base):
    """Blocked IP records with full audit trail."""
    __tablename__ = "blocked_ips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    ip_address: Mapped[str] = mapped_column(
        String(45), nullable=False, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text)
    blocked_by: Mapped[str] = mapped_column(String(100), default="system")
    alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("alerts.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()")
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    unblocked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class MLPrediction(Base):
    """ML prediction log for model performance tracking."""
    __tablename__ = "ml_predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prediction: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    model_version: Mapped[Optional[str]] = mapped_column(String(50))
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"), index=True
    )


class AuditLog(Base):
    """System-wide audit log for compliance and forensics."""
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    actor: Mapped[Optional[str]] = mapped_column(String(255))  # user email or 'system'
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[str]] = mapped_column(String(255))
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"), index=True
    )


class ModelRegistry(Base):
    """Registry of trained ML models for version tracking and hot-reload."""
    __tablename__ = "model_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    algorithm: Mapped[Optional[str]] = mapped_column(String(100))
    accuracy: Mapped[Optional[float]] = mapped_column(Float)
    f1_score: Mapped[Optional[float]] = mapped_column(Float)
    feature_columns: Mapped[Optional[dict]] = mapped_column(JSONB)
    training_samples: Mapped[Optional[int]] = mapped_column(Integer)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()")
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class MLExperiment(Base):
    """Experiment tracking for ML model training runs (like MLflow).

    MULTI-TENANT:
        tenant_id is nullable — system-level experiments (auto-retrain, CLI)
        use tenant_id=NULL and are visible to all tenants via RLS policy.
        Experiments created through the API are scoped to the requesting tenant.
    """

    __tablename__ = "ml_experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    experiment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    hyperparameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dataset_name: Mapped[Optional[str]] = mapped_column(String(255))
    dataset_rows: Mapped[Optional[int]] = mapped_column(Integer)
    feature_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Training metrics
    accuracy: Mapped[Optional[float]] = mapped_column(Float)
    precision: Mapped[Optional[float]] = mapped_column(Float)
    recall: Mapped[Optional[float]] = mapped_column(Float)
    f1_score: Mapped[Optional[float]] = mapped_column(Float)
    roc_auc: Mapped[Optional[float]] = mapped_column(Float)

    # Cross-validation details
    cv_scores: Mapped[Optional[dict]] = mapped_column(JSONB)
    cv_mean: Mapped[Optional[float]] = mapped_column(Float)
    cv_std: Mapped[Optional[float]] = mapped_column(Float)

    # Model artifacts
    confusion_matrix: Mapped[Optional[dict]] = mapped_column(JSONB)
    feature_importance: Mapped[Optional[dict]] = mapped_column(JSONB)
    model_file_path: Mapped[Optional[str]] = mapped_column(String(500))
    model_hash: Mapped[Optional[str]] = mapped_column(String(64))

    # Training metadata
    training_time_seconds: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Activation tracking
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)
    promoted_to_registry: Mapped[bool] = mapped_column(Boolean, default=False)
    registry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("model_registry.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"), index=True
    )


# ---------------------------------------------------------------------------
# Invitation Model (for team invites)
# ---------------------------------------------------------------------------

class Invitation(Base):
    """Pending team invitations."""
    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="analyst")
    invited_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _validate_tenant_id(tenant_id: str) -> str:
    """
    Validate that tenant_id is a well-formed UUID string.

    SECURITY: Prevents SQL injection via malformed tenant_id values
    being passed to SET LOCAL. Although parameterized, defense-in-depth
    requires format validation.

    Raises ValueError if the format is invalid.
    """
    if not tenant_id:
        return ""
    tid = str(tenant_id).strip()
    try:
        # Round-trip through uuid.UUID to validate format
        validated = str(uuid.UUID(tid))
        return validated
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid tenant_id format: {tenant_id!r}")


async def get_session():
    """FastAPI dependency for database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def tenant_session(tenant_id: str):
    """
    Create a database session scoped to a specific tenant via RLS.

    Sets the PostgreSQL session variable `app.tenant_id` which is used
    by Row-Level Security policies to filter all queries automatically.

    CRITICAL SAFETY NOTES:
    - asyncpg uses implicit transactions: the first SQL statement in a
      session auto-begins a transaction. SET LOCAL is therefore scoped
      to that implicit transaction and discarded on COMMIT/ROLLBACK.
    - The finally block always RESETs app.tenant_id as defense-in-depth
      to prevent tenant context from leaking across pooled connections.
    - tenant_id is validated as a UUID to prevent injection.
    - Callers CAN call session.commit() / session.flush() as before.

    Args:
        tenant_id: UUID string of the tenant to scope the session to.

    Raises:
        ValueError: If tenant_id is not a valid UUID format.
    """
    tid = _validate_tenant_id(tenant_id)

    async with async_session() as session:
        try:
            if tid:
                # Execute SET LOCAL as the first statement in the session.
                # asyncpg auto-begins a transaction, so SET LOCAL is scoped.
                await session.execute(
                    text(f"SET LOCAL app.tenant_id = '{tid}'")
                )
            yield session
        except Exception:
            # On error, ensure rollback so SET LOCAL is discarded
            await session.rollback()
            raise
        finally:
            # DEFENSE-IN-DEPTH: Reset tenant context even after commit/rollback.
            # Prevents any edge case where the pooled connection retains state.
            try:
                await session.execute(text("RESET app.tenant_id"))
            except Exception:
                # If RESET fails (connection closed/broken), pool_pre_ping
                # will discard this connection on next checkout.
                pass


@asynccontextmanager
async def tenant_session_readonly(tenant_id: str):
    """
    Read-only tenant session variant.

    Same tenant isolation as tenant_session() but additionally sets the
    transaction to READ ONLY for extra protection on query-only paths.
    This prevents accidental writes in read-only endpoints.

    Args:
        tenant_id: UUID string of the tenant to scope the session to.
    """
    tid = _validate_tenant_id(tenant_id)

    async with async_session() as session:
        try:
            if tid:
                await session.execute(
                    text(f"SET LOCAL app.tenant_id = '{tid}'")
                )
            await session.execute(text("SET TRANSACTION READ ONLY"))
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("RESET app.tenant_id"))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------

import logging

_audit_logger = logging.getLogger("securenet.audit")


async def write_audit_log(
    action: str,
    actor: str = "system",
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Write an entry to the audit_log table. Fire-and-forget; never raises."""
    try:
        async with async_session() as session:
            entry = AuditLog(
                tenant_id=tenant_id,
                actor=actor,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        _audit_logger.error(f"Audit log write failed: {e}")
