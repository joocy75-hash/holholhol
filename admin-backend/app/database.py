from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import get_settings

settings = get_settings()

# Admin database engine (for admin-specific data)
admin_engine = create_async_engine(
    settings.admin_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

# Main database engine (read-only access to game data)
main_engine = create_async_engine(
    settings.main_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AdminSessionLocal = async_sessionmaker(
    admin_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

MainSessionLocal = async_sessionmaker(
    main_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_admin_db() -> AsyncSession:
    """Get admin database session"""
    async with AdminSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_main_db() -> AsyncSession:
    """Get main database session (read-only)"""
    async with MainSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
