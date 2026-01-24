"""Rakeback settlement tasks.

Phase 6.2: Weekly rakeback settlement job.

Scheduled to run every Monday at 4 AM KST.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.rakeback.calculate_weekly_rakeback_task",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def calculate_weekly_rakeback_task(self, week_start_iso: str | None = None):
    """Calculate and settle weekly rakeback for all users.
    
    This task runs every Monday at 4 AM KST to process the previous week's
    rakeback for all users who paid rake.
    
    Args:
        week_start_iso: Optional ISO format date string for week start.
                       If None, processes the previous week.
    
    Returns:
        Summary dict with processing results
    """
    logger.info(f"Starting weekly rakeback settlement task (attempt {self.request.retries + 1})")
    
    # Parse week_start if provided
    week_start = None
    if week_start_iso:
        week_start = datetime.fromisoformat(week_start_iso)
    
    # Run the async settlement process
    result = asyncio.get_event_loop().run_until_complete(
        _process_weekly_rakeback(week_start)
    )
    
    logger.info(f"Weekly rakeback settlement complete: {result}")
    return result


async def _process_weekly_rakeback(week_start: datetime | None = None) -> dict:
    """Process weekly rakeback (async implementation).
    
    Args:
        week_start: Start of the week to process
        
    Returns:
        Summary dict with results
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    
    from app.config import get_settings
    from app.services.vip import VIPService
    
    settings = get_settings()
    
    # Create async engine and session
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    try:
        async with async_session() as session:
            vip_service = VIPService(session)
            
            results = await vip_service.process_weekly_rakeback_all(
                week_start=week_start,
            )
            
            # Build summary
            total_users = len(results)
            total_rakeback = sum(r.rakeback_amount for r in results)
            total_rake = sum(r.rake_paid for r in results)
            
            # Count by VIP level
            by_level = {}
            for r in results:
                level = r.vip_level.value
                if level not in by_level:
                    by_level[level] = {"count": 0, "rakeback": 0}
                by_level[level]["count"] += 1
                by_level[level]["rakeback"] += r.rakeback_amount
            
            return {
                "status": "success",
                "total_users": total_users,
                "total_rake_paid": total_rake,
                "total_rakeback": total_rakeback,
                "by_vip_level": by_level,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            
    except Exception as e:
        logger.error(f"Weekly rakeback settlement failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.tasks.rakeback.calculate_user_rakeback_task",
)
def calculate_user_rakeback_task(user_id: str, week_start_iso: str | None = None):
    """Calculate rakeback for a single user (manual trigger).
    
    Args:
        user_id: User ID to process
        week_start_iso: Optional ISO format date string for week start
        
    Returns:
        Rakeback result dict
    """
    logger.info(f"Processing rakeback for user {user_id[:8]}...")
    
    week_start = None
    if week_start_iso:
        week_start = datetime.fromisoformat(week_start_iso)
    
    result = asyncio.get_event_loop().run_until_complete(
        _process_user_rakeback(user_id, week_start)
    )
    
    return result


async def _process_user_rakeback(
    user_id: str,
    week_start: datetime | None = None,
) -> dict:
    """Process rakeback for a single user (async implementation)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    
    from app.config import get_settings
    from app.services.vip import VIPService
    
    settings = get_settings()
    
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    try:
        async with async_session() as session:
            vip_service = VIPService(session)
            
            # Calculate rakeback
            rakeback = await vip_service.calculate_weekly_rakeback(
                user_id=user_id,
                week_start=week_start,
            )
            
            # Settle if there's rakeback
            if rakeback.rakeback_amount > 0:
                rakeback = await vip_service.settle_rakeback(rakeback)
                await session.commit()
            
            return {
                "status": "success",
                "user_id": user_id,
                "rake_paid": rakeback.rake_paid,
                "rakeback_amount": rakeback.rakeback_amount,
                "vip_level": rakeback.vip_level.value,
                "transaction_id": rakeback.transaction_id,
            }
            
    except Exception as e:
        logger.error(f"User rakeback processing failed: {e}")
        return {
            "status": "error",
            "user_id": user_id,
            "error": str(e),
        }
    finally:
        await engine.dispose()
