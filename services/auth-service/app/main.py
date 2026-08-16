from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth
from app.service_discovery import deregister_service, register_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await register_service()

    yield

    await deregister_service()


app = FastAPI(title="auth-service", lifespan=lifespan)
app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}