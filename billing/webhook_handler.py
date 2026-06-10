"""
SecureNet SOC — Stripe Webhook Handler

Handles incoming Stripe webhooks for subscription lifecycle events.
Runs as part of the gateway service or as a standalone FastAPI app.

Supported Events:
- checkout.session.completed — New subscription created
- customer.subscription.updated — Plan change, renewal
- customer.subscription.deleted — Cancellation
- invoice.paid — Successful payment
- invoice.payment_failed — Payment failure
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import async_session, Tenant, Subscription, Notification
from shared.feature_gates import PLAN_LIMITS
from sqlalchemy import select

logger = logging.getLogger("securenet.billing")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Plan mapping from Stripe price IDs
STRIPE_PRICE_TO_PLAN = {
    os.getenv("STRIPE_PRICE_PRO", "price_pro"): "pro",
    os.getenv("STRIPE_PRICE_BUSINESS", "price_business"): "business",
    os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise"): "enterprise",
}

router = APIRouter(prefix="/v1/webhooks", tags=["Billing"])


def _get_stripe():
    """Lazy import stripe to avoid import errors when not configured."""
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        logger.warning("Stripe library not installed. Billing webhooks disabled.")
        return None


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle incoming Stripe webhook events."""
    stripe = _get_stripe()
    if not stripe:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        else:
            # Development mode — no signature verification
            event = json.loads(payload)
            logger.warning("Stripe webhook signature verification DISABLED (dev mode)")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signature verification failed: {e}")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info(f"Stripe webhook received: {event_type}")

    if event_type == "checkout.session.completed":
        await handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data)
    elif event_type == "invoice.paid":
        await handle_invoice_paid(data)
    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(data)
    else:
        logger.debug(f"Unhandled Stripe event: {event_type}")

    return {"status": "ok"}


async def handle_checkout_completed(data: dict):
    """New subscription created via Stripe Checkout."""
    customer_id = data.get("customer", "")
    subscription_id = data.get("subscription", "")
    tenant_id = data.get("client_reference_id", "")  # We set this when creating the session

    if not tenant_id:
        logger.error("checkout.session.completed missing client_reference_id (tenant_id)")
        return

    async with async_session() as session:
        # Update tenant
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            logger.error(f"Tenant {tenant_id} not found for checkout")
            return

        tenant.stripe_customer_id = customer_id
        tenant.stripe_subscription_id = subscription_id
        tenant.status = "active"

        # Determine plan from subscription items
        stripe = _get_stripe()
        if stripe and subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                price_id = sub["items"]["data"][0]["price"]["id"]
                plan = STRIPE_PRICE_TO_PLAN.get(price_id, "pro")
                tenant.plan = plan

                # Update limits based on plan
                limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
                tenant.max_sensors = limits["max_sensors"]
                tenant.max_users = limits["max_users"]
                tenant.max_ai_analyses_monthly = limits["max_ai_analyses_monthly"]
            except Exception as e:
                logger.error(f"Failed to fetch subscription details: {e}")
                tenant.plan = "pro"  # Default to pro

        # Create notification
        notification = Notification(
            tenant_id=tenant_id,
            type="billing",
            title="Subscription activated! 🎉",
            message=f"Your {tenant.plan.title()} plan is now active. Enjoy enhanced features!",
        )
        session.add(notification)
        await session.commit()

    logger.info(f"Checkout completed for tenant {tenant_id}: plan={tenant.plan}")


async def handle_subscription_updated(data: dict):
    """Subscription plan change or renewal."""
    customer_id = data.get("customer", "")
    subscription_id = data.get("id", "")
    status = data.get("status", "")

    async with async_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            logger.warning(f"Tenant not found for customer {customer_id}")
            return

        # Update plan if items changed
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            new_plan = STRIPE_PRICE_TO_PLAN.get(price_id)
            if new_plan and new_plan != tenant.plan:
                old_plan = tenant.plan
                tenant.plan = new_plan
                limits = PLAN_LIMITS.get(new_plan, PLAN_LIMITS["free"])
                tenant.max_sensors = limits["max_sensors"]
                tenant.max_users = limits["max_users"]
                tenant.max_ai_analyses_monthly = limits["max_ai_analyses_monthly"]

                notification = Notification(
                    tenant_id=str(tenant.id),
                    type="billing",
                    title=f"Plan changed: {old_plan.title()} → {new_plan.title()}",
                    message=f"Your subscription has been updated to the {new_plan.title()} plan.",
                )
                session.add(notification)

        tenant.stripe_subscription_id = subscription_id
        if status == "active":
            tenant.status = "active"

        await session.commit()

    logger.info(f"Subscription updated for tenant {tenant.id}")


async def handle_subscription_deleted(data: dict):
    """Subscription cancelled."""
    customer_id = data.get("customer", "")

    async with async_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return

        old_plan = tenant.plan
        tenant.plan = "free"
        tenant.status = "active"  # Downgrade to free, don't suspend
        limits = PLAN_LIMITS["free"]
        tenant.max_sensors = limits["max_sensors"]
        tenant.max_users = limits["max_users"]
        tenant.max_ai_analyses_monthly = limits["max_ai_analyses_monthly"]

        notification = Notification(
            tenant_id=str(tenant.id),
            type="billing",
            title="Subscription cancelled",
            message=f"Your {old_plan.title()} plan has been cancelled. You've been moved to the Free plan.",
        )
        session.add(notification)
        await session.commit()

    logger.info(f"Subscription cancelled for tenant {tenant.id}")


async def handle_invoice_paid(data: dict):
    """Successful payment — reset monthly usage counters."""
    customer_id = data.get("customer", "")

    async with async_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return

        tenant.ai_analyses_used = 0
        tenant.ai_analyses_reset_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

    logger.info(f"Invoice paid for tenant — usage counters reset")


async def handle_payment_failed(data: dict):
    """Payment failure — notify tenant."""
    customer_id = data.get("customer", "")

    async with async_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return

        notification = Notification(
            tenant_id=str(tenant.id),
            type="billing",
            title="⚠️ Payment failed",
            message="Your latest payment could not be processed. Please update your payment method to avoid service interruption.",
        )
        session.add(notification)
        await session.commit()

    logger.warning(f"Payment failed for tenant {tenant.id}")
