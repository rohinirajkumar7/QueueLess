import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def _send_email_sync(to_email, subject, body):
    settings = get_settings()

    if not settings.email_host:
        logging.getLogger("queueless.email").warning(
            "email_not_configured",
            extra={"recipient": to_email, "subject": subject},
        )
        return False

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(
        settings.email_host,
        settings.email_port,
        timeout=10,
    ) as smtp:
        if settings.email_username and settings.email_password:
            smtp.starttls()
            smtp.login(settings.email_username, settings.email_password)

        smtp.send_message(msg)

    return True


async def send_email(to_email, subject, body):
    return await asyncio.to_thread(
        _send_email_sync,
        to_email,
        subject,
        body,
    )