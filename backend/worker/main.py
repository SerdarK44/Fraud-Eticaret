from __future__ import annotations

import json
import time

import pika
from pydantic import ValidationError

from backend.common.broker import create_connection, declare_queues, publish_json
from backend.common.config import get_settings
from backend.common.database import SessionLocal, init_database
from backend.common.fraud import evaluate_transaction, get_redis_client
from backend.common.models import Transaction, TransactionStatus
from backend.common.schemas import TransactionCreate, TransactionEvent, TransactionRecord


def process_payload(payload: dict) -> dict:
    transaction_input = TransactionCreate.model_validate(payload)
    redis_client = get_redis_client()
    evaluation = evaluate_transaction(
        redis_client,
        user_id=transaction_input.user_id,
        amount=transaction_input.amount,
        location=transaction_input.location,
        occurred_at=transaction_input.occurred_at,
    )

    transaction = Transaction(
        user_id=transaction_input.user_id,
        amount=transaction_input.amount,
        location=transaction_input.location,
        occurred_at=transaction_input.occurred_at,
        status=TransactionStatus(evaluation.status),
        reasons=evaluation.reasons,
        velocity_violation=evaluation.velocity_violation,
        amount_violation=evaluation.amount_violation,
        location_violation=evaluation.location_violation,
    )

    with SessionLocal() as session:
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

    event = TransactionEvent(
        event_type=(
            "fraud_alert"
            if transaction.status == TransactionStatus.SUSPICIOUS
            else "transaction_processed"
        ),
        transaction=TransactionRecord.model_validate(transaction),
        alert_message=(
            f"Suspicious transaction detected for {transaction.user_id}."
            if transaction.status == TransactionStatus.SUSPICIOUS
            else None
        ),
    )
    return event.model_dump(mode="json")


def run_worker() -> None:
    settings = get_settings()
    init_database()

    while True:
        connection = None
        try:
            connection = create_connection()
            channel = connection.channel()
            declare_queues(channel)
            channel.basic_qos(prefetch_count=10)

            def handle_delivery(
                ch: pika.adapters.blocking_connection.BlockingChannel,
                method: pika.spec.Basic.Deliver,
                _properties: pika.BasicProperties,
                body: bytes,
            ) -> None:
                try:
                    payload = json.loads(body.decode("utf-8"))
                    processed_event = process_payload(payload)
                    publish_json(settings.processed_transactions_queue, processed_event)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except ValidationError as exc:
                    print(f"Skipping invalid transaction payload: {exc}")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:  # noqa: BLE001
                    print(f"Worker failed to process delivery: {exc}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            channel.basic_consume(
                queue=settings.raw_transactions_queue,
                on_message_callback=handle_delivery,
            )
            print("Worker is consuming transactions...")
            channel.start_consuming()
        except pika.exceptions.AMQPError as exc:
            print(f"RabbitMQ unavailable, retrying in 3 seconds: {exc}")
            time.sleep(3)
        finally:
            if connection and connection.is_open:
                connection.close()


if __name__ == "__main__":
    run_worker()
