from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.events import EventManager, ProcessedTransactionConsumer
from backend.common.broker import publish_json
from backend.common.config import get_settings
from backend.common.database import SessionLocal, get_db, init_database
from backend.common.fraud import evaluate_transaction_from_history
from backend.common.location import KNOWN_LOCATIONS
from backend.common.models import Transaction, TransactionStatus
from backend.common.repository import (
    get_fraud_trend,
    get_user_status,
    list_fraud_transactions,
    list_recent_transactions,
)
from backend.common.schemas import (
    FraudListResponse,
    FraudTrendPoint,
    TransactionEvent,
    TransactionCreate,
    TransactionQueuedResponse,
    TransactionRecord,
    UserStatusResponse,
    ensure_utc,
    utc_now,
)

settings = get_settings()
event_manager = EventManager()
consumer = ProcessedTransactionConsumer(event_manager)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    event_manager.bind_loop(asyncio.get_running_loop())
    if not settings.demo_mode:
        consumer.start()
    try:
        yield
    finally:
        if not settings.demo_mode:
            consumer.stop()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def parse_datetime_or_default(value: datetime | None, fallback: datetime) -> datetime:
    return fallback if value is None else ensure_utc(value)


def process_transaction_inline(transaction_input: TransactionCreate) -> dict:
    window_start = transaction_input.occurred_at - timedelta(hours=settings.average_window_hours)
    with SessionLocal() as session:
        recent_transactions = list(
            session.query(Transaction)
            .filter(
                Transaction.user_id == transaction_input.user_id,
                Transaction.occurred_at >= window_start,
                Transaction.occurred_at <= transaction_input.occurred_at,
            )
            .order_by(Transaction.occurred_at.asc())
        )
        last_transaction = recent_transactions[-1] if recent_transactions else None
        evaluation = evaluate_transaction_from_history(
            recent_transactions=recent_transactions,
            last_transaction=last_transaction,
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "api": "ready",
        "mcp_endpoint": "http://localhost:9000/mcp",
    }


@app.post("/transactions", response_model=TransactionQueuedResponse, status_code=202)
async def create_transaction(transaction: TransactionCreate) -> TransactionQueuedResponse:
    if settings.demo_mode:
        event = await run_in_threadpool(process_transaction_inline, transaction)
        await event_manager.broadcast(event)
    else:
        payload = transaction.model_dump(mode="json")
        await run_in_threadpool(publish_json, settings.raw_transactions_queue, payload)
    return TransactionQueuedResponse(
        message=(
            "Transaction processed inline in demo mode."
            if settings.demo_mode
            else "Transaction queued for analysis."
        ),
        queued_at=utc_now(),
        transaction=transaction,
    )


@app.get("/transactions/recent", response_model=list[TransactionRecord])
def recent_transactions(
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[TransactionRecord]:
    transactions = list_recent_transactions(db, limit=limit)
    return [TransactionRecord.model_validate(item) for item in transactions]


@app.get("/users/{user_id}/status", response_model=UserStatusResponse)
def user_status(
    user_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> UserStatusResponse:
    return get_user_status(db, user_id=user_id, limit=limit)


@app.get("/frauds", response_model=FraudListResponse)
def frauds(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> FraudListResponse:
    end_dt = parse_datetime_or_default(end, utc_now())
    start_dt = parse_datetime_or_default(start, end_dt - timedelta(hours=24))
    transactions = list_fraud_transactions(db, start=start_dt, end=end_dt, limit=limit)
    return FraudListResponse(
        start=start_dt,
        end=end_dt,
        total=len(transactions),
        transactions=[TransactionRecord.model_validate(item) for item in transactions],
    )


@app.get("/metrics/fraud-trend", response_model=list[FraudTrendPoint])
def fraud_trend(
    hours: int = Query(default=24, ge=1, le=168),
    bucket_minutes: int = Query(default=15, ge=5, le=60),
    db: Session = Depends(get_db),
) -> list[FraudTrendPoint]:
    return get_fraud_trend(db, hours=hours, bucket_minutes=bucket_minutes)


@app.get("/meta/locations")
def locations() -> dict[str, list[str]]:
    return {"locations": sorted(location.title() for location in KNOWN_LOCATIONS)}


def _to_sse_message(event: dict) -> str:
    return f"event: {event['event_type']}\ndata: {json.dumps(event)}\n\n"


@app.get("/stream/events")
async def stream_events() -> StreamingResponse:
    queue = await event_manager.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield _to_sse_message(event)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            event_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
