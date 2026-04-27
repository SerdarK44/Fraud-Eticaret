from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.database import Base


class TransactionStatus(str, enum.Enum):
    APPROVED = "approved"
    SUSPICIOUS = "suspicious"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_id_occurred_at", "user_id", "occurred_at"),
        Index("ix_transactions_status_occurred_at", "status", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status"),
        nullable=False,
    )
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    velocity_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    amount_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
