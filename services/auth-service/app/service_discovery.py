import os

import httpx

CONSUL_URL = os.getenv("CONSUL_URL", "http://localhost:8500")
SERVICE_NAME = "auth-service"
SERVICE_PORT = 8000


async def register_service() -> None:
    service_id = f"{SERVICE_NAME}-1"

    payload = {
        "ID": service_id,
        "Name": SERVICE_NAME,
        "Address": SERVICE_NAME,
        "Port": SERVICE_PORT,
        "Tags": ["fastapi", "traefik.enable=true"],
        "Check": {
            "HTTP": f"http://{SERVICE_NAME}:{SERVICE_PORT}/health",
            "Interval": "10s",
            "Timeout": "5s",
            "DeregisterCriticalServiceAfter": "1m",
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{CONSUL_URL}/v1/agent/service/register", json=payload
        )
        response.raise_for_status()


async def deregister_service() -> None:
    service_id = f"{SERVICE_NAME}-1"

    async with httpx.AsyncClient() as client:
        try:
            await client.put(f"{CONSUL_URL}/v1/agent/service/deregister/{service_id}")
        except httpx.RequestError:
            pass