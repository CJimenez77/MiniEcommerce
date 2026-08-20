import asyncio
import json
import os
import uuid

import aio_pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

EXCHANGE_NAME = "payments"


async def get_rabbitmq_channel(
    max_attempts: int = 10, delay_seconds: int = 3
) -> aio_pika.abc.AbstractChannel:
    for attempt in range(1, max_attempts + 1):
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            return await connection.channel()
        except Exception as exc:
            if attempt == max_attempts:
                raise
            print(f"RabbitMQ no disponible aún (intento {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)


async def publish_payment_event(
    channel: aio_pika.abc.AbstractChannel,
    routing_key: str,
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
) -> None:
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )

    message_body = json.dumps(
        {
            "order_id": str(order_id),
            "payment_id": str(payment_id),
        }
    ).encode()

    message = aio_pika.Message(
        body=message_body,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    await exchange.publish(message, routing_key=routing_key)    