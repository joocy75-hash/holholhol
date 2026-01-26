from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Application
    app_name: str = "Admin Dashboard API"
    debug: bool = False
    
    # Database - Admin DB (separate from main)
    admin_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/admin_db"
    
    # Database - Main DB Read Replica (read-only access)
    main_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pokerkit"
    
    # Redis
    redis_url: str = "redis://localhost:6379/1"
    
    # JWT - 보안상 기본값 없음, 환경변수 필수
    jwt_secret_key: str = Field(
        ...,  # 필수 필드
        min_length=32,
        description="JWT 서명 키 (최소 32자, 환경변수 JWT_SECRET_KEY로 설정)"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # Main Backend API (for write operations)
    main_api_url: str = "http://localhost:8000"
    main_api_key: str = Field(
        ...,  # 필수 필드
        min_length=16,
        description="메인 API 인증 키 (최소 16자, 환경변수 MAIN_API_KEY로 설정)"
    )
    
    @field_validator('jwt_secret_key')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """JWT Secret이 안전한지 검증"""
        weak_secrets = [
            'admin-secret-key-change-in-production',
            'secret', 'password', 'admin', 'test', 'dev',
            'jwt-secret', 'change-me', 'your-secret-key'
        ]
        if v.lower() in weak_secrets or len(v) < 32:
            raise ValueError(
                'JWT_SECRET_KEY must be at least 32 characters and not a weak default value. '
                'Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return v
    
    @field_validator('main_api_key')
    @classmethod
    def validate_main_api_key(cls, v: str) -> str:
        """Main API Key가 안전한지 검증"""
        weak_keys = ['admin-api-key', 'api-key', 'secret', 'password', 'admin', 'test']
        if v.lower() in weak_keys or len(v) < 16:
            raise ValueError(
                'MAIN_API_KEY must be at least 16 characters and not a weak default value. '
                'Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(24))"'
            )
        return v
    
    # Crypto - TRON Network (Legacy)
    tron_network: str = "mainnet"  # or "shasta" for testnet
    tron_hot_wallet_address: str = ""
    
    # Crypto - TON Network
    ton_network: str = "testnet"  # or "mainnet" for production
    ton_hot_wallet_address: str = ""
    ton_usdt_master_address: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
    tonapi_key: str = ""
    ton_center_api_key: str = ""

    # KMS (Key Management Service) - Phase 8
    kms_provider: str = ""  # "local", "vault", "secrets" (auto-detect if empty)
    ton_hot_wallet_private_key: str = ""  # Base64 encoded (LocalKmsProvider only)

    # HashiCorp Vault (for VaultKmsProvider)
    vault_addr: str = ""  # e.g., "https://vault.example.com:8200"
    vault_token: str = ""
    vault_transit_mount: str = "transit"

    # AWS (for SecretsKmsProvider)
    aws_region: str = ""
    use_secrets_manager: bool = False

    # Withdrawal Automation - Phase 8
    withdrawal_auto_enabled: bool = False  # 출금 자동화 활성화
    withdrawal_auto_threshold_usdt: float = 100.0  # 이 금액 이하는 자동 처리
    withdrawal_monitor_interval: int = 30  # TX 모니터링 간격 (초)
    withdrawal_tx_timeout_minutes: int = 30  # TX 타임아웃 (분)
    withdrawal_max_retry: int = 3  # 최대 재시도 횟수
    
    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""
    
    # Exchange Rate Cache
    exchange_rate_cache_ttl: int = 30  # seconds
    
    # Deposit Settings
    deposit_expiry_minutes: int = 30
    deposit_amount_tolerance: float = 0.005  # 0.5%
    deposit_polling_interval: int = 10  # seconds
    deposit_monitor_enabled: bool = True  # Enable TonDepositMonitor for automatic deposit detection
    hot_wallet_min_balance: float = 1000.0  # USDT
    
    # Security
    withdrawal_supervisor_threshold: float = 1000.0  # USDT
    hot_wallet_alert_threshold: float = 5000.0  # USDT
    deposit_confirmations_required: int = 20
    csrf_enabled: bool = False  # Enable for defense-in-depth (JWT tokens already protect against CSRF)

    # CORS - 프로덕션에서는 실제 도메인으로 설정
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    
    # Fraud Detection
    fraud_consumer_enabled: bool = True  # Enable FraudEventConsumer for real-time fraud detection
    
    # Bot Detection Thresholds
    bot_min_sample_size: int = 10  # Minimum actions for analysis
    bot_std_dev_threshold: float = 50.0  # Max std dev for "consistent timing"
    bot_min_response_time_ms: int = 100  # Superhuman reaction threshold
    bot_time_range_threshold: int = 200  # Max time range for "narrow range"
    bot_excessive_fold_ratio: float = 0.8  # Fold ratio above this is suspicious
    bot_never_fold_ratio: float = 0.1  # Fold ratio below this is suspicious
    bot_excessive_raise_ratio: float = 0.5  # Raise ratio above this is suspicious
    bot_excessive_daily_hours: float = 12.0  # Daily play hours above this is suspicious
    bot_superhuman_session_hours: float = 20.0  # Max daily hours before flagged
    bot_schedule_std_dev: float = 1.0  # Std dev below this indicates robotic schedule
    bot_suspicion_threshold: int = 60  # Score above this = likely bot

    # Auto Ban Thresholds (Phase 2.4)
    auto_ban_threshold_chip_dumping: int = 3  # 칩 밀어주기 탐지 횟수 임계값
    auto_ban_threshold_bot: int = 5  # 봇 탐지 횟수 임계값
    auto_ban_threshold_anomaly: int = 4  # 이상 행동 탐지 횟수 임계값
    auto_ban_temp_duration_hours: int = 24  # 임시 밴 기간 (시간)
    auto_ban_enabled: bool = True  # 자동 밴 활성화 여부
    auto_ban_high_severity_immediate: bool = True  # high 심각도 시 즉시 밴
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 정의되지 않은 환경변수 무시


@lru_cache
def get_settings() -> Settings:
    return Settings()
