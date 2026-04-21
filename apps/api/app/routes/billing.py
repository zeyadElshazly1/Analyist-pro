"""
Billing routes — Stripe Checkout session creation and webhook handling.

Environment variables required for Stripe integration:
  STRIPE_SECRET_KEY             — your Stripe secret key (sk_live_... or sk_test_...)
  STRIPE_WEBHOOK_SECRET         — from the Stripe dashboard after registering the webhook
  STRIPE_CONSULTANT_PRICE_ID    — Stripe Price ID for the Consultant plan
  STRIPE_STUDIO_PRICE_ID        — Stripe Price ID for the Studio plan
  STRIPE_SUCCESS_URL            — URL to redirect to after successful checkout
  STRIPE_CANCEL_URL             — URL to redirect to when checkout is abandoned

Legacy aliases (kept until env vars are renamed in deployment):
  STRIPE_PRO_PRICE_ID   → falls back to STRIPE_CONSULTANT_PRICE_ID if not set
  STRIPE_TEAM_PRICE_ID  → falls back to STRIPE_STUDIO_PRICE_ID if not set

Without STRIPE_SECRET_KEY the checkout endpoint returns a 503 with a clear message
so the rest of the app continues to work during development.
"""
import hashlib
import hmac
import json
import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

import app.db as _db_module
from app.middleware.auth import get_current_user
from app.models import User
from app.plan_names import PLAN_CONSULTANT, PLAN_FREE, PLAN_STUDIO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# Map Stripe price/product IDs → internal plan names.
# Populate these with your actual Stripe IDs.
STRIPE_PLAN_MAP: dict[str, str] = {
    os.getenv("STRIPE_CONSULTANT_PRICE_ID", os.getenv("STRIPE_PRO_PRICE_ID", "price_consultant")): PLAN_CONSULTANT,
    os.getenv("STRIPE_STUDIO_PRICE_ID", os.getenv("STRIPE_TEAM_PRICE_ID", "price_studio")): PLAN_STUDIO,
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
        plan = STRIPE_PLAN_MAP.get(price_id or "", PLAN_CONSULTANT)
        if email:
            _set_user_plan(email, plan)

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_email = data.get("customer_email") or ""
        if event_type == "customer.subscription.deleted":
            if customer_email:
                _set_user_plan(customer_email, PLAN_FREE)
        else:
            # Extract price from the first subscription item
            items = data.get("items", {}).get("data", [])
            if items:
                price_id = (items[0].get("price") or {}).get("id")
                plan = STRIPE_PLAN_MAP.get(price_id or "", PLAN_CONSULTANT)
                if customer_email:
                    _set_user_plan(customer_email, plan)

    else:
        # Unhandled event type — acknowledge receipt so Stripe doesn't retry
        logger.debug(f"Billing webhook: unhandled event type '{event_type}'")

    return {"received": True}


# ── Checkout session creation ─────────────────────────────────────────────────

# Plans available for checkout — free has no Stripe price.
# This is the single authoritative set; both the schema validator and
# the price map are derived from it.
CHECKOUT_PLANS: frozenset[str] = frozenset({PLAN_CONSULTANT, PLAN_STUDIO})

_PLAN_PRICE_MAP: dict[str, str] = {
    PLAN_CONSULTANT: os.getenv("STRIPE_CONSULTANT_PRICE_ID", os.getenv("STRIPE_PRO_PRICE_ID", "")),
    PLAN_STUDIO:     os.getenv("STRIPE_STUDIO_PRICE_ID", os.getenv("STRIPE_TEAM_PRICE_ID", "")),
}

_DEFAULT_SUCCESS_URL = os.getenv(
    "STRIPE_SUCCESS_URL",
    "http://localhost:3000/billing?checkout=success",
)
_DEFAULT_CANCEL_URL = os.getenv(
    "STRIPE_CANCEL_URL",
    "http://localhost:3000/billing?checkout=cancelled",
)


class CheckoutRequest(BaseModel):
    plan: str

    @field_validator("plan")
    @classmethod
    def plan_must_be_checkout_plan(cls, v: str) -> str:
        if v not in CHECKOUT_PLANS:
            raise ValueError(
                f"plan must be one of: {', '.join(sorted(CHECKOUT_PLANS))}"
            )
        return v


@router.post("/create-checkout-session")
def create_checkout_session(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for the requested plan and return the URL.
    The frontend redirects the user to this URL to complete payment.

    Requires STRIPE_SECRET_KEY and the relevant STRIPE_*_PRICE_ID env vars.
    """
    secret_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not secret_key:
        raise HTTPException(
            status_code=503,
            detail="Payment integration is not yet configured. Please contact support.",
        )

    price_id = _PLAN_PRICE_MAP.get(body.plan, "")
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe price ID for plan '{body.plan}' is not configured. Contact support.",
        )

    try:
        import stripe  # type: ignore[import]
        stripe.api_key = secret_key

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=current_user.email,
            client_reference_id=current_user.id,
            metadata={"price_id": price_id, "plan": body.plan},
            success_url=_DEFAULT_SUCCESS_URL + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=_DEFAULT_CANCEL_URL,
        )
        return {"checkout_url": session.url}

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="stripe library is not installed. Add stripe to requirements.txt.",
        )
    except Exception as e:
        logger.error(f"Stripe checkout session creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create checkout session.")
