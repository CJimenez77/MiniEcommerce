import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, async_session, engine
from app.messaging import connect_rabbitmq_with_retry, consume_payment_events, get_rabbitmq_channel
from app.routers import orders
from app.service_discovery import deregister_service, register_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.rabbitmq_channel = await get_rabbitmq_channel()

    payment_events_connection = await connect_rabbitmq_with_retry()
    consumer_task = asyncio.create_task(
        consume_payment_events(payment_events_connection, async_session)
    )

    await register_service()

    yield

    await deregister_service()
    consumer_task.cancel()
    await payment_events_connection.close()


app = FastAPI(title="order-service", lifespan=lifespan)
app.include_router(orders.router)


@app.get("/health")
async def health():
    return {"status": "ok"}