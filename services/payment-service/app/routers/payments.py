import os
import uuid

import httpx
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.messaging import publish_payment_event
from app.models import Payment, PaymentStatus
from app.schemas import PaymentCreate, PaymentRead
from app.security import decode_access_token

router = APIRouter(tags=["payments"])

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8000")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> uuid.UUID:
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return uuid.UUID(payload["sub"])


def get_rabbitmq_channel(request: Request):
    return request.app.state.rabbitmq_channel


@router.post("/payments", response_model=PaymentRead, status_code=201)
async def create_payment(
    payload: PaymentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    channel=Depends(get_rabbitmq_channel),
):
    auth_header = request.headers.get("Authorization")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{ORDER_SERVICE_URL}/orders/{payload.order_id}",
                headers={"Authorization": auth_header},
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="order-service no disponible")

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    response.raise_for_status()

    order = response.json()

    if order["status"] != "pending":
        raise HTTPException(status_code=400, detail="La orden no está pendiente de pago")

    amount = order["unit_price"] * order["quantity"]

    intent = stripe.PaymentIntent.create(
    amount=int(amount * 100),
    currency="mxn",
    metadata={"order_id": str(payload.order_id)},
    automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
)

    payment = Payment(
        order_id=payload.order_id,
        stripe_payment_intent_id=intent.id,
        amount=amount,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return payment


@router.post("/payments/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    channel=Depends(get_rabbitmq_channel),
):
    payload_body = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload_body, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    event_type = event["type"]
    stripe_payment_intent_id = event["data"]["object"]["id"]

    result = await db.execute(
        select(Payment).where(Payment.stripe_payment_intent_id == stripe_payment_intent_id)
    )
    payment = result.scalar_one_or_none()

    if payment is None:
        return {"status": "ignored"}

    if event_type == "payment_intent.succeeded":
        payment.status = PaymentStatus.SUCCEEDED
        await db.commit()
        await publish_payment_event(
            channel, "payment.succeeded", order_id=payment.order_id, payment_id=payment.id
        )
    elif event_type == "payment_intent.payment_failed":
        payment.status = PaymentStatus.FAILED
        await db.commit()
        await publish_payment_event(
            channel, "payment.failed", order_id=payment.order_id, payment_id=payment.id
        )

    return {"status": "received"}