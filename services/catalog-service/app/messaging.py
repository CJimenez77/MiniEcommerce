import json
import logging
import os

import aio_pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

EXCHANGE_NAME = "orders"
QUEUE_NAME = "catalog.stock-updates"
ROUTING_KEY = "order.created"

logger = logging.getLogger(__name__)


async def consume_order_created(connection: aio_pika.abc.AbstractConnection, session_factory) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key=ROUTING_KEY)

    async def handle_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            data = json.loads(message.body)
            product_id = data["product_id"]
            quantity = data["quantity"]

            from app.models import Product
            from sqlalchemy import select

            async with session_factory() as session:
                product = await session.get(Product, product_id)
                if product is None:
                    logger.error("Producto %s no encontrado, descartando mensaje", product_id)
                    await message.ack()
                    return

                product.stock -= quantity
                await session.commit()
                logger.info("Stock actualizado para producto %s: -%s", product_id, quantity)

            await message.ack()
        except Exception:
            logger.exception("Error procesando mensaje, será reintentado")
            await message.nack(requeue=True)

    await queue.consume(handle_message)