from __future__ import annotations

import json

try:
    import pika
except ImportError:  # pragma: no cover - optional in demo mode
    pika = None

from backend.common.config import get_settings


def create_connection() -> pika.BlockingConnection:
    if pika is None:
        raise RuntimeError("pika is required for broker connections.")
    parameters = pika.URLParameters(get_settings().rabbitmq_url)
    return pika.BlockingConnection(parameters)


def declare_queues(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    settings = get_settings()
    channel.queue_declare(queue=settings.raw_transactions_queue, durable=True)
    channel.queue_declare(queue=settings.processed_transactions_queue, durable=True)


def publish_json(queue_name: str, payload: dict) -> None:
    connection = create_connection()
    try:
        channel = connection.channel()
        declare_queues(channel)
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=json.dumps(payload).encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
    finally:
        connection.close()
