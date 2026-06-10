-- SecureNet SOC — PostgreSQL Schema (Initial Migration)
-- Run: psql -U securenet -d securenet -f migrations/001_initial.sql

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ===================================================================
-- Users and authentication
-- ===================================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'viewer'
                    CHECK (role IN ('admin', 'analyst', 'viewer')),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_login      TIMESTAMPTZ
);

-- ===================================================================
-- Threat alerts (permanent audit log)
-- ===================================================================
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    src_ip          VARCHAR(45) NOT NULL,
    attack_type     VARCHAR(100),
    severity        VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    confidence      FLOAT,
    explanation     TEXT,
    recommendation  TEXT,
    raw_features    JSONB NOT NULL DEFAULT '{}',
    llm_response    JSONB,
    status          VARCHAR(20) DEFAULT 'new'
                    CHECK (status IN ('new', 'investigating', 'resolved', 'false_positive')),
    analyst_notes   TEXT,
    resolved_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

-- ===================================================================
-- Blocked IPs with audit trail
-- ===================================================================
CREATE TABLE IF NOT EXISTS blocked_ips (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address      VARCHAR(45) UNIQUE NOT NULL,
    reason          TEXT,
    blocked_by      VARCHAR(100) DEFAULT 'system',
    alert_id        UUID REFERENCES alerts(id),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    unblocked_at    TIMESTAMPTZ
);

-- ===================================================================
-- ML prediction log (for model performance monitoring)
-- ===================================================================
CREATE TABLE IF NOT EXISTS ml_predictions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    src_ip          VARCHAR(45) NOT NULL,
    features        JSONB NOT NULL,
    prediction      VARCHAR(20) NOT NULL,
    confidence      FLOAT,
    model_version   VARCHAR(50),
    latency_ms      FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ===================================================================
-- System audit log
-- ===================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor           VARCHAR(255),
    action          VARCHAR(100) NOT NULL,
    resource_type   VARCHAR(50),
    resource_id     VARCHAR(255),
    details         JSONB,
    ip_address      VARCHAR(45),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ===================================================================
-- Decision audit log (Human-in-the-Loop decisions)
-- ===================================================================
CREATE TABLE IF NOT EXISTS decision_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id        VARCHAR(36) UNIQUE NOT NULL,
    action          VARCHAR(20) NOT NULL
                    CHECK (action IN ('BLOCK', 'ALLOW', 'ESCALATE')),
    source          VARCHAR(50) NOT NULL,
    trace_id        VARCHAR(36) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ===================================================================
-- Performance indexes
-- ===================================================================
CREATE INDEX IF NOT EXISTS idx_alerts_src_ip ON alerts(src_ip);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_blocked_ips_active ON blocked_ips(ip_address) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_ml_predictions_created ON ml_predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_logs_alert ON decision_logs(alert_id);
CREATE INDEX IF NOT EXISTS idx_decision_logs_trace ON decision_logs(trace_id);

-- ===================================================================
-- Admin user creation
-- ===================================================================
-- DO NOT seed credentials here. Use the CLI tool instead:
--   python manage.py create-admin --email admin@securenet.local --password <strong-password>
-- This ensures passwords are never committed to version control.
