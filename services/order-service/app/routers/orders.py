import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Order
from app.schemas import OrderCreate, OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])

CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://localhost:8001")


@router.get("", response_model=list[OrderRead])
async def list_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order))
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return order


@router.post("", response_model=OrderRead, status_code=201)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{CATALOG_SERVICE_URL}/products/{payload.product_id}"
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503, detail="catalog-service no disponible"
            )

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    response.raise_for_status()

    product = response.json()

    if product["stock"] < payload.quantity:
        raise HTTPException(status_code=400, detail="Stock insuficiente")

    order = Order(
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_price=product["price"],
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order