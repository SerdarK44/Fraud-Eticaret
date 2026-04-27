from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fraud Sentinel"
    database_url: str = "postgresql+psycopg://fraud:fraud@postgres:5432/frauddb"
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/%2F"
    demo_mode: bool = False
    raw_transactions_queue: str = "raw-transactions"
    processed_transactions_queue: str = "processed-transactions"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    velocity_window_seconds: int = 60
    max_velocity_count: int = 5
    average_window_hours: int = 24
    amount_multiplier_threshold: float = 3.0
    max_travel_speed_kmh: float = 900.0
    recent_transactions_limit: int = 100
    sse_history_limit: int = 200
    api_port: int = 8000
    mcp_port: int = 9000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
