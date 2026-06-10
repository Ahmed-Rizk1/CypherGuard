# SecureNet SOC → SaaS Implementation Plan

## Part 3: Billing, Infrastructure & Security

---

# PART 6 — BILLING & SUBSCRIPTION ARCHITECTURE

## 6.1 Stripe Integration Strategy

**Approach:** Stripe Checkout (hosted) + Stripe Billing (subscriptions) + Stripe Webhooks.

**Why Stripe Checkout (not custom payment form):** PCI compliance is handled by Stripe. No sensitive card data touches SecureNet servers. This is critical for SOC2 and customer trust.

### New Database Models

```python
class Subscription(Base):
    """Stripe subscription state mirror."""
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), unique=True, nullable=False)
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ai_analysis, sensor_hours
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(nullable=False)
    reported_to_stripe: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
```

## 6.2 Subscription Lifecycle

```
Free Trial (14 days)
  │
  ├── User upgrades → Stripe Checkout → subscription.created webhook
  │     └── tenant.plan = 'pro', tenant.status = 'active'
  │
  ├── Trial expires, no upgrade → tenant.plan stays 'free'
  │     └── Feature gates enforce limits (50 AI analyses, 1 sensor, 1 user)
  │
  └── User ignores → stays on free tier (never suspended)

Active Subscription
  │
  ├── Payment succeeds monthly → invoice.paid webhook → no action needed
  │
  ├── Payment fails → invoice.payment_failed webhook
  │     ├── Attempt 1: Email "Payment failed, updating card"
  │     ├── Attempt 2 (3 days later): Email "Final notice"
  │     └── Attempt 3 (7 days later): subscription.deleted webhook
  │           └── tenant.plan = 'free', feature gates kick in
  │
  ├── User upgrades plan → checkout.session.completed webhook
  │     └── tenant.plan = 'business', limits increased
  │
  ├── User downgrades → via customer portal or API
  │     └── Effective at period end (cancel_at_period_end = true)
  │
  └── User cancels → customer_subscription_deleted webhook
        └── tenant.plan = 'free' at period end
```

## 6.3 Webhook Handler

**New service file:** `billing/webhook_handler.py`

**Security:** Stripe signature verification on EVERY webhook. Reject unsigned events.

```python
@app.post("/v1/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.paid": handle_invoice_paid,
        "invoice.payment_failed": handle_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler:
        await handler(data)

    return {"received": True}
```

## 6.4 Feature Gate Middleware

**File:** `shared/feature_gates.py` (new)

```python
PLAN_LIMITS = {
    "free":       {"max_sensors": 1,  "max_users": 1,  "max_ai_monthly": 50,    "mobile_hitl": False, "siem_export": False},
    "pro":        {"max_sensors": 5,  "max_users": 5,  "max_ai_monthly": 2000,  "mobile_hitl": True,  "siem_export": False},
    "business":   {"max_sensors": 15, "max_users": 20, "max_ai_monthly": 10000, "mobile_hitl": True,  "siem_export": True},
    "enterprise": {"max_sensors": -1, "max_users": -1, "max_ai_monthly": -1,    "mobile_hitl": True,  "siem_export": True},
}

def require_feature(feature: str):
    """FastAPI dependency that checks if the tenant's plan includes a feature."""
    async def _check(auth: TokenPayload = Depends(verify_jwt)):
        async with tenant_session(auth.tid) as session:
            tenant = await session.get(Tenant, auth.tid)
            limits = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
            if not limits.get(feature, False):
                raise HTTPException(
                    status_code=403,
                    detail=f"Feature '{feature}' requires a plan upgrade"
                )
        return auth
    return _check
```

**Usage in mobile gateway:**
```python
@app.post("/v1/mobile/decision")
async def handle_decision(
    req: DecisionRequest,
    payload: TokenPayload = Depends(require_feature("mobile_hitl")),  # ← gate
):
    ...
```

## 6.5 AI Usage Metering

**In `llm_analyzer/main.py`** — after successful LLM analysis:

```python
# After successful LLM call, increment usage counter
async def increment_ai_usage(tenant_id: str):
    """Atomic increment of AI usage counter. Returns True if within quota."""
    key = f"t:{tenant_id}:ai_usage:{datetime.now().strftime('%Y-%m')}"
    count = await redis_manager.client.incr(key)
    if count == 1:
        # First usage this month — set 35-day expiry
        await redis_manager.client.expire(key, 35 * 86400)

    # Check against tenant limit
    async with tenant_session(tenant_id) as session:
        tenant = await session.get(Tenant, tenant_id)
        limit = PLAN_LIMITS.get(tenant.plan, {}).get("max_ai_monthly", 50)
        if limit != -1 and count > limit:
            return False  # Over quota — use heuristic fallback instead
    return True
```

**Integration point:** In `analyze_alert()` before calling LLM:
```python
if not await increment_ai_usage(tenant_id):
    logger.info(f"Tenant {tenant_id} exceeded AI quota — using heuristic")
    return heuristic_fallback(alert)
```

---

# PART 7 — CLOUD & INFRASTRUCTURE ROADMAP

## 7.1 Incremental Migration Strategy

**Principle: Change ONE layer at a time. Never migrate compute + storage simultaneously.**

### Phase A: Externalize Databases (Week 1–2)

```
BEFORE:                              AFTER:
┌──────────────────────┐             ┌──────────────────────┐
│   EC2 Instance       │             │   EC2 Instance       │
│  ┌────────────────┐  │             │  ┌────────────────┐  │
│  │ docker-compose │  │             │  │ docker-compose │  │
│  │  ┌──────────┐  │  │             │  │  (services     │  │
│  │  │ Redis    │  │  │  ──────►    │  │   only, no DB) │  │
│  │  │ Postgres │  │  │             │  └────────────────┘  │
│  │  │ Services │  │  │             └──────────┬───────────┘
│  │  └──────────┘  │  │                        │
│  └────────────────┘  │             ┌──────────▼───────────┐
└──────────────────────┘             │  RDS PostgreSQL      │
                                     │  ElastiCache Redis   │
                                     └──────────────────────┘
```

**Steps:**
1. Create RDS PostgreSQL Multi-AZ instance (db.t3.medium initially)
2. Create ElastiCache Redis node (cache.t3.medium)
3. `pg_dump` → restore to RDS
4. Update `DATABASE_URL` and `REDIS_URL` in `.env`
5. Remove `postgres` and `redis` containers from docker-compose
6. Verify all services connect to external databases
7. **Rollback:** Switch ENV vars back to localhost, restart containers

### Phase B: Container Registry + CI/CD (Week 2–3)

```
GitHub Push → GitHub Actions → ECR Push → Deploy to EC2 (docker pull)
```

**Steps:**
1. Create ECR repositories for each service image
2. Add `docker build` + `docker push` to `.github/workflows/ci.yml`
3. Add deploy step: SSH to EC2, `docker compose pull && docker compose up -d`
4. **Rollback:** `docker compose down && docker tag :previous :latest && docker compose up -d`

### Phase C: ECS Migration (Week 4–6)

Replace Docker Compose on EC2 with ECS Fargate task definitions.

```
┌──────────────────────────────────────────────────────────────┐
│                    AWS Account                                │
│                                                               │
│  ┌─────────────────────┐      ┌──────────────────────┐       │
│  │  ALB (public)       │      │  VPC Private Subnets │       │
│  │  ├─ /api/*  → gateway│     │  ┌─────────────────┐ │       │
│  │  ├─ /v1/*   → gateway│     │  │ ECS Cluster     │ │       │
│  │  ├─ /mobile/→ mobile │     │  │  ├─ gateway     │ │       │
│  │  ├─ /ws/*   → gateway│     │  │  ├─ mobile-gw   │ │       │
│  │  ├─ /ingest/→ ingest │     │  │  ├─ ingest-gw   │ │       │
│  │  └─ /*      → frontend│    │  │  ├─ extractor   │ │       │
│  └─────────────────────┘      │  │  ├─ ml-engine   │ │       │
│                               │  │  ├─ llm-analyzer│ │       │
│  ┌─────────────────────┐      │  │  ├─ decision-*  │ │       │
│  │  CloudFront CDN     │      │  │  ├─ firewall    │ │       │
│  │  (frontend assets)  │      │  │  └─ billing     │ │       │
│  └─────────────────────┘      │  └─────────────────┘ │       │
│                               └──────────────────────┘       │
│  ┌─────────────────────┐      ┌──────────────────────┐       │
│  │  RDS Multi-AZ       │      │  ElastiCache Cluster │       │
│  │  PostgreSQL 16      │      │  Redis 7             │       │
│  └─────────────────────┘      └──────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

**ECS Task Definition per Service:**
```json
{
  "family": "securenet-gateway",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "gateway",
    "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/securenet-gateway:latest",
    "portMappings": [{"containerPort": 8000}],
    "environment": [
      {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/securenet-gateway",
        "awslogs-region": "us-east-1"
      }
    },
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
    }
  }]
}
```

## 7.2 Auto-Scaling Configuration

| Service | Min | Max | Scale Metric | Threshold |
|---|---|---|---|---|
| gateway | 2 | 8 | ALBRequestCountPerTarget | >1000/min |
| mobile-gateway | 2 | 4 | ALBRequestCountPerTarget | >500/min |
| ingest-gateway | 2 | 10 | Custom: `stream:raw_packets` lag | >5000 |
| extractor | 2 | 8 | Custom: `stream:raw_packets` lag | >5000 |
| ml-engine | 2 | 8 | Custom: `stream:features` lag | >5000 |
| llm-analyzer | 1 | 4 | Custom: `stream:alerts` lag | >100 |
| firewall | 1 | 4 | Custom: `stream:block_commands` lag | >100 |
| decision-engine | 1 | 2 | CPU | >70% |

Custom metrics published to CloudWatch from each service's `/metrics` endpoint via a Prometheus → CloudWatch adapter.

## 7.3 Disaster Recovery

| Component | RPO | RTO | Strategy |
|---|---|---|---|
| PostgreSQL | 5 min | 15 min | RDS Multi-AZ automated failover + daily snapshots |
| Redis | 1 min | 5 min | ElastiCache Multi-AZ with AOF persistence |
| Application | 0 | 2 min | ECS auto-restart on health check failure |
| Secrets | N/A | 5 min | AWS Secrets Manager (multi-region replication) |
| ML Models | N/A | 10 min | S3 versioned bucket + ECS task pulls on start |

---

# PART 8 — SECURITY & COMPLIANCE

## 8.1 Sensor Trust Model

### API Key Security
- **Format:** `snk_` prefix + 48 cryptographic random bytes (base62 encoded) = 68 character string
- **Storage:** Only the bcrypt hash is stored in `sensors.api_key_hash`. The plaintext is shown once at generation.
- **Validation:** Every ingest request validates via constant-time bcrypt comparison
- **Rotation:** Admin can regenerate key. Old key is immediately invalidated.
- **IP binding (optional):** Sensor can be bound to a specific source IP via `sensors.config.allowed_ips`

### Ingest Gateway Isolation
- The ingest gateway (`ingest_gateway` service) runs in a separate ECS service
- It has **no access** to user authentication, billing, or admin functions
- It can ONLY write to `stream:raw_packets` — no read access to other streams
- Network: separate security group, only accepts HTTPS on port 443 from public internet

## 8.2 Tenant Isolation Guarantees

| Layer | Isolation Mechanism | Enforcement |
|---|---|---|
| **Database** | PostgreSQL RLS policies | `SET LOCAL app.tenant_id` per session |
| **Redis** | Key prefix `t:{tid}:` | Application-level (all methods in `redis_client.py`) |
| **Streams** | `tenant_id` field in every message | Consumer filters + RLS on DB writes |
| **WebSocket** | Tenant-scoped connection registry | `ConnectionManager.broadcast(tenant_id, msg)` |
| **API** | JWT `tid` claim | Middleware extracts + validates on every request |
| **Firewall** | Per-tenant blocklist | `t:{tid}:blocked_ips` Redis SET |
| **Sensors** | API key → tenant binding | `sensors.tenant_id` FK |
| **Files/Logs** | Tenant-tagged structured logs | Log filtering by `tenant_id` field |

## 8.3 Encryption Strategy

| Data | At Rest | In Transit |
|---|---|---|
| PostgreSQL | RDS TDE (AES-256) | TLS 1.3 (enforced via `sslmode=require` in connection string) |
| Redis | ElastiCache at-rest encryption | ElastiCache in-transit encryption (TLS) |
| S3 (models, exports) | SSE-KMS (customer-managed keys for enterprise) | HTTPS only |
| Secrets | AWS Secrets Manager (AES-256) | IAM role-based access |
| Sensor ↔ Platform | N/A | TLS 1.3 (certificate pinning in sensor) |
| User passwords | bcrypt (12 rounds) | HTTPS |

## 8.4 SOC2 Readiness Roadmap

| Control Category | Current State | Required | Effort |
|---|---|---|---|
| **CC6.1 Logical Access** | JWT + RBAC ✅ | Add MFA (TOTP), SSO (SAML/OIDC) | 3 weeks |
| **CC6.2 Access Provisioning** | Manual user creation | Self-service + invitation flow | 2 weeks (in onboarding plan) |
| **CC6.3 Access Removal** | Manual | Auto-deactivate on subscription cancel | 1 week |
| **CC7.1 Monitoring** | Prometheus + Grafana ✅ | Add CloudWatch alarms + PagerDuty | 1 week |
| **CC7.2 Incident Response** | `docs/incident_response.md` ✅ | Formalize with SLAs + PagerDuty runbooks | 1 week |
| **CC8.1 Change Management** | GitHub PRs ✅ | Add approval requirements + deployment audit | 2 days |
| **A1.2 Recovery** | Not tested ❌ | Document + test DR procedures quarterly | 1 week |
| **PI1.1 Data Privacy** | Audit log ✅ | Add data retention policies, DPA template | 1 week |

**Timeline to SOC2 Type I:** ~3 months after Phase 2 implementation.
**Timeline to SOC2 Type II:** ~9 months (requires 6-month observation period).

## 8.5 Threat Intelligence Integration

**Implementation:** New `threat_intel` module in `shared/` that enriches alerts.

**Integration point:** In `llm_analyzer/main.py`, before LLM call:

```python
async def enrich_alert(alert: dict) -> dict:
    """Enrich alert with threat intelligence data."""
    src_ip = alert.get("src_ip", "")

    # VirusTotal IP reputation (cached 24h)
    vt_data = await threat_intel.check_virustotal(src_ip)
    alert["vt_reputation"] = vt_data.get("reputation", 0)
    alert["vt_malicious_votes"] = vt_data.get("malicious", 0)

    # AbuseIPDB confidence score (cached 24h)
    abuse_data = await threat_intel.check_abuseipdb(src_ip)
    alert["abuse_confidence"] = abuse_data.get("confidence_score", 0)

    return alert
```

This enrichment data is included in the LLM prompt, giving the AI more context for classification, and stored in `alert.raw_features` for analyst review.
