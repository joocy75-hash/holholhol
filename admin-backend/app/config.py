from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "Admin Dashboard API"
    debug: bool = False
    
    # Database - Admin DB (separate from main)
    admin_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/admin_db"
    
    # Database - Main DB Read Replica (read-only access)
    main_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/holdem_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/1"
    
    # JWT
    jwt_secret_key: str = "admin-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # Main Backend API (for write operations)
    main_api_url: str = "http://localhost:8000"
    main_api_key: str = "admin-api-key"
    
    # Crypto - TRON Network
    tron_network: str = "mainnet"  # or "shasta" for testnet
    tron_hot_wallet_address: str = ""
    
    # Crypto - Exchange Rate
    upbit_api_url: str = "https://api.upbit.com/v1"
    binance_api_url: str = "https://api.binance.com/api/v3"
    exchange_rate_cache_ttl: int = 30  # seconds
    
    # Security
    withdrawal_supervisor_threshold: float = 1000.0  # USDT
    hot_wallet_alert_threshold: float = 5000.0  # USDT
    deposit_confirmations_required: int = 20
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
