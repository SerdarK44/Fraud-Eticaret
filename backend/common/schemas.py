from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.common.models import TransactionStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class TransactionCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    amount: float = Field(..., gt=0)
    location: str = Field(..., min_length=1, max_length=128)
    occurred_at: datetime = Field(default_factory=utc_now)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class TransactionQueuedResponse(BaseModel):
    message: str
    queued_at: datetime
    transaction: TransactionCreate


class TransactionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    amount: float
    location: str
    occurred_at: datetime
    status: TransactionStatus
    reasons: list[str]
    velocity_violation: bool
    amount_violation: bool
    location_violation: bool
    created_at: datetime


class UserStatusResponse(BaseModel):
    user_id: str
    risk_level: Literal["normal", "elevated", "high"]
    suspicious_transactions_last_24h: int
    approved_transactions_last_24h: int
    average_amount_last_24h: float
    latest_location: str | None
    transactions: list[TransactionRecord]


class FraudListResponse(BaseModel):
    start: datetime
    end: datetime
    total: int
    transactions: list[TransactionRecord]


class FraudTrendPoint(BaseModel):
    bucket: datetime
    total_transactions: int
    suspicious_transactions: int
    fraud_rate: float


class TransactionEvent(BaseModel):
    event_type: Literal["transaction_processed", "fraud_alert"]
    transaction: TransactionRecord
    alert_message: str | None = None
