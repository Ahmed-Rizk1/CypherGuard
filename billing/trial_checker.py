"""
SecureNet SOC — Trial Checker

Periodic background task that checks for expired trials and
downgrades tenants to the free plan.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import async_session, Tenant, Notification
from shared.feature_gates import PLAN_LIMITS
from shared.email import send_trial_expiring_email
from shared.database import User

logger = logging.getLogger("securenet.trial_checker")

CHECK_INTERVAL = int(os.getenv("TRIAL_CHECK_INTERVAL", "3600"))  # Check every hour


async def check_expiring_trials():
    """Send warning emails for trials expiring in 3 days or 1 day."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session() as session:
        result = await session.execute(
            select(Tenant).where(
                Tenant.status == "trial",
                Tenant.trial_ends_at != None,
            )
        )
        tenants = list(result.scalars().all())

        for tenant in tenants:
            if not tenant.trial_ends_at:
                continue

            days_remaining = (tenant.trial_ends_at - now).days

            if days_remaining in [3, 1]:
                # Get owner email
                owner_q = await session.execute(
                    select(User).where(User.id == tenant.owner_id)
                )
                owner = owner_q.scalar_one_or_none()
                if owner:
                    await send_trial_expiring_email(
                        owner.email, tenant.name, days_remaining
                    )
                    logger.info(f"Trial warning sent to {owner.email} ({days_remaining} days)")


async def expire_trials():
    """Downgrade expired trials to the free plan."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session() as session:
        result = await session.execute(
            select(Tenant).where(
                Tenant.status == "trial",
                Tenant.trial_ends_at != None,
                Tenant.trial_ends_at < now,
            )
        )
        expired_tenants = list(result.scalars().all())

        for tenant in expired_tenants:
            old_plan = tenant.plan
            tenant.plan = "free"
            tenant.status = "active"  # Downgrade, not suspend
            limits = PLAN_LIMITS["free"]
            tenant.max_sensors = limits["max_sensors"]
            tenant.max_users = limits["max_users"]
            tenant.max_ai_analyses_monthly = limits["max_ai_analyses_monthly"]

            notification = Notification(
                tenant_id=str(tenant.id),
                type="billing",
                title="Trial period ended",
                message=(
                    "Your free trial has expired. You've been moved to the Free plan. "
                    "Upgrade anytime to unlock full features."
                ),
            )
            session.add(notification)
            logger.info(f"Trial expired for tenant {tenant.id} — downgraded to free")

        if expired_tenants:
            await session.commit()
            logger.info(f"Expired {len(expired_tenants)} trial(s)")


async def main():
    from shared.redis_client import redis_manager
    await redis_manager.connect()

    logger.info(f"Trial Checker started (interval: {CHECK_INTERVAL}s)")

    while True:
        try:
            await check_expiring_trials()
            await expire_trials()
        except Exception as e:
            logger.error(f"Trial checker error: {e}", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
