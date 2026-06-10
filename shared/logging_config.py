"""
Structured JSON logging for all SecureNet SOC services.

Provides:
- JSON-formatted log output with timestamp, level, service, trace_id, tenant_id
- Context variables for trace_id and tenant_id (propagated across async calls)
- Utility functions to get/set context values

Usage:
    from shared.logging_config import setup_logging, set_tenant_context
    logger = setup_logging("my_service")
    set_tenant_context("tenant-uuid")
    logger.info("Something happened", extra={"src_ip": "1.2.3.4"})

Output:
    {"timestamp":"2026-04-22T19:00:00+00:00","level":"INFO","service":"my_service","tenant_id":"tenant-uuid","message":"Something happened","src_ip":"1.2.3.4"}
"""

import logging
import sys
import contextvars
import uuid
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger

# Context variables to hold trace and tenant IDs across async calls
trace_id_ctx = contextvars.ContextVar("trace_id", default=None)
tenant_id_ctx = contextvars.ContextVar("tenant_id", default=None)

def get_trace_id() -> str:
    """Get current trace_id or generate a new one if missing."""
    tid = trace_id_ctx.get()
    if not tid:
        tid = str(uuid.uuid4())
        trace_id_ctx.set(tid)
    return tid


def set_tenant_context(tenant_id: str) -> None:
    """Set the tenant_id context variable for the current async task."""
    tenant_id_ctx.set(tenant_id or None)


def get_tenant_context() -> str:
    """Get the current tenant_id context variable."""
    return tenant_id_ctx.get() or ""


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter using python-json-logger."""
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname


class ServiceFilter(logging.Filter):
    """Injects the service name, trace_id, and tenant_id into every log record."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service_name
        record.trace_id = trace_id_ctx.get()
        record.tenant_id = tenant_id_ctx.get() or ""
        return True


def setup_logging(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    Configure the root logger with JSON formatting and return a named logger.

    Uses a logging.Filter (scoped to handler) instead of replacing the global
    LogRecordFactory, which is safer when multiple modules call setup_logging.

    Call once at service startup:
        logger = setup_logging("extractor")

    Args:
        service_name: Identifier injected into every log record.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        A configured logging.Logger instance.
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(service)s %(trace_id)s %(tenant_id)s %(message)s %(module)s %(funcName)s %(lineno)d'
    )
    handler.setFormatter(formatter)
    handler.addFilter(ServiceFilter(service_name))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet down noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger(service_name)

