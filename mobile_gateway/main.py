"""
SecureNet SOC — Mobile Gateway Service (Phase 2: Full API)

Complete mobile command center with:
- Auth with refresh token rotation
- PostgreSQL-backed alerts with cursor pagination
- Alert detail + status updates
- User profile + password change
- Firewall block/unblock
- Decision history
- Dashboard summary
- FCM device registration
- WebSocket with heartbeat + token watchdog
- Standard response envelope
- API versioning (/v1)
"""

import os
import sys
import time
import json
import asyncio
import ipaddress
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum

import bcrypt
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request, Query, APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, and_, update
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logging_config import setup_logging, trace_id_ctx, get_trace_id
from shared.redis_client import redis_manager
from shared.metrics import (
    MOBILE_ACTIONS_RECEIVED, STREAM_LAG, AUTH_EVENTS, FIREWALL_BLOCKS,
    metrics_endpoint,
)
from shared.auth import (
    create_access_token, create_refresh_token, refresh_access_token,
    verify_jwt, require_role, decode_jwt, validate_secrets,
    TokenPayload, JWT_EXPIRY_SECONDS, VALID_ROLES,
    blacklist_token, is_token_blacklisted,
    record_failed_login, clear_failed_logins, is_account_locked,
    security_headers_middleware, request_size_limit_middleware,
)
from shared.database import (
    async_session, tenant_session, User, Alert, BlockedIP, DecisionLog, write_audit_log,
    Tenant, Notification
)
from shared.responses import (
    success_response, paginated_response, error_response,
    alert_to_dict, blocked_ip_to_dict, decision_to_dict, user_to_dict,
)
from shared.middleware import require_active_tenant, get_current_tenant
from shared.lua_scripts import LUA_EXECUTE_DECISION, get_execute_decision_keys
from shared.rate_limiter import RateLimiter

try:
    from shared.firebase_client import send_push_notification
except ImportError:
    async def send_push_notification(*args, **kwargs):
        return True

load_dotenv()
logger = setup_logging("mobile_gateway")

SERVICE_START_TIME = time.time()
MOBILE_TOKEN_EXPIRY = 900

mobile_auth_limiter = RateLimiter(max_requests=5, window_seconds=60)


# ===================================================================
# WebSocket Manager (tenant-scoped)
# ===================================================================

class ConnectionManager:
    def __init__(self):
        # tenant_id -> list of WebSockets
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, tenant_id: str = "") -> None:
        await ws.accept()
        if tenant_id not in self.connections:
            self.connections[tenant_id] = []
        self.connections[tenant_id].append(ws)

    def disconnect(self, ws: WebSocket, tenant_id: str = "") -> None:
        if tenant_id in self.connections and ws in self.connections[tenant_id]:
            self.connections[tenant_id].remove(ws)
            if not self.connections[tenant_id]:
                del self.connections[tenant_id]

    async def broadcast(self, tenant_id: str, message: dict) -> int:
        success_count = 0
        conns = self.connections.get(tenant_id, [])
        for conn in conns:
            try:
                await conn.send_json(message)
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to mobile WS client for tenant {tenant_id}: {e}")
        return success_count

manager = ConnectionManager()


# ===================================================================
# Request Models
# ===================================================================

class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

class RefreshRequest(BaseModel):
    refresh_token: str

class DecisionAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"

class DecisionRequest(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=100)
    action: DecisionAction

class AlertStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(new|investigating|resolved|false_positive)$")
    analyst_notes: str | None = Field(default=None, max_length=2000)

class BlockIPRequest(BaseModel):
    ip_address: str = Field(..., min_length=7, max_length=45)
    reason: str = Field(default="manual_block", max_length=500)

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

class DeviceRegisterRequest(BaseModel):
    fcm_token: str = Field(..., min_length=10, max_length=500)
    device_name: str = Field(default="Unknown", max_length=100)
    platform: str = Field(default="android", pattern="^(android|ios)$")


# ===================================================================
# Consumer Loop
# ===================================================================

_shutdown_event = asyncio.Event()

async def consumer_loop():
    logger.info("Mobile Gateway consumer started")
    while not _shutdown_event.is_set():
        try:
            lag = await redis_manager.stream_length("stream:mobile_notifications")
            STREAM_LAG.labels(stream="stream:mobile_notifications", group="mobile_group").set(lag)

            messages = await redis_manager.consume(
                stream="stream:mobile_notifications", group="mobile_group",
                consumer="mobile_worker_1", count=10, block_ms=5000,
            )
            if messages:
                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        trace_id_ctx.set(data.get("trace_id") or get_trace_id())
                        try:
                            tenant_id = data.get("tenant_id") or ""
                            ws_deliveries = await manager.broadcast(tenant_id, data)
                            if ws_deliveries == 0:
                                title = f"🚨 {data.get('severity', 'HIGH')} Alert"
                                body = f"IP {data.get('ip', 'unknown')} requires action."
                                await send_push_notification(title, body, data, topic="soc_alerts")
                            await redis_manager.ack("stream:mobile_notifications", "mobile_group", msg_id)
                        except Exception as e:
                            logger.error(f"Failed to process notification {msg_id}: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            await asyncio.sleep(5)


# ===================================================================
# App Setup & Middleware
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_secrets()
    await redis_manager.connect()
    consumer_task = asyncio.create_task(consumer_loop())
    logger.info("Mobile Gateway started")
    yield
    _shutdown_event.set()
    consumer_task.cancel()
    try:
        await asyncio.wait_for(consumer_task, timeout=10)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    await redis_manager.close()

app = FastAPI(
    title="SecureNet Mobile SOC Gateway",
    version="1.4.0",
    description=(
        "Mobile command center for SecureNet IDS.\n\n"
        "## Authentication\n"
        "All protected endpoints require a JWT Bearer token.\n\n"
        "## Decision Flow\n"
        "Critical/high alerts are dispatched to mobile for analyst approval (APPROVE/REJECT/ESCALATE)."
    ),
    docs_url="/docs", redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware: Tenant Identity Rule (Block manual overrides)
@app.middleware("http")
async def enforce_tenant_identity(request: Request, call_next):
    # 1. Reject query parameters overrides
    for q_key in request.query_params.keys():
        if q_key in ("tenant_id", "tenant"):
            return error_response("FORBIDDEN", "Manually specifying tenant_id is forbidden.", 403)

    # 2. Reject HTTP headers overrides
    for header in ("x-tenant-id", "x-tenant", "tenant-id", "tenant"):
        if header in request.headers:
            return error_response("FORBIDDEN", "Manually specifying tenant_id is forbidden.", 403)

    # 3. Reject JSON request body overrides
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            if body_bytes:
                body_json = json.loads(body_bytes)
                if isinstance(body_json, dict):
                    if "tenant_id" in body_json or "tenant" in body_json:
                        return error_response("FORBIDDEN", "Manually specifying tenant_id is forbidden.", 403)
            # Reset request receive stream so endpoint can read it again
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            request._receive = receive
        except Exception:
            pass

    return await call_next(request)

app.middleware("http")(security_headers_middleware)
app.middleware("http")(request_size_limit_middleware)
app.add_route("/metrics", metrics_endpoint)

# Router for V1 mobile endpoints
v1_router = APIRouter(prefix="/v1/mobile")


# ===================================================================
# Health
# ===================================================================

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mobile_gateway",
            "uptime_seconds": round(time.time() - SERVICE_START_TIME, 1)}


# ===================================================================
# AUTH ENDPOINTS
# ===================================================================

@v1_router.post("/auth")
async def login(data: AuthRequest, request: Request):
    """Mobile login — returns access + refresh tokens."""
    await mobile_auth_limiter(request)

    if await is_account_locked(data.email):
        raise HTTPException(status_code=429, detail="Account temporarily locked.")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == data.email, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        dummy_hash = "$2b$12$LJ3m4ys3Lf1vGshMBfeGJOFB.gMOsR6b7R1E0xq4K3e0WZ5v5q3.a"
        pw_hash = user.password_hash if user else dummy_hash

        if not bcrypt.checkpw(data.password.encode(), pw_hash.encode()):
            AUTH_EVENTS.labels(event="mobile_login_failure").inc()
            if user:
                await record_failed_login(data.email)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

    await clear_failed_logins(data.email)
    tenant_id = str(user.tenant_id) if user.tenant_id else ""

    # SECURITY: Check tenant status — block login for suspended/cancelled tenants.
    # Runs AFTER password verification to prevent leaking tenant status to attackers.
    if tenant_id:
        async with async_session() as session:
            tenant_result = await session.execute(
                select(Tenant.status).where(Tenant.id == user.tenant_id)
            )
            tenant_status = tenant_result.scalar_one_or_none()
        if tenant_status and tenant_status not in ("trial", "active"):
            AUTH_EVENTS.labels(event="mobile_login_tenant_suspended").inc()
            raise HTTPException(
                status_code=403,
                detail=f"Tenant account is {tenant_status}. Contact support."
            )

    token = create_access_token(str(user.id), user.role, tenant_id=tenant_id, expires_in=MOBILE_TOKEN_EXPIRY)
    refresh = create_refresh_token(str(user.id), user.role, tenant_id=tenant_id)
    AUTH_EVENTS.labels(event="mobile_login_success").inc()
    await write_audit_log(
        action="auth.mobile_login", actor=data.email,
        resource_type="session", resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        tenant_id=tenant_id,
    )

    return success_response(data={
        "access_token": token, "refresh_token": refresh,
        "token_type": "bearer", "expires_in": MOBILE_TOKEN_EXPIRY, "role": user.role,
    })


@v1_router.post("/auth/refresh")
async def mobile_refresh(req: RefreshRequest):
    """Exchange refresh token for new access + refresh tokens (rotation)."""
    try:
        result = await refresh_access_token(req.refresh_token)
        # Re-issue with mobile-specific shorter expiry and preserve tenant_id (tid claim)
        payload = decode_jwt(result["access_token"])
        result["access_token"] = create_access_token(
            payload.get("sub", ""), payload.get("role", "viewer"),
            tenant_id=payload.get("tid", ""),
            expires_in=MOBILE_TOKEN_EXPIRY,
        )
        result["expires_in"] = MOBILE_TOKEN_EXPIRY
        AUTH_EVENTS.labels(event="mobile_token_refresh").inc()
        return success_response(data=result)
    except HTTPException:
        AUTH_EVENTS.labels(event="mobile_refresh_failure").inc()
        raise


@v1_router.post("/auth/logout")
async def mobile_logout(token: TokenPayload = Depends(verify_jwt)):
    """Invalidate the current access token."""
    await blacklist_token(token.jti, int(token.exp - time.time()))
    return success_response(message="Logged out successfully")


# ===================================================================
# ALERTS ENDPOINTS (PostgreSQL-backed with cursor pagination & RLS)
# ===================================================================

@v1_router.get("/alerts")
async def get_alerts(
    cursor: str | None = Query(default=None, description="ISO timestamp cursor"),
    per_page: int = Query(default=20, ge=1, le=100),
    severity: str | None = Query(default=None, pattern="^(low|medium|high|critical)$"),
    status: str | None = Query(default=None, pattern="^(new|investigating|resolved|false_positive)$"),
    tenant_id: str = Depends(require_active_tenant),
):
    """Get alerts from PostgreSQL with cursor-based pagination and tenant isolation."""
    async with tenant_session(tenant_id) as session:
        query = select(Alert).order_by(desc(Alert.created_at), desc(Alert.id))

        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                query = query.where(Alert.created_at < cursor_dt)
            except ValueError:
                return error_response("INVALID_CURSOR", "Invalid cursor format", 400)

        if severity:
            query = query.where(Alert.severity == severity)
        if status:
            query = query.where(Alert.status == status)

        query = query.limit(per_page + 1)
        result = await session.execute(query)
        alerts = list(result.scalars().all())

    has_next = len(alerts) > per_page
    alerts = alerts[:per_page]
    next_cursor = alerts[-1].created_at.isoformat() if alerts else None

    return paginated_response(
        data=[alert_to_dict(a) for a in alerts],
        cursor=next_cursor, per_page=per_page, has_next=has_next,
    )


@v1_router.get("/alerts/{alert_id}")
async def get_alert_detail(
    alert_id: str,
    tenant_id: str = Depends(require_active_tenant)
):
    """Get a single alert by ID with tenant isolation."""
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        return error_response("VALIDATION_ERROR", "Invalid alert UUID", 400)

    async with tenant_session(tenant_id) as session:
        result = await session.execute(select(Alert).where(Alert.id == alert_uuid))
        alert = result.scalar_one_or_none()

    if not alert:
        return error_response("RESOURCE_NOT_FOUND", "Alert not found", 404)

    return success_response(data=alert_to_dict(alert))


@v1_router.patch("/alerts/{alert_id}")
async def update_alert(
    alert_id: str, update: AlertStatusUpdate,
    auth: TokenPayload = Depends(require_role("admin", "analyst")),
    tenant_id: str = Depends(require_active_tenant),
):
    """Update an alert's status and/or analyst notes with tenant isolation."""
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        return error_response("VALIDATION_ERROR", "Invalid alert UUID", 400)

    async with tenant_session(tenant_id) as session:
        result = await session.execute(select(Alert).where(Alert.id == alert_uuid))
        alert = result.scalar_one_or_none()
        if not alert:
            return error_response("RESOURCE_NOT_FOUND", "Alert not found", 404)

        alert.status = update.status
        if update.analyst_notes is not None:
            alert.analyst_notes = update.analyst_notes
        if update.status == "resolved":
            alert.resolved_by = uuid.UUID(auth.sub)
            alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await session.commit()
        await session.refresh(alert)

    return success_response(data=alert_to_dict(alert), message="Alert updated")


# ===================================================================
# USER PROFILE ENDPOINTS
# ===================================================================

@v1_router.get("/users/me")
async def get_profile(auth: TokenPayload = Depends(verify_jwt)):
    """Get the current user's profile."""
    user_uuid = uuid.UUID(auth.sub)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
    if not user:
        return error_response("RESOURCE_NOT_FOUND", "User not found", 404)
    return success_response(data=user_to_dict(user))


@v1_router.post("/users/me/password")
async def change_password(
    req: PasswordChangeRequest, auth: TokenPayload = Depends(verify_jwt),
):
    """Change the current user's password."""
    user_uuid = uuid.UUID(auth.sub)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if not user:
            return error_response("RESOURCE_NOT_FOUND", "User not found", 404)

        if not bcrypt.checkpw(req.current_password.encode(), user.password_hash.encode()):
            return error_response("AUTH_INVALID_CREDENTIALS", "Current password is incorrect", 401)

        user.password_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
        await session.commit()

    return success_response(message="Password changed successfully")


# ===================================================================
# FIREWALL ENDPOINTS
# ===================================================================

@v1_router.get("/firewall")
async def get_blocked_ips(
    cursor: str | None = Query(default=None),
    per_page: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=True),
    tenant_id: str = Depends(require_active_tenant),
):
    """Get blocked IPs from PostgreSQL with metadata, pagination, and tenant isolation."""
    async with tenant_session(tenant_id) as session:
        query = select(BlockedIP).order_by(desc(BlockedIP.created_at))
        if active_only:
            query = query.where(BlockedIP.is_active == True)
        if cursor:
            try:
                query = query.where(BlockedIP.created_at < datetime.fromisoformat(cursor))
            except ValueError:
                return error_response("INVALID_CURSOR", "Invalid cursor format", 400)
        query = query.limit(per_page + 1)
        result = await session.execute(query)
        ips = list(result.scalars().all())

    has_next = len(ips) > per_page
    ips = ips[:per_page]
    next_cursor = ips[-1].created_at.isoformat() if ips else None

    return paginated_response(
        data=[blocked_ip_to_dict(ip) for ip in ips],
        cursor=next_cursor, per_page=per_page, has_next=has_next,
    )


@v1_router.post("/firewall/block")
async def block_ip(
    req: BlockIPRequest,
    auth: TokenPayload = Depends(require_role("admin", "analyst")),
    tenant_id: str = Depends(require_active_tenant),
):
    """Manually block an IP address with tenant isolation."""
    # Validate IP
    try:
        ip_obj = ipaddress.ip_address(req.ip_address.strip())
        if ip_obj.is_loopback or ip_obj.is_link_local:
            return error_response("VALIDATION_ERROR", "Cannot block loopback/link-local", 400)
    except ValueError:
        return error_response("VALIDATION_ERROR", "Invalid IP address", 400)

    ip_str = str(ip_obj)

    # Add to Redis blocklist
    await redis_manager.add_blocked_ip(ip_str)
    FIREWALL_BLOCKS.labels(source="manual").inc()

    # Persist to PostgreSQL with tenant scoping
    async with tenant_session(tenant_id) as session:
        existing = await session.execute(
            select(BlockedIP).where(
                BlockedIP.ip_address == ip_str,
                BlockedIP.tenant_id == uuid.UUID(tenant_id),
                BlockedIP.is_active == True
            )
        )
        if existing.scalar_one_or_none():
            return error_response("RESOURCE_EXISTS", "IP already blocked", 409)

        record = BlockedIP(
            tenant_id=uuid.UUID(tenant_id),
            ip_address=ip_str, reason=req.reason,
            blocked_by=f"user:{auth.sub}", is_active=True,
        )
        session.add(record)
        await session.commit()

    logger.info(f"Manual block: {ip_str} by user {auth.sub} (tenant {tenant_id})")
    return success_response(message=f"IP {ip_str} blocked", status_code=201)


@v1_router.delete("/firewall/block/{ip_address}")
async def unblock_ip(
    ip_address: str,
    auth: TokenPayload = Depends(require_role("admin", "analyst")),
    tenant_id: str = Depends(require_active_tenant),
):
    """Unblock an IP address with tenant isolation."""
    try:
        ip_str = str(ipaddress.ip_address(ip_address.strip()))
    except ValueError:
        return error_response("VALIDATION_ERROR", "Invalid IP address", 400)

    # Remove from Redis
    await redis_manager.remove_blocked_ip(ip_str)

    # Update PostgreSQL with tenant scoping
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            select(BlockedIP).where(
                BlockedIP.ip_address == ip_str,
                BlockedIP.tenant_id == uuid.UUID(tenant_id),
                BlockedIP.is_active == True
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return error_response("RESOURCE_NOT_FOUND", "IP not in blocklist", 404)

        record.is_active = False
        record.unblocked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

    logger.info(f"Manual unblock: {ip_str} by user {auth.sub} (tenant {tenant_id})")
    return success_response(message=f"IP {ip_str} unblocked")


# ===================================================================
# DECISION HISTORY
# ===================================================================

@v1_router.get("/decisions")
async def get_decisions(
    cursor: str | None = Query(default=None),
    per_page: int = Query(default=20, ge=1, le=100),
    tenant_id: str = Depends(require_active_tenant),
):
    """Get decision history from PostgreSQL with cursor pagination and tenant isolation."""
    async with tenant_session(tenant_id) as session:
        query = select(DecisionLog).order_by(desc(DecisionLog.created_at))
        if cursor:
            try:
                query = query.where(DecisionLog.created_at < datetime.fromisoformat(cursor))
            except ValueError:
                return error_response("INVALID_CURSOR", "Invalid cursor format", 400)
        query = query.limit(per_page + 1)
        result = await session.execute(query)
        logs = list(result.scalars().all())

    has_next = len(logs) > per_page
    logs = logs[:per_page]
    next_cursor = logs[-1].created_at.isoformat() if logs else None

    return paginated_response(
        data=[decision_to_dict(l) for l in logs],
        cursor=next_cursor, per_page=per_page, has_next=has_next,
    )


# ===================================================================
# DASHBOARD SUMMARY
# ===================================================================

@v1_router.get("/dashboard/summary")
async def dashboard_summary(tenant_id: str = Depends(require_active_tenant)):
    """Get aggregated dashboard statistics with tenant isolation."""
    tenant_uuid = uuid.UUID(tenant_id)
    async with tenant_session(tenant_id) as session:
        # Alert counts by severity (scoped to tenant automatically by tenant_session RLS)
        severity_q = await session.execute(
            select(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)
        )
        severity_counts = {row[0] or "unknown": row[1] for row in severity_q.all()}

        # Alert counts by status
        status_q = await session.execute(
            select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
        )
        status_counts = {row[0] or "unknown": row[1] for row in status_q.all()}

        # Total alerts
        total_q = await session.execute(select(func.count(Alert.id)))
        total_alerts = total_q.scalar() or 0

        # Active blocked IPs
        blocked_q = await session.execute(
            select(func.count(BlockedIP.id)).where(BlockedIP.is_active == True)
        )
        active_blocks = blocked_q.scalar() or 0

        # Decisions today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        decisions_q = await session.execute(
            select(func.count(DecisionLog.id)).where(DecisionLog.created_at >= today_start)
        )
        decisions_today = decisions_q.scalar() or 0

    # Live metrics from Redis (tenant-scoped key check inside helper or directly here)
    live_metrics = await redis_manager.get_live_metrics()

    return success_response(data={
        "total_alerts": total_alerts,
        "severity_breakdown": severity_counts,
        "status_breakdown": status_counts,
        "active_blocked_ips": active_blocks,
        "decisions_today": decisions_today,
        "live_metrics": live_metrics,
    })


# ===================================================================
# DEVICE REGISTRATION (FCM)
# ===================================================================

@v1_router.post("/devices/register")
async def register_device(
    req: DeviceRegisterRequest,
    auth: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(require_active_tenant)
):
    """Register a mobile device for push notifications (tenant-scoped)."""
    try:
        redis = redis_manager.client
        device_key = f"fcm:device:{auth.sub}"
        device_data = json.dumps({
            "fcm_token": req.fcm_token,
            "device_name": req.device_name,
            "platform": req.platform,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        })
        fcm_key = redis_manager._tenant_key("fcm:devices", tenant_id)
        await redis.hset(fcm_key, auth.sub, device_data)
        logger.info(f"Device registered for user {auth.sub} (tenant {tenant_id})")
        return success_response(message="Device registered for push notifications")
    except Exception as e:
        logger.error(f"Device registration failed: {e}")
        return error_response("SERVER_ERROR", "Failed to register device", 500)


# ===================================================================
# ALERT DECISION (APPROVE/REJECT/ESCALATE)
# ===================================================================

@v1_router.post("/decision")
async def handle_decision(
    req: DecisionRequest,
    payload: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(require_active_tenant)
):
    user_id = payload.sub
    trace_id_ctx.set(get_trace_id())
    MOBILE_ACTIONS_RECEIVED.labels(action=req.action.value).inc()

    payload_str = await redis_manager.client.hget(
        redis_manager._tenant_key("decision_payloads", tenant_id), req.alert_id
    )
    if not payload_str:
        return error_response("RESOURCE_NOT_FOUND", "Alert timed out or already processed.", 404)

    alert_payload = json.loads(payload_str)

    result = await redis_manager.execute_lua(
        LUA_EXECUTE_DECISION,
        keys=get_execute_decision_keys(req.alert_id, tenant_id=tenant_id),
        args=[req.alert_id, req.action.value, "mobile", get_trace_id(), user_id, str(time.time())]
    )

    if result == 0:
        return error_response("CONFLICT", "Alert already processed.", 409)

    if req.action == DecisionAction.APPROVE:
        logger.info(f"User {user_id} APPROVED alert {req.alert_id}")
        block_command = {
            "src_ip": alert_payload.get("ip"),
            "reason": alert_payload.get("reason", "unknown"),
            "alert_id": req.alert_id, "trace_id": get_trace_id(),
            "tenant_id": tenant_id,
        }
        await redis_manager.publish("stream:block_commands", block_command)
    elif req.action == DecisionAction.REJECT:
        logger.info(f"User {user_id} REJECTED alert {req.alert_id}")
    elif req.action == DecisionAction.ESCALATE:
        logger.info(f"User {user_id} ESCALATED alert {req.alert_id}")

    return success_response(data={"action": req.action.value}, message="Decision recorded")


# ===================================================================
# NOTIFICATION ENDPOINTS (NEW for Phase 3)
# ===================================================================

def notification_to_dict(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "title": n.title,
        "message": n.message,
        "type": n.type,
        "created_at": n.created_at.isoformat() if n.created_at else "",
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "data": n.data or {}
    }


@v1_router.get("/notifications")
async def get_notifications(
    cursor: str | None = Query(default=None, description="ISO timestamp cursor"),
    per_page: int = Query(default=20, ge=1, le=100),
    tenant_id: str = Depends(require_active_tenant)
):
    """Get in-app notifications for the active tenant."""
    async with tenant_session(tenant_id) as session:
        query = select(Notification).order_by(desc(Notification.created_at))

        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                query = query.where(Notification.created_at < cursor_dt)
            except ValueError:
                return error_response("INVALID_CURSOR", "Invalid cursor format", 400)

        query = query.limit(per_page + 1)
        result = await session.execute(query)
        notifications = list(result.scalars().all())

    has_next = len(notifications) > per_page
    notifications = notifications[:per_page]
    next_cursor = notifications[-1].created_at.isoformat() if notifications else None

    return paginated_response(
        data=[notification_to_dict(n) for n in notifications],
        cursor=next_cursor, per_page=per_page, has_next=has_next,
    )


@v1_router.post("/notifications/{id}/read")
async def mark_notification_read(
    id: str,
    tenant_id: str = Depends(require_active_tenant)
):
    """Mark a specific notification as read."""
    try:
        notif_uuid = uuid.UUID(id)
    except ValueError:
        return error_response("VALIDATION_ERROR", "Invalid notification UUID", 400)

    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            select(Notification).where(Notification.id == notif_uuid)
        )
        notif = result.scalar_one_or_none()
        if not notif:
            return error_response("RESOURCE_NOT_FOUND", "Notification not found", 404)

        notif.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

    return success_response(message="Notification marked as read")


@v1_router.post("/notifications/read-all")
async def mark_all_notifications_read(
    tenant_id: str = Depends(require_active_tenant)
):
    """Mark all unread notifications of the tenant as read."""
    async with tenant_session(tenant_id) as session:
        await session.execute(
            update(Notification)
            .where(Notification.read_at == None)
            .values(read_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        await session.commit()

    return success_response(message="All notifications marked as read")


# Mount versioned router
app.include_router(v1_router)


# ===================================================================
# BACKWARD COMPATIBILITY ENDPOINTS (Direct app mounting)
# ===================================================================

@app.post("/v1/mobile/auth")
@app.post("/mobile/auth")
async def legacy_login(data: AuthRequest, request: Request):
    return await login(data, request)


@app.post("/v1/mobile/auth/refresh")
@app.post("/mobile/auth/refresh")
async def legacy_refresh(req: RefreshRequest):
    return await mobile_refresh(req)


@app.post("/v1/mobile/auth/logout")
@app.post("/mobile/auth/logout")
async def legacy_logout(token: TokenPayload = Depends(verify_jwt)):
    return await mobile_logout(token)


@app.post("/v1/mobile/decision")
@app.post("/mobile/decision")
async def legacy_decision(
    req: DecisionRequest,
    payload: TokenPayload = Depends(verify_jwt),
    tenant_id: str = Depends(require_active_tenant)
):
    return await handle_decision(req, payload, tenant_id)


# ===================================================================
# WebSocket — Mobile Push (JWT + heartbeat + watchdog)
# ===================================================================

@app.websocket("/ws/mobile")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    # 1. Enforce query parameters check for manual tenant overrides
    if "tenant_id" in websocket.query_params or "tenant" in websocket.query_params:
        await websocket.close(code=4003, reason="Manual tenant_id forbidden")
        return

    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        payload = decode_jwt(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    jti = payload.get("jti", "")
    if jti and await is_token_blacklisted(jti):
        await websocket.close(code=4001, reason="Token revoked")
        return

    tenant_id = payload.get("tid", "")
    if not tenant_id:
        await websocket.close(code=4003, reason="No tenant context in token")
        return

    # Check tenant status is active or trial
    try:
        # Cache / DB lookup for tenant status
        from shared.middleware import require_active_tenant
        await require_active_tenant(tenant_id)
    except HTTPException as he:
        await websocket.close(code=4003, reason=he.detail)
        return
    except Exception:
        pass # Fail open on validation connection issues

    token_exp = payload.get("exp", 0)
    remaining = max(token_exp - time.time(), 0)

    await manager.connect(websocket, tenant_id)

    async def _watchdog():
        await asyncio.sleep(remaining)
        try:
            await websocket.send_json({"type": "token_expired"})
            await websocket.close(code=4001, reason="Token expired")
        except Exception:
            pass

    expiry_task = asyncio.create_task(_watchdog())

    try:
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
        manager.disconnect(websocket, tenant_id)
    except Exception as e:
        logger.error(f"Mobile WS error: {e}")
        manager.disconnect(websocket, tenant_id)
    finally:
        expiry_task.cancel()


if __name__ == "__main__":
    host = os.getenv("MOBILE_GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("MOBILE_GATEWAY_PORT", "8005"))
    uvicorn.run(app, host=host, port=port)
