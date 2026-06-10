"""
Feature gates for SecureNet SOC SaaS plans.

Controls access to features based on tenant subscription plan.
Provides both FastAPI dependency injection and direct utility functions.
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException

from shared.middleware import get_current_tenant
from shared.database import async_session, Tenant
from sqlalchemy import select

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan limits configuration
# ---------------------------------------------------------------------------

PLAN_LIMITS = {
    "free": {
        "max_sensors": 1,
        "max_users": 1,
        "max_ai_analyses_monthly": 50,
        "max_alert_retention_days": 7,
        "custom_playbooks": False,
        "siem_export": False,
        "api_access": False,
        "priority_support": False,
        "custom_ml_models": False,
        "sso": False,
        "mssp": False,
    },
    "pro": {
        "max_sensors": 5,
        "max_users": 5,
        "max_ai_analyses_monthly": 500,
        "max_alert_retention_days": 30,
        "custom_playbooks": True,
        "siem_export": False,
        "api_access": True,
        "priority_support": False,
        "custom_ml_models": False,
        "sso": False,
        "mssp": False,
    },
    "business": {
        "max_sensors": 25,
        "max_users": 25,
        "max_ai_analyses_monthly": 5000,
        "max_alert_retention_days": 90,
        "custom_playbooks": True,
        "siem_export": True,
        "api_access": True,
        "priority_support": True,
        "custom_ml_models": False,
        "sso": False,
        "mssp": False,
    },
    "enterprise": {
        "max_sensors": -1,  # unlimited
        "max_users": -1,
        "max_ai_analyses_monthly": -1,
        "max_alert_retention_days": 365,
        "custom_playbooks": True,
        "siem_export": True,
        "api_access": True,
        "priority_support": True,
        "custom_ml_models": True,
        "sso": True,
        "mssp": True,
    },
}


def get_plan_limit(plan: str, feature: str):
    """Get a specific limit for a plan."""
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    return limits.get(feature, None)


async def get_tenant_plan(tenant_id: str) -> str:
    """Fetch the current plan for a tenant from the database."""
    async with async_session() as session:
        result = await session.execute(
            select(Tenant.plan).where(Tenant.id == tenant_id)
        )
        plan = result.scalar_one_or_none()
        return plan or "free"


# ---------------------------------------------------------------------------
# FastAPI dependency factories
# ---------------------------------------------------------------------------

def require_feature(feature_name: str):
    """
    FastAPI dependency factory that checks if the tenant's plan includes a feature.

    Usage:
        @app.post("/api/playbooks")
        async def create_playbook(
            _gate = Depends(require_feature("custom_playbooks")),
            tenant_id: str = Depends(get_current_tenant),
        ):
            ...
    """
    async def _check_feature(
        tenant_id: str = Depends(get_current_tenant),
    ):
        plan = await get_tenant_plan(tenant_id)
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        
        if feature_name not in limits:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown feature: {feature_name}"
            )
        
        if not limits[feature_name]:
            raise HTTPException(
                status_code=403,
                detail=f"Feature '{feature_name}' requires a higher plan. Current plan: {plan}",
                headers={"X-Upgrade-Required": "true"},
            )
        return True

    return _check_feature


async def check_tenant_limit(
    tenant_id: str,
    limit_type: str,
    current_count: int,
) -> bool:
    """
    Check if a tenant has reached their plan limit for a specific resource.

    Args:
        tenant_id: The tenant UUID.
        limit_type: One of 'max_sensors', 'max_users', 'max_ai_analyses_monthly'.
        current_count: The current count of the resource.

    Returns:
        True if within limits, False if limit exceeded.

    Raises HTTPException 403 if limit exceeded.
    """
    plan = await get_tenant_plan(tenant_id)
    limit = get_plan_limit(plan, limit_type)
    
    if limit == -1:  # unlimited
        return True
    
    if current_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Plan limit reached: {limit_type}={limit} on '{plan}' plan. Upgrade to add more.",
            headers={"X-Upgrade-Required": "true"},
        )
    
    return True
