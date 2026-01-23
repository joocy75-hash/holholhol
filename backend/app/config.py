"""Application configuration."""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    log_level: str = "DEBUG"
    # Uvicorn Workers (프로덕션 환경에서 멀티 워커 사용)
    uvicorn_workers: int = Field(
        default=1,
        description="Number of Uvicorn workers (프로덕션: CPU 코어 수 * 2 + 1 권장)",
    )

    # Database - 필수 필드 (환경변수에서 반드시 읽어야 함)
    database_url: str = Field(
        ...,
        description="Database connection URL (required)",
    )
    # Database Connection Pool Settings (300-500명 동시 접속 대응)
    db_pool_size: int = Field(
        default=100,
        description="DB connection pool size (기본: 100, 300명 동시접속 대응)",
    )
    db_max_overflow: int = Field(
        default=50,
        description="Max overflow connections (기본: 50)",
    )
    db_pool_timeout: int = Field(
        default=30,
        description="Pool connection timeout in seconds (기본: 30초)",
    )
    db_pool_recycle: int = Field(
        default=1800,
        description="Connection recycle time in seconds (기본: 1800초/30분)",
    )

    # Redis - 필수 필드 (환경변수에서 반드시 읽어야 함)
    redis_url: str = Field(
        ...,
        description="Redis connection URL (required)",
    )
    redis_session_ttl: int = 86400
    # Redis Connection Pool Settings (300-500명 동시 접속 대응)
    redis_max_connections: int = Field(
        default=100,
        description="Redis max connections (기본: 100)",
    )
    redis_socket_timeout: float = Field(
        default=5.0,
        description="Redis socket timeout in seconds (기본: 5초)",
    )
    redis_socket_connect_timeout: float = Field(
        default=5.0,
        description="Redis socket connect timeout in seconds (기본: 5초)",
    )
    redis_health_check_interval: int = Field(
        default=30,
        description="Redis health check interval in seconds (기본: 30초)",
    )

    # JWT - 필수 필드 (기본값 제거)
    jwt_secret_key: str = Field(
        ...,
        description="JWT secret key (required, minimum 32 characters)",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 3  # 보안 강화: 7일 → 3일

    # Serialization HMAC key for internal state integrity
    serialization_hmac_key: str = Field(
        ...,
        description="HMAC key for state serialization integrity (required)",
    )

    # Sentry Error Tracking (Phase 11)
    sentry_dsn: str | None = Field(
        default=None,
        description="Sentry DSN for error tracking (required in production)",
    )
    sentry_traces_sample_rate: float = Field(
        default=0.05,
        description="Sentry transaction sampling rate (0.0-1.0, default 5%)",
    )
    sentry_profiles_sample_rate: float = Field(
        default=0.01,
        description="Sentry profiling sampling rate (0.0-1.0, default 1%)",
    )

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Game
    default_max_seats: int = 6
    default_small_blind: int = 10
    default_big_blind: int = 20
    turn_timeout_seconds: int = 30
    reconnect_grace_period: int = 60
    heartbeat_interval: int = 15

    # Game Timing Settings (Phase 3)
    turn_time_default: int = Field(
        default=15,
        description="Default turn time in seconds",
    )
    turn_time_utg: int = Field(
        default=20,
        description="UTG (Under The Gun) turn time in seconds",
    )
    hand_result_display_seconds: float = Field(
        default=3.0,
        description="Time to display hand result before next hand",
    )
    phase_transition_delay_seconds: float = Field(
        default=0.5,
        description="Delay between phase transitions",
    )

    # Bot Timing Settings (Phase 3)
    bot_think_time_min: float = Field(
        default=0.8,
        description="Minimum bot thinking time in seconds",
    )
    bot_think_time_max: float = Field(
        default=2.5,
        description="Maximum bot thinking time in seconds",
    )
    bot_think_time_mode: float = Field(
        default=1.2,
        description="Mode (most likely) bot thinking time for triangular distribution",
    )

    # WebSocket Connection Limits (300-500명 동시 접속 대응)
    ws_max_connections: int = Field(
        default=600,
        description="Maximum WebSocket connections per instance (기본: 600)",
    )
    ws_max_connections_per_user: int = Field(
        default=3,
        description="Maximum WebSocket connections per user (멀티 디바이스, 기본: 3)",
    )

    # Bot Manager Settings
    bot_ws_url: str = Field(
        default="ws://localhost:8000/ws",
        description="WebSocket URL for bot connections",
    )
    bot_api_url: str = Field(
        default="http://localhost:8000",
        description="API URL for bot authentication",
    )

    # Internal Admin API Settings (admin-backend 연동)
    internal_api_key: str = Field(
        ...,
        description="API key for internal admin endpoints (X-API-Key header, required)",
    )

    # Dev/Test API Settings (E2E 테스트용 치트 API)
    dev_api_enabled: bool = Field(
        default=True,
        description="Enable dev/test API endpoints (자동: production에서 비활성화)",
    )
    dev_api_key: str = Field(
        default="dev-key",
        description="API key for dev endpoints (X-Dev-Key header)",
    )

    # Partner System Settings (파트너/총판 시스템)
    default_partner_code: str | None = Field(
        default=None,
        description="기본 파트너 코드 (코드 없이 가입 시 이 파트너에 연결)",
    )

    # S3 Cold Storage (Phase 10 - optional)
    s3_bucket_name: Optional[str] = Field(
        default=None,
        description="S3 bucket name for cold storage (optional)",
    )
    s3_region: str = Field(
        default="ap-northeast-2",
        description="AWS region for S3",
    )
    s3_access_key_id: Optional[str] = Field(
        default=None,
        description="AWS access key ID (or use IAM role)",
    )
    s3_secret_access_key: Optional[str] = Field(
        default=None,
        description="AWS secret access key (or use IAM role)",
    )
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        description="Custom S3 endpoint (for LocalStack, MinIO)",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        """Validate JWT secret key length."""
        if len(v) < 32:
            raise ValueError(
                "jwt_secret_key must be at least 32 characters long"
            )

        # 약한 키 패턴 검사
        weak_patterns = [
            "change-this",
            "secret",
            "password",
            "12345",
            "qwerty",
            "admin",
        ]
        lower_v = v.lower()
        for pattern in weak_patterns:
            if pattern in lower_v:
                raise ValueError(
                    f"jwt_secret_key contains weak pattern '{pattern}'. "
                    "Use a strong, random secret key."
                )

        return v

    @field_validator("internal_api_key")
    @classmethod
    def validate_internal_api_key(cls, v: str) -> str:
        """Validate internal API key strength."""
        if len(v) < 16:
            raise ValueError(
                "internal_api_key must be at least 16 characters long"
            )

        # 약한 키 패턴 검사
        weak_patterns = [
            "dev_api_key",
            "dev-key",
            "dev-api",
            "test-key",
            "local",
            "12345",
            "admin",
        ]
        lower_v = v.lower()
        for pattern in weak_patterns:
            if pattern in lower_v:
                raise ValueError(
                    f"internal_api_key contains weak pattern '{pattern}'. "
                    "Use a strong, random API key."
                )

        return v

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: str, info) -> str:
        """Validate CORS origins - disallow wildcard in production."""
        # info.data에서 app_env를 가져올 수 없으므로 model_validator에서 처리
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Validate settings for production environment."""
        if self.app_env == "production":
            # 프로덕션에서는 debug=False 강제
            if self.app_debug:
                raise ValueError(
                    "app_debug must be False in production environment"
                )

            # 프로덕션에서 CORS에 "*" 금지
            origins = [o.strip() for o in self.cors_origins.split(",")]
            if "*" in origins:
                raise ValueError(
                    "CORS wildcard '*' is not allowed in production environment. "
                    "Specify explicit allowed origins."
                )

            # 프로덕션에서 로그 레벨 검증
            if self.log_level == "DEBUG":
                # 경고만 하고 에러는 발생시키지 않음
                import warnings
                warnings.warn(
                    "DEBUG log level in production may expose sensitive information"
                )

            # 프로덕션에서 dev API 자동 비활성화
            object.__setattr__(self, 'dev_api_enabled', False)

        return self

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
