"""
Celery application for QueueLess background workers.

IMPORTANT: Workers use a dedicated *synchronous* SQLAlchemy engine (psycopg).
They must NEVER import or use the async engine / SessionLocal from
app.core.database.  asyncio.run() inside a Celery task creates a new event
loop on each call which is incompatible with the async SQLAlchemy engine
connection pool and causes "Future attached to a different loop" / "Event
loop is closed" errors.
"""
from celery import Celery
from app.core.config import get_settings

_settings = get_settings()

celery = Celery(
    "queueless",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["app.workers.tasks"],
)

celery.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    # Reliability settings
    worker_concurrency=2,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat schedules (all intervals in seconds)
    beat_schedule={
        "appointment-reminders": {
            "task": "app.workers.tasks.send_appointment_reminders",
            "schedule": 300.0,  # every 5 minutes
        },
        "pending-email-delivery": {
            "task": "app.workers.tasks.send_pending_emails",
            "schedule": 30.0,  # every 30 seconds
        },
        "cleanup-notifications": {
            "task": "app.workers.tasks.cleanup_notifications",
            "schedule": 3600.0,  # every hour
        },
        "cleanup-test-users": {
            "task": "app.workers.tasks.cleanup_test_users",
            "schedule": 600.0,  # every 10 minutes
        },
    },
)
