# SecureNet SOC — Architecture Overview

## System Architecture

```mermaid
graph TB
    subgraph "Data Ingestion"
        SNIFFER["🔍 Sniffer<br/>(scapy)"]
        EXTRACTOR["⚙️ Extractor<br/>(Feature Engineering)"]
    end

    subgraph "Intelligence Pipeline"
        ML["🧠 ML Engine<br/>(scikit-learn)"]
        LLM["🤖 LLM Analyzer<br/>(GPT-4o-mini)"]
    end

    subgraph "Decision & Control"
        DE["⚡ Decision Engine"]
        TL["⏰ Timeout Listener"]
        FS["🔄 Fallback Scanner"]
        LW["📝 Log Writer"]
        FW["🛡️ Firewall"]
    end

    subgraph "API Surface"
        GW["🌐 API Gateway<br/>(Dashboard)"]
        MG["📱 Mobile Gateway<br/>(REST + WS)"]
    end

    subgraph "Frontend"
        DASH["💻 React Dashboard"]
        APP["📱 Mobile App"]
    end

    subgraph "Infrastructure"
        REDIS[("Redis 7<br/>Streams + Cache")]
        PG[("PostgreSQL 16<br/>Persistence")]
        PROM["📊 Prometheus"]
        GRAF["📈 Grafana"]
    end

    SNIFFER -->|stream:packets| REDIS
    REDIS -->|stream:packets| EXTRACTOR
    EXTRACTOR -->|stream:features| REDIS
    REDIS -->|stream:features| ML
    ML -->|stream:alerts| REDIS
    REDIS -->|stream:alerts| LLM
    LLM -->|stream:decisions_pending| REDIS
    LLM -->|INSERT alert| PG
    REDIS -->|stream:decisions_pending| DE
    DE -->|route by severity| REDIS
    DE -->|high/critical → mobile| MG
    DE -->|low/medium → auto-block| FW
    TL -->|expired TTL → auto-block| FW
    FS -->|orphaned decisions| FW
    LW -->|INSERT decision_log| PG
    FW -->|block IP| REDIS
    FW -->|INSERT blocked_ip| PG
    GW <-->|WebSocket| DASH
    MG <-->|WebSocket + REST| APP
    GW -->|query| PG
    MG -->|query| PG
    PROM -->|scrape /metrics| GW
    PROM -->|scrape /metrics| MG
    PROM -->|scrape /metrics| ML
    PROM -->|scrape /metrics| LLM
    GRAF -->|query| PROM
```

## Data Flow

### 1. Packet Ingestion
Raw network packets → scapy capture → Redis Stream `stream:packets`

### 2. Feature Engineering
Packets → rolling window statistics (30s) → 11 features → Redis Stream `stream:features`

### 3. ML Inference
Features → scikit-learn Random Forest → benign/malicious classification
- Predictions logged to PostgreSQL `ml_predictions` table
- Feature drift detection via KL divergence
- Alert cooldown prevents duplicate LLM calls

### 4. LLM Classification
Malicious alerts → GPT-4o-mini (or heuristic fallback) → attack type + severity
- Cache → LLM → Heuristic Fallback chain
- Response validated with Pydantic schema
- Results persisted to PostgreSQL `alerts` table

### 5. Decision Routing
```
Critical/High → Mobile dispatch → SOC analyst decision → APPROVE/REJECT/ESCALATE
Medium/Low → Auto-block → Firewall → iptables + PostgreSQL
Timeout (60s) → Auto-block fallback
```

### 6. Observability
All services expose `/metrics` (Prometheus) → 3 Grafana dashboards → 21 alert rules → Alertmanager

## Communication Patterns

| Pattern | Technology | Use Case |
|---|---|---|
| **Event streaming** | Redis Streams | Inter-service pipeline (packets → features → alerts) |
| **Consumer groups** | Redis XREADGROUP | Exactly-once processing with ACK |
| **Pub/Sub** | Redis XADD | Dashboard WebSocket broadcast |
| **Request/Response** | HTTP REST | API Gateway ↔ clients |
| **Bidirectional** | WebSocket | Real-time dashboard + mobile |
| **Atomic operations** | Redis Lua scripts | Decision execution (idempotent) |

## Security Architecture

```
┌─────────────────────────────────────────────┐
│                  Traefik                     │
│        TLS Termination + HSTS               │
│       Let's Encrypt auto-renewal            │
├─────────────────────────────────────────────┤
│              Security Headers               │
│  X-Frame-Options │ X-Content-Type │ CSP     │
├─────────────────────────────────────────────┤
│             Rate Limiting                   │
│   Gateway: 120/60s │ Mobile Auth: 5/60s     │
├─────────────────────────────────────────────┤
│       JWT Authentication (jti claims)       │
│  Access Token (1h) + Refresh Token (7d)     │
│  Token Blacklisting (Redis) on logout       │
│  Refresh Token Rotation (one-time use)      │
├─────────────────────────────────────────────┤
│          Account Lockout                    │
│  5 failed attempts → 15 min lockout         │
│  Constant-time comparison (timing attack)   │
├─────────────────────────────────────────────┤
│         Input Validation (Pydantic)         │
│  IP validation │ Size limits │ SQL defense   │
├─────────────────────────────────────────────┤
│            Audit Trail                      │
│  PostgreSQL audit_log table                 │
│  Login/logout/block/decision events         │
└─────────────────────────────────────────────┘
```
