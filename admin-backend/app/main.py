from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import auth, dashboard, statistics, users, rooms, hands, bans, crypto, audit

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Admin Dashboard API for Holdem Game Management",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
