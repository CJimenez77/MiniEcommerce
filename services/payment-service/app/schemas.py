import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PaymentStatus


class PaymentCreate(BaseModel):
    order_id: uuid.UUID


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    stripe_payment_intent_id: str
    amount: float
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime