from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

try:
    import redis
except ImportError:  # pragma: no cover - optional in demo mode
    redis = None

from backend.common.config import get_settings
from backend.common.location import is_impossible_travel
from backend.common.models import Transaction
from backend.common.schemas import ensure_utc


@dataclass
class FraudEvaluation:
    status: str
    reasons: list[str]
    velocity_violation: bool
    amount_violation: bool
    location_violation: bool
    average_amount_24h: float
    recent_transaction_count: int
    distance_km: float | None


def get_redis_client() -> redis.Redis:
    if redis is None:
        raise RuntimeError("redis package is required for Redis-backed fraud evaluation.")
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _history_key(user_id: str) -> str:
    return f"fraud:user:{user_id}:history"


def _last_transaction_key(user_id: str) -> str:
    return f"fraud:user:{user_id}:last"


def evaluate_transaction(
    redis_client: redis.Redis,
    *,
    user_id: str,
    amount: float,
    location: str,
    occurred_at: datetime,
) -> FraudEvaluation:
    settings = get_settings()
    now_ts = occurred_at.timestamp()
    history_key = _history_key(user_id)
    last_key = _last_transaction_key(user_id)
    history_window_seconds = settings.average_window_hours * 3600
    velocity_window_start = now_ts - settings.velocity_window_seconds
    history_window_start = now_ts - history_window_seconds

    redis_client.zremrangebyscore(history_key, "-inf", history_window_start)

    recent_transaction_count = int(redis_client.zcount(history_key, velocity_window_start, now_ts))
    velocity_violation = recent_transaction_count + 1 > settings.max_velocity_count

    amount_entries = redis_client.zrangebyscore(history_key, history_window_start, now_ts)
    historical_amounts = [float(entry.split("|", 2)[1]) for entry in amount_entries]
    average_amount_24h = (
        sum(historical_amounts) / len(historical_amounts) if historical_amounts else 0.0
    )
    amount_violation = average_amount_24h > 0 and amount > (
        average_amount_24h * settings.amount_multiplier_threshold
    )

    previous_transaction = redis_client.hgetall(last_key)
    location_violation = False
    distance_km = None
    if previous_transaction:
        previous_timestamp = float(previous_transaction["timestamp"])
        elapsed_hours = (now_ts - previous_timestamp) / 3600
        location_violation, distance_km = is_impossible_travel(
            previous_transaction["location"],
            location,
            elapsed_hours,
            settings.max_travel_speed_kmh,
        )

    reasons: list[str] = []
    if velocity_violation:
        reasons.append(
            f"Velocity: last {settings.velocity_window_seconds} seconds exceeded "
            f"{settings.max_velocity_count} transactions."
        )
    if amount_violation:
        reasons.append(
            f"Amount: {amount:.2f} is above {settings.amount_multiplier_threshold:.1f}x "
            f"the 24h average ({average_amount_24h:.2f})."
        )
    if location_violation:
        if distance_km is None:
            reasons.append("Location: impossible travel detected.")
        else:
            reasons.append(
                f"Location: {distance_km:.0f} km jump in too little time for physical travel."
            )

    status = "suspicious" if len(reasons) >= 2 else "approved"
    history_member = f"{now_ts}|{amount}|{uuid4()}"

    pipeline = redis_client.pipeline()
    pipeline.zadd(history_key, {history_member: now_ts})
    pipeline.expire(history_key, history_window_seconds + 3600)
    pipeline.hset(last_key, mapping={"timestamp": now_ts, "location": location})
    pipeline.expire(last_key, history_window_seconds + 3600)
    pipeline.execute()

    return FraudEvaluation(
        status=status,
        reasons=reasons,
        velocity_violation=velocity_violation,
        amount_violation=amount_violation,
        location_violation=location_violation,
        average_amount_24h=average_amount_24h,
        recent_transaction_count=recent_transaction_count + 1,
        distance_km=distance_km,
    )


def evaluate_transaction_from_history(
    *,
    recent_transactions: list[Transaction],
    last_transaction: Transaction | None,
    amount: float,
    location: str,
    occurred_at: datetime,
) -> FraudEvaluation:
    settings = get_settings()
    velocity_window_start = occurred_at.timestamp() - settings.velocity_window_seconds
    normalized_recent_datetimes = [ensure_utc(transaction.occurred_at) for transaction in recent_transactions]
    recent_transaction_count = sum(
        transaction_time.timestamp() >= velocity_window_start
        for transaction_time in normalized_recent_datetimes
    )
    velocity_violation = recent_transaction_count + 1 > settings.max_velocity_count

    historical_amounts = [transaction.amount for transaction in recent_transactions]
    average_amount_24h = (
        sum(historical_amounts) / len(historical_amounts) if historical_amounts else 0.0
    )
    amount_violation = average_amount_24h > 0 and amount > (
        average_amount_24h * settings.amount_multiplier_threshold
    )

    location_violation = False
    distance_km = None
    if last_transaction is not None:
        last_occurred_at = ensure_utc(last_transaction.occurred_at)
        elapsed_hours = (
            occurred_at.timestamp() - last_occurred_at.timestamp()
        ) / 3600
        location_violation, distance_km = is_impossible_travel(
            last_transaction.location,
            location,
            elapsed_hours,
            settings.max_travel_speed_kmh,
        )

    reasons: list[str] = []
    if velocity_violation:
        reasons.append(
            f"Velocity: last {settings.velocity_window_seconds} seconds exceeded "
            f"{settings.max_velocity_count} transactions."
        )
    if amount_violation:
        reasons.append(
            f"Amount: {amount:.2f} is above {settings.amount_multiplier_threshold:.1f}x "
            f"the 24h average ({average_amount_24h:.2f})."
        )
    if location_violation:
        if distance_km is None:
            reasons.append("Location: impossible travel detected.")
        else:
            reasons.append(
                f"Location: {distance_km:.0f} km jump in too little time for physical travel."
            )

    return FraudEvaluation(
        status="suspicious" if len(reasons) >= 2 else "approved",
        reasons=reasons,
        velocity_violation=velocity_violation,
        amount_violation=amount_violation,
        location_violation=location_violation,
        average_amount_24h=average_amount_24h,
        recent_transaction_count=recent_transaction_count + 1,
        distance_km=distance_km,
    )
