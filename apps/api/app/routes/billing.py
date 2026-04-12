"""
Billing webhook — receives Stripe events to update user plan in the database.

To wire up Stripe:
1. Set STRIPE_WEBHOOK_SECRET in your environment (from the Stripe dashboard).
2. Point your Stripe webhook to POST /billing/webhook.
3. Subscribe to at minimum: checkout.session.completed, customer.subscription.deleted.

Without STRIPE_WEBHOOK_SECRET set, the endpoint accepts any payload (dev mode).
"""
import hashlib
import hmac
import json
import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request

import app.db as _db_module
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# Map Stripe price/product IDs → internal plan names.
# Populate these with your actual Stripe IDs.
STRIPE_PLAN_MAP: dict[str, str] = {
    os.getenv("STRIPE_PRO_PRICE_ID", "price_pro"): "pro",
    os.getenv("STRIPE_TEAM_PRICE_ID", "price_team"): "team",
}


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Validate Stripe-Signature header (v1 scheme)."""
    try:
        parts = {k: v for k, v in (p.split("=", 1) for p in sig_header.split(","))}
        timestamp = int(parts["t"])
        # Reject replays older than 5 minutes
        if abs(time.time() - timestamp) > 300:
            return False
        signed = f"{timestamp}.".encode() + payload
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, parts.get("v1", ""))
    except Exception:
        return False


def _set_user_plan(email: str, plan: str) -> bool:
    """Update user.plan by email. Returns True if a row was updated."""
    # Access SessionLocal via the module so test monkeypatching takes effect.
    db: Session = _db_module.SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.warning(f"Billing webhook: no user found for email={email}")
            return False
        user.plan = plan
        db.commit()
        logger.info(f"Billing webhook: set plan={plan} for user={email}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Billing webhook: DB error updating plan for {email}: {e}", exc_info=True)
        return False
    finally:
        db.close()


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint.  Handles:
      - checkout.session.completed  → activate plan on first payment
      - customer.subscription.updated → plan change (upgrade/downgrade)
      - customer.subscription.deleted → revert to free on cancellation
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    if webhook_secret:
        if not _verify_stripe_signature(payload, sig_header, webhook_secret):
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        email = (data.get("customer_details") or {}).get("email") or data.get("customer_email")
        price_id = None
        line_items = data.get("line_items", {}).get("data", [])
        if line_items:
            price_id = (line_items[0].get("price") or {}).get("id")
        if not price_id:
            # Fallback: metadata field set in your Stripe Checkout session
            price_id = (data.get("metadata") or {}).get("price_id")
        plan = STRIPE_PLAN_MAP.get(price_id or "", "pro")
        if email:
            _set_user_plan(email, plan)

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_email = data.get("customer_email") or ""
        if event_type == "customer.subscription.deleted":
            if customer_email:
                _set_user_plan(customer_email, "free")
        else:
            # Extract price from the first subscription item
            items = data.get("items", {}).get("data", [])
            if items:
                price_id = (items[0].get("price") or {}).get("id")
                plan = STRIPE_PLAN_MAP.get(price_id or "", "pro")
                if customer_email:
                    _set_user_plan(customer_email, plan)

    else:
        # Unhandled event type — acknowledge receipt so Stripe doesn't retry
        logger.debug(f"Billing webhook: unhandled event type '{event_type}'")

    return {"received": True}
