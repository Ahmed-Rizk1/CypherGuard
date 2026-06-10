"""
Standardized API response envelope for SecureNet SOC.

Provides consistent response formatting across all gateway services,
including cursor-based pagination metadata.

Usage:
    from shared.responses import success_response, error_response, paginated_response

    # Simple success
    return success_response(data={"user": user_dict})

    # Paginated list
    return paginated_response(
        data=[alert_to_dict(a) for a in alerts],
        cursor=last_alert.created_at.isoformat() if alerts else None,
        per_page=20,
        has_next=True,
    )

    # Error
    return error_response(code="RESOURCE_NOT_FOUND", message="Alert not found", status_code=404)
"""

from typing import Any, Optional
from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    message: str = "OK",
    status_code: int = 200,
) -> JSONResponse:
    """Wrap a successful response in the standard envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "message": message,
        },
    )


def paginated_response(
    data: list,
    cursor: Optional[str] = None,
    per_page: int = 20,
    has_next: bool = False,
    total: Optional[int] = None,
    status_code: int = 200,
) -> JSONResponse:
    """Wrap a paginated list response with cursor metadata."""
    meta = {
        "per_page": per_page,
        "has_next": has_next,
        "cursor": cursor,
    }
    if total is not None:
        meta["total"] = total

    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "meta": meta,
        },
    )


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: Any = None,
) -> JSONResponse:
    """Wrap an error response in the standard envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
        },
    )


# ---------------------------------------------------------------------------
# ORM to dict helpers
# ---------------------------------------------------------------------------

def alert_to_dict(alert) -> dict:
    """Convert an Alert ORM object to a clean API dict."""
    return {
        "id": str(alert.id),
        "src_ip": alert.src_ip,
        "attack_type": alert.attack_type,
        "severity": alert.severity,
        "confidence": alert.confidence,
        "explanation": alert.explanation,
        "recommendation": alert.recommendation,
        "status": alert.status,
        "analyst_notes": alert.analyst_notes,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolved_by": str(alert.resolved_by) if alert.resolved_by else None,
    }


def blocked_ip_to_dict(ip) -> dict:
    """Convert a BlockedIP ORM object to a clean API dict."""
    return {
        "id": str(ip.id),
        "ip_address": ip.ip_address,
        "reason": ip.reason,
        "blocked_by": ip.blocked_by,
        "is_active": ip.is_active,
        "created_at": ip.created_at.isoformat() if ip.created_at else None,
        "expires_at": ip.expires_at.isoformat() if ip.expires_at else None,
        "unblocked_at": ip.unblocked_at.isoformat() if ip.unblocked_at else None,
    }


def decision_to_dict(log) -> dict:
    """Convert a DecisionLog ORM object to a clean API dict."""
    return {
        "id": str(log.id),
        "alert_id": log.alert_id,
        "action": log.action,
        "source": log.source,
        "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def user_to_dict(user) -> dict:
    """Convert a User ORM object to a safe API dict (no password hash)."""
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": getattr(user, "full_name", None),
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "is_active": user.is_active,
        "is_email_verified": getattr(user, "is_email_verified", True),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def tenant_to_dict(tenant) -> dict:
    """Convert a Tenant ORM object to an API dict."""
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "status": tenant.status,
        "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        "max_sensors": tenant.max_sensors,
        "max_users": tenant.max_users,
        "max_ai_analyses_monthly": tenant.max_ai_analyses_monthly,
        "ai_analyses_used": tenant.ai_analyses_used,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
    }


def sensor_to_dict(sensor) -> dict:
    """Convert a Sensor ORM object to an API dict."""
    return {
        "id": str(sensor.id),
        "name": sensor.name,
        "api_key_prefix": sensor.api_key_prefix,
        "status": sensor.status,
        "last_heartbeat": sensor.last_heartbeat.isoformat() if sensor.last_heartbeat else None,
        "last_ip": sensor.last_ip,
        "version": sensor.version,
        "created_at": sensor.created_at.isoformat() if sensor.created_at else None,
    }


def notification_to_dict(notification) -> dict:
    """Convert a Notification ORM object to an API dict."""
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "data": notification.data,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }
