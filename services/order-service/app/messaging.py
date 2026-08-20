import asyncio
import json
import logging
import os
import uuid

import aio_pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

EXCHANGE_NAME = "orders"

logger = logging.getLogger(__name__)


async def get_rabbitmq_channel() -> aio_pika.abc.AbstractChannel:
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    return await connection.channel()


async def publish_order_created(
    channel: aio_pika.abc.AbstractChannel,
    order_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: int,
) -> None:
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )

    message_body = json.dumps(
        {
            "order_id": str(order_id),
            "product_id": str(product_id),
            "quantity": quantity,
        }
    ).encode()

    message = aio_pika.Message(
        body=message_body,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    await exchange.publish(message, routing_key="order.created")


PAYMENTS_EXCHANGE_NAME = "payments"
PAYMENTS_QUEUE_NAME = "order.payment-updates"


async def connect_rabbitmq_with_retry(
    max_attempts: int = 10, delay_seconds: int = 3
) -> aio_pika.abc.AbstractRobustConnection:
    for attempt in range(1, max_attempts + 1):
        try:
            return await aio_pika.connect_robust(RABBITMQ_URL)
        except Exception as exc:
            if attempt == max_attempts:
                raise
            print(f"RabbitMQ no disponible aún (intento {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)


async def consume_payment_events(
    connection: aio_pika.abc.AbstractConnection, session_factory
) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        PAYMENTS_EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(PAYMENTS_QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key="payment.succeeded")
    await queue.bind(exchange, routing_key="payment.failed")

    async def handle_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            data = json.loads(message.body)
            order_id = data["order_id"]

            from app.models import Order, OrderStatus

            async with session_factory() as session:
                order = await session.get(Order, uuid.UUID(order_id))
                if order is None:
                    logger.error("Orden %s no encontrada, descartando mensaje", order_id)
                    await message.ack()
                    return

                if message.routing_key == "payment.succeeded":
                    order.status = OrderStatus.CONFIRMED
                else:
                    order.status = OrderStatus.CANCELLED

                await session.commit()
                logger.info("Orden %s actualizada a %s", order_id, order.status)

            await message.ack()
        except Exception:
            logger.exception("Error procesando evento de pago, será reintentado")
            await message.nack(requeue=True)

    await queue.consume(handle_message)