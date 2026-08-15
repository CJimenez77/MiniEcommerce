import asyncio
from contextlib import asynccontextmanager

import aio_pika
from fastapi import FastAPI

from app.database import Base, async_session, engine
from app.messaging import RABBITMQ_URL, consume_order_created
from app.routers import products
from app.service_discovery import deregister_service, register_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    consumer_task = asyncio.create_task(consume_order_created(connection, async_session))

    await register_service()

    yield

    await deregister_service()
    consumer_task.cancel()
    await connection.close()


app = FastAPI(title="catalog-service", lifespan=lifespan)
app.include_router(products.router)


@app.get("/health")
async def health():
    return {"status": "ok"}