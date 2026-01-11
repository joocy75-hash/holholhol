"""Application configuration."""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    log_level: str = "DEBUG"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pokerkit"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl: int = 86400

    # JWT
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Game
    default_max_seats: int = 6
    default_small_blind: int = 10
    default_big_blind: int = 20
    turn_timeout_seconds: int = 30
    reconnect_grace_period: int = 60
    heartbeat_interval: int = 15

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
