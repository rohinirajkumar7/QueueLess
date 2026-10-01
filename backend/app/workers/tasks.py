"""
Celery tasks for QueueLess.

All database access here is SYNCHRONOUS via SyncSessionLocal (psycopg v3).
Do NOT use asyncio.run(), async def, await, or import SessionLocal (async)
in this module.  Mixing asyncio with Celery's sync process model causes
"Future attached to a different loop" and "Event loop is closed" errors.

Pattern for every task:
  1. Open a short-lived sync session:  db = SyncSessionLocal()
  2. Do work inside try/except.
  3. Commit on success, rollback on exception.
  4. Always close in finally.
"""
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select, delete, text

from app.core.config import get_settings
from app.core.database import SyncSessionLocal
from app.models.models import (
    Appointment,
    AppointmentStatus,
    Notification,
    NotificationStatus,
    User,
)
from app.workers.celery_app import celery

logger = logging.getLogger("queueless.worker")


# ---------------------------------------------------------------------------
# Internal helpers (sync)
# ---------------------------------------------------------------------------

def _send_email_sync(to_email: str, subject: str, body: str) -> bool:
    """
    Synchronous SMTP send.  Returns True if delivered, False if skipped
    (no SMTP config), raises on hard SMTP errors.
    """
    settings = get_settings()
    if not settings.email_host:
        logger.warning(
            "email_not_configured",
            extra={"recipient": to_email, "subject": subject},
        )
        return False

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.email_host, settings.email_port, timeout=15) as smtp:
        if settings.email_username and settings.email_password:
            smtp.starttls()
            smtp.login(settings.email_username, settings.email_password)
        smtp.send_message(msg)

    return True


# ---------------------------------------------------------------------------
# Task: send_appointment_reminders
# ---------------------------------------------------------------------------

@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.tasks.send_appointment_reminders",
)
def send_appointment_reminders(self):
    """
    Create in-app APPOINTMENT_REMINDER notifications for appointments
    occurring within the next 24 hours.  Idempotent: skips if a reminder
    notification with the same message already exists for that user.
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=24)

    db = SyncSessionLocal()
    try:
        appts = db.scalars(
            select(Appointment).where(
                Appointment.status.in_([
                    AppointmentStatus.BOOKED,
                    AppointmentStatus.CONFIRMED,
                ]),
                Appointment.appointment_date >= now.date(),
                Appointment.appointment_date <= end.date(),
            )
        ).all()

        count = 0
        for a in appts:
            msg = (
                f"Reminder: your appointment is scheduled for "
                f"{a.appointment_date} from {a.start_time} to {a.end_time}."
            )
            existing = db.scalar(
                select(Notification).where(
                    Notification.user_id == a.user_id,
                    Notification.type == "APPOINTMENT_REMINDER",
                    Notification.message == msg,
                )
            )
            if existing:
                continue
            n = Notification(
                user_id=a.user_id,
                type="APPOINTMENT_REMINDER",
                title="Appointment reminder",
                message=msg,
            )
            db.add(n)
            count += 1

        db.commit()
        logger.info("appointment_reminders_created", extra={"count": count})
        return {"created": count}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task: send_notification_email  (triggered per-notification from router)
# ---------------------------------------------------------------------------

@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.tasks.send_notification_email",
)
def send_notification_email(self, notification_id: str):
    """
    Send the email for a single PENDING notification.
    Uses SELECT … FOR UPDATE SKIP LOCKED so two concurrent workers never
    double-send the same notification.
    """
    db = SyncSessionLocal()
    try:
        # Claim the notification row exclusively; skip if another worker
        # already owns it or it is no longer PENDING.
        note = db.scalar(
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.status == NotificationStatus.PENDING,
            )
            .with_for_update(skip_locked=True)
        )
        if not note:
            return {"sent": 0}

        user = db.get(User, note.user_id)
        if not user:
            note.status = NotificationStatus.FAILED
            db.commit()
            return {"sent": 0}

        try:
            delivered = _send_email_sync(user.email, note.title, note.message)
            note.status = (
                NotificationStatus.SENT if delivered else NotificationStatus.FAILED
            )
            db.commit()
            return {"sent": 1 if delivered else 0}
        except Exception:
            note.status = NotificationStatus.FAILED
            db.commit()
            raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task: send_pending_emails  (beat — every 30 s)
# ---------------------------------------------------------------------------

@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.tasks.send_pending_emails",
)
def send_pending_emails(self):
    """
    Batch sweep of PENDING notifications.
    Uses SELECT … FOR UPDATE SKIP LOCKED so concurrent task invocations
    never process the same notification twice (no double-send).
    Bulk-fetches users in one query to avoid N+1.
    """
    db = SyncSessionLocal()
    try:
        # Claim up to 50 pending notifications exclusively.
        notes = db.scalars(
            select(Notification)
            .where(Notification.status == NotificationStatus.PENDING)
            .with_for_update(skip_locked=True)
            .limit(50)
        ).all()

        if not notes:
            return {"sent": 0}

        # Bulk-fetch all relevant users in one query.
        user_ids = list({n.user_id for n in notes})
        users = {
            u.id: u
            for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
        }

        sent = 0
        for n in notes:
            user = users.get(n.user_id)
            if not user:
                n.status = NotificationStatus.FAILED
                continue
            try:
                delivered = _send_email_sync(user.email, n.title, n.message)
                n.status = (
                    NotificationStatus.SENT if delivered else NotificationStatus.FAILED
                )
                if delivered:
                    sent += 1
            except smtplib.SMTPException as exc:
                logger.warning(
                    "smtp_error", extra={"notification_id": str(n.id), "error": str(exc)}
                )
                n.status = NotificationStatus.FAILED

        db.commit()
        logger.info("pending_emails_swept", extra={"sent": sent, "total": len(notes)})
        return {"sent": sent}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task: cleanup_notifications  (beat — every hour)
# ---------------------------------------------------------------------------

@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.tasks.cleanup_notifications",
)
def cleanup_notifications(self):
    """Delete SENT/READ notifications older than 90 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    db = SyncSessionLocal()
    try:
        result = db.execute(
            delete(Notification).where(
                Notification.created_at < cutoff,
                Notification.status.in_([
                    NotificationStatus.SENT,
                    NotificationStatus.READ,
                ]),
            )
        )
        db.commit()
        deleted = result.rowcount or 0
        logger.info("notifications_cleaned", extra={"deleted": deleted})
        return {"deleted": deleted}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
