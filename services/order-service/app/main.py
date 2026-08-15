from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.messaging import get_rabbitmq_channel
from app.routers import orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.rabbitmq_channel = await get_rabbitmq_channel()

    yield


app = FastAPI(title="order-service", lifespan=lifespan)
app.include_router(orders.router)


@app.get("/health")
async def health():
    return {"status": "ok"}