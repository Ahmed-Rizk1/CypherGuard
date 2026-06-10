# SecureNet SOC — Database Schema

## Entity Relationship Diagram

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK
        string password_hash
        string role
        boolean is_active
        datetime created_at
        datetime last_login
    }

    alerts {
        uuid id PK
        string src_ip
        string attack_type
        string severity
        float confidence
        text explanation
        text recommendation
        string status
        text analyst_notes
        jsonb raw_features
        jsonb llm_response
        datetime created_at
        datetime resolved_at
        string resolved_by
    }

    blocked_ips {
        uuid id PK
        string ip_address
        string reason
        string blocked_by
        boolean is_active
        datetime created_at
        datetime expires_at
        datetime unblocked_at
    }

    decision_logs {
        uuid id PK
        string alert_id
        string action
        string source
        string user_id
        string trace_id
        datetime created_at
    }

    ml_predictions {
        uuid id PK
        string src_ip
        jsonb features
        string prediction
        float confidence
        string model_version
        float latency_ms
        datetime created_at
    }

    audit_log {
        uuid id PK
        string actor
        string action
        string resource_type
        string resource_id
        jsonb details
        string ip_address
        datetime created_at
    }

    model_registry {
        uuid id PK
        string version UK
        string algorithm
        float accuracy
        float f1_score
        jsonb feature_columns
        int training_samples
        string file_hash
        boolean is_active
        datetime created_at
        datetime activated_at
    }

    users ||--o{ decision_logs : "makes decisions"
    alerts ||--o| decision_logs : "has decision"
    alerts }o--|| users : "resolved_by"
    users ||--o{ audit_log : "actor"
```

## Table Details

### `users`
Stores SOC analyst accounts. Passwords are bcrypt-hashed. Roles: `admin`, `analyst`, `viewer`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Generated server-side |
| `email` | VARCHAR(255) | Unique, used for login |
| `password_hash` | TEXT | bcrypt hash |
| `role` | VARCHAR(20) | `admin` / `analyst` / `viewer` |
| `is_active` | BOOLEAN | Soft delete support |
| `last_login` | TIMESTAMP | Updated on each login |

### `alerts`
Permanent threat log. Every ML-flagged + LLM-classified alert is persisted here.

| Column | Type | Notes |
|---|---|---|
| `status` | VARCHAR(20) | `new` → `acknowledged` → `resolved` → `false_positive` |
| `raw_features` | JSONB | Original extractor features for reproducibility |
| `llm_response` | JSONB | Complete LLM output (attack_type, severity, etc.) |
| `analyst_notes` | TEXT | Free-form notes from SOC analyst |

**Indexes:** `(created_at DESC, id DESC)` for cursor pagination, `severity` for filtered queries.

### `ml_predictions`
Every ML inference is logged for model performance tracking and drift analysis.

| Column | Type | Notes |
|---|---|---|
| `features` | JSONB | Input features at inference time |
| `latency_ms` | FLOAT | Inference wall-clock time |
| `model_version` | VARCHAR | Maps to `model_registry.version` |

### `audit_log`
Compliance-grade event log for forensic investigation.

| Action | Actor | Resource |
|---|---|---|
| `auth.login` | user email | session ID |
| `auth.mobile_login` | user email | session ID |
| `auth.logout` | user email | token JTI |
| `firewall.block` | user email or `system` | IP address |
| `firewall.unblock` | user email | IP address |
| `alert.update` | user email | alert ID |

### `model_registry`
Tracks deployed ML models for versioning and hot-reload verification.

| Column | Type | Notes |
|---|---|---|
| `file_hash` | VARCHAR(64) | SHA256 of model file |
| `is_active` | BOOLEAN | Only one model active at a time |
| `feature_columns` | JSONB | Feature list for schema validation |

## Migrations

Managed by Alembic with async PostgreSQL support:

```bash
# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

### Migration History

| Revision | Description |
|---|---|
| `2e7b90c40679` | Initial schema (users, alerts, blocked_ips, decision_logs, ml_predictions, audit_log) |
| `a1b2c3d4e5f6` | Phase 3: Composite indexes, model_registry table, decision_logs.user_id |
