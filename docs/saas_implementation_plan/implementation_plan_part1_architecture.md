# SecureNet SOC → SaaS Implementation Plan

## Part 1: Architecture Analysis & Multi-Tenant Design

---

# PART 1 — CURRENT ARCHITECTURE ANALYSIS

## 1.1 Strengths to Preserve

| Strength | Location | Why It Matters |
|---|---|---|
| **Event-driven pipeline** | All services via `redis_client.py` `publish()`/`consume()` | Decoupled services = independent scaling. Adding `tenant_id` to messages is trivial. |
| **Consumer group pattern** | Each service creates its own `xgroup_create()` | Exactly-once processing within each group. Multi-tenant messages can be filtered at consumer level. |
| **Atomic Lua decisions** | `shared/lua_scripts.py` `LUA_EXECUTE_DECISION` | Race-condition-free decision execution. Tenant-scoping the keys is a prefix change only. |
| **Shared module layer** | `shared/` (15 modules) | Single place to inject tenant middleware — changes propagate to all services. |
| **JWT + RBAC** | `shared/auth.py` `TokenPayload`, `verify_jwt()`, `require_role()` | Adding `tenant_id` claim is a 3-line change to `TokenPayload` and `create_access_token()`. |
| **Standard response envelope** | `shared/responses.py` | Consistent API contract. No changes needed for multi-tenancy. |
| **Structured logging** | `shared/logging_config.py` with `trace_id` | Add `tenant_id` to log context for tenant-scoped log filtering. |
| **Prometheus metrics** | `shared/metrics.py` (15 counters, 5 histograms, 8 gauges) | Add `tenant_id` label to key metrics for per-tenant monitoring. |
| **SQLAlchemy async ORM** | `shared/database.py` with `async_session` | RLS policy application via `SET app.tenant_id` per session is native to this pattern. |

## 1.2 SaaS Blockers (Exact Locations)

### Blocker 1: No Tenant Model

**Current state:** The `User` model in [database.py:72-88](file:///d:/Graduation%20Project/SecureNet_IDS_Project/shared/database.py#L72-L88) has no `tenant_id` column. Users exist in a global namespace. Every query across all services assumes a single tenant.

**Impact:** Every table (`alerts`, `blocked_ips`, `decision_logs`, `ml_predictions`, `audit_log`) lacks tenant isolation. A query like `select(Alert).order_by(desc(Alert.created_at))` in [gateway/main.py:314](file:///d:/Graduation%20Project/SecureNet_IDS_Project/gateway/main.py#L314) returns ALL tenants' data.

**Fix scope:** 7 ORM models + 1 new `Tenant` model + RLS policies + Alembic migration.

### Blocker 2: No Tenant in JWT

**Current state:** `TokenPayload` in [auth.py:99-105](file:///d:/Graduation%20Project/SecureNet_IDS_Project/shared/auth.py#L99-L105) contains `sub` (user ID), `role`, `exp`, `iat`, `jti`. No tenant context.

**Impact:** `verify_jwt()` returns a token with no tenant scope. Every endpoint handler must be individually modified OR a middleware must inject tenant context.

**Fix scope:** Add `tid` field to `TokenPayload`, modify `create_access_token()` and `create_refresh_token()` in auth.py.

### Blocker 3: Global Redis Keys

**Current state:** Redis keys are global. Examples from [redis_client.py](file:///d:/Graduation%20Project/SecureNet_IDS_Project/shared/redis_client.py):
- `blocked_ips` (line 252) — single SET for all tenants
- `recent_alerts` (line 287) — single LIST for all tenants
- `live_metrics` (line 272) — single key for all tenants
- `conn:{ip}:packets` (line 145) — per-IP but not per-tenant
- `cooldown:alert:{ip}` (line 243) — per-IP but not per-tenant

**Impact:** Tenant A's blocked IPs are visible to Tenant B. Metrics from different tenants bleed.

**Fix scope:** Prefix all keys with `t:{tenant_id}:`. Modify 12 methods in `RedisManager`.

### Blocker 4: Global Redis Streams

**Current state:** All services use global stream names: `stream:raw_packets`, `stream:features`, `stream:alerts`, etc. Every message from every tenant flows through the same stream.

**Impact:** This is actually **fine for now**. Unlike keys, streams can carry multi-tenant data with a `tenant_id` field in each message. Consumers can process all tenants' messages. This is the **shared-stream** pattern and it's simpler than per-tenant streams until you hit ~100 tenants.

**Decision:** Keep shared streams, add `tenant_id` to every message. Switch to per-tenant streams only if stream lag exceeds thresholds per-tenant.

### Blocker 5: Sniffer Runs Locally

**Current state:** [sniffer/main.py](file:///d:/Graduation%20Project/SecureNet_IDS_Project/sniffer/main.py) uses `scapy.sniff()` which captures packets on the host NIC. This runs with `network_mode: host` and `privileged: true`.

**Impact:** In a SaaS model, the sniffer runs on the **customer's network**, not on the SaaS platform. It becomes a **sensor** — a remotely deployed agent that authenticates to the platform and pushes data.

**Fix scope:** Refactor sniffer into a "SecureNet Sensor" Docker image that: (1) authenticates via API key, (2) tags all packets with `tenant_id` and `sensor_id`, (3) pushes to the platform's Redis, (4) sends heartbeats. This is the largest architectural change.

### Blocker 6: No Signup/Onboarding Flow

**Current state:** Users are created manually (presumably via SQL or a script). No self-service registration, email verification, tenant provisioning, or guided setup.

**Impact:** Cannot acquire customers without manual intervention.

**Fix scope:** New signup API, email service, tenant provisioning pipeline, onboarding wizard in frontend.

### Blocker 7: No Billing Integration

**Current state:** No Stripe, no subscription management, no feature gating, no usage tracking.

**Fix scope:** New `Subscription`, `Invoice`, `UsageRecord` models. Stripe webhook handler. Feature gate middleware.

## 1.3 Scaling Limitations

| Limitation | Current Behavior | At Scale Impact | Fix |
|---|---|---|---|
| **Single Redis** | All services connect to one Redis | OOM at ~50K msg/sec | ElastiCache cluster mode |
| **Single PostgreSQL** | All services share one DB | Connection pool exhaustion at ~100 tenants | RDS Multi-AZ + read replicas |
| **Sniffer in Docker Compose** | `network_mode: host` | Cannot deploy to customer sites | Sensor agent architecture |
| **In-memory `_active_ips` set** in [extractor/main.py:51](file:///d:/Graduation%20Project/SecureNet_IDS_Project/extractor/main.py#L51) | Capped at 5000 IPs globally | Multiple tenants overflow the cap | Move to Redis SET per-tenant |
| **WebSocket list** in [gateway/main.py:70-71](file:///d:/Graduation%20Project/SecureNet_IDS_Project/gateway/main.py#L70-L71) | Python list `self.active: list[WebSocket]` | Linear scan for broadcast, no tenant filtering | Add tenant-scoped connection registry |

## 1.4 Security Gaps for SaaS

| Gap | Current | Required |
|---|---|---|
| **Tenant data isolation** | None | RLS + application-level checks |
| **Sensor authentication** | None | mTLS or API key with HMAC |
| **MFA** | None | TOTP or WebAuthn for admin accounts |
| **SSO** | None | SAML/OIDC for enterprise tier |
| **Data encryption at rest** | None | RDS TDE, S3 SSE-KMS |
| **Secret rotation** | Manual .env | AWS Secrets Manager with auto-rotation |
| **DDoS protection** | Traefik rate limiting | CloudFront + AWS WAF |

---

# PART 3 — SAAS MULTI-TENANT ARCHITECTURE

## 3.1 Strategy: Shared-Everything with Row-Level Security

**Decision:** Use PostgreSQL RLS (Row-Level Security) with a shared database. This is the right choice because:
1. **Operational simplicity** — One database to manage, backup, migrate
2. **Cost efficiency** — Don't need a database per tenant until 500+ tenants
3. **Fast tenant provisioning** — INSERT a row, not CREATE a database
4. **RLS is battle-tested** — Used by Supabase, Citus, and many SaaS platforms

**Future escape hatch:** When a single enterprise tenant needs physical isolation (compliance requirement), use the `tenant.isolation_mode` column to route them to a dedicated schema or database.

## 3.2 New Database Models (Exact Schema)

### New Table: `tenants`

```python
class Tenant(Base):
    """SaaS tenant (organization/company)."""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
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
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
```

### New Table: `sensors`

```python
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
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt hash of API key
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)  # first 8 chars for identification
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|active|offline|revoked
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
```

### New Table: `api_keys`

```python
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
```

## 3.3 Existing Table Modifications

### Alembic Migration: Add `tenant_id` to All Tables

```python
# alembic/versions/xxxx_add_multi_tenancy.py

def upgrade():
    # 1. Create tenants table FIRST
    op.create_table('tenants', ...)
    op.create_table('sensors', ...)
    op.create_table('api_keys', ...)

    # 2. Add tenant_id to existing tables
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.add_column(table, sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))

    # 3. Create a "default" tenant for existing data
    op.execute("""
        INSERT INTO tenants (id, name, slug, plan, status)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Default', 'default', 'enterprise', 'active')
    """)

    # 4. Backfill existing data
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.execute(f"UPDATE {table} SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL")

    # 5. Make tenant_id NOT NULL after backfill
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.alter_column(table, 'tenant_id', nullable=False)
        op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])

    # 6. Add composite unique constraint for blocked_ips (per-tenant unique)
    op.drop_constraint('blocked_ips_ip_address_key', 'blocked_ips', type_='unique')
    op.create_unique_constraint('uq_blocked_ips_tenant_ip', 'blocked_ips', ['tenant_id', 'ip_address'])

    # Remove global email uniqueness, add per-tenant uniqueness
    op.drop_constraint('users_email_key', 'users', type_='unique')
    op.create_unique_constraint('uq_users_tenant_email', 'users', ['tenant_id', 'email'])

    # 7. Enable Row-Level Security
    for table in ['alerts', 'blocked_ips', 'decision_logs', 'ml_predictions', 'audit_log']:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """)
        op.execute(f"""
            CREATE POLICY tenant_insert_{table} ON {table}
            FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """)

def downgrade():
    # Reverse: drop policies, drop columns, drop tables
    ...
```

## 3.4 Tenant-Aware Database Session

**File:** `shared/database.py` — New function `tenant_session()`

```python
# Add alongside existing async_session
@asynccontextmanager
async def tenant_session(tenant_id: str):
    """Create a database session scoped to a specific tenant via RLS."""
    async with async_session() as session:
        # Set the tenant context for RLS policies
        await session.execute(
            text("SET LOCAL app.tenant_id = :tid"),
            {"tid": tenant_id}
        )
        yield session
```

**Usage in endpoints (replacing `async_session()`):**

```python
# BEFORE (gateway/main.py:313):
async with async_session() as session:
    query = select(Alert).order_by(desc(Alert.created_at))

# AFTER:
async with tenant_session(auth.tid) as session:
    query = select(Alert).order_by(desc(Alert.created_at))
    # RLS automatically filters to this tenant's alerts
```

**Impact:** Every endpoint handler that uses `async_session()` changes to `tenant_session(auth.tid)`. The actual queries remain UNCHANGED — RLS handles filtering invisibly.

## 3.5 JWT Tenant Claims

**File:** `shared/auth.py`

```python
# BEFORE (line 99-105):
class TokenPayload(BaseModel):
    sub: str        # user ID
    role: str       # admin | analyst | viewer
    exp: float
    iat: float = 0
    jti: str = ""

# AFTER:
class TokenPayload(BaseModel):
    sub: str        # user ID
    tid: str        # tenant ID ← NEW
    role: str       # owner | admin | analyst | viewer
    exp: float
    iat: float = 0
    jti: str = ""
```

**`create_access_token()` change (line 197-229):**

```python
# BEFORE:
def create_access_token(user_id: str, role: str, ...) -> str:
    payload = {"sub": user_id, "role": role, ...}

# AFTER:
def create_access_token(user_id: str, tenant_id: str, role: str, ...) -> str:
    payload = {"sub": user_id, "tid": tenant_id, "role": role, ...}
```

**Cascading changes:** Every call to `create_access_token()` in `gateway/main.py:264` and `mobile_gateway/main.py:270` needs to pass `tenant_id`. The user's `tenant_id` is loaded from the `users` table during login.

## 3.6 Redis Tenant Key Strategy

**File:** `shared/redis_client.py` — All methods get a `tenant_id` parameter

| Current Key | Multi-Tenant Key | Method |
|---|---|---|
| `blocked_ips` | `t:{tid}:blocked_ips` | `add_blocked_ip()`, `remove_blocked_ip()`, `is_blocked()`, `get_blocked_ips()` |
| `recent_alerts` | `t:{tid}:recent_alerts` | `push_recent_alert()`, `get_recent_alerts()` |
| `live_metrics` | `t:{tid}:live_metrics` | `set_live_metrics()`, `get_live_metrics()` |
| `conn:{ip}:packets` | `t:{tid}:conn:{ip}:packets` | `update_conn_stats()`, `get_conn_features()` |
| `cooldown:alert:{ip}` | `t:{tid}:cooldown:{ip}` | `should_alert()` |
| `token:blacklist:{jti}` | `token:blacklist:{jti}` | **NO CHANGE** — tokens are global |
| `auth:lockout:{email}` | `auth:lockout:{email}` | **NO CHANGE** — lockout is global (prevents cross-tenant attacks) |
| `pending_decision:{alert_id}` | `t:{tid}:pending:{alert_id}` | Decision engine keys |
| `decision_payloads` | `t:{tid}:decision_payloads` | Decision payload hash |
| `decision_executed:{alert_id}` | `t:{tid}:executed:{alert_id}` | Lua idempotency key |
| `llm_cache:{hash}` | `t:{tid}:llm_cache:{hash}` | LLM result cache |
| `fcm:devices` | `t:{tid}:fcm:devices` | FCM device registry |

**Implementation approach:** Add `tenant_id` parameter to each method, default to `None` for backward compat during migration:

```python
async def add_blocked_ip(self, ip: str, tenant_id: str = None) -> None:
    key = f"t:{tenant_id}:blocked_ips" if tenant_id else "blocked_ips"
    await self.client.sadd(key, ip)
```

## 3.7 Tenant-Aware Pipeline Messages

Every message flowing through Redis Streams gets a `tenant_id` field. The sniffer/sensor is the origin point.

**Sensor publishes:**
```python
payload = {
    "tenant_id": SENSOR_TENANT_ID,   # ← injected at sensor registration
    "sensor_id": SENSOR_ID,          # ← identifies which sensor
    "timestamp": str(time.time()),
    "src_ip": src_ip,
    "dst_ip": dst_ip,
    "protocol": proto_name,
    "size": str(size),
    "trace_id": str(uuid.uuid4()),
}
await redis_manager.publish("stream:raw_packets", payload)
```

**Downstream services** (extractor, ml_engine, llm_analyzer, decision_engine, firewall) simply pass through the `tenant_id` from the incoming message to all outgoing messages and database writes. No routing logic needed — the tenant context flows naturally through the pipeline.

## 3.8 Tenant-Aware WebSocket

**File:** `gateway/main.py` — Modify `ConnectionManager`

```python
class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}  # tenant_id -> [ws, ...]

    async def connect(self, ws: WebSocket, tenant_id: str) -> None:
        await ws.accept()
        if tenant_id not in self.connections:
            self.connections[tenant_id] = []
        self.connections[tenant_id].append(ws)

    async def broadcast(self, tenant_id: str, message: dict) -> None:
        """Broadcast only to connections belonging to this tenant."""
        for ws in self.connections.get(tenant_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws, tenant_id)
```

**Telemetry push loop** (`telemetry_push_loop` in gateway/main.py:202) changes from broadcasting to ALL connections to iterating over tenant groups and fetching tenant-scoped metrics.

## 3.9 RBAC Hierarchy (Updated)

```
VALID_ROLES = {"owner", "admin", "analyst", "viewer"}
```

| Role | Tenant Scope | Capabilities |
|---|---|---|
| `owner` | Full control | Billing, delete tenant, transfer ownership, all admin capabilities |
| `admin` | Full operational | Manage team, manage sensors, all security operations, settings |
| `analyst` | Operational | View/manage alerts, block/unblock IPs, make decisions, add notes |
| `viewer` | Read-only | View dashboard, view alerts (no actions) |

**File change:** `shared/auth.py` line 92:
```python
VALID_ROLES = {"owner", "admin", "analyst", "viewer"}
```

## 3.10 Lua Script Tenant Scoping

**File:** `shared/lua_scripts.py` — Modify `get_execute_decision_keys()`

```python
def get_execute_decision_keys(alert_id: str, tenant_id: str) -> list[str]:
    return [
        f"t:{tenant_id}:executed:{alert_id}",
        f"t:{tenant_id}:decision_payloads",
        f"t:{tenant_id}:pending:{alert_id}",
        "stream:decision_logs",  # stream stays global
    ]
```

The Lua script itself (`LUA_EXECUTE_DECISION`) needs **no changes** — it operates on the KEYS passed to it.

## 3.11 MSSP Future Support Strategy

MSSPs manage multiple tenants. The architecture supports this with a `parent_tenant_id` concept:

```python
# Future addition to Tenant model:
parent_tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
    ForeignKey("tenants.id"), nullable=True
)
mssp_mode: Mapped[bool] = mapped_column(Boolean, default=False)
```

An MSSP user with `mssp_mode=True` can access all child tenants. This is NOT implemented in Phase 1 — the schema column is added but the access control logic comes later.

## 3.12 Migration Strategy: Zero-Downtime Transition

1. **Deploy new schema** (additive only — new columns, new tables)
2. **Backfill** existing data with default tenant_id
3. **Deploy tenant-aware code** with `tenant_id=None` fallback (backward compat)
4. **Enable RLS policies** (existing queries still work because default tenant is set)
5. **Remove fallback code** once all services are tenant-aware
6. **Enable tenant provisioning** for new signups

**Estimated risk: LOW** — Every step is additive. No existing data is modified or deleted. Rollback = disable RLS policies and revert code.
