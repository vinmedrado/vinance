from __future__ import annotations

import os
import stripe
from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/billing", tags=["billing"])
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICE_MAP = {
    "pro": os.getenv("STRIPE_PRICE_PRO", ""),
    "premium": os.getenv("STRIPE_PRICE_PREMIUM", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", os.getenv("STRIPE_PRICE_PREMIUM", "")),
}

def _update_plan(organization_id: str, plan: str, customer_id: str | None = None, subscription_id: str | None = None, status: str = "active"):
    from db.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    db.execute(text("""
        UPDATE organizations
        SET plan=:plan, subscription_status=:status, stripe_customer_id=:customer, stripe_subscription_id=:sub
        WHERE id=:organization_id
    """), {"plan": plan, "status": status, "customer": customer_id, "sub": subscription_id, "organization_id": organization_id})
    existing = db.execute(text("SELECT id FROM subscriptions WHERE organization_id=:organization_id ORDER BY id DESC LIMIT 1"), {"organization_id": organization_id}).first()
    if existing:
        db.execute(text("""
            UPDATE subscriptions SET plan=:plan, status=:status, stripe_customer_id=:customer, stripe_subscription_id=:sub, updated_at=NOW()
            WHERE id=:id
        """), {"id": existing[0], "plan": plan, "status": status, "customer": customer_id, "sub": subscription_id})
    else:
        db.execute(text("""
            INSERT INTO subscriptions (organization_id, plan, status, stripe_customer_id, stripe_subscription_id)
            VALUES (:organization_id, :plan, :status, :customer, :sub)
        """), {"organization_id": organization_id, "plan": plan, "status": status, "customer": customer_id, "sub": subscription_id})
    db.commit(); db.close()

@router.post("/create-checkout-session")
def create_checkout_session(plan: str = "pro", organization_id: str | None = None):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe não configurado")
    price = PRICE_MAP.get(plan)
    if not price:
        raise HTTPException(status_code=400, detail="Plano sem price_id configurado")
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price, "quantity": 1}],
        success_url=os.getenv("BILLING_SUCCESS_URL", "http://localhost:3000/planos?billing=success"),
        cancel_url=os.getenv("BILLING_CANCEL_URL", "http://localhost:3000/planos?billing=cancel"),
        metadata={"organization_id": organization_id or "", "plan": plan},
    )
    return {"checkout_url": session.url}

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(None)):
    payload = await request.body()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, secret) if secret else stripe.Event.construct_from(__import__("json").loads(payload), stripe.api_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if event["type"] == "checkout.session.completed":
        metadata = event["data"]["object"].get("metadata", {})
        organization_id = metadata.get("organization_id") or metadata.get("tenant_id")
        plan = metadata.get("plan", "pro")
        if organization_id:
            _update_plan(organization_id, plan, event["data"]["object"].get("customer"), event["data"]["object"].get("subscription"))
    elif event["type"] == "customer.subscription.deleted":
        customer_id = event["data"]["object"].get("customer")
        if customer_id:
            from db.database import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            org = db.execute(text("SELECT id FROM organizations WHERE stripe_customer_id=:customer"), {"customer": customer_id}).mappings().first()
            if org:
                _update_plan(str(org["id"]), "free", customer_id, None, status="canceled")
            db.close()
    return {"received": True, "type": event["type"]}

@router.get("/portal")
def billing_portal(customer_id: str):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe não configurado")
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=os.getenv("BILLING_PORTAL_RETURN_URL", "http://localhost:3000/planos"))
    return {"portal_url": session.url}
