# SecureNet SOC → SaaS Implementation Plan

## Part 4: Implementation Roadmap & Final Recommendations

---

# PART 9 — IMPLEMENTATION ROADMAP

## Overview: Four Phases

```
Phase 1 (Weeks 1-4)     Phase 2 (Weeks 5-8)     Phase 3 (Weeks 9-12)    Phase 4 (Weeks 13-16)
─────────────────────    ─────────────────────    ─────────────────────    ─────────────────────
FOUNDATION               SAAS EXPERIENCE          PRODUCTION INFRA        ENTERPRISE READY
                                                  
Multi-Tenancy            Billing (Stripe)         AWS Migration            SOC2 Controls
Tenant-Aware Auth        Dashboard UX             ECS Fargate              Threat Intelligence
Sensor System            Onboarding Wizard        Auto-Scaling             SSO (SAML/OIDC)
Ingest Gateway           Team Management          DR Testing               MFA
RLS Policies             Feature Gates            Observability            Advanced Reporting
                         Notification Center      CDN + WAF                MSSP Groundwork
```

---

## Phase 1: FOUNDATION (Weeks 1-4)

### Objective
Establish the multi-tenant data layer, tenant-aware authentication, and sensor deployment system. After this phase, the platform can support multiple tenants with isolated data, and remote sensors can authenticate and push data.

### Week 1: Multi-Tenant Data Layer

#### Backend Changes

| # | Task | File(s) | Estimated Hours |
|---|---|---|---|
| 1.1 | Create `Tenant`, `Sensor`, `APIKey` ORM models | `shared/database.py` | 3h |
| 1.2 | Add `tenant_id` column to all 7 existing models | `shared/database.py` | 2h |
| 1.3 | Write Alembic migration (create tables, add columns, backfill, RLS) | `alembic/versions/` | 4h |
| 1.4 | Implement `tenant_session()` context manager with RLS | `shared/database.py` | 2h |
| 1.5 | Add `tenant_id` parameter to all `RedisManager` methods | `shared/redis_client.py` | 4h |
| 1.6 | Update `get_execute_decision_keys()` for tenant-scoped keys | `shared/lua_scripts.py` | 1h |
| 1.7 | Add `tid` to `TokenPayload`, `create_access_token()`, `create_refresh_token()` | `shared/auth.py` | 2h |
| 1.8 | Create `TenantMiddleware` (extract tenant from JWT, set in request state) | `shared/middleware.py` (new) | 3h |

**Total: ~21 hours**

#### Testing Strategy
- **Migration test:** Run Alembic upgrade/downgrade on a test database. Verify data integrity.
- **RLS test:** Insert rows for Tenant A and B. Verify session scoped to A cannot see B's data.
- **Key isolation test:** Verify Redis `t:{tid_a}:blocked_ips` does not intersect with `t:{tid_b}:blocked_ips`.
- **Auth test:** Verify JWT with `tid` claim creates proper tenant session.
- **Backward compat test:** All existing 137 tests pass with default tenant fallback.

#### Rollback Strategy
- Alembic downgrade removes columns and tables
- RLS policies can be disabled with `ALTER TABLE ... DISABLE ROW LEVEL SECURITY`
- Code changes are backward compatible (tenant_id defaults to None in all methods)

### Week 2: Tenant-Aware Services

| # | Task | File(s) | Hours |
|---|---|---|---|
| 2.1 | Update gateway login to include `tenant_id` in JWT | `gateway/main.py` | 2h |
| 2.2 | Update all gateway endpoints to use `tenant_session()` | `gateway/main.py` | 4h |
| 2.3 | Update all mobile gateway endpoints to use `tenant_session()` | `mobile_gateway/main.py` | 4h |
| 2.4 | Update extractor to pass `tenant_id` through pipeline | `extractor/main.py` | 2h |
| 2.5 | Update ML engine to include `tenant_id` in predictions and alerts | `ml_engine/main.py` | 2h |
| 2.6 | Update LLM analyzer to scope cache keys per tenant | `llm_analyzer/main.py` | 2h |
| 2.7 | Update decision engine to use tenant-scoped keys | `control_plane/decision_engine.py` | 2h |
| 2.8 | Update timeout listener for tenant-scoped expiration keys | `control_plane/decision_timeout_listener.py` | 1h |
| 2.9 | Update fallback scanner for tenant-scoped scanning | `control_plane/decision_fallback_scanner.py` | 1h |
| 2.10 | Update decision log writer for tenant context | `control_plane/decision_log_writer.py` | 1h |
| 2.11 | Update firewall service for tenant-scoped blocklist | `firewall/main.py` | 2h |
| 2.12 | Update WebSocket `ConnectionManager` for tenant-scoped broadcasts | `gateway/main.py` | 3h |

**Total: ~26 hours**

#### Key Decision: Stream Strategy

**Shared streams with tenant_id field** (chosen over per-tenant streams):

```python
# Every service's consumer loop adds tenant extraction:
for stream_name, entries in messages:
    for msg_id, data in entries:
        tenant_id = data.get("tenant_id", DEFAULT_TENANT_ID)
        # All operations use this tenant_id
```

**Why not per-tenant streams?**
- With 10 tenants: 10 × 5 streams = 50 streams with 50 consumer groups. Manageable.
- With 100 tenants: 500 streams. Redis overhead becomes significant.
- Shared streams are simpler operationally and scale fine to ~200 tenants.
- Per-tenant streams become necessary only for large enterprise isolation requirements.

### Week 3: Ingest Gateway + Sensor Image

| # | Task | File(s) | Hours |
|---|---|---|---|
| 3.1 | Create Ingest Gateway FastAPI service | `ingest_gateway/main.py` (new) | 6h |
| 3.2 | Implement `verify_sensor_key()` dependency (bcrypt validation) | `ingest_gateway/auth.py` (new) | 3h |
| 3.3 | Implement `/v1/ingest/register` endpoint | `ingest_gateway/main.py` | 2h |
| 3.4 | Implement `/v1/ingest/packets` batch endpoint | `ingest_gateway/main.py` | 3h |
| 3.5 | Implement `/v1/ingest/heartbeat` endpoint | `ingest_gateway/main.py` | 2h |
| 3.6 | Implement `/v1/ingest/config` endpoint | `ingest_gateway/main.py` | 1h |
| 3.7 | Refactor `sniffer/main.py` into sensor Docker image | `sensor/main.py` (new) | 6h |
| 3.8 | Implement sensor heartbeat loop | `sensor/heartbeat.py` (new) | 2h |
| 3.9 | Implement local packet buffer (SQLite) for offline handling | `sensor/buffer.py` (new) | 4h |
| 3.10 | Create `sensor/Dockerfile` with multi-stage build | `sensor/Dockerfile` | 2h |
| 3.11 | Add sensor to `docker-compose.yml` | `docker-compose.yml` | 1h |
| 3.12 | Sensor health monitor background task (offline detection) | `ingest_gateway/monitor.py` (new) | 2h |

**Total: ~34 hours**

#### Dependencies
- Requires: Week 1 (Tenant, Sensor ORM models) + Week 2 (tenant-aware Redis)
- Blocked by: Nothing

### Week 4: Signup & Auth Endpoints

| # | Task | File(s) | Hours |
|---|---|---|---|
| 4.1 | Create `POST /v1/auth/signup` endpoint | `gateway/main.py` | 4h |
| 4.2 | Create `POST /v1/auth/verify-email` endpoint | `gateway/main.py` | 2h |
| 4.3 | Create email sending utility (SMTP/SES) | `shared/email.py` (new) | 3h |
| 4.4 | Create email template system (verification, invitation) | `shared/email_templates/` (new) | 2h |
| 4.5 | Create `POST /v1/api/sensors` (generate sensor key) | `gateway/main.py` | 3h |
| 4.6 | Create `GET /v1/api/sensors` (list sensors with status) | `gateway/main.py` | 2h |
| 4.7 | Create `DELETE /v1/api/sensors/{id}` (revoke sensor) | `gateway/main.py` | 1h |
| 4.8 | Create `POST /v1/api/team/invite` | `gateway/main.py` | 3h |
| 4.9 | Create `GET /v1/api/team` (list team members) | `gateway/main.py` | 1h |
| 4.10 | Create `GET /v1/api/onboarding/status` | `gateway/main.py` | 1h |
| 4.11 | Update `VALID_ROLES` to include "owner" | `shared/auth.py` | 0.5h |
| 4.12 | Write tests for all new endpoints | `tests/` | 6h |

**Total: ~28.5 hours**

### Phase 1 Risk Analysis

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| RLS misconfiguration leaks tenant data | Medium | Critical | Automated test suite that inserts data for 2 tenants and verifies isolation at DB level |
| Redis key collision between tenants | Low | Critical | Key prefix format is deterministic. Unit tests verify key generation. |
| Existing tests break | High | Medium | Run full test suite after each week. Default tenant ID ensures backward compat. |
| Sensor authentication bypass | Low | Critical | Bcrypt comparison is constant-time. API keys are 68 chars (cryptographically strong). |

---

## Phase 2: SAAS EXPERIENCE (Weeks 5-8)

### Objective
Build the customer-facing SaaS experience: billing, dashboard redesign, onboarding wizard, team management, and feature gates. After this phase, customers can self-serve from signup to paid subscription.

### Week 5: Billing Integration

| # | Task | File(s) | Hours |
|---|---|---|---|
| 5.1 | Create `Subscription`, `UsageRecord` ORM models | `shared/database.py` | 2h |
| 5.2 | Alembic migration for billing tables | `alembic/versions/` | 1h |
| 5.3 | Create `shared/feature_gates.py` with plan limits | New | 3h |
| 5.4 | Create `POST /v1/api/billing/checkout` (Stripe Checkout session) | `gateway/main.py` | 3h |
| 5.5 | Create `POST /v1/webhooks/stripe` webhook handler | `billing/webhook_handler.py` (new) | 6h |
| 5.6 | Create `GET /v1/api/billing/portal` (Stripe Customer Portal link) | `gateway/main.py` | 1h |
| 5.7 | Create `GET /v1/api/billing/usage` (current AI usage stats) | `gateway/main.py` | 2h |
| 5.8 | Integrate AI usage metering in LLM analyzer | `llm_analyzer/main.py` | 2h |
| 5.9 | Create trial expiration checker (cron/scheduler) | `billing/trial_checker.py` (new) | 3h |
| 5.10 | Write Stripe webhook tests with mock events | `tests/` | 4h |

**Total: ~27 hours**

### Week 6-7: Frontend — Dashboard Redesign + Onboarding

| # | Task | File(s) | Hours |
|---|---|---|---|
| 6.1 | Update `AuthContext.jsx` to store `tenant_id` from JWT | `hooks/AuthContext.jsx` | 2h |
| 6.2 | Create `RBACGate.jsx` component | `components/` | 1h |
| 6.3 | Create `OnboardingWizard.jsx` (4-step wizard) | `pages/` | 8h |
| 6.4 | Create `SensorsPage.jsx` (sensor management) | `pages/` | 6h |
| 6.5 | Create `TeamPage.jsx` (team management + invitations) | `pages/` | 5h |
| 6.6 | Create `BillingPage.jsx` (plan display, Stripe portal link) | `pages/` | 4h |
| 6.7 | Create `NotificationCenter.jsx` (bell icon dropdown) | `components/` | 4h |
| 6.8 | Create `FeatureGate.jsx` (upgrade prompt UI) | `components/` | 2h |
| 6.9 | Update `Sidebar.jsx` with new navigation + RBAC | `components/Sidebar.jsx` | 3h |
| 6.10 | Update `App.jsx` with new routes | `App.jsx` | 1h |
| 6.11 | Create `SignupPage.jsx` | `pages/` | 5h |
| 6.12 | Create `EmailVerifyPage.jsx` | `pages/` | 2h |
| 6.13 | Update `useSOCData.js` to pass tenant context to WebSocket | `hooks/useSOCData.js` | 2h |
| 6.14 | Redesign `Telemetry.jsx` with per-sensor breakdown | `pages/Telemetry.jsx` | 4h |
| 6.15 | Create `ReportsPage.jsx` (weekly/monthly security reports) | `pages/` | 5h |

**Total: ~54 hours**

### Week 8: Integration Testing + Polish

| # | Task | Hours |
|---|---|---|
| 8.1 | End-to-end test: Signup → Deploy sensor → See alerts → Approve via mobile | 8h |
| 8.2 | End-to-end test: Free trial → Upgrade → Feature unlock | 4h |
| 8.3 | End-to-end test: Multi-tenant isolation (2 tenants, verify no data leak) | 4h |
| 8.4 | Load test: 10 concurrent tenants, 1000 pps each | 4h |
| 8.5 | UX review and polish (animations, loading states, error handling) | 8h |
| 8.6 | Documentation update (README, API docs, sensor docs) | 4h |

**Total: ~32 hours**

### Phase 2 Rollback Strategy
- Frontend: Feature flags for new pages (show/hide via config)
- Billing: Stripe can be disconnected without data loss (subscriptions live in Stripe)
- Feature gates: `PLAN_LIMITS` can be overridden to grant all features (bypass mode)

---

## Phase 3: PRODUCTION INFRASTRUCTURE (Weeks 9-12)

### Objective
Migrate from EC2 Docker Compose to AWS managed services (ECS Fargate, RDS, ElastiCache). Establish auto-scaling, monitoring, alerting, and disaster recovery.

### Week 9: Database Migration

| # | Task | Hours |
|---|---|---|
| 9.1 | Create Terraform module for VPC, subnets, security groups | 6h |
| 9.2 | Create Terraform module for RDS PostgreSQL Multi-AZ | 4h |
| 9.3 | Create Terraform module for ElastiCache Redis | 3h |
| 9.4 | Create Terraform module for Secrets Manager | 2h |
| 9.5 | Migrate PostgreSQL data: `pg_dump` → RDS restore | 3h |
| 9.6 | Verify all services connect to RDS + ElastiCache | 4h |
| 9.7 | Test failover (simulate RDS AZ failure) | 2h |

**Total: ~24 hours**

### Week 10: ECS Migration

| # | Task | Hours |
|---|---|---|
| 10.1 | Create ECR repositories for all services | 1h |
| 10.2 | Create ECS task definitions for all 13 services | 8h |
| 10.3 | Create ECS services with desired counts | 4h |
| 10.4 | Create ALB with target groups and path routing | 4h |
| 10.5 | Create ACM certificate + configure HTTPS | 1h |
| 10.6 | Blue/green deployment: run ECS alongside EC2, route 10% traffic | 4h |
| 10.7 | Validate ECS deployment, shift 100% traffic | 2h |
| 10.8 | Decommission EC2 instance | 1h |

**Total: ~25 hours**

### Week 11: Observability + CDN

| # | Task | Hours |
|---|---|---|
| 11.1 | CloudWatch log groups for all ECS tasks | 2h |
| 11.2 | CloudWatch alarms (CPU, memory, 5xx rate, latency p99) | 3h |
| 11.3 | CloudFront distribution for frontend static assets | 2h |
| 11.4 | WAF rules (rate limiting, SQL injection, XSS, geo-blocking) | 3h |
| 11.5 | PagerDuty/OpsGenie integration for critical alarms | 2h |
| 11.6 | Move Prometheus/Grafana to managed (Grafana Cloud or AMP) | 3h |
| 11.7 | Create SLI/SLO dashboard (availability, latency, error rate) | 3h |

**Total: ~18 hours**

### Week 12: Auto-Scaling + DR Testing

| # | Task | Hours |
|---|---|---|
| 12.1 | Configure ECS auto-scaling policies per service | 3h |
| 12.2 | Custom CloudWatch metrics from Redis stream lag | 3h |
| 12.3 | DR drill: simulate RDS failure, validate failover | 2h |
| 12.4 | DR drill: simulate ECS task failure, validate restart | 1h |
| 12.5 | DR drill: simulate Redis failure, validate fallback | 2h |
| 12.6 | Create runbook documentation for all DR scenarios | 4h |
| 12.7 | Load test on production infrastructure (gradual ramp to 10K pps) | 4h |

**Total: ~19 hours**

---

## Phase 4: ENTERPRISE READINESS (Weeks 13-16)

### Objective
Implement compliance controls, threat intelligence integration, SSO, MFA, and lay the groundwork for MSSP support.

| # | Task | Hours |
|---|---|---|
| 13.1 | TOTP MFA implementation (setup, verify, enforce for admins) | 12h |
| 13.2 | SSO integration (SAML 2.0 or OIDC via Auth0/WorkOS) | 16h |
| 13.3 | Threat intelligence module (VirusTotal + AbuseIPDB) | 10h |
| 13.4 | SIEM export (syslog forwarding + webhook notifications) | 8h |
| 13.5 | IP whitelist management (per-tenant exclusion lists) | 4h |
| 13.6 | Audit log immutability (append-only with hash chain) | 6h |
| 13.7 | Data retention policies (auto-purge per tenant plan) | 4h |
| 13.8 | Compliance report generation (PDF/CSV export) | 8h |
| 13.9 | MSSP schema design (parent_tenant_id, cross-tenant views) | 6h |
| 13.10 | Security penetration testing engagement | External vendor |
| 13.11 | SOC2 Type I auditor engagement | External vendor |

---

# PART 10 — FINAL RECOMMENDATIONS

## Best Architectural Decisions

1. **Row-Level Security over schema-per-tenant.** RLS provides cryptographic-level isolation without the operational complexity of managing hundreds of databases. You can always upgrade a single tenant to dedicated schema later.

2. **Shared Redis Streams with tenant_id field.** Per-tenant streams create O(tenants × streams) consumer groups. Shared streams scale to ~200 tenants with zero overhead. The tenant_id field enables filtering.

3. **Separate Ingest Gateway.** Sensor traffic is fundamentally different from user traffic (API key auth vs JWT, high volume vs interactive). Separating it provides security isolation and independent scaling.

4. **Sensor as Docker image, not agent binary.** Docker is already your deployment model. The sensor is just a packaged version of the existing sniffer with authentication and buffering added. Customers who use Docker (which is most of your target market) get a one-command deployment.

5. **Feature gates in middleware, not in UI.** Feature gating at the API level prevents bypass. The UI gates are just for UX — the real enforcement happens server-side.

## Critical Mistakes to Avoid

| Mistake | Why It's Dangerous | How to Avoid |
|---|---|---|
| **Implementing multi-tenancy in the frontend only** | Backend still returns all tenants' data. One API call with modified parameters leaks everything. | RLS at database level + middleware at API level. Double enforcement. |
| **Per-tenant Redis instances** | Operational nightmare. Connection pool explosion. Cost scales linearly. | Key prefixing is simpler, cheaper, and operationally manageable. |
| **Rewriting the sniffer for SaaS** | Loses the battle-tested packet capture logic. Introduces bugs in the most critical component. | The sensor is the sniffer + auth wrapper + buffer. Core logic unchanged. |
| **Custom payment processing** | PCI compliance is a years-long, $100K+ process. | Stripe Checkout handles everything. Card data never touches your servers. |
| **Launching without load testing** | First customer with real traffic discovers your system falls over at 5K pps. | Week 12 load test is mandatory before public launch. |
| **Skipping the default tenant migration** | Existing data has no tenant_id. New code crashes on NULL tenant references. | Backfill migration in step 1.3 assigns all existing data to a default tenant. |

## Most Dangerous Technical Risks

| Risk | Severity | Probability | Mitigation |
|---|---|---|---|
| **RLS bypass** (application bug sets wrong tenant_id) | Critical | Medium | Automated security test: create data as Tenant A, query as Tenant B, assert empty. Run on every CI build. |
| **Redis memory exhaustion** (many tenants × many keys) | High | Medium | Set `maxmemory-policy volatile-lru`. Monitor per-tenant key count. Alert at 80% memory. |
| **Stripe webhook replay attack** | High | Low | Verify Stripe signature on every webhook. Store processed event IDs for idempotency. |
| **Sensor key brute force** | High | Low | 68-character keys = 2^380 keyspace. Rate limit ingest endpoint to 100 requests/minute per source IP. |
| **LLM cost explosion** | Medium | Medium | AI usage metering + hard quota per tenant plan. Heuristic fallback when quota exceeded. |

## Highest ROI Implementations (Priority Order)

1. **Multi-tenancy (Phase 1, Weeks 1-2)** — Without this, nothing else matters. You cannot sell SaaS without tenant isolation. ROI: Infinite (enables all revenue).

2. **Sensor system (Phase 1, Week 3)** — This is how customers connect to the platform. Without sensors, the product is a demo. ROI: Enables customer deployment.

3. **Signup + onboarding (Phase 1, Week 4 + Phase 2, Week 6)** — Self-service acquisition. Without this, every customer requires manual setup. ROI: Removes manual bottleneck.

4. **Stripe billing (Phase 2, Week 5)** — Revenue collection. ROI: Enables monetization.

5. **AWS migration (Phase 3)** — Required for SLA commitments and scaling. ROI: Enables >10 customers.

6. **Threat intelligence (Phase 4)** — Differentiator that CISOs expect. ROI: Reduces churn, justifies pricing.

## Fastest Path to First Paying Customer

```
Week 1-2: Multi-tenancy → Can isolate tenant data
Week 3:   Sensor system → Customer can deploy on their network
Week 4:   Signup flow → Customer can self-register
Week 5:   Billing → Customer can pay
Week 6-7: Dashboard → Customer has great UX

→ TOTAL: 7 weeks to first possible paying customer

Shortcut (5 weeks):
- Skip billing (invoice manually via Stripe dashboard)
- Skip onboarding wizard (deploy sensor for them manually)
- Just multi-tenancy + sensor + signup = 4 weeks
- Then 1 week of testing
- Deploy for your first customer with white-glove setup
```

## Safest Scaling Strategy

```
1-10 customers:   Single EC2 + external RDS/ElastiCache (Phase A only)
10-50 customers:  ECS Fargate with auto-scaling (Phase C)
50-200 customers: ECS + CloudFront + WAF + multi-region (Phase C complete)
200+ customers:   EKS Kubernetes + per-tenant stream routing + read replicas
```

**Rule:** Don't pre-optimize. Each scaling step is triggered by actual need, not anticipated need.

---

> [!IMPORTANT]
> **The implementation plan is designed for incremental, safe evolution.** Each week delivers working functionality. Each phase has independent value. You can stop after Phase 1 and have a functional multi-tenant platform. You can stop after Phase 2 and have a sellable SaaS product. Phase 3 and 4 are about scale and enterprise readiness.

> [!TIP]
> **Start Phase 1 this week.** The first task (create ORM models in `database.py`) is low-risk, high-impact, and takes 3 hours. Every subsequent task depends on it. The sooner the tenant model exists, the sooner everything else can begin.
