"""
Prometheus metrics for SecureNet SOC services.

Defines counters, histograms, and gauges that every service can
increment/observe. Metrics are exposed via a /metrics endpoint.

Usage:
    from shared.metrics import (
        PACKETS_PROCESSED, PREDICTIONS_TOTAL, PREDICTION_LATENCY,
        metrics_endpoint
    )

    # Increment counters
    PACKETS_PROCESSED.labels(service="extractor", status="success").inc()

    # Observe latency
    PREDICTION_LATENCY.labels(model_version="20260422").observe(0.005)

    # Mount endpoint
    app.add_route("/metrics", metrics_endpoint)
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

PACKETS_PROCESSED = Counter(
    "securenet_packets_processed_total",
    "Total packets processed by the pipeline",
    ["service", "status"],  # status: success, error, dropped
)

PREDICTIONS_TOTAL = Counter(
    "securenet_predictions_total",
    "Total ML predictions performed",
    ["result", "model_version"],  # result: benign, malicious
)

ALERTS_GENERATED = Counter(
    "securenet_alerts_total",
    "Total threat alerts generated",
    ["attack_type", "severity"],
)

LLM_CALLS = Counter(
    "securenet_llm_calls_total",
    "Total LLM API calls (including cache hits and fallbacks)",
    ["status"],  # status: success, failure, cache_hit, circuit_open, fallback
)

FIREWALL_BLOCKS = Counter(
    "securenet_firewall_blocks_total",
    "Total IPs blocked by the firewall",
    ["source"],  # source: automated, manual
)

AUTH_EVENTS = Counter(
    "securenet_auth_events_total",
    "Authentication events",
    ["event"],  # event: login_success, login_failure, token_expired
)

SYSTEM_DROPPED_MESSAGES = Counter(
    "securenet_system_dropped_messages_total",
    "Total messages dropped due to chaos testing or backpressure",
    ["service", "reason"], # reason: chaos_drop, full_queue, malformed
)

RATE_LIMIT_TRIGGERS = Counter(
    "securenet_rate_limit_triggers_total",
    "Total requests rejected by rate limiter",
    ["endpoint"],
)

MOBILE_ALERTS_SENT = Counter(
    "securenet_mobile_alerts_sent_total",
    "Total alerts routed to the mobile gateway",
    ["severity"],
)

MOBILE_ACTIONS_RECEIVED = Counter(
    "securenet_mobile_actions_received_total",
    "Total decisions received from mobile users",
    ["action"], # APPROVE, REJECT, ESCALATE
)

MOBILE_TIMEOUT_FALLBACKS = Counter(
    "securenet_mobile_timeout_fallbacks_total",
    "Total mobile alerts that timed out and fell back to auto-execute",
    [],
)

DECISIONS_TOTAL = Counter(
    "securenet_decisions_total",
    "Total decisions processed (auto + mobile)",
    ["severity"],
)

DECISIONS_EXECUTED = Counter(
    "securenet_decisions_executed_total",
    "Total decisions actually logged to PostgreSQL and executed",
    ["source"], # mobile, timeout, auto
)

SCANNER_PROCESSED_ITEMS = Counter(
    "securenet_scanner_processed_items_total",
    "Total expired decisions caught and processed by the fallback scanner",
    [],
)

# ---------------------------------------------------------------------------
# Histograms (latency distributions)
# ---------------------------------------------------------------------------

PREDICTION_LATENCY = Histogram(
    "securenet_prediction_duration_seconds",
    "ML prediction latency in seconds",
    ["model_version"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

LLM_LATENCY = Histogram(
    "securenet_llm_duration_seconds",
    "LLM API call latency in seconds",
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0],
)

REQUEST_LATENCY = Histogram(
    "securenet_request_duration_seconds",
    "HTTP request latency for the API gateway",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

MOBILE_DECISION_LATENCY = Histogram(
    "securenet_mobile_decision_duration_seconds",
    "Latency between sending to mobile and receiving decision",
    buckets=[1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0],
)

DECISION_DB_WRITE_LATENCY = Histogram(
    "securenet_decision_db_write_duration_seconds",
    "Latency for batch inserts of decision logs to PostgreSQL",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

# ---------------------------------------------------------------------------
# Gauges (current values)
# ---------------------------------------------------------------------------

ACTIVE_CONNECTIONS = Gauge(
    "securenet_active_connections",
    "Current number of tracked IP connections",
)

DECISION_QUEUE_SIZE = Gauge(
    "securenet_decision_queue_size",
    "Current number of pending database writes in the decision log queue",
)

BLOCKED_IPS_COUNT = Gauge(
    "securenet_blocked_ips_count",
    "Current number of IPs in the active blocklist",
)

QUEUE_DEPTH = Gauge(
    "securenet_queue_depth",
    "Current Redis stream depth",
    ["stream"],  # stream: raw_packets, features, alerts, block_commands
)

STREAM_LAG = Gauge(
    "securenet_stream_lag",
    "Number of messages pending for a consumer group",
    ["stream", "group"],
)

WEBSOCKET_CONNECTIONS = Gauge(
    "securenet_websocket_connections",
    "Current number of active WebSocket connections from dashboards",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "securenet_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["name"],
)

# AI Enhancement: Live model monitoring gauges
MODEL_ACCURACY_RECENT = Gauge(
    "securenet_model_accuracy_recent",
    "Estimated accuracy of the ML model over recent predictions",
)

MODEL_F1_RECENT = Gauge(
    "securenet_model_f1_recent",
    "Estimated F1 score of the ML model over recent predictions",
)

MODEL_LATENCY_P95 = Gauge(
    "securenet_model_latency_p95",
    "95th percentile latency of the ML model in milliseconds",
)

PREDICTION_DRIFT_SCORE = Gauge(
    "securenet_prediction_drift_score",
    "Maximum prediction drift score (KL divergence) across features",
)


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------

async def metrics_endpoint() -> Response:
    """
    FastAPI route handler for Prometheus scraping.

    Mount with:
        app.add_route("/metrics", metrics_endpoint)
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
