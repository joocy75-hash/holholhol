from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import auth, dashboard, statistics, users, rooms, hands, bans, crypto, audit, ton_deposit, admin_ton_deposit, fraud, system, announcements, suspicious, notifications, export, public_announcements, partners, partner_portal, messages
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import setup_rate_limiting

settings = get_settings()
logger = logging.getLogger(__name__)

# Global task instances
_fraud_consumer = None
_exchange_rate_task = None
_wallet_balance_task = None
_wallet_alert_service = None
_deposit_monitor = None
_withdrawal_executor = None
_withdrawal_monitor = None
_redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    global _fraud_consumer, _exchange_rate_task, _wallet_balance_task, _wallet_alert_service
    global _deposit_monitor, _withdrawal_executor, _withdrawal_monitor, _redis_client
    import asyncio

    # Startup
    try:
        from redis.asyncio import Redis
        from app.database import get_main_db_session, get_admin_db_session, AdminSessionLocal

        # Redis 클라이언트 생성 (공유)
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=False,  # Binary for some services
        )

        # FraudEventConsumer 시작
        if settings.fraud_consumer_enabled:
            try:
                from app.services.fraud_event_consumer import init_fraud_consumer

                # FraudConsumer용 별도 Redis (decode_responses=True 필요)
                fraud_redis = Redis.from_url(settings.redis_url, decode_responses=True)

                _fraud_consumer = init_fraud_consumer(
                    fraud_redis,
                    get_main_db_session,
                    get_admin_db_session,
                )
                await _fraud_consumer.start()
                logger.info("FraudEventConsumer started successfully")
            except Exception as e:
                logger.error(f"Failed to start FraudEventConsumer: {e}")
        else:
            logger.info("FraudEventConsumer is disabled")

        # Exchange Rate History Task 시작 (1분 간격)
        try:
            from app.tasks.exchange_rate_history import ExchangeRateHistoryTask

            _exchange_rate_task = ExchangeRateHistoryTask(
                db_session_factory=AdminSessionLocal,
                redis_client=_redis_client,
                interval=60,  # 1분
            )
            asyncio.create_task(_exchange_rate_task.start())
            logger.info("ExchangeRateHistoryTask started (1 min interval)")
        except Exception as e:
            logger.error(f"Failed to start ExchangeRateHistoryTask: {e}")

        # Hot Wallet Balance Task 시작 (1시간 간격) with Alert Service
        try:
            from app.tasks.hot_wallet_balance import HotWalletBalanceTask
            from app.services.crypto.wallet_alert_service import WalletAlertService

            # WalletAlertService 초기화
            _wallet_alert_service = WalletAlertService(redis=_redis_client)
            await _wallet_alert_service.initialize()

            _wallet_balance_task = HotWalletBalanceTask(
                db_session_factory=AdminSessionLocal,
                redis_client=_redis_client,
                interval=3600,  # 1시간
                on_low_balance=_wallet_alert_service.handle_balance_update,
            )
            asyncio.create_task(_wallet_balance_task.start())
            logger.info("HotWalletBalanceTask started with WalletAlertService (1 hour interval)")
        except Exception as e:
            logger.error(f"Failed to start HotWalletBalanceTask: {e}")

        # TonDepositMonitor 시작 (입금 자동 감지)
        if settings.deposit_monitor_enabled:
            try:
                from app.services.crypto.ton_deposit_monitor import TonDepositMonitor
                from app.services.crypto.deposit_processor import DepositProcessor
                from app.models.deposit_request import DepositRequest

                # 콜백 함수: 입금 확인 시 DepositProcessor로 처리
                async def on_deposit_confirmed(request: DepositRequest, tx_hash: str):
                    """입금 확인 시 잔액 크레딧 처리"""
                    try:
                        async with AdminSessionLocal() as db:
                            processor = DepositProcessor(admin_db=db)
                            await processor.process_deposit(request, tx_hash)
                            logger.info(f"Deposit processed: {request.memo} - {tx_hash}")
                    except Exception as e:
                        logger.error(f"Failed to process deposit {request.memo}: {e}")

                # 콜백 함수: 연속 오류 알림
                async def on_polling_error_alert(error_count: int, last_error: str):
                    """연속 폴링 오류 알림"""
                    logger.critical(
                        f"ALERT: TonDepositMonitor has {error_count} consecutive errors! "
                        f"Last error: {last_error}"
                    )
                    # TODO: 관리자 알림 (이메일, 슬랙 등) 추가 가능

                _deposit_monitor = TonDepositMonitor(
                    db_session_factory=AdminSessionLocal,
                    polling_interval=settings.deposit_polling_interval,
                )
                _deposit_monitor.set_callbacks(
                    on_confirmed=on_deposit_confirmed,
                    on_polling_error_alert=on_polling_error_alert,
                )
                asyncio.create_task(_deposit_monitor.start_polling())
                logger.info(
                    f"TonDepositMonitor started (interval: {settings.deposit_polling_interval}s)"
                )
            except Exception as e:
                logger.error(f"Failed to start TonDepositMonitor: {e}")
        else:
            logger.info("TonDepositMonitor is disabled")

        # Withdrawal Automation Tasks (Phase 8)
        if settings.withdrawal_auto_enabled:
            try:
                from app.services.crypto.withdrawal_executor import WithdrawalExecutor
                from app.services.crypto.withdrawal_monitor import WithdrawalMonitor

                # WithdrawalExecutor - 승인된 출금 자동 실행
                _withdrawal_executor = WithdrawalExecutor(
                    session_factory=AdminSessionLocal,
                )
                asyncio.create_task(_withdrawal_executor.start())
                logger.info("WithdrawalExecutor started (auto-execution enabled)")

                # WithdrawalMonitor - TX 확인 모니터링
                _withdrawal_monitor = WithdrawalMonitor(
                    session_factory=AdminSessionLocal,
                )
                asyncio.create_task(_withdrawal_monitor.start())
                logger.info(
                    f"WithdrawalMonitor started (interval: {settings.withdrawal_monitor_interval}s)"
                )
            except Exception as e:
                logger.error(f"Failed to start withdrawal automation: {e}")
        else:
            logger.info("Withdrawal automation is disabled")

    except Exception as e:
        logger.error(f"Error during startup: {e}")

    yield

    # Shutdown
    if _withdrawal_executor:
        try:
            await _withdrawal_executor.stop()
            await _withdrawal_executor.close()
            logger.info("WithdrawalExecutor stopped")
        except Exception as e:
            logger.error(f"Error stopping WithdrawalExecutor: {e}")

    if _withdrawal_monitor:
        try:
            await _withdrawal_monitor.stop()
            await _withdrawal_monitor.close()
            logger.info("WithdrawalMonitor stopped")
        except Exception as e:
            logger.error(f"Error stopping WithdrawalMonitor: {e}")

    if _deposit_monitor:
        try:
            _deposit_monitor.stop_polling()
            await _deposit_monitor.close()
            logger.info("TonDepositMonitor stopped")
        except Exception as e:
            logger.error(f"Error stopping TonDepositMonitor: {e}")

    if _exchange_rate_task:
        try:
            _exchange_rate_task.stop()
            logger.info("ExchangeRateHistoryTask stopped")
        except Exception as e:
            logger.error(f"Error stopping ExchangeRateHistoryTask: {e}")

    if _wallet_balance_task:
        try:
            _wallet_balance_task.stop()
            logger.info("HotWalletBalanceTask stopped")
        except Exception as e:
            logger.error(f"Error stopping HotWalletBalanceTask: {e}")

    if _fraud_consumer:
        try:
            await _fraud_consumer.stop()
            logger.info("FraudEventConsumer stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping FraudEventConsumer: {e}")

    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis client closed")
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")

app = FastAPI(
    title=settings.app_name,
    description="Admin Dashboard API for Holdem Game Management",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF middleware (disabled by default since JWT tokens are used)
# Enable via CSRF_ENABLED=true environment variable for defense-in-depth
app.add_middleware(
    CSRFMiddleware,
    enabled=settings.csrf_enabled,
    cookie_secure=not settings.debug,  # Secure in production
    exempt_paths={"/health", "/docs", "/redoc", "/openapi.json", "/api/auth/login"},
)

# Rate Limiting middleware (보안: Brute-force/DoS 방지)
setup_rate_limiting(app)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "admin-backend"}


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["Statistics"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(rooms.router, prefix="/api/rooms", tags=["Rooms"])
app.include_router(hands.router, prefix="/api/hands", tags=["Hands"])
app.include_router(bans.router, prefix="/api/bans", tags=["Bans"])
app.include_router(crypto.router, prefix="/api/crypto", tags=["Crypto"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])
app.include_router(ton_deposit.router, prefix="/api/ton", tags=["TON Deposit"])
app.include_router(admin_ton_deposit.router, prefix="/api", tags=["Admin TON Deposit"])
app.include_router(fraud.router, prefix="/api/fraud", tags=["Fraud Monitoring"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(announcements.router, prefix="/api/announcements", tags=["Announcements"])
app.include_router(suspicious.router, prefix="/api/suspicious", tags=["Suspicious Users"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(public_announcements.router, prefix="/api/public/announcements", tags=["Public Announcements"])
app.include_router(partners.router, prefix="/api/partners", tags=["Partners"])
app.include_router(partner_portal.router, prefix="/api/partner-portal", tags=["Partner Portal"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
