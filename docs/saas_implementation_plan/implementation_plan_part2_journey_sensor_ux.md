# SecureNet SOC → SaaS Implementation Plan

## Part 2: User Journey, Sensor System & Dashboard UX

---

# PART 2 — TARGET USER JOURNEY (DETAILED)

## Stage 1: Visitor Discovers Product → Signup

### 1a. Landing Page Visit
- **User sees:** Marketing landing page at `securenet.io`. Hero section, feature grid, pricing, demo video.
- **Frontend:** Static page served from CDN (CloudFront). No authentication required.
- **Backend:** None — pure static content.

### 1b. Click "Start Free Trial"
- **User sees:** Registration form: Company name, Full name, Work email, Password, Company size dropdown.
- **User does:** Fills form, clicks "Create Account."
- **Frontend:** `POST /v1/auth/signup` with form data.
- **Backend (new `gateway/main.py` endpoint):**
  1. Validate email (format + not disposable domain)
  2. Check email uniqueness globally
  3. Hash password with bcrypt
  4. **Create Tenant:** `INSERT INTO tenants (name, slug, plan, status, trial_ends_at)` — status=`trial`, plan=`free`, trial_ends_at = NOW() + 14 days
  5. **Create User:** `INSERT INTO users (email, password_hash, role, tenant_id)` — role=`owner`
  6. **Set tenant.owner_id** = new user ID
  7. Generate email verification token (signed JWT, 24h expiry, type=`email_verify`)
  8. Publish to `stream:email_queue`: `{type: "verify_email", to: email, token: ...}`
  9. `write_audit_log(action="tenant.created", actor=email, resource_type="tenant")`
- **Redis events:** Email queued to `stream:email_queue`
- **Database changes:** New row in `tenants`, new row in `users`
- **Security:** Password strength validation (min 8 chars, 1 upper, 1 number). Rate limit: 3 signups per IP per hour.
- **Response:** `{success: true, message: "Verification email sent"}`

### 1c. Email Verification
- **User sees:** Email with "Verify Your Account" button linking to `https://app.securenet.io/verify?token=...`
- **User does:** Clicks link.
- **Frontend:** `POST /v1/auth/verify-email` with token.
- **Backend:**
  1. Decode JWT token, verify type=`email_verify`
  2. `UPDATE users SET is_active = true WHERE id = :user_id`
  3. `write_audit_log(action="auth.email_verified")`
- **Security:** Token is single-use (blacklisted after use). Expires in 24h.

### 1d. First Login
- **User sees:** Login page → redirects to `/app/onboarding` (setup wizard).
- **Backend:** Standard login flow from existing `gateway/main.py:237` but now includes `tid` (tenant_id) in the JWT. Also checks `user.is_active` and `tenant.status != 'suspended'`.
- **JWT now contains:** `{sub: user_id, tid: tenant_id, role: "owner", ...}`

## Stage 2: Onboarding Wizard (First Login Only)

### Step 1 of 4: "Welcome to SecureNet"
- **User sees:** Welcome message with company name. "Let's set up your security monitoring in 5 minutes."
- **Backend:** `GET /v1/api/onboarding/status` → returns `{step: 1, sensor_deployed: false, team_invited: false}`
- **No DB changes.** Just reads tenant state.

### Step 2 of 4: "Deploy Your Sensor"
- **User sees:** Sensor deployment instructions. Three tabs: Docker, Kubernetes, Manual.
- **User does:** Clicks "Generate Sensor Key" button.
- **Backend:** `POST /v1/api/sensors` →
  1. Validate `tenant.max_sensors > current_sensor_count`
  2. Generate cryptographic API key: `snk_` + 48 random bytes (base62)
  3. Hash with bcrypt, store hash in `sensors.api_key_hash`
  4. Store prefix `snk_XXXXXXXX` in `sensors.api_key_prefix`
  5. Return **full API key exactly once** — user must copy it now
- **User sees:** API key displayed with copy button + Docker command:

```bash
docker run -d --name securenet-sensor \
  --network host --privileged \
  -e SECURENET_API_KEY=snk_XXXXXXXXXXXXX \
  -e SECURENET_ENDPOINT=https://ingest.securenet.io \
  -e SENSOR_NAME="Office-Network" \
  securenet/sensor:latest
```

- **Security:** API key shown once. Cannot be retrieved again. Can only be revoked and regenerated.

### Step 3 of 4: "Waiting for Connection..."
- **User sees:** Animated waiting indicator: "Listening for your sensor..."
- **Frontend:** Polls `GET /v1/api/sensors` every 3 seconds.
- **Backend flow (when sensor starts):**
  1. Sensor sends `POST /v1/ingest/register` with `{api_key, sensor_name, version}`
  2. Platform validates API key: bcrypt compare against `sensors.api_key_hash`
  3. `UPDATE sensors SET status='active', last_heartbeat=NOW(), last_ip=:ip`
  4. Returns `{sensor_id, tenant_id, config: {feature_window: 30, ...}}`
  5. Sensor begins capturing packets and publishing to `stream:raw_packets` with `tenant_id` and `sensor_id`
- **User sees:** ✅ "Sensor connected! Monitoring has started." Auto-advances to Step 4.
- **Time expected:** 30–120 seconds between Docker run and connection.

### Step 4 of 4: "Invite Your Team" (Optional)
- **User sees:** "Invite team members" form. Email + role selector. "Skip for now" button.
- **Backend:** `POST /v1/api/team/invite` → creates invitation record, sends email with signup link containing tenant_id claim.
- **User does:** Invites 1–2 analysts or skips.
- **Final:** Redirects to `/app/telemetry` — the main dashboard.

## Stage 3: First Traffic Analysis

- **What happens behind the scenes (first 60 seconds):**
  1. Sensor captures packets → `stream:raw_packets` (with `tenant_id`)
  2. Extractor computes features → `stream:features` (passes `tenant_id`)
  3. ML Engine runs inference → benign predictions logged to `ml_predictions` (with `tenant_id`)
  4. Live metrics published to `t:{tid}:live_metrics`
  5. Dashboard receives metrics via WebSocket → displays packets/sec, bytes/sec, active connections

- **User sees:** Dashboard comes alive with real-time traffic metrics. "Your network is being monitored. 0 threats detected."

## Stage 4: First Alert Experience

- **Trigger:** ML Engine detects malicious traffic from a real or simulated attack.
- **Backend pipeline:**
  1. ML Engine publishes to `stream:alerts` (with `tenant_id`)
  2. LLM Analyzer processes → persists Alert to PostgreSQL (with `tenant_id`)
  3. Decision Engine routes based on severity
  4. WebSocket broadcasts `{type: "new_alert", data: {...}}` to tenant's connections
  5. Push notification sent to tenant's registered mobile devices
- **User sees:** Alert badge on Threats tab. Real-time alert card slides in:
  - Severity badge (color-coded)
  - Source IP
  - AI-generated attack explanation
  - "View Details" and "Block IP" buttons

## Stage 5: Mobile Approval Flow

- **Existing flow preserved** — [mobile_gateway/main.py:647-682](file:///d:/Graduation%20Project/SecureNet_IDS_Project/mobile_gateway/main.py#L647-L682)
- **Only change:** All Redis keys and DB operations are tenant-scoped.
- **User experience unchanged:** Push notification → Review alert → APPROVE/REJECT/ESCALATE → Confirmation.

## Stage 6: Billing & Subscription Flow

- **Day 12 of trial:** In-app banner: "Your trial ends in 2 days. Upgrade to Pro to keep monitoring."
- **User navigates to:** Settings → Billing → Sees plan comparison table.
- **User clicks:** "Upgrade to Pro ($499/mo)"
- **Frontend:** Opens Stripe Checkout session (redirect or embedded).
- **Backend:** `POST /v1/api/billing/checkout` → creates Stripe Checkout Session with `tenant_id` in metadata.
- **Stripe webhook** `checkout.session.completed`:
  1. `UPDATE tenants SET plan='pro', status='active', stripe_customer_id=:cust, stripe_subscription_id=:sub`
  2. `UPDATE tenants SET max_sensors=5, max_users=5, max_ai_analyses_monthly=2000`
  3. `write_audit_log(action="billing.upgraded", details={plan: "pro"})`

## Stage 7: Trial Expiration Flow

- **Day 14 (if not upgraded):**
  1. Cron job/scheduler checks `tenants WHERE status='trial' AND trial_ends_at < NOW()`
  2. `UPDATE tenants SET status='active', plan='free'` (downgrade, not suspend)
  3. Feature gates kick in: AI analyses limited to 50/mo, 1 sensor, 1 user
  4. Email: "Your trial has ended. You're on the Free plan."
- **User experience:** Dashboard still works but with limitations. Upgrade prompts appear.
- **NOT suspended** — Free tier keeps working. This reduces churn vs. hard cutoffs.

---

# PART 4 — SENSOR DEPLOYMENT SYSTEM

## 4.1 Sensor Architecture

The existing `sniffer/main.py` becomes the basis for the **SecureNet Sensor** — a Docker image deployed on customer networks.

### Current Sniffer vs. SaaS Sensor

| Aspect | Current Sniffer | SaaS Sensor |
|---|---|---|
| Authentication | None | API key (HMAC-validated) |
| Connection | Direct Redis on localhost | HTTPS to platform ingest endpoint |
| Tenant context | None | `tenant_id` + `sensor_id` in every message |
| Health reporting | None | Heartbeat every 30 seconds |
| Configuration | ENV vars | Fetched from platform on startup + periodic refresh |
| Updates | Manual docker pull | Auto-update via version check |
| Offline handling | Crashes | Local buffer → replay on reconnect |

### Sensor → Platform Communication

```
┌─────────────────────┐          HTTPS/WSS          ┌──────────────────────┐
│   SecureNet Sensor   │ ◄─────────────────────────► │   Ingest Gateway     │
│   (customer network) │                             │   (new service)      │
│                      │  POST /v1/ingest/register   │                      │
│   scapy capture      │  POST /v1/ingest/packets    │   validates API key  │
│   local buffer       │  POST /v1/ingest/heartbeat  │   publishes to Redis │
│   heartbeat loop     │  GET  /v1/ingest/config     │   Streams            │
│   auto-update check  │                             │                      │
└─────────────────────┘                              └──────────────────────┘
```

## 4.2 New Service: Ingest Gateway

A new lightweight FastAPI service dedicated to sensor communication. Separated from the main gateway for security isolation — sensor traffic is unauthenticated by JWT (uses API keys instead).

**Port:** 8007
**Authentication:** API key in `X-Sensor-Key` header, validated against `sensors.api_key_hash`

### Endpoints

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/v1/ingest/register` | POST | API Key | Initial sensor registration + config fetch |
| `/v1/ingest/packets` | POST | API Key | Batch packet submission (replaces direct Redis publish) |
| `/v1/ingest/heartbeat` | POST | API Key | Health check + status update |
| `/v1/ingest/config` | GET | API Key | Fetch latest sensor configuration |

### Packet Batch Endpoint

```python
@app.post("/v1/ingest/packets")
async def ingest_packets(
    packets: list[dict],   # batch of up to 100 packets
    sensor: SensorContext = Depends(verify_sensor_key),  # extracts tenant_id, sensor_id
):
    """Receive a batch of packets from a sensor and publish to Redis Streams."""
    for pkt in packets[:100]:  # enforce batch limit
        payload = {
            "tenant_id": sensor.tenant_id,
            "sensor_id": sensor.sensor_id,
            "src_ip": pkt["src_ip"],
            "dst_ip": pkt["dst_ip"],
            "protocol": pkt["protocol"],
            "size": str(pkt["size"]),
            "timestamp": pkt.get("timestamp", str(time.time())),
            "trace_id": str(uuid.uuid4()),
        }
        await redis_manager.publish("stream:raw_packets", payload)
    return {"accepted": len(packets)}
```

## 4.3 Sensor Lifecycle State Machine

```
               ┌──────────┐
               │  PENDING  │ ← Sensor key generated, not yet connected
               └─────┬─────┘
                     │ POST /v1/ingest/register (valid API key)
               ┌─────▼─────┐
               │   ACTIVE   │ ← Sending packets + heartbeats
               └─────┬─────┘
                     │ No heartbeat for 5 minutes
               ┌─────▼─────┐
               │  OFFLINE   │ ← Dashboard shows ⚠️ warning
               └─────┬─────┘
                     │ Heartbeat received again
                     ├──────────────────────────┐
                     │                          │
               ┌─────▼─────┐          ┌────────▼────────┐
               │   ACTIVE   │          │    REVOKED      │ ← Admin revoked API key
               └────────────┘          └─────────────────┘
```

**Offline detection:** Background task runs every 60 seconds:
```sql
UPDATE sensors SET status = 'offline'
WHERE status = 'active'
  AND last_heartbeat < NOW() - INTERVAL '5 minutes'
```

Dashboard shows sensor status with color-coded indicator:
- 🟢 Active (heartbeat < 1 min ago)
- 🟡 Stale (heartbeat 1–5 min ago)
- 🔴 Offline (heartbeat > 5 min ago)
- ⬛ Revoked (key revoked by admin)

## 4.4 Sensor Heartbeat Protocol

Sensor sends heartbeat every 30 seconds:

```python
# In sensor Docker image
async def heartbeat_loop():
    while True:
        try:
            response = await http_client.post(
                f"{ENDPOINT}/v1/ingest/heartbeat",
                headers={"X-Sensor-Key": API_KEY},
                json={
                    "version": SENSOR_VERSION,
                    "uptime_seconds": time.time() - START_TIME,
                    "packets_captured": PACKET_COUNTER,
                    "errors": ERROR_COUNTER,
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                }
            )
            # Check for config updates or version updates
            if response.json().get("update_available"):
                await self_update(response.json()["update_url"])
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
        await asyncio.sleep(30)
```

## 4.5 Sensor Offline Handling

When the sensor cannot reach the platform (network outage, platform downtime):

1. **Local buffer:** Packets are buffered in a local SQLite database (max 100MB / ~1M packets)
2. **Exponential backoff:** Retry connection every 5s → 10s → 30s → 60s (max)
3. **Replay on reconnect:** When connection restores, drain local buffer to platform in chronological order
4. **Dashboard notification:** When sensor reconnects after offline period, user sees: "Sensor 'Office-Network' reconnected. Processing 45,000 buffered packets."

---

# PART 5 — CUSTOMER DASHBOARD UX ARCHITECTURE

## 5.1 Navigation Structure

```
┌─────────────────────────────────────────────────────────┐
│  SecureNet   [Telemetry ▼]  [🔔 3]  [avatar ▼]         │
├────────────┬────────────────────────────────────────────┤
│            │                                            │
│  📊 Overview    │  Main Content Area                    │
│  🔍 Threats     │                                      │
│  🛡️ Firewall    │                                      │
│  📡 Sensors     │  ← NEW                               │
│  📋 Playbooks   │                                      │
│  📈 Reports     │  ← NEW                               │
│  ─────────      │                                      │
│  👥 Team        │  ← NEW                               │
│  💳 Billing     │  ← NEW                               │
│  ⚙️ Settings    │                                      │
│                 │                                       │
└─────────────────┴───────────────────────────────────────┘
```

### New Frontend Routes

```jsx
// App.jsx additions
<Route path="sensors" element={<SensorsPage />} />
<Route path="reports" element={<ReportsPage />} />
<Route path="team" element={<TeamPage />} />
<Route path="billing" element={<BillingPage />} />
<Route path="onboarding" element={<OnboardingWizard />} />
```

## 5.2 RBAC-Based UI Rendering

```jsx
// New component: RBACGate.jsx
function RBACGate({ allowed, children }) {
  const { user } = useAuth();
  if (!allowed.includes(user.role)) return null;
  return children;
}

// Usage in Sidebar:
<RBACGate allowed={["owner", "admin"]}>
  <NavLink to="/app/team">👥 Team</NavLink>
</RBACGate>
<RBACGate allowed={["owner"]}>
  <NavLink to="/app/billing">💳 Billing</NavLink>
</RBACGate>
```

| Page | Owner | Admin | Analyst | Viewer |
|---|---|---|---|---|
| Overview | ✅ | ✅ | ✅ | ✅ |
| Threats | ✅ full | ✅ full | ✅ full | ✅ read-only |
| Firewall | ✅ full | ✅ full | ✅ block/unblock | ✅ read-only |
| Sensors | ✅ manage | ✅ manage | ✅ view | ✅ view |
| Reports | ✅ | ✅ | ✅ | ✅ |
| Team | ✅ manage | ✅ manage | ❌ hidden | ❌ hidden |
| Billing | ✅ | ❌ hidden | ❌ hidden | ❌ hidden |
| Settings | ✅ full | ✅ limited | ✅ profile | ✅ profile |

## 5.3 SaaS Onboarding Wizard UX

```
Step 1/4              Step 2/4              Step 3/4              Step 4/4
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Welcome    │ ──►  │  Deploy      │ ──►  │  Waiting...  │ ──►  │  Invite      │
│              │      │  Sensor      │      │              │      │  Team        │
│  "Let's set  │      │              │      │  ◉ ← pulse   │      │              │
│   up your    │      │  [Generate   │      │  "Listening  │      │  [email]     │
│   security"  │      │   API Key]   │      │   for your   │      │  [role ▼]    │
│              │      │              │      │   sensor..." │      │  [+ Invite]  │
│  [Continue →]│      │  docker run  │      │              │      │              │
│              │      │  securenet/  │      │  ✅ Connected!│      │  [Skip →]    │
│              │      │  sensor ...  │      │  [Continue →]│      │  [Finish →]  │
└──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
```

## 5.4 Sensors Management Page

```
┌──────────────────────────────────────────────────────────┐
│  📡 Sensors                          [+ Add Sensor]      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ 🟢 Office-Network                                   │ │
│  │ Status: Active · Last seen: 12s ago                 │ │
│  │ Packets: 1.2M · Version: 1.0.3                      │ │
│  │ API Key: snk_a3f8****                                │ │
│  │ [View Details] [Regenerate Key] [Revoke]            │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ 🔴 Cloud-VPC                                         │ │
│  │ Status: Offline · Last seen: 3 hours ago            │ │
│  │ Packets: 450K · Version: 1.0.2 (update available)   │ │
│  │ API Key: snk_b7e2****                                │ │
│  │ [View Details] [Regenerate Key] [Revoke]            │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## 5.5 Feature Gate UI Components

When a user on the Free plan tries to access a Pro feature:

```
┌──────────────────────────────────────────┐
│  🔒 Pro Feature                          │
│                                          │
│  Mobile Human-in-the-Loop approval       │
│  is available on the Pro plan.           │
│                                          │
│  [Upgrade to Pro — $499/mo]              │
│  [Learn More]                            │
└──────────────────────────────────────────┘
```

## 5.6 Notification Center

A bell icon in the top nav with a dropdown showing recent events:

```
┌──────────────────────────────────────────┐
│  🔔 Notifications                    ✓ all │
├──────────────────────────────────────────┤
│  🚨 Critical alert: DDoS from 10.0.1.55  │
│  2 minutes ago · [View Alert]             │
│                                           │
│  📡 Sensor "Cloud-VPC" went offline       │
│  3 hours ago · [View Sensor]              │
│                                           │
│  ✅ IP 192.168.1.100 blocked by analyst   │
│  5 hours ago · [View Details]             │
│                                           │
│  💳 Trial ends in 2 days                  │
│  Yesterday · [Upgrade]                    │
└───────────────────────────────────────────┘
```

Backend: New `notifications` table with `tenant_id`, `user_id` (nullable for tenant-wide), `type`, `message`, `data`, `read_at`, `created_at`. WebSocket delivers in real-time; API endpoint for history.
