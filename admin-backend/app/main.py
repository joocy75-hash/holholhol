from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import auth, dashboard, statistics, users, rooms, hands, bans, crypto, audit, ton_deposit, admin_ton_deposit, fraud, system, announcements, suspicious
from app.middleware.csrf import CSRFMiddleware

settings = get_settings()
logger = logging.getLogger(__name__)

# FraudEventConsumer 인스턴스 (전역)
_fraud_consumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    global _fraud_consumer
    
    # Startup
    if settings.fraud_consumer_enabled:
        try:
            from redis.asyncio import Redis
            from app.services.fraud_event_consumer import init_fraud_consumer
            from app.database import get_main_db_session, get_admin_db_session
            
            # Redis 클라이언트 생성
            redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            
            # FraudEventConsumer 초기화 및 시작
            _fraud_consumer = init_fraud_consumer(
                redis_client,
                get_main_db_session,
                get_admin_db_session,
            )
            await _fraud_consumer.start()
            logger.info("FraudEventConsumer started successfully")
        except Exception as e:
            logger.error(f"Failed to start FraudEventConsumer: {e}")
    else:
        logger.info("FraudEventConsumer is disabled")
    
    yield
    
    # Shutdown
    if _fraud_consumer:
        try:
            await _fraud_consumer.stop()
            logger.info("FraudEventConsumer stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping FraudEventConsumer: {e}")

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
