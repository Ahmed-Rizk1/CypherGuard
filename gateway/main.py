"""
SecureNet SOC — API Gateway Service (SaaS Multi-Tenant)

Central entry point for the React dashboard and external API consumers.
Provides:
- WebSocket for real-time dashboard telemetry (tenant-scoped)
- REST API with PostgreSQL-backed alerts, cursor pagination
- SaaS signup + email verification + onboarding
- Sensor management (CRUD + API key generation)
- Team management (invite, list, remove)
- Billing portal (Stripe checkout, portal, usage)
- Firewall management (block/unblock)
- User profile management
- Dashboard summary statistics
- JWT auth with jti, tid (tenant), blacklisting, refresh rotation
- Standard response envelope
- API versioning (/v1 + backward compat)
- Security headers, rate limiting, request size limits
"""

import os
import sys
import re
import time
import json
import uuid
import asyncio
import secrets
import ipaddress
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import uvicorn
import bcrypt
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    Depends, HTTPException, Query, Request,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, desc, and_
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging
from shared.redis_client import redis_manager
from shared.database import (
    async_session, tenant_session, DEFAULT_TENANT_ID,
    Alert, BlockedIP, User, DecisionLog, Tenant, Sensor, Invitation, Notification,
    MLExperiment, ModelRegistry,
    write_audit_log,
)
from ml_engine.feature_engineering import FEATURE_COLUMNS
from shared.auth import (
    verify_jwt, require_role, create_access_token, create_refresh_token,
    refresh_access_token, validate_secrets, TokenPayload, TokenResponse,
    decode_jwt, JWT_EXPIRY_SECONDS,
    blacklist_token, is_token_blacklisted,
    record_failed_login, clear_failed_logins, is_account_locked,
    security_headers_middleware, request_size_limit_middleware,
)
from shared.responses import (
    success_response, paginated_response, error_response,
    alert_to_dict, blocked_ip_to_dict, decision_to_dict, user_to_dict,
    sensor_to_dict, tenant_to_dict, notification_to_dict,
)
from shared.validators import HealthResponse
from shared.rate_limiter import RateLimiter
from shared.metrics import WEBSOCKET_CONNECTIONS, AUTH_EVENTS, FIREWALL_BLOCKS, metrics_endpoint
from shared.middleware import get_current_tenant, require_active_tenant
from shared.feature_gates import check_tenant_limit, require_feature
from shared.email import (
    send_verification_email, send_invite_email,
    generate_verification_token, generate_invite_token,
)

load_dotenv()
logger = setup_logging("gateway")

SERVICE_START_TIME = time.time()
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:80").split(",")


# ===================================================================
# WebSocket Manager (tenant-scoped)
# ===================================================================

class ConnectionManager:
    def __init__(self):
        # tenant_id -> list of WebSocket connections
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, tenant_id: str = "") -> None:
        await ws.accept()
        if tenant_id not in self.connections:
            self.connections[tenant_id] = []
        self.connections[tenant_id].append(ws)
        total = sum(len(v) for v in self.connections.values())
        WEBSOCKET_CONNECTIONS.set(total)

    def disconnect(self, ws: WebSocket, tenant_id: str = "") -> None:
        if tenant_id in self.connections:
            if ws in self.connections[tenant_id]:
                self.connections[tenant_id].remove(ws)
            if not self.connections[tenant_id]:
                del self.connections[tenant_id]
        total = sum(len(v) for v in self.connections.values())
        WEBSOCKET_CONNECTIONS.set(total)

    async def broadcast_to_tenant(self, tenant_id: str, message: dict) -> None:
        """Send a message to all WebSocket clients for a specific tenant."""
        conns = self.connections.get(tenant_id, [])
        disconnected = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws, tenant_id)

    async def broadcast_all(self, message: dict) -> None:
        """Broadcast to all tenants (used for system messages)."""
        for tid in list(self.connections.keys()):
            await self.broadcast_to_tenant(tid, message)


ws_manager = ConnectionManager()
rate_limiter = RateLimiter(max_requests=120, window_seconds=60)
login_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


# ===================================================================
# Request Models
# ===================================================================

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

class RefreshRequest(BaseModel):
    refresh_token: str

class SignupRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    full_name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError("Invalid email format")
        return v.lower()

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=255)

class CreateSensorRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class InviteRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    role: str = Field(default="analyst", pattern="^(admin|analyst|viewer)$")

class BlockIPRequest(BaseModel):
    ip_address: str = Field(..., min_length=7, max_length=45)
    reason: str = Field(default="manual_block", max_length=500)


# ===================================================================
# App Setup
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_secrets()
    await redis_manager.connect()
    push_task = asyncio.create_task(telemetry_push_loop())
    logger.info("API Gateway started (SaaS mode)")
    yield
    push_task.cancel()
    await redis_manager.close()

app = FastAPI(
    title="SecureNet SOC API Gateway",
    version="2.0.0",
    description=(
        "Central REST + WebSocket API for the SecureNet SaaS IDS Platform.\n\n"
        "## Authentication\n"
        "All protected endpoints require a JWT Bearer token in the `Authorization` header.\n\n"
        "## Multi-Tenancy\n"
        "Data is scoped to the tenant identified by the `tid` claim in the JWT.\n\n"
        "## Pagination\n"
        "List endpoints use cursor-based pagination."
    ),
    docs_url="/docs", redoc_url="/redoc", lifespan=lifespan,
    openapi_tags=[
        {"name": "Auth", "description": "Authentication, signup, and token management"},
        {"name": "Onboarding", "description": "New tenant onboarding wizard"},
        {"name": "Alerts", "description": "Threat alert history and management"},
        {"name": "Dashboard", "description": "Aggregated statistics"},
        {"name": "Firewall", "description": "IP blocklist management"},
        {"name": "Sensors", "description": "Sensor deployment management"},
        {"name": "Team", "description": "Team and invitation management"},
        {"name": "Billing", "description": "Subscription and usage management"},
        {"name": "Notifications", "description": "In-app notification center"},
        {"name": "Users", "description": "User profile management"},
        {"name": "Health", "description": "Service health checks"},
    ],
    contact={"name": "SecureNet Team"},
    license_info={"name": "Proprietary"},
)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(request_size_limit_middleware)
app.add_middleware(
    CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
app.add_route("/metrics", metrics_endpoint)


# ===================================================================
# WebSocket — Telemetry (tenant-scoped)
# ===================================================================

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket, token: str = Query(default="")):
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        payload = decode_jwt(token)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    jti = payload.get("jti", "")
    if jti and await is_token_blacklisted(jti):
        await websocket.close(code=4001, reason="Token revoked")
        return

    tenant_id = payload.get("tid", "")
    token_exp = payload.get("exp", 0)
    remaining = max(token_exp - time.time(), 0)
    await ws_manager.connect(websocket, tenant_id)

    async def _watchdog():
        await asyncio.sleep(remaining)
        try:
            await websocket.send_json({"type": "token_expired", "data": {"message": "Session expired."}})
            await websocket.close(code=4001, reason="Token expired")
        except Exception:
            pass

    expiry_task = asyncio.create_task(_watchdog())
    try:
        # Send initial data scoped to tenant
        blocked = list(await redis_manager.get_blocked_ips(tenant_id=tenant_id))
        await websocket.send_json({"type": "blocked_ips", "data": blocked})
        alerts = await redis_manager.get_recent_alerts(count=50, tenant_id=tenant_id)
        await websocket.send_json({"type": "alert_list", "data": alerts})

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if len(data) > 4096:
                    await websocket.close(code=1009, reason="Message too large")
                    break
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, tenant_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, tenant_id)
    finally:
        expiry_task.cancel()


async def telemetry_push_loop():
    _last_hashes: dict[str, dict] = {}
    while True:
        try:
            for tenant_id, conns in list(ws_manager.connections.items()):
                if not conns:
                    continue
                if tenant_id not in _last_hashes:
                    _last_hashes[tenant_id] = {"blocked": "", "alerts": ""}

                metrics = await redis_manager.get_live_metrics(tenant_id=tenant_id)
                await ws_manager.broadcast_to_tenant(tenant_id, {"type": "metrics", "data": metrics})

                blocked = list(await redis_manager.get_blocked_ips(tenant_id=tenant_id))
                bh = str(sorted(blocked))
                if bh != _last_hashes[tenant_id]["blocked"]:
                    await ws_manager.broadcast_to_tenant(tenant_id, {"type": "blocked_ips", "data": blocked})
                    _last_hashes[tenant_id]["blocked"] = bh

                alerts = await redis_manager.get_recent_alerts(count=20, tenant_id=tenant_id)
                ah = str(len(alerts)) + (alerts[0].get("alert_id", "") if alerts else "")
                if ah != _last_hashes[tenant_id]["alerts"]:
                    await ws_manager.broadcast_to_tenant(tenant_id, {"type": "alert_list", "data": alerts})
                    _last_hashes[tenant_id]["alerts"] = ah
        except Exception as e:
            logger.error(f"Telemetry push error: {e}")
        await asyncio.sleep(1)


# ===================================================================
# AUTH ENDPOINTS
# ===================================================================

@app.post("/v1/auth/signup", tags=["Auth"])
async def signup(request: SignupRequest, raw_request: Request):
    """Create a new tenant organization and owner account."""
    await login_rate_limiter(raw_request)

    # Check if email is already taken
    async with async_session() as session:
        existing = await session.execute(
            select(User).where(User.email == request.email)
        )
        if existing.scalar_one_or_none():
            return error_response("EMAIL_EXISTS", "An account with this email already exists.", 409)

    # Create slug from company name
    slug = re.sub(r'[^a-z0-9-]', '', request.company_name.lower().replace(' ', '-'))[:50]
    slug = f"{slug}-{secrets.token_hex(3)}"

    # Hash password
    pw_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()

    # Email verification token
    verify_token = generate_verification_token()

    async with async_session() as session:
        # Create tenant
        tenant = Tenant(
            name=request.company_name,
            slug=slug,
            plan="free",
            status="trial",
            trial_ends_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=14),
            max_sensors=1,
            max_users=3,
            max_ai_analyses_monthly=50,
        )
        session.add(tenant)
        await session.flush()  # get tenant.id

        # Create owner user
        user = User(
            tenant_id=tenant.id,
            email=request.email,
            full_name=request.full_name,
            password_hash=pw_hash,
            role="owner",
            is_active=True,
            is_email_verified=False,
        )
        session.add(user)
        await session.flush()

        # Set tenant owner
        tenant.owner_id = user.id
        await session.commit()

        # Store verification token in Redis (24h expiry)
        await redis_manager.client.set(
            f"verify:{verify_token}", json.dumps({
                "user_id": str(user.id),
                "tenant_id": str(tenant.id),
                "email": request.email,
            }),
            ex=86400,
        )

    # Send verification email
    await send_verification_email(request.email, verify_token)

    AUTH_EVENTS.labels(event="signup").inc()
    await write_audit_log(
        action="auth.signup", actor=request.email,
        resource_type="tenant", resource_id=str(tenant.id),
        ip_address=raw_request.client.host if raw_request.client else None,
        tenant_id=str(tenant.id),
    )

    return success_response(
        data={"tenant_id": str(tenant.id), "email": request.email},
        message="Account created. Please check your email to verify.",
        status_code=201,
    )


@app.post("/v1/auth/verify-email", tags=["Auth"])
async def verify_email(request: VerifyEmailRequest):
    """Verify email address using the token from the verification email."""
    raw = await redis_manager.client.get(f"verify:{request.token}")
    if not raw:
        return error_response("INVALID_TOKEN", "Verification token is invalid or expired.", 400)

    data = json.loads(raw)
    user_id = data["user_id"]

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return error_response("USER_NOT_FOUND", "User not found.", 404)

        user.is_email_verified = True
        await session.commit()

    # Clean up token
    await redis_manager.client.delete(f"verify:{request.token}")

    return success_response(message="Email verified successfully. You can now log in.")


@app.post("/v1/auth/login", response_model=TokenResponse, tags=["Auth"])
@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, raw_request: Request):
    """Login with email + password. Returns JWT with tenant context."""
    await login_rate_limiter(raw_request)
    if await is_account_locked(request.email):
        raise HTTPException(status_code=429, detail="Account temporarily locked.")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == request.email, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        dummy_hash = "$2b$12$LJ3m4ys3Lf1vGshMBfeGJOFB.gMOsR6b7R1E0xq4K3e0WZ5v5q3.a"
        pw_hash = user.password_hash if user else dummy_hash

        if not bcrypt.checkpw(request.password.encode(), pw_hash.encode()):
            AUTH_EVENTS.labels(event="login_failure").inc()
            if user:
                await record_failed_login(request.email)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

    await clear_failed_logins(request.email)
    tenant_id = str(user.tenant_id) if user.tenant_id else ""

    # SECURITY: Check tenant status — block login for suspended/cancelled tenants.
    # This runs AFTER password verification to avoid leaking tenant state
    # to attackers who don't know the password.
    if tenant_id:
        async with async_session() as session:
            tenant_result = await session.execute(
                select(Tenant.status).where(Tenant.id == tenant_id)
            )
            tenant_status = tenant_result.scalar_one_or_none()
        if tenant_status and tenant_status not in ("trial", "active"):
            AUTH_EVENTS.labels(event="login_tenant_suspended").inc()
            logger.warning(
                f"Login denied: tenant {tenant_id} status={tenant_status}",
                extra={"email": request.email, "tenant_id": tenant_id},
            )
            raise HTTPException(
                status_code=403,
                detail=f"Your organization's account is {tenant_status}. Contact support.",
            )

    token = create_access_token(str(user.id), user.role, tenant_id=tenant_id)
    refresh = create_refresh_token(str(user.id), user.role, tenant_id=tenant_id)
    AUTH_EVENTS.labels(event="login_success").inc()
    await write_audit_log(
        action="auth.login", actor=request.email,
        resource_type="session", resource_id=str(user.id),
        ip_address=raw_request.client.host if raw_request.client else None,
        tenant_id=tenant_id,
    )

    return TokenResponse(
        access_token=token, refresh_token=refresh,
        expires_in=JWT_EXPIRY_SECONDS, role=user.role,
    )


@app.post("/v1/auth/refresh", tags=["Auth"])
@app.post("/auth/refresh")
async def refresh_token(request: RefreshRequest):
    try:
        result = await refresh_access_token(request.refresh_token)
        AUTH_EVENTS.labels(event="token_refresh").inc()
        return result
    except HTTPException:
        AUTH_EVENTS.labels(event="refresh_failure").inc()
        raise


@app.post("/v1/auth/logout", tags=["Auth"])
@app.post("/auth/logout")
async def logout(token: TokenPayload = Depends(verify_jwt)):
    await blacklist_token(token.jti, int(token.exp - time.time()))
    return success_response(message="Logged out successfully")


# ===================================================================
# ONBOARDING
# ===================================================================

@app.get("/v1/api/onboarding/status", tags=["Onboarding"])
async def onboarding_status(
    auth: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(get_current_tenant),
):
    """Get onboarding completion status."""
    async with tenant_session(tenant_id) as session:
        # Check email verified
        user_q = await session.execute(select(User).where(User.id == auth.sub))
        user = user_q.scalar_one_or_none()
        email_verified = user.is_email_verified if user else False

        # Check sensor deployed
        sensor_q = await session.execute(
            select(func.count(Sensor.id)).where(
                Sensor.tenant_id == tenant_id,
                Sensor.status.in_(["active", "pending"])
            )
        )
        has_sensor = (sensor_q.scalar() or 0) > 0

        # Check team invited
        invite_q = await session.execute(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.id != auth.sub
            )
        )
        has_team = (invite_q.scalar() or 0) > 0

        # Check first alert received
        alert_q = await session.execute(
            select(func.count(Alert.id)).where(Alert.tenant_id == tenant_id)
        )
        has_alerts = (alert_q.scalar() or 0) > 0

    return success_response(data={
        "email_verified": email_verified,
        "sensor_deployed": has_sensor,
        "first_alert": has_alerts,
        "team_invited": has_team,
        "completed": all([email_verified, has_sensor]),
    })


# ===================================================================
# SENSORS
# ===================================================================

@app.get("/v1/api/sensors", tags=["Sensors"])
async def list_sensors(
    auth: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(get_current_tenant),
):
    """List all sensors for the current tenant."""
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            select(Sensor).where(Sensor.tenant_id == tenant_id)
            .order_by(desc(Sensor.created_at))
        )
        sensors = list(result.scalars().all())
    return success_response(data=[sensor_to_dict(s) for s in sensors])


@app.post("/v1/api/sensors", tags=["Sensors"])
async def create_sensor(
    req: CreateSensorRequest,
    auth: TokenPayload = Depends(require_role("owner", "admin")),
    tenant_id: str = Depends(require_active_tenant),
):
    """Create a new sensor and return the API key (shown once)."""
    # Check plan limit
    async with tenant_session(tenant_id) as session:
        count_q = await session.execute(
            select(func.count(Sensor.id)).where(Sensor.tenant_id == tenant_id)
        )
        current_count = count_q.scalar() or 0

    await check_tenant_limit(tenant_id, "max_sensors", current_count)

    # Generate API key
    raw_key = f"sn_{secrets.token_hex(24)}"
    key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
    key_prefix = raw_key[:11]  # "sn_" + first 8 hex

    async with tenant_session(tenant_id) as session:
        sensor = Sensor(
            tenant_id=tenant_id,
            name=req.name,
            api_key_hash=key_hash,
            api_key_prefix=key_prefix,
            status="pending",
        )
        session.add(sensor)
        await session.commit()
        await session.refresh(sensor)

    await write_audit_log(
        action="sensor.create", actor=auth.sub,
        resource_type="sensor", resource_id=str(sensor.id),
        tenant_id=tenant_id,
    )

    return success_response(
        data={
            **sensor_to_dict(sensor),
            "api_key": raw_key,  # Only shown ONCE
        },
        message="Sensor created. Save the API key — it won't be shown again.",
        status_code=201,
    )


@app.delete("/v1/api/sensors/{sensor_id}", tags=["Sensors"])
async def delete_sensor(
    sensor_id: str,
    auth: TokenPayload = Depends(require_role("owner", "admin")),
    tenant_id: str = Depends(get_current_tenant),
):
    """Revoke a sensor's API key."""
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            select(Sensor).where(Sensor.id == sensor_id, Sensor.tenant_id == tenant_id)
        )
        sensor = result.scalar_one_or_none()
        if not sensor:
            return error_response("RESOURCE_NOT_FOUND", "Sensor not found", 404)
        sensor.status = "revoked"
        await session.commit()

    return success_response(message="Sensor revoked successfully")


# ===================================================================
# TEAM
# ===================================================================

@app.get("/v1/api/team", tags=["Team"])
async def list_team(
    auth: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(get_current_tenant),
):
    """List all team members and pending invitations."""
    async with tenant_session(tenant_id) as session:
        users_q = await session.execute(
            select(User).where(User.tenant_id == tenant_id)
            .order_by(User.created_at)
        )
        users = list(users_q.scalars().all())

        invites_q = await session.execute(
            select(Invitation).where(
                Invitation.tenant_id == tenant_id,
                Invitation.accepted_at == None
            )
        )
        invites = list(invites_q.scalars().all())

    return success_response(data={
        "members": [user_to_dict(u) for u in users],
        "pending_invitations": [
            {"email": i.email, "role": i.role, "created_at": i.created_at.isoformat()}
            for i in invites
        ],
    })


@app.post("/v1/api/team/invite", tags=["Team"])
async def invite_member(
    req: InviteRequest,
    auth: TokenPayload = Depends(require_role("owner", "admin")),
    tenant_id: str = Depends(require_active_tenant),
):
    """Invite a team member by email."""
    # Check plan limit
    async with tenant_session(tenant_id) as session:
        count_q = await session.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant_id)
        )
        current_count = count_q.scalar() or 0

    await check_tenant_limit(tenant_id, "max_users", current_count)

    invite_token = generate_invite_token()

    async with tenant_session(tenant_id) as session:
        # Get inviter info
        inviter_q = await session.execute(select(User).where(User.id == auth.sub))
        inviter = inviter_q.scalar_one_or_none()
        inviter_name = inviter.full_name or inviter.email if inviter else "A team member"

        tenant_q = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_q.scalar_one_or_none()
        tenant_name = tenant.name if tenant else "SecureNet"

        invite = Invitation(
            tenant_id=tenant_id,
            email=req.email,
            role=req.role,
            invited_by=auth.sub,
            token=invite_token,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
        )
        session.add(invite)
        await session.commit()

    await send_invite_email(req.email, invite_token, inviter_name, tenant_name, req.role)

    return success_response(
        message=f"Invitation sent to {req.email}",
        status_code=201,
    )


# ===================================================================
# NOTIFICATIONS
# ===================================================================

@app.get("/v1/api/notifications", tags=["Notifications"])
async def list_notifications(
    auth: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(get_current_tenant),
    limit: int = Query(default=20, le=50),
):
    """Get recent notifications for the current user."""
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            select(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                (Notification.user_id == auth.sub) | (Notification.user_id == None)
            )
            .order_by(desc(Notification.created_at))
            .limit(limit)
        )
        notifications = list(result.scalars().all())

    unread = sum(1 for n in notifications if not n.read_at)
    return success_response(data={
        "items": [notification_to_dict(n) for n in notifications],
        "unread_count": unread,
    })


@app.post("/v1/api/notifications/{notification_id}/read", tags=["Notifications"])
async def mark_notification_read(
    notification_id: str,
    auth: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(get_current_tenant),
):
    """Mark a notification as read."""
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.tenant_id == tenant_id,
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return error_response("RESOURCE_NOT_FOUND", "Notification not found", 404)
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

    return success_response(message="Notification marked as read")


# ===================================================================
# ALERTS — PostgreSQL-backed with cursor pagination (tenant-scoped)
# ===================================================================

@app.get("/v1/api/alerts", tags=["Alerts"])
@app.get("/api/alerts")
async def get_alerts(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, le=200, ge=1),
    status: str | None = Query(default=None, pattern="^(new|investigating|resolved|false_positive)$"),
    severity: str | None = Query(default=None, pattern="^(low|medium|high|critical)$"),
    auth: TokenPayload = Depends(verify_jwt),
    _dep=Depends(rate_limiter),
):
    """Get alerts from PostgreSQL with cursor pagination."""
    tenant_id = auth.tid
    async with tenant_session(tenant_id) as session:
        query = select(Alert).order_by(desc(Alert.created_at), desc(Alert.id))

        # Tenant scoping (explicit filter as RLS may not be active for all users)
        if tenant_id:
            query = query.where(Alert.tenant_id == tenant_id)

        if cursor:
            try:
                query = query.where(Alert.created_at < datetime.fromisoformat(cursor))
            except ValueError:
                return error_response("INVALID_CURSOR", "Invalid cursor format", 400)
        if status:
            query = query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)

        query = query.limit(limit + 1)
        result = await session.execute(query)
        alerts = list(result.scalars().all())

    has_next = len(alerts) > limit
    alerts = alerts[:limit]
    next_cursor = alerts[-1].created_at.isoformat() if alerts else None

    return paginated_response(
        data=[alert_to_dict(a) for a in alerts],
        cursor=next_cursor, per_page=limit, has_next=has_next,
    )


@app.get("/v1/api/alerts/{alert_id}", tags=["Alerts"])
async def get_alert_detail(alert_id: str, auth: TokenPayload = Depends(verify_jwt)):
    async with tenant_session(auth.tid) as session:
        query = select(Alert).where(Alert.id == alert_id)
        if auth.tid:
            query = query.where(Alert.tenant_id == auth.tid)
        result = await session.execute(query)
        alert = result.scalar_one_or_none()
    if not alert:
        return error_response("RESOURCE_NOT_FOUND", "Alert not found", 404)
    return success_response(data=alert_to_dict(alert))


# ===================================================================
# FIREWALL
# ===================================================================

@app.get("/v1/api/firewall/status", tags=["Firewall"])
@app.get("/api/firewall/status")
async def get_firewall_status(
    auth: TokenPayload = Depends(verify_jwt),
    _dep=Depends(rate_limiter),
):
    """Get blocked IPs with full metadata from PostgreSQL."""
    tenant_id = auth.tid
    async with tenant_session(tenant_id) as session:
        query = select(BlockedIP).where(BlockedIP.is_active == True)
        if tenant_id:
            query = query.where(BlockedIP.tenant_id == tenant_id)
        result = await session.execute(
            query.order_by(desc(BlockedIP.created_at)).limit(200)
        )
        ips = list(result.scalars().all())

    return success_response(data={
        "blocked_ips": [blocked_ip_to_dict(ip) for ip in ips],
        "count": len(ips),
    })


@app.post("/v1/api/firewall/block", tags=["Firewall"])
async def block_ip(
    req: BlockIPRequest,
    auth: TokenPayload = Depends(require_role("owner", "admin", "analyst")),
):
    """Manually block an IP address."""
    tenant_id = auth.tid
    try:
        ip_obj = ipaddress.ip_address(req.ip_address.strip())
        if ip_obj.is_loopback or ip_obj.is_link_local:
            return error_response("VALIDATION_ERROR", "Cannot block loopback/link-local", 400)
    except ValueError:
        return error_response("VALIDATION_ERROR", "Invalid IP address", 400)

    ip_str = str(ip_obj)
    await redis_manager.add_blocked_ip(ip_str, tenant_id=tenant_id)
    FIREWALL_BLOCKS.labels(source="manual").inc()

    async with tenant_session(tenant_id) as session:
        existing = await session.execute(
            select(BlockedIP).where(
                BlockedIP.ip_address == ip_str,
                BlockedIP.tenant_id == tenant_id,
                BlockedIP.is_active == True
            )
        )
        if existing.scalar_one_or_none():
            return error_response("RESOURCE_EXISTS", "IP already blocked", 409)

        record = BlockedIP(
            tenant_id=tenant_id,
            ip_address=ip_str,
            reason=req.reason,
            blocked_by=f"user:{auth.sub}",
            is_active=True,
        )
        session.add(record)
        await session.commit()

    return success_response(message=f"IP {ip_str} blocked", status_code=201)


# ===================================================================
# METRICS & DASHBOARD
# ===================================================================

@app.get("/v1/api/metrics", tags=["Dashboard"])
@app.get("/api/metrics")
async def get_metrics(
    auth: TokenPayload = Depends(verify_jwt),
    _dep=Depends(rate_limiter),
):
    return await redis_manager.get_live_metrics(tenant_id=auth.tid)


@app.get("/v1/api/dashboard/summary", tags=["Dashboard"])
async def dashboard_summary(auth: TokenPayload = Depends(verify_jwt)):
    """Aggregated dashboard statistics (tenant-scoped)."""
    tenant_id = auth.tid
    async with tenant_session(tenant_id) as session:
        base_alert_filter = [Alert.tenant_id == tenant_id] if tenant_id else []

        total_q = await session.execute(
            select(func.count(Alert.id)).where(*base_alert_filter)
        )
        total_alerts = total_q.scalar() or 0

        severity_q = await session.execute(
            select(Alert.severity, func.count(Alert.id))
            .where(*base_alert_filter).group_by(Alert.severity)
        )
        severity_counts = {r[0] or "unknown": r[1] for r in severity_q.all()}

        status_q = await session.execute(
            select(Alert.status, func.count(Alert.id))
            .where(*base_alert_filter).group_by(Alert.status)
        )
        status_counts = {r[0] or "unknown": r[1] for r in status_q.all()}

        blocked_filter = [BlockedIP.is_active == True]
        if tenant_id:
            blocked_filter.append(BlockedIP.tenant_id == tenant_id)
        blocked_q = await session.execute(
            select(func.count(BlockedIP.id)).where(*blocked_filter)
        )
        active_blocks = blocked_q.scalar() or 0

    live = await redis_manager.get_live_metrics(tenant_id=tenant_id)

    # Get tenant info
    tenant_info = None
    if tenant_id:
        async with async_session() as session:
            t_q = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = t_q.scalar_one_or_none()
            if tenant:
                tenant_info = tenant_to_dict(tenant)

    return success_response(data={
        "total_alerts": total_alerts,
        "severity_breakdown": severity_counts,
        "status_breakdown": status_counts,
        "active_blocked_ips": active_blocks,
        "live_metrics": live,
        "tenant": tenant_info,
    })


# ===================================================================
# BILLING
# ===================================================================

@app.get("/v1/api/billing/usage", tags=["Billing"])
async def get_usage(
    auth: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(get_current_tenant),
):
    """Get current billing usage for the tenant."""
    async with tenant_session(tenant_id) as session:
        tenant_q = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_q.scalar_one_or_none()
        if not tenant:
            return error_response("TENANT_NOT_FOUND", "Tenant not found", 404)

        sensor_count_q = await session.execute(
            select(func.count(Sensor.id)).where(
                Sensor.tenant_id == tenant_id,
                Sensor.status != "revoked"
            )
        )
        sensor_count = sensor_count_q.scalar() or 0

        user_count_q = await session.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant_id)
        )
        user_count = user_count_q.scalar() or 0

    return success_response(data={
        "plan": tenant.plan,
        "status": tenant.status,
        "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        "sensors": {"used": sensor_count, "max": tenant.max_sensors},
        "users": {"used": user_count, "max": tenant.max_users},
        "ai_analyses": {
            "used": tenant.ai_analyses_used,
            "max": tenant.max_ai_analyses_monthly,
        },
    })


# ===================================================================
# USER PROFILE
# ===================================================================

@app.get("/v1/api/users/me", tags=["Users"])
async def get_profile(auth: TokenPayload = Depends(verify_jwt)):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == auth.sub))
        user = result.scalar_one_or_none()
    if not user:
        return error_response("RESOURCE_NOT_FOUND", "User not found", 404)
    return success_response(data=user_to_dict(user))


# ===================================================================
# ML EXPERIMENTS — Tenant-isolated experiment tracking & model management
# ===================================================================


@app.get("/v1/ml/experiments", tags=["ML"])
@app.get("/ml/experiments", tags=["ML"])
async def list_experiments(
    limit: int = Query(default=50, le=200, ge=1),
    algorithm: str | None = Query(default=None),
    auth: TokenPayload = Depends(verify_jwt),
    _dep=Depends(rate_limiter),
    _active=Depends(require_active_tenant),
):
    """List ML experiments visible to this tenant (own + system-level)."""
    async with tenant_session(auth.tid) as session:
        query = select(MLExperiment).order_by(desc(MLExperiment.created_at))

        if algorithm:
            query = query.where(MLExperiment.algorithm == algorithm)

        query = query.limit(limit)
        result = await session.execute(query)
        experiments = list(result.scalars().all())

    return success_response(
        data={
            "experiments": [
                {
                    "id": str(exp.id),
                    "name": exp.experiment_name,
                    "algorithm": exp.algorithm,
                    "accuracy": exp.accuracy,
                    "precision": exp.precision,
                    "recall": exp.recall,
                    "f1_score": exp.f1_score,
                    "roc_auc": exp.roc_auc,
                    "cv_mean": exp.cv_mean,
                    "cv_std": exp.cv_std,
                    "dataset": exp.dataset_name,
                    "dataset_rows": exp.dataset_rows,
                    "training_time_sec": exp.training_time_seconds,
                    "is_best": exp.is_best,
                    "promoted": exp.promoted_to_registry,
                    "created_at": exp.created_at.isoformat(),
                }
                for exp in experiments
            ],
            "total": len(experiments),
        }
    )


@app.get("/v1/ml/experiments/{experiment_id}", tags=["ML"])
@app.get("/ml/experiments/{experiment_id}", tags=["ML"])
async def get_experiment(
    experiment_id: str,
    auth: TokenPayload = Depends(verify_jwt),
    _active=Depends(require_active_tenant),
):
    """Get detailed experiment info (tenant-scoped via RLS)."""
    async with tenant_session(auth.tid) as session:
        result = await session.execute(
            select(MLExperiment).where(MLExperiment.id == experiment_id)
        )
        exp = result.scalar_one_or_none()

    if not exp:
        return error_response("RESOURCE_NOT_FOUND", "Experiment not found", 404)

    return success_response(
        data={
            "id": str(exp.id),
            "name": exp.experiment_name,
            "algorithm": exp.algorithm,
            "hyperparameters": exp.hyperparameters,
            "dataset": exp.dataset_name,
            "dataset_rows": exp.dataset_rows,
            "feature_count": exp.feature_count,
            "metrics": {
                "accuracy": exp.accuracy,
                "precision": exp.precision,
                "recall": exp.recall,
                "f1_score": exp.f1_score,
                "roc_auc": exp.roc_auc,
            },
            "cross_validation": {
                "mean": exp.cv_mean,
                "std": exp.cv_std,
                "fold_scores": exp.cv_scores,
            },
            "confusion_matrix": exp.confusion_matrix,
            "feature_importance": exp.feature_importance,
            "training_time_sec": exp.training_time_seconds,
            "is_best": exp.is_best,
            "promoted": exp.promoted_to_registry,
            "created_at": exp.created_at.isoformat(),
        }
    )


@app.get("/v1/ml/best-model", tags=["ML"])
@app.get("/ml/best-model", tags=["ML"])
async def get_best_model(
    auth: TokenPayload = Depends(verify_jwt),
    _dep=Depends(rate_limiter),
    _active=Depends(require_active_tenant),
):
    """Get the current best-performing experiment (tenant-scoped via RLS)."""
    async with tenant_session(auth.tid) as session:
        result = await session.execute(
            select(MLExperiment)
            .where(MLExperiment.is_best == True)
            .order_by(desc(MLExperiment.created_at))
            .limit(1)
        )
        best = result.scalar_one_or_none()

    if not best:
        return error_response("NOT_FOUND", "No best model recorded yet", 404)

    return success_response(
        data={
            "id": str(best.id),
            "name": best.experiment_name,
            "algorithm": best.algorithm,
            "accuracy": best.accuracy,
            "f1_score": best.f1_score,
            "roc_auc": best.roc_auc,
            "created_at": best.created_at.isoformat(),
        }
    )


@app.post("/v1/ml/promote/{experiment_id}", tags=["ML"])
@app.post("/ml/promote/{experiment_id}", tags=["ML"])
async def promote_model(
    experiment_id: str,
    auth: TokenPayload = Depends(require_role("admin")),
    _active=Depends(require_active_tenant),
):
    """Manually promote an experiment to model_registry (admin-only, tenant-scoped)."""
    async with tenant_session(auth.tid) as session:
        exp_result = await session.execute(
            select(MLExperiment).where(MLExperiment.id == experiment_id)
        )
        exp = exp_result.scalar_one_or_none()

        if not exp:
            return error_response("RESOURCE_NOT_FOUND", "Experiment not found", 404)

        if exp.promoted_to_registry:
            return error_response(
                "ALREADY_PROMOTED",
                "This experiment is already promoted",
                400,
            )

        # Deactivate current active models for this tenant
        prev_active = await session.execute(
            select(ModelRegistry).where(ModelRegistry.is_active == True)
        )
        for prev in prev_active.scalars():
            prev.is_active = False

        # Promote this experiment
        model_version = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        new_registry = ModelRegistry(
            tenant_id=uuid.UUID(auth.tid) if auth.tid else None,
            version=model_version,
            algorithm=exp.algorithm,
            accuracy=exp.accuracy,
            f1_score=exp.f1_score,
            feature_columns={"features": FEATURE_COLUMNS},
            training_samples=exp.dataset_rows,
            file_hash=exp.model_hash,
            is_active=True,
        )
        session.add(new_registry)
        await session.flush()

        exp.promoted_to_registry = True
        exp.registry_id = new_registry.id
        await session.commit()

    await write_audit_log(
        action="ml.promote_model",
        actor=auth.email or "system",
        resource_type="experiment",
        resource_id=experiment_id,
        details={"model_version": model_version},
        tenant_id=auth.tid,
    )

    return success_response(
        data={"message": "Model promoted", "version": model_version},
        message="Model successfully promoted to registry",
    )


# ===================================================================
# HEALTH
# ===================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(
        status="healthy", service="gateway",
        uptime_seconds=round(time.time() - SERVICE_START_TIME, 1),
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
