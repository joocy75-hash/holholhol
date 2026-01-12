"""Celery application configuration.

Phase 6 & 10: Async job queue setup.

Features:
- Redis as broker and result backend
- Task routing by queue
- Scheduled tasks via Celery Beat
- MessagePack serialization for efficiency
"""

import os

from celery import Celery
from celery.schedules import crontab

from app.tasks.schedules import CELERY_BEAT_SCHEDULE, CELERY_TASK_ROUTES

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "poker_tasks",
    broker=f"{REDIS_URL.rsplit('/', 1)[0]}/1",  # Use DB 1 for broker
    backend=f"{REDIS_URL.rsplit('/', 1)[0]}/2",  # Use DB 2 for results
    include=[
        "app.tasks.rakeback",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization - use msgpack for efficiency (Phase 10)
    task_serializer="json",  # Keep JSON for compatibility, switch to msgpack when ready
    accept_content=["json", "msgpack"],
    result_serializer="json",
    
    # Timezone
    timezone="Asia/Seoul",
    enable_utc=True,
    
    # Task routing (from schedules.py)
    task_routes=CELERY_TASK_ROUTES,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    
    # Result settings
    result_expires=86400,  # 24 hours
    
    # Beat schedule (from schedules.py)
    beat_schedule=CELERY_BEAT_SCHEDULE,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)


# Optional: Configure for development
if os.getenv("APP_ENV") == "development":
    celery_app.conf.update(
        task_always_eager=False,  # Set to True to run tasks synchronously
        task_eager_propagates=True,
    )
