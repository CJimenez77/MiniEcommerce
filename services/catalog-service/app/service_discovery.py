import asyncio
import os

import httpx

CONSUL_URL = os.getenv("CONSUL_URL", "http://localhost:8500")
SERVICE_NAME = "catalog-service"
SERVICE_PORT = 8000


async def register_service(max_attempts: int = 10, delay_seconds: int = 3) -> None:
    service_id = f"{SERVICE_NAME}-1"

    payload = {
        "ID": service_id,
        "Name": SERVICE_NAME,
        "Address": SERVICE_NAME,
        "Port": SERVICE_PORT,
        "Tags": [
            "traefik.enable=true",
            "traefik.http.routers.catalog.rule=PathPrefix(`/products`)",
            "traefik.http.routers.catalog.entrypoints=web",
        ],
        "Check": {
            "HTTP": f"http://{SERVICE_NAME}:{SERVICE_PORT}/health",
            "Interval": "10s",
            "Timeout": "5s",
            "DeregisterCriticalServiceAfter": "1m",
        },
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.put(
                    f"{CONSUL_URL}/v1/agent/service/register", json=payload
                )
                response.raise_for_status()
                return
            except httpx.RequestError as exc:
                if attempt == max_attempts:
                    raise
                print(f"Consul no disponible aún (intento {attempt}/{max_attempts}): {exc}")
                await asyncio.sleep(delay_seconds)



async def deregister_service() -> None:
    service_id = f"{SERVICE_NAME}-1"

    async with httpx.AsyncClient() as client:
        try:
            await client.put(f"{CONSUL_URL}/v1/agent/service/deregister/{service_id}")
        except httpx.RequestError:
            pass