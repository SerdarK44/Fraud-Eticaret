from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.common.models import Transaction, TransactionStatus
from backend.common.schemas import FraudTrendPoint, TransactionRecord, UserStatusResponse


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def list_recent_transactions(session: Session, limit: int = 50) -> list[Transaction]:
    statement = select(Transaction).order_by(Transaction.occurred_at.desc()).limit(limit)
    return list(session.scalars(statement))


def list_fraud_transactions(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    limit: int = 200,
) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(
            Transaction.status == TransactionStatus.SUSPICIOUS,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


def get_user_transactions(session: Session, user_id: str, limit: int = 25) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


def get_user_status(session: Session, user_id: str, limit: int = 25) -> UserStatusResponse:
    transactions = get_user_transactions(session, user_id=user_id, limit=limit)
    window_start = utc_now() - timedelta(hours=24)
    recent_statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.occurred_at >= window_start)
        .order_by(Transaction.occurred_at.desc())
    )
    recent_transactions = list(session.scalars(recent_statement))
    suspicious_count = sum(
        transaction.status == TransactionStatus.SUSPICIOUS for transaction in recent_transactions
    )
    approved_count = sum(
        transaction.status == TransactionStatus.APPROVED for transaction in recent_transactions
    )
    average_amount = (
        sum(transaction.amount for transaction in recent_transactions) / len(recent_transactions)
        if recent_transactions
        else 0.0
    )
    risk_level = "high" if suspicious_count >= 3 else "elevated" if suspicious_count else "normal"
    latest_location = transactions[0].location if transactions else None

    return UserStatusResponse(
        user_id=user_id,
        risk_level=risk_level,
        suspicious_transactions_last_24h=suspicious_count,
        approved_transactions_last_24h=approved_count,
        average_amount_last_24h=round(average_amount, 2),
        latest_location=latest_location,
        transactions=[TransactionRecord.model_validate(item) for item in transactions],
    )


def get_fraud_trend(
    session: Session,
    *,
    hours: int = 24,
    bucket_minutes: int = 15,
) -> list[FraudTrendPoint]:
    end = utc_now()
    start = end - timedelta(hours=hours)
    statement = (
        select(Transaction)
        .where(Transaction.occurred_at >= start)
        .order_by(Transaction.occurred_at.asc())
    )
    transactions = list(session.scalars(statement))

    def floor_bucket(value: datetime) -> datetime:
        value = value.astimezone(timezone.utc)
        floored_minutes = value.minute - (value.minute % bucket_minutes)
        return value.replace(minute=floored_minutes, second=0, microsecond=0)

    series: dict[datetime, dict[str, int]] = {}
    for transaction in transactions:
        bucket = floor_bucket(transaction.occurred_at)
        counters = series.setdefault(bucket, {"total": 0, "suspicious": 0})
        counters["total"] += 1
        if transaction.status == TransactionStatus.SUSPICIOUS:
            counters["suspicious"] += 1

    points: list[FraudTrendPoint] = []
    current = floor_bucket(start)
    final_bucket = floor_bucket(end)
    while current <= final_bucket:
        counters = series.get(current, {"total": 0, "suspicious": 0})
        total = counters["total"]
        suspicious = counters["suspicious"]
        fraud_rate = round((suspicious / total) * 100, 2) if total else 0.0
        points.append(
            FraudTrendPoint(
                bucket=current,
                total_transactions=total,
                suspicious_transactions=suspicious,
                fraud_rate=fraud_rate,
            )
        )
        current += timedelta(minutes=bucket_minutes)

    return points
