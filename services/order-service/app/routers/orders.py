import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Order
from app.schemas import OrderCreate, OrderRead
from app.security import decode_access_token

router = APIRouter(prefix="/orders", tags=["orders"])

CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://localhost:8001")

bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> uuid.UUID:
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return uuid.UUID(payload["sub"])


@router.get("", response_model=list[OrderRead])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    result = await db.execute(select(Order).where(Order.user_id == user_id))
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    order = await db.get(Order, order_id)
    if not order or order.user_id != user_id:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return order


@router.post("", response_model=OrderRead, status_code=201)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{CATALOG_SERVICE_URL}/products/{payload.product_id}"
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="catalog-service no disponible")

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    response.raise_for_status()

    product = response.json()

    if product["stock"] < payload.quantity:
        raise HTTPException(status_code=400, detail="Stock insuficiente")

    order = Order(
        user_id=user_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_price=product["price"],
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order