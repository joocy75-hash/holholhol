"""Celery Beat schedule configuration.

Phase 10: Scheduled tasks for maintenance and analytics.

Tasks:
- Hourly: Hand history archival
- Daily: Statistics aggregation
- Weekly: Rakeback settlement
- Monthly: Cold storage migration
"""

from celery.schedules import crontab


# Celery Beat schedule
CELERY_BEAT_SCHEDULE = {
    # ==========================================================================
    # Hourly Tasks
    # ==========================================================================

    # Archive old hands to Redis (warm storage)
    "archive-hands-hourly": {
        "task": "app.tasks.archive.archive_old_hands_task",
        "schedule": crontab(minute=0),  # Every hour at :00
        "options": {"queue": "analytics"},
    },

    # Clean up expired sessions
    "cleanup-sessions-hourly": {
        "task": "app.tasks.maintenance.cleanup_expired_sessions_task",
        "schedule": crontab(minute=15),  # Every hour at :15
        "options": {"queue": "analytics"},
    },

    # ==========================================================================
    # Daily Tasks
    # ==========================================================================

    # Aggregate daily statistics (3 AM KST)
    "daily-stats-aggregation": {
        "task": "app.tasks.analytics.aggregate_daily_stats_task",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "analytics"},
    },

    # Clean up old cache entries (4 AM KST)
    "daily-cache-cleanup": {
        "task": "app.tasks.maintenance.cleanup_cache_task",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "analytics"},
    },

    # ==========================================================================
    # Weekly Tasks
    # ==========================================================================

    # Weekly rakeback settlement (Monday 4 AM KST)
    "weekly-rakeback-settlement": {
        "task": "app.tasks.rakeback.calculate_weekly_rakeback_task",
        "schedule": crontab(hour=4, minute=0, day_of_week=1),
        "options": {"queue": "settlement"},
    },

    # Weekly VIP level recalculation (Monday 5 AM KST)
    "weekly-vip-recalculation": {
        "task": "app.tasks.vip.recalculate_vip_levels_task",
        "schedule": crontab(hour=5, minute=0, day_of_week=1),
        "options": {"queue": "settlement"},
    },

    # ==========================================================================
    # Monthly Tasks
    # ==========================================================================

    # Move old archives to cold storage (1st of month, 2 AM KST)
    "monthly-archive-to-cold": {
        "task": "app.tasks.archive.move_to_cold_storage_task",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
        "options": {"queue": "analytics"},
    },

    # Monthly financial report generation (1st of month, 6 AM KST)
    "monthly-financial-report": {
        "task": "app.tasks.reports.generate_monthly_report_task",
        "schedule": crontab(hour=6, minute=0, day_of_month=1),
        "options": {"queue": "analytics"},
    },
}


# Task routing configuration
CELERY_TASK_ROUTES = {
    # Settlement tasks (high priority, dedicated queue)
    "app.tasks.rakeback.*": {"queue": "settlement"},
    "app.tasks.vip.*": {"queue": "settlement"},
    "app.tasks.wallet.*": {"queue": "settlement"},

    # Analytics tasks (lower priority)
    "app.tasks.analytics.*": {"queue": "analytics"},
    "app.tasks.archive.*": {"queue": "analytics"},
    "app.tasks.reports.*": {"queue": "analytics"},

    # Maintenance tasks
    "app.tasks.maintenance.*": {"queue": "analytics"},

    # Notification tasks
    "app.tasks.notification.*": {"queue": "notification"},
}


# Queue configuration
CELERY_TASK_QUEUES = {
    "settlement": {
        "exchange": "settlement",
        "routing_key": "settlement",
        "delivery_mode": 2,  # Persistent
    },
    "analytics": {
        "exchange": "analytics",
        "routing_key": "analytics",
        "delivery_mode": 1,  # Transient (can be lost)
    },
    "notification": {
        "exchange": "notification",
        "routing_key": "notification",
        "delivery_mode": 1,
    },
}
